"""Prueba una dirección a varias velocidades y, si sincroniza, sigue hasta los datos.

Motivación: la dirección 0x6C devolvió `66 33 7E E0 06 C0 ...` leída a 9600. Eso
no es un sync KWP71 (debería empezar en 0x55), pero es exactamente lo que parece
un 0x55 enviado a la MITAD de nuestra velocidad:

    0x55 a 4800, muestreado a 9600 -> cada bit se duplica
    trama: 0 | 1 0 1 0 1 0 1 0 | 1        (start, 0x55 LSB primero, stop)
    doble: 00 11 00 11 00 11 00 11 00 11
    nuestro UART toma el primer 0 como start y los 8 siguientes como dato:
           0 1 1 0 0 1 1 0  -> LSB primero -> 0x66

Así que 0x66 es la firma de "cable correcto, baudios equivocados". Este script
recorre las velocidades plausibles y, en la que sincronice de verdad, arranca
una sesión KWP71 completa: keywords, strings de identificación y memoria de
fallas.

Uso:  ./.venv/bin/python tools/probe_baud.py 0x6C [0x10 ...]
"""

from __future__ import annotations

import sys

from e36obd.kline import InitError, KLine, KLineError
from e36obd.kwp71 import KWP71Session

PORT = "/dev/cu.usbserial-A50285BI"
BAUDS = [4800, 9600, 2400, 1200, 10400, 19200]


def hexs(b) -> str:
    return " ".join(f"{x:02X}" for x in b)


def guess_true_baud(data: bytes, sampled_at: int) -> str:
    """Pista sobre la velocidad real a partir de una trama ilegible.

    No es exacto: es una heurística sobre la firma del bit duplicado. Un 0x55
    a la mitad de velocidad aparece como 0x66/0x33; a un cuarto, como 0x0F/0xF0.
    """
    if not data:
        return ""
    first = data[0]
    # Valores calculados, no estimados a ojo: un 0x55 remuestreado da 0x66 al
    # doble y 0x78 al cuádruple. Los acompañantes (0x33, 0x99, 0xCC) salen de
    # dónde cae el bit de start dentro del flujo duplicado.
    if first in (0x66, 0x33, 0x99, 0xCC):
        return f"  pista: patrón de bit duplicado -> probá {sampled_at // 2} baudios"
    if first in (0x78, 0x1E, 0x87, 0xE1):
        return f"  pista: bit cuadruplicado -> probá {sampled_at // 4} baudios"
    return ""


def try_session(port: str, baud: int, addr: int) -> bool:
    """Init + sesión completa. Devuelve True si sacamos datos de verdad."""
    with KLine(port, baud=baud, timeout=1.5) as line:
        session = KWP71Session(line)
        keywords = session.connect(address=addr)
        print(f"    SYNC LIMPIO · keywords {hexs(keywords)}")

        if session.id_strings:
            print("    identificación:")
            for raw in session.id_strings:
                txt = raw.decode("ascii", errors="replace").strip()
                print(f"      {txt!r:34} raw: {hexs(raw)}")
        else:
            print("    (no mandó strings de identificación)")

        try:
            blocks = session.read_fault_codes()
            data = b"".join(blocks)
            print(f"    memoria de fallas ({len(data)} bytes): {hexs(data) or '(vacía)'}")
        except KLineError as exc:
            print(f"    lectura de fallas falló: {exc}")

        session.disconnect()
    return True


def main() -> int:
    addrs = [int(a, 0) for a in sys.argv[1:]] or [0x6C]
    for addr in addrs:
        print(f"\n=== dirección 0x{addr:02X} ===")
        for baud in BAUDS:
            print(f"  {baud} baudios ... ", end="", flush=True)
            try:
                if try_session(PORT, baud, addr):
                    print(f"  -> 0x{addr:02X} habla a {baud} baudios")
                    break
            except InitError:
                # Sin sync: releer crudo para ver si al menos hubo ruido.
                try:
                    with KLine(PORT, baud=baud, timeout=1.0) as line:
                        line.flush()
                        raw = b""
                        for _ in range(24):
                            b = line.try_read_byte(0.05)
                            if b is not None:
                                raw += bytes([b])
                except KLineError:
                    raw = b""
                if raw:
                    print(f"sin sync, pero llegó: {hexs(raw)}")
                    hint = guess_true_baud(raw, baud)
                    if hint:
                        print(hint)
                else:
                    print("silencio")
            except KLineError as exc:
                print(f"error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
