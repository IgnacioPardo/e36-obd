"""Exhaustively try every 5-baud init address and record any that answer.

Runs unattended for roughly 13 minutes. Any response at all -- even bytes that
are not the expected 0x55 sync -- is logged, because "the ECU said something
unexpected" and "the ECU said nothing" are very different problems.
"""

from __future__ import annotations

import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-A50285BI"
BIT_SECONDS = 0.200
LISTEN_SECONDS = 1.2
# BMW's tooling leaves 2600 ms of bus idle before a wakeup. Sweeping without it
# produces false negatives across the board -- the first version of this script
# used 300 ms and its "nothing responded" result was therefore meaningless.
IDLE_SECONDS = 2.6


def slow_init(ser: serial.Serial, addr: int, databits: int = 8, parity: int = 0) -> bytes:
    bits = [0]
    ones = 0
    for i in range(databits):
        bit = (addr >> i) & 1
        ones += bit
        bits.append(bit)
    if parity == 1:
        bits.append(1 if ones % 2 == 0 else 0)
    elif parity == 2:
        bits.append(0 if ones % 2 == 0 else 1)
    # Stop bit is idle-high and is deliberately not slept out: the ECU can
    # reply ~60ms after the frame ends and we must not flush that away.

    ser.reset_input_buffer()
    time.sleep(IDLE_SECONDS)
    ser.reset_input_buffer()
    start = time.monotonic()
    for index, bit in enumerate(bits):
        ser.break_condition = bit == 0
        deadline = start + (index + 1) * BIT_SECONDS
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
    ser.break_condition = False
    ser.reset_input_buffer()

    got = b""
    end = time.monotonic() + LISTEN_SECONDS
    while time.monotonic() < end:
        chunk = ser.read(1)
        if chunk:
            got += chunk
    return got


def main() -> int:
    ser = serial.Serial(PORT, 9600, timeout=0.05)
    hits: list[tuple[int, bytes]] = []
    print(f"Sweeping 0x00-0xFF on {PORT}. ~13 minutes.", flush=True)
    try:
        for addr in range(0x100):
            got = slow_init(ser, addr)
            if got:
                line = " ".join(f"{b:02X}" for b in got)
                print(f"  addr {addr:02X}: {line}   <-- RESPONSE", flush=True)
                hits.append((addr, got))
            elif addr % 16 == 0:
                print(f"  ... {addr:02X}", flush=True)
    except KeyboardInterrupt:
        print("interrupted", flush=True)
    finally:
        ser.close()

    print(f"\nDone. {len(hits)} address(es) responded.", flush=True)
    for addr, got in hits:
        print(f"  0x{addr:02X}: {' '.join(f'{b:02X}' for b in got)}", flush=True)
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
