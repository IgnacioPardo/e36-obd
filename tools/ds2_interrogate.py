"""Interroga a fondo un módulo DS2: barre TODOS los bytes de comando 0x00-0xFF
y reporta cuáles devuelven datos reales.

Motivación: el módulo en 0x00 de este auto contesta identificación y el comando
0x0E, pero devuelve b0/ff a todo lo demás. No sabemos qué es, y el TCM es
candidato. Un barrido de comandos suele delatar la familia del módulo por qué
servicios expone.

Uso:  ./.venv/bin/python tools/ds2_interrogate.py 0x00 [0x56 ...]
"""

from __future__ import annotations

import sys
import time

from e36obd.ds2 import DS2, DS2Error

PORT = "/dev/cu.usbserial-A50285BI"

# Respuestas de un solo byte que NO son datos: son acuse o rechazo. Filtrarlas
# es lo que separa "el módulo soporta esto" de "el módulo dijo que no".
TRIVIAL = {0xB0, 0xFF, 0xA0, 0xA1, 0xA2}


def interrogate(bus: DS2, addr: int) -> list[tuple[int, bytes]]:
    hits: list[tuple[int, bytes]] = []
    for cmd in range(0x100):
        try:
            r = bus.request(addr, bytes([cmd]))
        except (DS2Error, OSError):
            continue
        except Exception:
            continue
        if len(r) <= 1 and (not r or r[0] in TRIVIAL):
            continue                      # acuse vacío, no un servicio
        hits.append((cmd, r))
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in r)
        print(f"  cmd 0x{cmd:02X} -> {len(r):3d}B  {r.hex(' ')}", flush=True)
        print(f"              ascii: {txt}", flush=True)
        time.sleep(0.08)
    return hits


def main() -> int:
    addrs = [int(a, 0) for a in sys.argv[1:]] or [0x00]
    with DS2(PORT, timeout=0.45) as bus:
        for addr in addrs:
            print(f"\n=== módulo 0x{addr:02X} · barriendo comandos 0x00-0xFF ===", flush=True)
            hits = interrogate(bus, addr)
            print(f"  -> {len(hits)} comando(s) con datos", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
