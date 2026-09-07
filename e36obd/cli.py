"""Command line interface for talking to an E36 Motronic ECU over K-line."""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from datetime import datetime, timezone

import serial
from serial.tools import list_ports

from .ds2 import COMMON_ADDRESSES as COMMON_DS2_ADDRESSES
from .ds2 import DS2, DS2Error
from .egs import EGS_ADDRESS, EGS_BAUD
from .egs import decode as decode_egs
from .faults import decode as decode_faults
from .kline import InitError, KLine, KLineError
from .live import LiveReader
from .snapshot import Snapshot
from .snapshot import diff as diff_snapshots
from .web import serve
from .kwp71 import BlockType, KWP71Session, NotSupportedError

log = logging.getLogger("e36obd")

# FTDI's USB vendor ID. K+DCAN cables use the FT232R (product 0x6001).
FTDI_VID = 0x0403

# 0x10 wakes DME #1 and 0x14 wakes DME #2 on BMW Motronic units; the same 0x10
# appears for Alfa, Fiat and Volvo Motronics. The rest are longer shots.
#
# Note: 0x12 is deliberately NOT first. It is the DS2 engine-ECU address -- a
# different protocol entirely -- and appears in no KWP71 implementation.
DEFAULT_SCAN_ADDRESSES = [0x10, 0x14, 0x11, 0x01, 0x13, 0x33, 0x00, 0x12, 0x17]


# --------------------------------------------------------------------- helpers


def hexs(data: bytes | list[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def find_default_port() -> str | None:
    """Pick the most likely K-line cable from the attached serial devices."""
    candidates = [p for p in list_ports.comports() if p.vid == FTDI_VID]
    if not candidates:
        candidates = [p for p in list_ports.comports() if "usbserial" in p.device]
    if not candidates:
        return None
    # Prefer the callout device (/dev/cu.*) on macOS: /dev/tty.* blocks on open
    # waiting for carrier detect, which never asserts on a K-line cable.
    for port in candidates:
        if "/cu." in port.device:
            return port.device
    return candidates[0].device


def open_line(args: argparse.Namespace) -> KLine:
    port = args.port or find_default_port()
    if port is None:
        raise SystemExit(
            "No serial port found. Plug in the K+DCAN cable, or pass --port explicitly."
        )
    loopback = None
    if args.loopback == "on":
        loopback = True
    elif args.loopback == "off":
        loopback = False
    return KLine(port=port, baud=args.baud, timeout=args.timeout, loopback=loopback)


def connect_session(args: argparse.Namespace, line: KLine) -> KWP71Session:
    session = KWP71Session(line)
    keywords = session.connect(address=args.address, keyword_count=args.keyword_bytes)
    print(f"Connected. Keyword bytes: {hexs(keywords)}")
    if session.id_strings:
        print("ECU identification:")
        for raw in session.id_strings:
            text = raw.decode("ascii", errors="replace").strip()
            print(f"  {text!r:40} raw: {hexs(raw)}")
    return session


# -------------------------------------------------------------------- commands


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check the cable and port with no car attached."""
    print("=== Serial ports ===")
    ports = list(list_ports.comports())
    if not ports:
        print("  none found")
    for port in ports:
        vid = f"{port.vid:04X}" if port.vid is not None else "----"
        pid = f"{port.pid:04X}" if port.pid is not None else "----"
        marker = "  <-- FTDI" if port.vid == FTDI_VID else ""
        print(f"  {port.device:32} VID:PID={vid}:{pid}  {port.description}{marker}")

    chosen = args.port or find_default_port()
    if chosen is None:
        print("\nNo candidate cable found. Is the K+DCAN plugged into USB?")
        return 1

    print(f"\n=== Opening {chosen} ===")
    try:
        line = KLine(port=chosen, baud=args.baud, timeout=args.timeout)
    except serial.SerialException as exc:
        print(f"  FAILED to open: {exc}")
        return 1

    with line:
        print("  opened OK")
        try:
            line._ser.break_condition = True
            time.sleep(0.05)
            line._ser.break_condition = False
            print("  BREAK control works (needed for the 5-baud init)")
        except (OSError, serial.SerialException) as exc:
            print(f"  BREAK control FAILED: {exc}")
            print("  Without BREAK we cannot perform the slow init on macOS.")
            return 1

        print("\n=== Loopback probe ===")
        # The K-line transceiver inside the cable is powered from OBD2 pin 16,
        # i.e. from the car's battery -- not from USB. So an unplugged cable
        # cannot echo. Once plugged into the car, an echo here proves the
        # adapter is passing +12V and ground through, which is the single most
        # common failure with cheap K-line-only 20-pin adapters.
        line.flush()
        echoes = 0
        for probe in (0x55, 0xAA, 0xF7):
            line._ser.write(bytes([probe]))
            line._ser.flush()
            reply = line.try_read_byte(timeout=0.4)
            got = f"{reply:02X}" if reply is not None else "silence"
            print(f"  sent {probe:02X} -> {got}")
            if reply == probe:
                echoes += 1

        if echoes:
            print("  Cable is echoing: the transceiver is powered.")
        else:
            print("  No echo.")
            print("  * Unplugged from the car: normal, nothing is wrong.")
            print("  * Plugged into the car with ignition on: the cable is NOT")
            print("    getting +12V. Suspect the 20-pin adapter (K-line-only,")
            print("    no power pass-through) or pin 16 on the round connector.")

        print("\n=== Listening for 2s of unsolicited traffic ===")
        line.flush()
        seen = []
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            byte = line.try_read_byte(timeout=0.1)
            if byte is not None:
                seen.append(byte)
        if seen:
            print(f"  {len(seen)} bytes: {hexs(seen[:32])}")
            print("  (Traffic with no request sent usually means the K-line is active.)")
        else:
            print("  silent -- expected. The ECU only speaks when spoken to.")

    print("\nCable looks usable. Next: connect to the car and run `scan`.")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Try candidate ECU addresses and report which ones answer."""
    addresses = (
        [int(a, 0) for a in args.addresses]
        if args.addresses
        else DEFAULT_SCAN_ADDRESSES
    )
    print(f"Scanning {len(addresses)} address(es). Each attempt takes ~7s.")
    print("Ignition must be ON (position 2), engine off.\n")

    hits: list[tuple[int, list[int]]] = []
    with open_line(args) as line:
        for address in addresses:
            print(f"  address {address:02X} ... ", end="", flush=True)
            try:
                result = line.slow_init(
                    address=address,
                    data_bits=8,
                    parity=0,
                    keyword_count=args.keyword_bytes,
                )
            except InitError:
                print("no response")
            except KLineError as exc:
                print(f"error: {exc}")
            else:
                print(f"RESPONSE  keywords={hexs(result.keyword_bytes)}")
                hits.append((address, result.keyword_bytes))
            # slow_init() already leaves the required bus-idle gap of its own.

    print()
    if hits:
        print("Responding addresses:")
        for address, keywords in hits:
            print(f"  0x{address:02X}  keywords {hexs(keywords)}")
        print(f"\nUse: --address 0x{hits[0][0]:02X}")
        return 0

    print("No address responded. Work through, in order:")
    print("  1. Ignition in position 2 (dash lights on, engine off)?")
    print("  2. OBD2 pins 7-8 bridged on the cable (or its switch set for K-line)?")
    print("  3. 20-pin adapter carrying +12V and ground, not just the K-line?")
    print("  4. Pin 16 on the round connector reading battery voltage?")
    return 1


def cmd_id(args: argparse.Namespace) -> int:
    """Connect and print ECU identification."""
    with open_line(args) as line:
        session = connect_session(args, line)
        try:
            if not session.id_strings:
                print("No ID strings volunteered; requesting explicitly...")
                for raw in session.command(BlockType.REQUEST_ID):
                    text = raw.decode("ascii", errors="replace").strip()
                    print(f"  {text!r:40} raw: {hexs(raw)}")
        finally:
            session.disconnect()
    return 0


def cmd_codes(args: argparse.Namespace) -> int:
    """Read stored fault codes."""
    with open_line(args) as line:
        session = connect_session(args, line)
        try:
            blocks = session.read_fault_codes()
        except NotSupportedError as exc:
            print(f"\n{exc}")
            print("This ECU may use a non-standard title for fault codes.")
            print("Try: e36obd raw --title 0x3A")
            return 1
        finally:
            session.disconnect()

    print()
    if not blocks:
        print("No fault codes stored.")
        return 0

    data = b"".join(blocks)
    codes = decode_faults(data)

    print(f"{len(codes)} fault code(s) stored:\n")
    for code in codes:
        print(code.format())
        print()

    leftover = len(data) % 5
    if leftover:
        print(f"  note: {leftover} trailing byte(s) not part of a 5-byte record")
    print(f"  raw: {hexs(data)}")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    """Erase stored fault codes."""
    if not args.yes:
        reply = input("Erase all stored fault codes? [y/N] ").strip().lower()
        if reply != "y":
            print("Aborted.")
            return 1

    with open_line(args) as line:
        session = connect_session(args, line)
        try:
            session.erase_fault_codes()
            print("Fault codes erased.")
        finally:
            session.disconnect()
    return 0


def parse_channels(spec: str) -> list[int]:
    """Parse '0-7,9,12' into [0,1,...,7,9,12]."""
    channels: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            channels.extend(range(int(lo, 0), int(hi, 0) + 1))
        else:
            channels.append(int(part, 0))
    return channels


def cmd_log(args: argparse.Namespace) -> int:
    """Poll the ECU on an interval and write CSV."""
    channels = parse_channels(args.adc) if args.adc else []
    ram_reads: list[tuple[int, int]] = []
    for spec in args.ram or []:
        addr_str, _, len_str = spec.partition(":")
        ram_reads.append((int(addr_str, 0), int(len_str or "1", 0)))

    if not channels and not ram_reads and not args.param:
        print("Nothing to log. Pass --adc, --ram, and/or --param.")
        print("Start with:  e36obd log --adc 0-15")
        return 1

    columns = ["timestamp", "elapsed_s"]
    columns += [f"adc{c}" for c in channels]
    columns += [f"ram_{a:04X}_{n}" for a, n in ram_reads]
    if args.param:
        columns.append("param")

    out = open(args.out, "w", newline="") if args.out else sys.stdout
    writer = csv.writer(out)
    writer.writerow(columns)

    with open_line(args) as line:
        session = connect_session(args, line)
        print(f"\nLogging every {args.interval}s. Ctrl-C to stop.\n", file=sys.stderr)
        start = time.monotonic()
        try:
            while True:
                if args.duration and (time.monotonic() - start) >= args.duration:
                    break

                row = [
                    datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    f"{time.monotonic() - start:.3f}",
                ]
                for channel in channels:
                    try:
                        row.append(hexs(session.read_adc(channel)))
                    except KLineError as exc:
                        log.debug("adc %d failed: %s", channel, exc)
                        row.append("")
                for address, count in ram_reads:
                    try:
                        row.append(hexs(session.read_ram(address, count)))
                    except KLineError as exc:
                        log.debug("ram %04X failed: %s", address, exc)
                        row.append("")
                if args.param:
                    try:
                        row.append(hexs(session.read_param_data()))
                    except KLineError as exc:
                        log.debug("param failed: %s", exc)
                        row.append("")

                writer.writerow(row)
                out.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
        finally:
            session.disconnect()
            if args.out:
                out.close()
                print(f"Wrote {args.out}", file=sys.stderr)
    return 0


def cmd_egs(args: argparse.Namespace) -> int:
    """Read the automatic transmission controller.

    The EGS speaks KWP71 like the DME but at 0x6C **at 4800 baud**, which is why
    a 9600 sweep only ever returned garbage: a 0x55 sent at half our rate reads
    back as 0x66. Its fault numbers are a DIFFERENT table from the engine's --
    code 100 on the DME is an output stage, code 100 on the gearbox is speed
    monitoring.
    """
    port = args.port or find_default_port()
    if port is None:
        raise SystemExit("No serial port found.")
    addr = args.address if args.address != 0x10 else EGS_ADDRESS

    with KLine(port, baud=args.egs_baud, timeout=1.5) as line:
        session = KWP71Session(line)
        keywords = session.connect(address=addr)
        print(f"EGS conectado en 0x{addr:02X} a {args.egs_baud} baudios")
        print(f"  keywords: {hexs(keywords)}")
        if session.id_strings:
            print("  identificación:")
            for raw in session.id_strings:
                print(f"    {raw.decode('ascii', 'replace').strip()!r:34} raw: {hexs(raw)}")
        try:
            raw = b"".join(session.read_fault_codes())
        finally:
            session.disconnect()

    codes = decode_egs(raw)
    print(f"\n{len(codes)} código(s) en la caja:\n")
    for c in codes:
        print(c.format())
        print()
    print(f"  crudo: {hexs(raw) or '(memoria vacía)'}")
    return 0


def cmd_dash(args: argparse.Namespace) -> int:
    """Serve the local dashboard."""
    port = args.port or find_default_port()
    if port is None and args.live and not args.demo:
        print("Sin cable todavía: el panel arranca igual y conecta solo al enchufarlo.")
    serve(port or "", http_port=args.http_port, address=args.address,
          interval=args.interval, live=args.live, lan=args.lan, demo=args.demo,
          port_finder=(None if args.port else find_default_port))
    return 0


def cmd_ds2(args: argparse.Namespace) -> int:
    """Probe DS2 modules -- the transmission (EGS) and friends.

    DS2 needs no initialisation, so a full sweep of the common addresses takes
    seconds rather than the minutes a 5-baud KWP71 sweep costs.
    """
    port = args.port or find_default_port()
    if port is None:
        raise SystemExit("No serial port found.")

    addresses = ([int(a, 0) for a in args.addresses] if args.addresses
                 else COMMON_DS2_ADDRESSES)

    print(f"DS2 probe at 9600 8E1, no init. {len(addresses)} address(es).\n")
    hits: list[tuple[int, bytes]] = []
    with DS2(port, timeout=args.timeout) as bus:
        for address in addresses:
            label = {0x32: "EGS (transmission)", 0x12: "DME (DS2 cars)",
                     0x56: "ABS", 0x80: "cluster"}.get(address, "")
            print(f"  0x{address:02X} {label:20} ... ", end="", flush=True)
            reply = bus.probe(address)
            if reply is None:
                print("silent")
            else:
                text = reply.decode("ascii", errors="replace").strip()
                print(f"RESPONSE  {hexs(reply)}   {text!r}")
                hits.append((address, reply))
            time.sleep(0.1)

    if not hits:
        print("\nNothing answered on DS2.")
        return 1

    print(f"\n{len(hits)} module(s) responded. Reading fault memory:\n")
    with DS2(port, timeout=args.timeout) as bus:
        for address, _ in hits:
            try:
                faults = bus.read_faults(address)
            except DS2Error as exc:
                print(f"  0x{address:02X}: fault read failed: {exc}")
                continue
            print(f"  0x{address:02X} faults ({len(faults)} bytes): {hexs(faults)}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Save fault memory to a JSON file for later comparison."""
    with open_line(args) as line:
        session = connect_session(args, line)
        try:
            blocks = session.read_fault_codes()
        finally:
            session.disconnect()

    snap = Snapshot.capture(b"".join(blocks), note=args.note or "")
    snap.save(args.out)
    print(f"\nSaved {len(snap.codes)} code(s) to {args.out}")
    for code in snap.codes:
        print(f"  code {code['number']}: {code['description']}  "
              f"(count {code['frequency']})")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Compare two snapshots and report which faults re-occurred."""
    before = Snapshot.load(args.before)
    after = Snapshot.load(args.after)
    print(f"before: {before.taken_at}  {before.note}")
    print(f"after : {after.taken_at}  {after.note}\n")
    for line in diff_snapshots(before, after):
        print(line)
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    """Poll the decoded sensor map, reconnecting through ignition noise."""
    port = args.port or find_default_port()
    if port is None:
        raise SystemExit("No serial port found.")

    writer = None
    out = None
    if args.out:
        out = open(args.out, "w", newline="")
        writer = csv.writer(out)

    reader = LiveReader(port, address=args.address, timeout=args.timeout,
                        extras=args.extras)
    with reader:
        names = [s.name for s in reader.sensors]
        if writer:
            writer.writerow(["timestamp", "elapsed_s"] + names)

        header = "  ".join(f"{s.name}({s.unit})" if s.unit else s.name
                           for s in reader.sensors)
        print(f"\n{header}\n", file=sys.stderr)

        start = time.monotonic()
        samples = 0
        try:
            while True:
                if args.duration and (time.monotonic() - start) >= args.duration:
                    break

                raw = reader.sample()
                if raw is None:
                    print("lost the ECU and could not recover", file=sys.stderr)
                    return 1

                elapsed = time.monotonic() - start
                cells = [f"{s.render(raw[s.name])}" for s in reader.sensors]
                stamp = f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}"
                print(f"{stamp:>6}  " + "  ".join(f"{c:>8}" for c in cells),
                      file=sys.stderr)

                if writer:
                    writer.writerow([
                        datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                        f"{elapsed:.3f}",
                    ] + [f"{s.scale(raw[s.name]):.3f}" for s in reader.sensors])
                    out.flush()

                samples += 1
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nstopped", file=sys.stderr)
        finally:
            if out:
                out.close()
                print(f"wrote {args.out}", file=sys.stderr)
            print(f"{samples} samples, {reader.reconnects} reconnect(s)",
                  file=sys.stderr)
    return 0


def cmd_raw(args: argparse.Namespace) -> int:
    """Send an arbitrary block. For probing undocumented commands."""
    title = int(args.title, 0)
    payload = bytes(int(b, 16) for b in args.payload) if args.payload else b""

    with open_line(args) as line:
        session = connect_session(args, line)
        try:
            print(f"\nSending title 0x{title:02X} payload [{hexs(payload)}]")
            blocks = session.command(title, payload)
            if not blocks:
                print("ECU acknowledged with no data.")
            for i, block in enumerate(blocks):
                text = block.decode("ascii", errors="replace").strip()
                print(f"  block {i}: {hexs(block)}   ascii: {text!r}")
        except NotSupportedError as exc:
            print(f"  {exc}")
            return 1
        finally:
            session.disconnect()
    return 0


# ----------------------------------------------------------------------- entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="e36obd",
        description="Read a BMW E36 OBD1 Motronic ECU over K-line (KWP71).",
    )
    parser.add_argument("--port", help="serial device (default: autodetect FTDI)")
    parser.add_argument("--baud", type=int, default=9600, help="line rate (default 9600)")
    parser.add_argument("--timeout", type=float, default=1.0, help="read timeout seconds")
    parser.add_argument("--address", type=lambda s: int(s, 0), default=0x10,
                        help="ECU address for the slow init (default 0x10 = DME #1)")
    parser.add_argument("--keyword-bytes", type=int, default=3,
                        help="keyword bytes expected after the 0x55 sync (default 3)")
    parser.add_argument("--loopback", choices=["auto", "on", "off"], default="auto",
                        help="whether the cable echoes TX to RX (default auto-detect)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every byte")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the cable; works with no car attached")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("scan", help="find which ECU address responds")
    p.add_argument("addresses", nargs="*", help="addresses to try (default: common set)")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("id", help="print ECU identification strings")
    p.set_defaults(func=cmd_id)

    p = sub.add_parser("codes", help="read stored fault codes")
    p.set_defaults(func=cmd_codes)

    p = sub.add_parser("clear", help="erase stored fault codes")
    p.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    p.set_defaults(func=cmd_clear)

    p = sub.add_parser("log", help="poll live values into CSV")
    p.add_argument("--adc", help="ADC channels, e.g. 0-15 or 0,3,7")
    p.add_argument("--ram", action="append", help="RAM read as ADDR:LEN, repeatable")
    p.add_argument("--param", action="store_true", help="include the param data block")
    p.add_argument("--interval", type=float, default=0.5, help="seconds between samples")
    p.add_argument("--duration", type=float, help="stop after N seconds")
    p.add_argument("--out", help="CSV output path (default stdout)")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("egs", help="read the automatic transmission (0x6C @ 4800)")
    p.add_argument("--egs-baud", type=int, default=EGS_BAUD,
                   help=f"line rate for the EGS (default {EGS_BAUD})")
    p.set_defaults(func=cmd_egs)

    p = sub.add_parser("dash", help="serve the local web dashboard")
    p.add_argument("--http-port", type=int, default=8036, help="HTTP port (default 8036)")
    p.add_argument("--interval", type=float, default=1.0, help="ECU poll interval")
    p.add_argument("--no-live", dest="live", action="store_false",
                   help="do not touch the ECU; show saved logs and snapshots only")
    p.add_argument("--lan", action="store_true",
                   help="expose on the local network, protected by a generated token")
    p.add_argument("--demo", action="store_true",
                   help="synthetic data, no ECU -- for working on the panel offline")
    p.set_defaults(func=cmd_dash, live=True)

    p = sub.add_parser("ds2", help="probe DS2 modules (EGS/transmission, ABS...)")
    p.add_argument("addresses", nargs="*", help="addresses to try (default: common set)")
    p.set_defaults(func=cmd_ds2)

    p = sub.add_parser("snapshot", help="save fault memory to JSON for comparison")
    p.add_argument("--out", required=True, help="output JSON path")
    p.add_argument("--note", help="label, e.g. 'before drive'")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("diff", help="compare two fault snapshots")
    p.add_argument("before", help="earlier snapshot JSON")
    p.add_argument("after", help="later snapshot JSON")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("live", help="poll decoded live sensors (engine running)")
    p.add_argument("--interval", type=float, default=0.5, help="seconds between samples")
    p.add_argument("--duration", type=float, help="stop after N seconds")
    p.add_argument("--extras", action="store_true",
                   help="also poll ignition angle, speed, air mass, lambda (slower)")
    p.add_argument("--out", help="CSV output path")
    p.set_defaults(func=cmd_live)

    p = sub.add_parser("raw", help="send an arbitrary block title")
    p.add_argument("--title", required=True, help="block title, e.g. 0x07")
    p.add_argument("payload", nargs="*", help="payload bytes in hex")
    p.set_defaults(func=cmd_raw)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except InitError as exc:
        print(f"\nInit failed: {exc}")
        print("Run `e36obd scan` to find the right address, or `e36obd doctor`.")
        return 1
    except KLineError as exc:
        print(f"\nCommunication error: {exc}")
        return 1
    except serial.SerialException as exc:
        print(f"\nSerial error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
