"""
KWP71 (Keyword Protocol 71) block exchange for Bosch Motronic ECUs.

Protocol shape, as implemented by Bosch Motronic units of the M1.7.x era:

    Block on the wire:  [length] [seq] [title] [payload...] [0x03]

    `length` counts the sequence byte, the title byte, the payload, and the
    trailer -- but not the length byte itself. So the total byte count on the
    wire is length + 1.

    Every byte except the final one of a block is acknowledged by the receiving
    side with its bitwise inversion. This handshake runs in both directions.

    The session must keep exchanging blocks or the ECU drops the connection.
    When we have nothing to say we send an Empty (0x09) block as a keepalive.

Reference: colinbourassa/libiceblock, which documents the same framing from
tested hardware.
"""

from __future__ import annotations

import enum
import logging
import time

from .kline import KLine, KLineError

log = logging.getLogger(__name__)

# Delay between individual bytes. The spec allows 2-250 ms; too fast risks the
# ECU missing the handshake, too slow risks its inter-byte timeout.
INTER_BYTE_SECONDS = 0.002
# Delay between whole blocks. Spec allows 5-250 ms.
INTER_BLOCK_SECONDS = 0.010

MAX_PAYLOAD = 252


class BlockType(enum.IntEnum):
    """KWP71 block titles.

    Note: some manufacturers deviate from these values. If a command returns
    NotSupported on your ECU, the title may simply differ on that unit.
    """

    REQUEST_ID = 0x00
    READ_RAM = 0x01
    WRITE_RAM = 0x02
    READ_ROM = 0x03
    ACTIVATE_ACTUATOR = 0x04
    ERASE_TROUBLE_CODES = 0x05
    DISCONNECT = 0x06
    READ_TROUBLE_CODES = 0x07
    READ_ADC_CHANNEL = 0x08
    EMPTY = 0x09
    NACK = 0x0A
    NOT_SUPPORTED = 0x0B
    READ_PARAM_DATA = 0x10
    RECORD_PARAM_DATA = 0x11
    REQUEST_SNAPSHOT = 0x12
    READ_EEPROM = 0x19
    WRITE_EEPROM = 0x1A
    PARAM_RECORD_CONF = 0xEB
    PARAMETRIC_DATA = 0xEC
    EEPROM_CONTENT = 0xEF
    SNAPSHOT = 0xF4
    INFO_STRING = 0xF6
    ADC_VALUE = 0xFB
    BINARY_DATA = 0xFC
    RAM_CONTENT = 0xFD
    ROM_CONTENT = 0xFE


class ProtocolError(KLineError):
    """A block was malformed or the handshake broke down."""


class NotSupportedError(ProtocolError):
    """The ECU rejected the command as unsupported."""


class Block:
    """One decoded KWP71 block."""

    __slots__ = ("seq", "title", "payload")

    def __init__(self, seq: int, title: int, payload: bytes) -> None:
        self.seq = seq
        self.title = title
        self.payload = payload

    @property
    def title_name(self) -> str:
        try:
            return BlockType(self.title).name
        except ValueError:
            return f"UNKNOWN_0x{self.title:02X}"

    def __repr__(self) -> str:
        body = " ".join(f"{b:02X}" for b in self.payload)
        return f"<Block seq={self.seq} {self.title_name} [{body}]>"


class KWP71Session:
    """A live KWP71 conversation with one ECU.

    Typical use:

        with KLine(port) as line:
            session = KWP71Session(line)
            session.connect(address=0x12)
            codes = session.read_fault_codes()
            session.disconnect()
    """

    def __init__(self, line: KLine) -> None:
        self.line = line
        self.seq = 0
        self.id_strings: list[bytes] = []
        self.connected = False

    # ------------------------------------------------------------ block layer

    def send_block(self, title: int, payload: bytes = b"") -> None:
        """Frame and transmit one block, honouring the inverted-echo handshake."""
        if len(payload) > MAX_PAYLOAD:
            raise ProtocolError(f"payload of {len(payload)} exceeds {MAX_PAYLOAD} bytes")

        self.seq = (self.seq + 1) & 0xFF
        length = 1 + 1 + len(payload) + 1  # seq + title + payload + trailer
        buf = bytes([length, self.seq, title]) + payload + bytes([0x03])

        log.debug("send: %s", " ".join(f"{b:02X}" for b in buf))

        for index, byte in enumerate(buf):
            self.line.write_byte(byte)
            # Every byte but the last is acknowledged by the ECU, inverted.
            if index < length:
                expected = (~byte) & 0xFF
                ack = self.line.read_byte()
                if ack != expected:
                    raise ProtocolError(
                        f"bad ack for byte {index} ({byte:02X}): "
                        f"expected {expected:02X}, got {ack:02X}"
                    )
            time.sleep(INTER_BYTE_SECONDS)

    def recv_block(self, timeout: float = 2.0) -> Block:
        """Receive one block, acknowledging each byte as it arrives."""
        length = self.line.read_byte(timeout=timeout)
        raw = [length]

        # Acknowledge the length byte before the rest streams in.
        time.sleep(INTER_BYTE_SECONDS)
        self.line.write_byte((~length) & 0xFF)

        for index in range(1, length + 1):
            byte = self.line.read_byte()
            raw.append(byte)
            if index < length:
                time.sleep(INTER_BYTE_SECONDS)
                self.line.write_byte((~byte) & 0xFF)

        log.debug("recv: %s", " ".join(f"{b:02X}" for b in raw))

        if length < 3:
            raise ProtocolError(f"block too short: length byte was {length}")

        seq = raw[1]
        title = raw[2]
        # Trailing byte is the 0x03 terminator, so payload stops one short.
        payload = bytes(raw[3:length])

        # The sequence counter is shared; adopt whatever the ECU used.
        self.seq = seq
        return Block(seq=seq, title=title, payload=payload)

    def send_empty(self) -> None:
        """Send the Empty/ACK block that keeps the session alive."""
        self.send_block(BlockType.EMPTY)

    # -------------------------------------------------------------- session

    def connect(
        self,
        address: int = 0x12,
        keyword_count: int = 3,
        collect_id: bool = True,
    ) -> list[int]:
        """Run the slow init and drain the ECU's unsolicited ID strings.

        Returns the keyword bytes the ECU responded with.
        """
        init = self.line.slow_init(
            address=address,
            data_bits=8,
            parity=0,
            keyword_count=keyword_count,
        )
        # KWP71: echo the third keyword byte back, inverted.
        self.line.echo_keyword(init.keyword_bytes, index=2, invert=True)

        self.seq = 0
        self.id_strings = []
        self.connected = True

        if collect_id:
            self._drain_id_strings()

        return init.keyword_bytes

    def _drain_id_strings(self, max_blocks: int = 32) -> None:
        """After init the ECU volunteers ID info, then an Empty block.

        We must acknowledge each one or the session stalls.
        """
        for _ in range(max_blocks):
            block = self.recv_block()
            if block.title == BlockType.EMPTY:
                return
            if block.payload:
                self.id_strings.append(block.payload)
            time.sleep(INTER_BLOCK_SECONDS)
            self.send_empty()
        log.warning("ECU kept sending ID blocks past the %d-block limit", max_blocks)

    def command(self, title: int, payload: bytes = b"") -> list[bytes]:
        """Send a command and gather every response payload until Empty.

        The ECU may answer across several blocks; each one is acknowledged with
        an Empty block until it signals completion with an Empty of its own.
        """
        if not self.connected:
            raise ProtocolError("not connected -- call connect() first")

        time.sleep(INTER_BLOCK_SECONDS)
        self.send_block(title, payload)

        results: list[bytes] = []
        while True:
            block = self.recv_block()

            if block.title == BlockType.EMPTY:
                return results
            if block.title in (BlockType.NACK, BlockType.NOT_SUPPORTED):
                raise NotSupportedError(
                    f"ECU rejected command 0x{title:02X} with {block.title_name}"
                )

            if block.payload:
                results.append(block.payload)

            time.sleep(INTER_BLOCK_SECONDS)
            self.send_empty()

    def keepalive(self) -> None:
        """Exchange one idle block pair to hold the session open."""
        time.sleep(INTER_BLOCK_SECONDS)
        self.send_empty()
        self.recv_block()

    def disconnect(self) -> None:
        """Politely end the session. Errors are swallowed -- we're leaving anyway."""
        if not self.connected:
            return
        try:
            self.send_block(BlockType.DISCONNECT)
        except KLineError as exc:
            log.debug("disconnect block not acknowledged: %s", exc)
        finally:
            self.connected = False

    # ------------------------------------------------------------- commands

    def read_fault_codes(self) -> list[bytes]:
        """Read stored trouble codes. Returns raw payload blocks."""
        return self.command(BlockType.READ_TROUBLE_CODES)

    def erase_fault_codes(self) -> None:
        """Clear stored trouble codes."""
        self.command(BlockType.ERASE_TROUBLE_CODES)

    def read_ram(self, address: int, count: int) -> bytes:
        """Read `count` bytes from ECU RAM at `address`."""
        if count > MAX_PAYLOAD:
            raise ValueError(f"count {count} exceeds max payload {MAX_PAYLOAD}")
        payload = bytes([count, (address >> 8) & 0xFF, address & 0xFF])
        blocks = self.command(BlockType.READ_RAM, payload)
        return b"".join(blocks)

    def read_rom(self, address: int, count: int) -> bytes:
        """Read `count` bytes from ECU ROM at `address`."""
        if count > MAX_PAYLOAD:
            raise ValueError(f"count {count} exceeds max payload {MAX_PAYLOAD}")
        payload = bytes([count, (address >> 8) & 0xFF, address & 0xFF])
        blocks = self.command(BlockType.READ_ROM, payload)
        return b"".join(blocks)

    def read_adc(self, channel: int) -> bytes:
        """Read one ADC channel. Raw bytes; scaling is ECU-specific."""
        blocks = self.command(BlockType.READ_ADC_CHANNEL, bytes([channel]))
        return b"".join(blocks)

    def read_param_data(self) -> bytes:
        """Read the live parameter block, if this ECU implements it."""
        blocks = self.command(BlockType.READ_PARAM_DATA)
        return b"".join(blocks)

    def request_snapshot(self) -> bytes:
        """Request a freeze-frame style snapshot, if supported."""
        blocks = self.command(BlockType.REQUEST_SNAPSHOT)
        return b"".join(blocks)
