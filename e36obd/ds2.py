"""BMW DS2 client -- for modules that are not the Motronic DME.

DS2 is a completely different animal from the KWP71 used by the M1.7.2 DME,
which is why the 5-baud address sweep never found the transmission module:

    KWP71 (DME)        5-baud slow init, 0x55 sync, keyword handshake, 8N1,
                       per-byte inverted-echo acknowledgement.
    DS2  (EGS, ABS…)   no initialisation whatsoever. 9600 8E1. Just send a
                       frame and read the reply.

A DS2 module cannot answer a slow init at any address, so sweeping more
addresses with the KWP71 code would never have worked.

Frame format, both directions:

    [address] [length] [payload...] [checksum]

`length` counts the entire frame including the address, the length byte itself
and the checksum. The checksum is an XOR of every preceding byte. So the
shortest useful request is 4 bytes -- e.g. identify the transmission module:

    32 04 00 36      (0x32 ^ 0x04 ^ 0x00 == 0x36)
"""

from __future__ import annotations

import logging
import time

import serial

log = logging.getLogger(__name__)

# Addresses seen on BMW modules of this era. 0x12 is the engine ECU -- useful
# as a control: on a car whose DME speaks KWP71 it should stay silent, which
# tells you the bus is wired but nothing DS2 is answering there.
ADDR_EGS = 0x32          # automatic transmission
ADDR_DME = 0x12          # engine (DS2 cars only)
ADDR_ABS = 0x56
ADDR_CLUSTER = 0x80

CMD_IDENTIFY = 0x00
CMD_READ_FAULTS = 0x04
CMD_CLEAR_FAULTS = 0x05

COMMON_ADDRESSES = [0x32, 0x12, 0x56, 0x80, 0x44, 0x46, 0x64, 0xA0, 0xB0]


class DS2Error(Exception):
    """Malformed frame, bad checksum, or no reply."""


def checksum(data: bytes) -> int:
    result = 0
    for byte in data:
        result ^= byte
    return result


def build(address: int, payload: bytes = b"") -> bytes:
    """Build a DS2 request frame."""
    length = len(payload) + 3  # address + length + payload + checksum
    head = bytes([address, length]) + payload
    return head + bytes([checksum(head)])


class DS2:
    """A DS2 connection. No handshake, no session -- each frame stands alone."""

    def __init__(self, port: str, timeout: float = 1.0, echo: bool | None = None) -> None:
        self.echo = echo
        self._ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,  # DS2 is 8E1, unlike KWP71's 8N1
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )

    def __enter__(self) -> "DS2":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()

    def request(self, address: int, payload: bytes = b"", settle: float = 0.05) -> bytes:
        """Send a frame and return the reply payload.

        Raises DS2Error on no reply, a truncated frame, or a checksum mismatch.
        """
        frame = build(address, payload)
        self._ser.reset_input_buffer()
        self._ser.write(frame)
        self._ser.flush()
        log.debug("tx: %s", frame.hex(" "))

        # A cable that bridges its transmit line onto receive -- which ours does,
        # since we jumpered K to L -- returns our own frame first. Consume it.
        if self.echo is not False:
            maybe = self._ser.read(len(frame))
            if maybe == frame:
                if self.echo is None:
                    self.echo = True
                    log.debug("cable echoes DS2 frames; consuming")
            elif maybe:
                # Not our echo: it is the start of a real reply. Parse from here.
                return self._parse(maybe + self._read_rest(maybe))
            time.sleep(settle)

        head = self._ser.read(2)
        if len(head) < 2:
            raise DS2Error(f"no reply from 0x{address:02X}")
        return self._parse(head + self._read_rest(head))

    def _read_rest(self, head: bytes) -> bytes:
        """Given at least [addr][len], read the remainder of the frame."""
        if len(head) < 2:
            return self._ser.read(2 - len(head))
        remaining = head[1] - len(head)
        return self._ser.read(remaining) if remaining > 0 else b""

    @staticmethod
    def _parse(frame: bytes) -> bytes:
        if len(frame) < 4:
            raise DS2Error(f"frame too short: {frame.hex(' ')}")
        declared = frame[1]
        if len(frame) < declared:
            raise DS2Error(
                f"truncated: declared {declared} bytes, got {len(frame)} "
                f"({frame.hex(' ')})"
            )
        frame = frame[:declared]
        if checksum(frame[:-1]) != frame[-1]:
            raise DS2Error(
                f"bad checksum on {frame.hex(' ')}: "
                f"expected {checksum(frame[:-1]):02X}, got {frame[-1]:02X}"
            )
        return frame[2:-1]

    # ------------------------------------------------------------- commands

    def identify(self, address: int) -> bytes:
        return self.request(address, bytes([CMD_IDENTIFY]))

    def read_faults(self, address: int) -> bytes:
        return self.request(address, bytes([CMD_READ_FAULTS]))

    def probe(self, address: int) -> bytes | None:
        """Is anything alive at this address? Returns the reply, or None."""
        try:
            return self.identify(address)
        except (DS2Error, serial.SerialException) as exc:
            log.debug("0x%02X: %s", address, exc)
            return None
