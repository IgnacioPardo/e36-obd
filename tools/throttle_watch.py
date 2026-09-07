"""Sigue SOLO el canal de mariposa, para poder mirar la leva mientras se mueve.

Leyendo un canal en vez de ocho, el muestreo sube ~8x y ya se puede empujar la
leva a mano y ver la lectura seguir el movimiento.

QUÉ PREGUNTA RESPONDE

La captura anterior mostró que el reposo pasó de 22 a 36 cuentas y se quedó
ahí. Eso tiene tres explicaciones y hay que separarlas:

  a) quedó un pie apoyado en el pedal            -> lo más probable, y trivial
  b) el cable del acelerador está tenso          -> ajuste
  c) la mariposa no vuelve sola a su tope        -> carbonilla o resorte

Deriva del sensor YA está descartada por aritmética: el canal 07 cayó 2,5 % en
la misma ventana, así que si el 04 fuera ratiométrico habría bajado medio punto,
no subido trece.

SECUENCIA -- todo en el cuerpo de mariposa, sin tocar el pedal:

  1. no tocar nada                       (reposo de referencia)
  2. abrir la leva a fondo con la mano y soltarla de golpe, x3
  3. no tocar nada                       (¿dónde queda?)
  4. empujar la leva CONTRA EL TOPE con el dedo y sostener
  5. soltar y no tocar nada              (¿se queda o se escapa?)

No hace falta cronometrar: cada etapa deja una meseta y las mesetas se leen
solas en la serie. Tomate el tiempo que necesites.

CÓMO SE LEE EL RESULTADO

  · Si en (4) baja a ~22 y en (5) se queda en 22  -> el pedal la sostenía. Caso (a).
  · Si en (4) baja a ~22 y en (5) sube sola a 36  -> algo la empuja a abrir. (b) o (c).
  · Si en (4) NO llega a 22 ni empujada a mano    -> el cero del TPS se movió,
                                                     y ahí sí es el sensor.

Uso:  PYTHONPATH=. ./.venv/bin/python tools/throttle_watch.py [segundos]
"""

from __future__ import annotations

import json
import os
import sys
import time

from e36obd.kline import KLine, KLineError
from e36obd.kwp71 import BlockType, KWP71Session, NotSupportedError

PORT = "/dev/cu.usbserial-A50285BI"
DME_ADDRESS = 0x10
DME_BAUD = 9600
TPS_CHANNEL = 0x04           # confirmado 2026-08-15: recorrido 22 -> 168
WINDOW = 180.0
OUT = "captures/throttle-watch.json"

# Referencia de la captura anterior, para poder comparar en la misma escala.
CLOSED_REF = 22
BAR_MAX = 180                # el recorrido observado llegó a 168


def bar(v: int, width: int = 46) -> str:
    n = max(0, min(width, round(v * width / BAR_MAX)))
    mark = round(CLOSED_REF * width / BAR_MAX)
    cells = ["#" if i < n else ("|" if i == mark else ".") for i in range(width)]
    return "".join(cells)


def main() -> int:
    window = float(sys.argv[1]) if len(sys.argv) > 1 else WINDOW
    print(f"Mariposa en vivo · canal {TPS_CHANNEL:02X} · {window:.0f} s\n")
    print("  1. no toques nada")
    print("  2. abrí la leva a fondo y soltala de golpe, x3")
    print("  3. no toques nada")
    print("  4. empujá la leva contra el tope y sostené")
    print("  5. soltá y no toques nada\n")
    print(f"  la marca | es el reposo de la captura anterior ({CLOSED_REF})\n")

    try:
        ctx = KLine(PORT, baud=DME_BAUD, timeout=1.5)
    except OSError as exc:
        print(f"no se pudo abrir el puerto: {exc}")
        return 1

    series: list[tuple[float, int]] = []
    with ctx as line:
        session = KWP71Session(line)
        try:
            session.connect(address=DME_ADDRESS)
        except KLineError as exc:
            print(f"no conectó: {exc}")
            return 1

        t0 = time.monotonic()
        deadline = t0 + window
        while time.monotonic() < deadline:
            try:
                blocks = session.command(BlockType.READ_ADC_CHANNEL,
                                         bytes([TPS_CHANNEL]))
            except NotSupportedError:
                print("el canal dejó de contestar"); break
            except KLineError as exc:
                print(f"  se cortó ({exc}); reconectando…")
                try:
                    session = KWP71Session(line)
                    session.connect(address=DME_ADDRESS)
                except KLineError:
                    break
                continue
            data = b"".join(blocks)
            if not data:
                continue
            v = data[-1]
            t = time.monotonic() - t0
            series.append((round(t, 2), v))
            print(f"  {t:6.1f}s  {v:3d}  {v * 5 / 255:4.2f}V  {bar(v)}", flush=True)

        try:
            session.disconnect()
        except KLineError:
            pass

    if not series:
        print("\n  sin datos")
        return 1

    vals = [v for _, v in series]
    hz = len(series) / max(1e-6, series[-1][0])
    print(f"\n  {len(series)} muestras en {series[-1][0]:.0f} s  ({hz:.1f} Hz)")
    print(f"  mínimo {min(vals)}  máximo {max(vals)}")
    print(f"  reposo de referencia anterior: {CLOSED_REF}")
    print(f"  ¿tocó alguna vez {CLOSED_REF} o menos?  "
          + ("SÍ" if min(vals) <= CLOSED_REF else "NO"))

    try:
        os.makedirs("captures", exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump({"channel": TPS_CHANNEL, "series": series}, fh, indent=1)
        print(f"  serie en {OUT}")
    except OSError as exc:
        print(f"  no se pudo guardar: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
