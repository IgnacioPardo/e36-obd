"""Encuentra el canal del TPS preguntándole al DME, no al multímetro.

CONFIRMADO 2026-08-15: el DME M1.7.2 soporta READ_ADC_CHANNEL (0x08) y
devuelve 2 bytes por canal. Hay OCHO canales reales -- los índices 0x08..0x0F
devuelven lo mismo que 0x00..0x07, o sea que el índice se enmascara a 3 bits.
Entre dos lecturas seguidas los valores cambian de a poco, así que son
conversiones vivas y no una tabla estática.

Primera lectura, contacto puesto y motor apagado:

  canal 00  00 0E      canal 04  00 16
  canal 01  00 B4      canal 05  00 55
  canal 02  00 8D      canal 06  00 1E
  canal 03  00 58      canal 07  00 F6

Esto vale MÁS que medir en el conector: es la conversión que hace la ECU
después de todo el mazo, o sea el final del camino y no el medio. Y anda con
el motor apagado, a diferencia de los sensores que ya mapeamos, que leen 0x00
hasta que el motor gira.

MÉTODO -- ventana de captura, sin interacción:

  Se muestrean los ocho canales en bucle durante una ventana. Mientras corre,
  hay que BARRER EL PEDAL despacio, del piso a suelto, varias veces. Al final
  se informa mínimo, máximo y recorrido de cada canal. El que se movió mucho
  es el TPS; los demás se quedan quietos.

No hace falta coordinar nada: se barre el pedal durante toda la ventana.

Por qué importa el valor de CERRADA: es el que el DME usa para decidir "entro
en control de ralentí" y "corto combustible en retención". Un TPS que en el
banco barre lindo puede igual entregar un cerrado corrido, y eso rompe
justamente el ralentí y la retención sin tocar nada arriba de 1000 rpm. Por
eso la prueba que cierra el caso es correr esto con el TPS nuevo, anotar el
cerrado, poner el viejo y repetir.

NO manda bloques de escritura ni de actuador. Este panel lee.

Uso:  PYTHONPATH=. ./.venv/bin/python tools/adc_scan.py [segundos]
"""

from __future__ import annotations

import json
import sys
import time

from e36obd.kline import KLine, KLineError
from e36obd.kwp71 import BlockType, KWP71Session, NotSupportedError

PORT = "/dev/cu.usbserial-A50285BI"
DME_ADDRESS = 0x10
DME_BAUD = 9600
CHANNELS = list(range(0x08))          # ocho reales; 0x08..0x0F son espejo
WINDOW = 90.0
OUT = "captures/adc-sweep.json"

# Umbral para llamar "se movió" a un canal. Cuatro cuentas de 8 bits sobre
# 5 V son ~80 mV: bastante más que el ruido de conversión que ya vimos.
MOVED = 4


def read_channel(session: KWP71Session, ch: int) -> int | None:
    """Devuelve el byte bajo del canal, o None si no contesta."""
    try:
        blocks = session.command(BlockType.READ_ADC_CHANNEL, bytes([ch]))
    except NotSupportedError:
        return None
    data = b"".join(blocks)
    return data[-1] if data else None


def main() -> int:
    window = float(sys.argv[1]) if len(sys.argv) > 1 else WINDOW
    print("Barrido de canales analógicos del DME\n")
    print(f"  {PORT} · 0x{DME_ADDRESS:02X} @ {DME_BAUD} · ventana {window:.0f} s\n")
    print("  >>> BARRÉ EL PEDAL despacio, del piso a suelto, durante toda la")
    print("      ventana. Motor apagado, contacto puesto. Varias pasadas.\n")

    try:
        ctx = KLine(PORT, baud=DME_BAUD, timeout=1.5)
    except OSError as exc:
        print(f"no se pudo abrir el puerto: {exc}")
        return 1

    series: dict[int, list[int]] = {c: [] for c in CHANNELS}
    with ctx as line:
        session = KWP71Session(line)
        try:
            kw = session.connect(address=DME_ADDRESS)
        except KLineError as exc:
            print(f"no conectó: {exc}")
            return 1
        print("conectado · keywords " + " ".join(f"{b:02X}" for b in kw))

        deadline = time.monotonic() + window
        passes = 0
        while time.monotonic() < deadline:
            try:
                for ch in CHANNELS:
                    v = read_channel(session, ch)
                    if v is not None:
                        series[ch].append(v)
            except KLineError as exc:
                # La sesión se cae con ruido de encendido; reconectar y seguir,
                # que es la misma política que usa el lector en vivo.
                print(f"  se cortó ({exc}); reconectando…")
                try:
                    session = KWP71Session(line)
                    session.connect(address=DME_ADDRESS)
                except KLineError:
                    break
                continue
            passes += 1
            print(f"  pasada {passes:2d}  "
                  + "  ".join(f"{c:X}:{series[c][-1]:3d}" for c in CHANNELS
                              if series[c]), flush=True)
        try:
            session.disconnect()
        except KLineError:
            pass

    print(f"\n  {passes} pasadas\n")
    print(f"  {'canal':6} {'min':>5} {'max':>5} {'rec.':>6}   "
          f"{'V min':>6} {'V max':>6}")
    moved: list[tuple[int, int, int, int]] = []
    for ch in CHANNELS:
        s = series[ch]
        if not s:
            continue
        lo, hi = min(s), max(s)
        rng = hi - lo
        # Escala supuesta 8 bits sobre 5 V. Sin confirmar contra multímetro,
        # así que sirve para comparar canales, no como medida absoluta.
        print(f"  {ch:02X}     {lo:5d} {hi:5d} {rng:6d}   "
              f"{lo * 5 / 255:6.2f} {hi * 5 / 255:6.2f}")
        if rng >= MOVED:
            moved.append((rng, ch, lo, hi))

    print()
    if not moved:
        print("  Ningún canal siguió al pedal.")
        print("  O no se barrió durante la ventana, o el TPS no está en estos")
        print("  ocho canales y hay que buscarlo en la RAM con el explorador.")
    else:
        moved.sort(reverse=True)
        rng, ch, lo, hi = moved[0]
        print(f"  >>> El TPS es el canal {ch:02X}.")
        print(f"      cerrada {lo} (~{lo * 5 / 255:.2f} V) · "
              f"abierta {hi} (~{hi * 5 / 255:.2f} V) · recorrido {rng}")
        print()
        print("      ANOTÁ EL VALOR DE CERRADA. La prueba que cierra el caso es")
        print("      repetir esto con el TPS viejo puesto: si el cerrado cambia,")
        print("      ahí está la falla, medida en la entrada del DME.")
        if len(moved) > 1:
            print("      (también se movieron: "
                  + " ".join(f"{c:02X}" for _, c, _, _ in moved[1:]) + ")")

    try:
        import os
        os.makedirs("captures", exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump({"channels": {f"{c:02X}": series[c] for c in CHANNELS}},
                      fh, indent=1)
        print(f"\n  serie completa en {OUT}")
    except OSError as exc:
        print(f"\n  no se pudo guardar: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
