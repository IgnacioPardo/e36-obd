"""Averigua qué servicios KWP71 expone el EGS de la caja.

Sin esto, "agregar live data del EGS" no es accionable: puede tener ReadRAM,
puede tener ReadADC, puede no exponer ninguno. Este script pregunta.

Prueba cada título de bloque válido desde el tester y clasifica la respuesta:

  · datos          -> el servicio existe y devuelve payload
  · NACK / 0x0B    -> el módulo entiende el título y lo rechaza
  · sin respuesta  -> el título no existe en este módulo

Los bloques de escritura y de actuador NO se envían nunca. Este panel lee.

Uso:  PYTHONPATH=. ./.venv/bin/python tools/egs_services.py
"""

from __future__ import annotations

import sys
import time

from e36obd.egs import EGS_ADDRESS, EGS_BAUD
from e36obd.kline import KLine, KLineError
from e36obd.kwp71 import BlockType, KWP71Session, NotSupportedError

PORT = "/dev/cu.usbserial-A50285BI"

# Solo lectura. Ni WRITE_RAM (0x02), ni WRITE_EEPROM (0x1A), ni
# ACTIVATE_ACTUATOR (0x04): accionar un solenoide de la caja con el auto
# parado no es algo que este proyecto haga.
PROBES: list[tuple[int, str, bytes]] = [
    (BlockType.REQUEST_ID,          "RequestID",          b""),
    (BlockType.READ_TROUBLE_CODES,  "ReadTroubleCodes",   b""),
    (BlockType.READ_PARAM_DATA,     "ReadParamData",      b""),
    (BlockType.REQUEST_SNAPSHOT,    "RequestSnapshot",    b""),
    (BlockType.READ_ADC_CHANNEL,    "ReadADC ch0",        bytes([0x00])),
    (BlockType.READ_ADC_CHANNEL,    "ReadADC ch1",        bytes([0x01])),
    (BlockType.READ_ADC_CHANNEL,    "ReadADC ch5",        bytes([0x05])),
    (BlockType.READ_RAM,            "ReadRAM 0x0000 x8",  bytes([8, 0x00, 0x00])),
    (BlockType.READ_RAM,            "ReadRAM 0x0020 x8",  bytes([8, 0x00, 0x20])),
    (BlockType.READ_RAM,            "ReadRAM 0x0036 x8",  bytes([8, 0x00, 0x36])),
    (BlockType.READ_ROM,            "ReadROM 0x0000 x8",  bytes([8, 0x00, 0x00])),
    (BlockType.READ_EEPROM,         "ReadEEPROM 0x0 x8",  bytes([8, 0x00, 0x00])),
]


def hexs(b) -> str:
    return " ".join(f"{x:02X}" for x in b)


def main() -> int:
    print(f"EGS 0x{EGS_ADDRESS:02X} @ {EGS_BAUD} · probando servicios de LECTURA\n")
    supported: list[str] = []

    with KLine(PORT, baud=EGS_BAUD, timeout=1.5) as line:
        session = KWP71Session(line)
        keywords = session.connect(address=EGS_ADDRESS)
        print(f"conectado · keywords {hexs(keywords)}\n")

        for title, label, payload in PROBES:
            print(f"  {label:22} ", end="", flush=True)
            try:
                blocks = session.command(title, payload)
            except NotSupportedError:
                print("rechazado (el módulo conoce el título pero dice no)")
                continue
            except KLineError as exc:
                print(f"sin respuesta / se cortó ({exc})")
                # Un título inexistente puede tirar la sesión: reconectar.
                try:
                    session.disconnect()
                except KLineError:
                    pass
                try:
                    session = KWP71Session(line)
                    session.connect(address=EGS_ADDRESS)
                except KLineError as exc2:
                    print(f"    no se pudo reconectar: {exc2}")
                    break
                continue
            data = b"".join(blocks)
            if data:
                txt = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
                print(f"{len(data):3d}B  {hexs(data)}")
                print(f"                         ascii: {txt}")
                supported.append(label)
            else:
                print("acuse sin datos")
            time.sleep(0.15)

        try:
            session.disconnect()
        except KLineError:
            pass

    print(f"\n=== servicios con datos: {len(supported)} ===")
    for s in supported:
        print(f"  {s}")
    if not supported:
        print("  ninguno — este EGS solo expone identificación y fallas,")
        print("  así que NO hay live data posible y el freeze frame es el")
        print("  único instrumento disponible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
