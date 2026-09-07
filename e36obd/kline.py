"""
Low-level K-line transport for BMW OBD1 (Bosch Motronic) ECUs.

The K-line is a single bidirectional wire. Two consequences drive this module:

1.  Nearly every USB K-line interface (including the FTDI-based K+DCAN cable)
    loops the transmit line back into the receive line. Every byte we send
    reappears in the RX buffer and must be consumed before real ECU data.
    We auto-detect this rather than assuming it, since cable designs vary.

2.  The session is opened with a "5 baud slow init": the ECU address is
    clocked out at 5 bits/second (200 ms per bit) before the port switches to
    normal 9600 baud framing.

    The reference C implementation (libiceblock) does this with FTDI bitbang
    mode via libftdi. That is not workable on macOS, where Apple's own
    AppleUSBFTDI driver already claims the USB interface. Instead we bit-bang
    the line with the UART's BREAK control: asserting BREAK holds TX at logic
    0 (space), clearing it returns to idle logic 1 (mark) -- which is exactly
    the start bit / data bits / stop bit we need. The port stays at 9600 the
    whole time, so there is no baud switching at all.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

import serial

log = logging.getLogger(__name__)

# 5 baud -> 200 ms per bit.
SLOW_INIT_BIT_SECONDS = 0.200

# The bus must sit idle before an init attempt or the ECU ignores it. BMW's own
# tooling waits 2600 ms; the 260 ms quoted for generic KWP71 is too optimistic
# and produces false negatives when sweeping addresses back to back.
BUS_IDLE_SECONDS = 2.6

# The ECU answers the slow init with a sync byte of 0x55 followed by keyword
# bytes. Anything before the 0x55 is discarded as line noise.
SYNC_BYTE = 0x55


class KLineError(Exception):
    """Any failure to communicate over the K-line."""


class InitError(KLineError):
    """The ECU did not respond to the slow-init sequence."""


@dataclass
class InitResult:
    """What the ECU said immediately after the 5-baud wakeup."""

    address: int
    keyword_bytes: list[int] = field(default_factory=list)

    def __str__(self) -> str:
        kw = " ".join(f"{b:02X}" for b in self.keyword_bytes)
        return f"addr={self.address:02X} keywords=[{kw}]"


class KLine:
    """A half-duplex K-line port with slow-init support.

    Args:
        port: serial device path, e.g. /dev/cu.usbserial-A50285BI
        baud: post-init line rate. Bosch Motronic uses 9600.
        timeout: default per-byte read timeout in seconds.
        loopback: True/False to force, or None to auto-detect on first write.
    """

    def __init__(
        self,
        port: str,
        baud: int = 9600,
        timeout: float = 1.0,
        loopback: bool | None = None,
    ) -> None:
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self._loopback = loopback
        self._current_timeout = timeout
        # Bytes read while probing for a loopback echo that turned out to be
        # real ECU data. They must be handed out before touching the port.
        self._pushback: deque[int] = deque()
        self._ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            # No flow control: the K-line has no handshake lines.
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        log.debug("opened %s at %d baud", port, baud)

    # ---------------------------------------------------------------- context

    def __enter__(self) -> "KLine":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()

    # ------------------------------------------------------------- raw serial

    def flush(self) -> None:
        """Discard anything buffered in either direction, including pushback."""
        self._pushback.clear()
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def _set_timeout(self, value: float) -> None:
        """Set the port read timeout, but only when it actually changes.

        pyserial's timeout setter reconfigures the whole port via tcsetattr.
        Assigning it per byte costs two full termios reconfigurations for every
        byte exchanged, which dominates the round-trip time far more than the
        9600-baud line itself does. Caching the value is the single biggest
        win available for sample rate.
        """
        if self._current_timeout != value:
            self._ser.timeout = value
            self._current_timeout = value

    def read_byte(self, timeout: float | None = None) -> int:
        """Read one byte, or raise KLineError on timeout."""
        if self._pushback:
            return self._pushback.popleft()
        self._set_timeout(self.timeout if timeout is None else timeout)
        data = self._ser.read(1)
        if not data:
            raise KLineError("timed out waiting for a byte from the ECU")
        return data[0]

    def try_read_byte(self, timeout: float) -> int | None:
        """Read one byte, returning None on timeout instead of raising."""
        try:
            return self.read_byte(timeout=timeout)
        except KLineError:
            return None

    def write_byte(self, value: int) -> None:
        """Send one byte and swallow its loopback echo if the cable has one.

        On the first call, whether the cable loops back is determined
        empirically: we send the byte and look for it coming straight back.
        A byte that comes back but does *not* match what we sent is real ECU
        traffic and is pushed back for the next read.
        """
        self._ser.write(bytes([value]))
        self._ser.flush()

        if self._loopback is False:
            return

        echo = self.try_read_byte(timeout=0.3)

        if echo is None:
            if self._loopback is None:
                self._loopback = False
                log.debug("no loopback detected on this cable")
            elif self._loopback:
                raise KLineError(
                    f"expected loopback echo of {value:02X} but the line went silent"
                )
            return

        if echo == value:
            if self._loopback is None:
                self._loopback = True
                log.debug("loopback detected; TX echoes will be consumed")
            return

        # Not our echo -- it belongs to the ECU.
        if self._loopback is None:
            self._loopback = False
            log.debug("no loopback detected (got %02X, not our %02X)", echo, value)
        self._pushback.append(echo)

    # -------------------------------------------------------------- slow init

    def slow_init(
        self,
        address: int,
        data_bits: int = 8,
        parity: int = 0,
        keyword_count: int = 3,
        sync_timeout: float = 1.5,
        bus_idle: float = BUS_IDLE_SECONDS,
    ) -> InitResult:
        """Wake the ECU by clocking `address` out at 5 baud, then read keywords.

        Args:
            address: ECU address byte (Bosch Motronic commonly 0x12).
            data_bits: bits in the address frame. KWP71 uses 8.
            parity: 0 = none, 1 = odd, 2 = even. KWP71 uses none.
            keyword_count: how many bytes to collect starting at the 0x55 sync.
            sync_timeout: how long to wait for the 0x55 after the wakeup.
            bus_idle: quiet time to leave before the wakeup, in seconds.

        Returns:
            InitResult with the keyword bytes the ECU sent.

        Raises:
            InitError if no 0x55 sync arrives in time.
        """
        log.debug(
            "slow init: address %02X, %d data bits, parity %d",
            address,
            data_bits,
            parity,
        )
        self.flush()
        if bus_idle > 0:
            time.sleep(bus_idle)
            self.flush()

        # Build the bit pattern: start(0), data LSB-first, optional parity, stop(1).
        bits: list[int] = [0]
        ones = 0
        for i in range(data_bits):
            bit = (address >> i) & 1
            ones += bit
            bits.append(bit)
        if parity == 1:  # odd
            bits.append(1 if ones % 2 == 0 else 0)
        elif parity == 2:  # even
            bits.append(0 if ones % 2 == 0 else 1)
        bits.append(1)

        # Clock out every bit except the stop bit, using absolute deadlines so
        # per-bit sleep jitter cannot accumulate across the ~2 second sequence.
        start = time.monotonic()
        try:
            for index, bit in enumerate(bits[:-1]):
                # BREAK asserted == line held low == logic 0.
                self._ser.break_condition = bit == 0
                deadline = start + (index + 1) * SLOW_INIT_BIT_SECONDS
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            # Always leave the line idle-high, even if interrupted.
            self._ser.break_condition = False

        # The stop bit is simply the line sitting idle-high, so there is
        # nothing to transmit for it -- and crucially, nothing to wait for.
        #
        # The ECU may answer as little as ~60 ms after the address frame ends.
        # If we slept out a full 200 ms stop bit before clearing the buffer we
        # would flush the ECU's 0x55 away and conclude, wrongly, that nothing
        # is there. So discard our own wakeup garbage immediately and start
        # listening straight away; the stop-bit idle time simply overlaps the
        # beginning of the listen window, which is harmless.
        self._ser.reset_input_buffer()
        self._pushback.clear()

        keywords = self._await_sync(keyword_count, sync_timeout)
        result = InitResult(address=address, keyword_bytes=keywords)
        log.debug("slow init succeeded: %s", result)
        return result

    def _await_sync(self, keyword_count: int, timeout: float) -> list[int]:
        """Collect `keyword_count` bytes beginning with the 0x55 sync byte.

        Bytes arriving before the sync are noise from the wakeup transition and
        are discarded.
        """
        collected: list[int] = []
        deadline = time.monotonic() + timeout

        while len(collected) < keyword_count and time.monotonic() < deadline:
            byte = self.try_read_byte(timeout=0.05)
            if byte is None:
                continue
            if not collected:
                if byte == SYNC_BYTE:
                    collected.append(byte)
                else:
                    log.debug("pre-sync noise: %02X", byte)
            else:
                collected.append(byte)

        if len(collected) < keyword_count:
            got = " ".join(f"{b:02X}" for b in collected) or "nothing"
            raise InitError(
                f"no valid init response (wanted {keyword_count} bytes from 0x55, got {got})"
            )
        return collected

    def echo_keyword(self, keyword_bytes: list[int], index: int, invert: bool) -> None:
        """Acknowledge the init by echoing one keyword byte back.

        KWP71 echoes the third keyword byte (index 2), bitwise inverted.
        """
        if index >= len(keyword_bytes):
            raise KLineError(
                f"keyword index {index} out of range for {len(keyword_bytes)} bytes"
            )
        value = keyword_bytes[index]
        if invert:
            value = (~value) & 0xFF
        time.sleep(0.005)
        self.write_byte(value)
        log.debug("echoed keyword byte %02X", value)

    @property
    def loopback(self) -> bool | None:
        """Whether this cable echoes TX onto RX. None until first determined."""
        return self._loopback
