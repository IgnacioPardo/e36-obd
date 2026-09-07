"""Live sensor map for BMW DME M1.7.2 (E36 M43B16).

Addresses and scalings originate from a captured INPA session against a
Motronic 1.7 and were verified against this M43B16 1.7.2 at idle: battery
13.69 V while charging, intake air 17.2 C, coolant 37.1 C warming, 940 rpm.
Four mutually consistent physical readings is good evidence the map holds.

Important: the DME does not populate these locations until the engine is
actually running. With ignition on and the engine off they all read 0x00,
which looks like a dead link but is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Sensor:
    address: int
    name: str
    unit: str
    scale: Callable[[int], float]
    fmt: str = "{:.1f}"

    def render(self, raw: int) -> str:
        return self.fmt.format(self.scale(raw))


# Core block: contiguous from 0x0036 to 0x0040, readable in a single command.
# Keeping it to one read matters -- every extra round trip is another chance
# for ignition noise to corrupt the byte handshake.
CORE_START = 0x0036
CORE_LENGTH = 0x0B  # 0x0036..0x0040 inclusive

CORE_SENSORS: list[Sensor] = [
    Sensor(0x0036, "battery", "V", lambda b: 0.0681 * b, "{:.2f}"),
    Sensor(0x0037, "intake_air_temp", "C", lambda b: -33.5 + 0.65 * b),
    Sensor(0x0038, "coolant_temp", "C", lambda b: -32.5 + 0.65 * b),
    Sensor(0x003C, "rpm", "rpm", lambda b: 10.0 * b, "{:.0f}"),
    Sensor(0x0040, "load", "ms", lambda b: 0.05 * b, "{:.2f}"),
]

# Velocidad de camino. Documentada en 0x008B, pero NUNCA validada -- con el
# motor apagado leía 0x00 como todo lo demás. Vive fuera del bloque contiguo,
# así que leerla cuesta un round trip extra y baja la tasa de muestreo, por eso
# es opcional.
#
# OJO: puede estar DENTRO del bloque de 11 bytes. Seis bytes de ese bloque
# (0x39 0x3A 0x3B 0x3D 0x3E 0x3F) siguen sin identificar y viajan gratis en cada
# lectura. Antes de pagar un round trip, conviene buscarla ahí con el explorador.
ROAD_SPEED_ADDR = 0x008B
ROAD_SPEED_SCALE = 1.102          # km/h por cuenta (sin validar)

# Tren final, para pasar de velocidad de camino a vueltas del eje de salida.
# La relación de marcha es régimen / vueltas_de_salida, no régimen / km/h.
FINAL_DRIVE = 4.44                # E36 318i automático, típico
TYRE_CIRCUM_M = 1.87              # 205/60 R15

def output_shaft_rpm(speed_kmh: float, final_drive: float = FINAL_DRIVE,
                     circum_m: float = TYRE_CIRCUM_M) -> float:
    """Vueltas del eje de salida a partir de la velocidad de camino.

    Hay que calibrarlo: en 3ª la relación mecánica es exactamente 1.000, así que
    si andando en tercera esto no da ~1.00, el tren final o la circunferencia
    están mal y se corrigen desde ahí.
    """
    if speed_kmh <= 0 or circum_m <= 0:
        return 0.0
    return speed_kmh * 1000.0 / 60.0 / circum_m * final_drive


# Outside the core block, so each costs an extra round trip.
EXTRA_SENSORS: list[Sensor] = [
    Sensor(0x0055, "ignition_angle", "deg", lambda b: 0.75 * (96 - b)),
    Sensor(0x008B, "road_speed", "km/h", lambda b: 1.102 * b),
    Sensor(0x009D, "air_consumption", "kg/h", lambda b: 0.2 * b),
    Sensor(0x0211, "lambda_integrator", "", lambda b: float(b - 128), "{:.0f}"),
]

ALL_SENSORS = CORE_SENSORS + EXTRA_SENSORS


def core_offset(sensor: Sensor) -> int:
    """Index of a core sensor's byte within a CORE_LENGTH read from CORE_START."""
    return sensor.address - CORE_START
