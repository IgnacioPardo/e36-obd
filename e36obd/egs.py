"""EGS — computadora de la caja automática (A4S 310R / A4S 270R, THM-R1).

Descubierto empíricamente en este auto: **dirección 0x6C a 4800 baudios**, KWP71
igual que el motor pero a la mitad de velocidad. Por eso un barrido a 9600 solo
devolvía basura: un 0x55 enviado a 4800 y muestreado a 9600 se lee como 0x66.

Keywords observados: `55 87 81` (el DME devuelve `55 00 81`).

CUIDADO CON LOS HOMÓNIMOS: los números de código del EGS y del DME son tablas
distintas. El 100 del motor es "etapa de salida 1 en el DME"; el 100 de la caja
es "monitoreo de velocidad". Nunca decodificar uno con la tabla del otro.

Tabla reproducida del manual Baum Tools CS1000 para BMW, sección 4 (oct 1997),
sistema `U 4`, aplicable 1992–1995.
"""

from __future__ import annotations

# Configuración del enlace, verificada en el auto el 13-ago-2026.
#
#   módulo    EGS / AGS — A4S 310R (THM-R1), control Bosch, TCM 55 pines
#   dirección 0x6C
#   baudios   4800  (el DME es 9600: son distintos, no es un typo)
#   protocolo KWP71, init de 5 baudios 8N1, ≥2600 ms de bus en reposo
#   sync      55 87 81   (el DME devuelve 55 00 81)
#
# CABLEADO — el bloque completo, porque falta un solo ítem y no despierta nada:
#
#   OBD2  7  <- redondo 17 + 20 comuneados   TXD / TXD II  (datos)
#   OBD2 15  <- redondo 15                   RXD           (despertar)
#   OBD2 4+5 <- redondo 19                   masa
#   OBD2 16  <- redondo 14                   +12V PERMANENTE, no conmutado
#
#   Y LO IMPRESCINDIBLE: un puente soldado entre **OBD2 pin 7 y pin 15** dentro
#   del conector del cable. Un K+DCAN de fábrica maneja solo el pin 7, así que
#   la línea RXD nunca se excita y NINGÚN módulo contesta -- ni el DME ni el EGS.
#   Sin ese puente, todo lo de arriba es inútil.
EGS_ADDRESS = 0x6C
EGS_BAUD = 4800

# Tabla de códigos tomada del SGBD `gs41x.prg` de EDIABAS (Getriebesteuerung
# 4.1x, rev 1.43, 1996), descifrado con XOR 0xF7. Es la fuente autoritativa:
# el texto sale del propio archivo que usa INPA, no de un manual de terceros.
# Los números son decimales; entre paréntesis va el hex como lo guarda el SGBD.
EGS_CODES: dict[int, str] = {
    1:   "Solenoide de bloqueo Shift-Lock",
    2:   "Interruptor de programa",
    4:   "Intervención sobre el motor",
    9:   "Señal KVA (tiempo de inyección) desde el DME",
    11:  "Señal de régimen del motor (n-mot)",
    20:  "Señal de velocidad de salida (n-ab)",
    22:  "Sensor de temperatura del cárter de aceite",
    23:  "Posición de la palanca selectora",
    28:  "Alimentación Ubatt (permanente)",
    30:  "Interruptor de kickdown",
    37:  "Alimentación Ubatt",
    38:  "Solenoide MV-WK (embrague del convertidor)",
    40:  "Regulador de presión",
    43:  "Solenoide MV 2-3",
    45:  "Solenoide de banda",
    48:  "Solenoide MV 1-2 / 3-4",
    54:  "Masa de los solenoides",
    55:  "Señal de mariposa",
    57:  "Interruptor de luz de freno",
    100: "Monitoreo de marcha (Gangüberwachung)",
    101: "Seguro de reducción",
    102: "Seguro de sobre-régimen",
    103: "Checksum de EPROM",
    104: "DKT — info de temperatura",
    105: "DKT — info de mariposa",
    106: "DKT — cantidad de inyección",
    107: "Conmutación N→D con velocidad de salida alta",
}

# Vocabulario de "tipo de falla" (Fehlerart) del SGBD. NO es un campo de bits
# suelto: el byte de tipo selecciona, bit por bit, entre dos textos de esta
# lista según una matriz por código (FArtMatrix), que todavía no decodifiqué.
# Así que "esporádica" es lectura probable del bit 7, no certeza.
FAULT_TYPES: dict[int, str] = {
    1:  "cortocircuito a U-Batt",
    2:  "cortocircuito a masa",
    3:  "interrupción de línea",
    4:  "sin plausibilidad",
    5:  "plausibilidad",
    6:  "no presente en la última consulta",
    7:  "presente en la última consulta",
    8:  "condición de prueba no alcanzada",
    9:  "condición de prueba alcanzada",
    10: "falla no presente ahora",
    11: "falla presente ahora",
    12: "falla estática",
    13: "falla esporádica",
    14: "temperatura de caja demasiado alta (>165 °C)",
    15: "tensión fuera del rango válido",
    16: "el DME reconoce señal de mariposa incorrecta",
    17: "el DME envía señal de temperatura de motor errónea",
    18: "el DME envía señal de mariposa errónea",
}

# Condiciones ambientales del freeze frame, con las escalas EXACTAS del SGBD.
# El emparejamiento (nombre, unidad, factor, offset) se verificó por tres vías
# independientes: 0.392 = 100/255 para mariposa, 0.068 coincide con el DME para
# tensión, y el offset −40 es la convención automotriz de temperatura.
ENV_CONDITIONS: dict[int, tuple[str, str, float, float]] = {
    1: ("Régimen del motor",        "rpm", 32.0,   0.0),
    2: ("Velocidad de salida",      "rpm", 32.0,   0.0),
    3: ("Mariposa",                 "%",    0.392, 0.0),
    4: ("Tensión de batería",       "V",    0.068, 0.0),
    5: ("Temperatura de aceite",    "°C",   1.0,  -40.0),
    6: ("Corriente del regulador",  "mA",   1.0,   0.0),
    7: ("Byte de estado 1",         "",     1.0,   0.0),
    8: ("Byte de estado 2",         "",     1.0,   0.0),
}

# Jobs de live data que el SGBD declara para este módulo. Confirma que el EGS
# SÍ expone datos en vivo -- y justo los dos lados de la relación de la que se
# queja el código 100. Los títulos/direcciones KWP71 concretos están en el
# bytecode y todavía no se extrajeron; RAM_LESEN toma (dirección, cantidad),
# que es exactamente nuestro read_ram.
# Inmediatos extraídos del bytecode de cada job de status (SGBD gs41x, XOR 0xF7).
# Los seis jobs son bytecode IDÉNTICO salvo estos dos bytes, así que la request
# está parametrizada por ellos. Lo que NO está confirmado es que el par sea
# (título, payload): la VM de EDIABAS no está decodificada.
#
# PELIGRO: en KWP71 estándar el título 0x05 es EraseTroubleCodes. Si el EGS
# sigue el estándar, mandar 0x05 a ciegas BORRA la memoria de fallas, que es la
# única evidencia que tenemos. No probar sin snapshot previo.
STATUS_JOB_IMMEDIATES: dict[str, tuple[int, int]] = {
    "STATUS_MOTORDREHZAHL":  (0x05, 0x01),
    "STATUS_ABTRIEBSDREHZ":  (0x05, 0x02),   # velocidad de salida — la clave
    "STATUS_LASTSIGNAL_DKG": (0x05, 0x04),
    "STATUS_GETRIEBETEMP":   (0x05, 0x13),
    "STATUS_UBATT":          (0x05, 0x14),
    "STATUS_DIGITAL_LESEN":  (0x03, 0x06),   # el más seguro para probar primero
}

LIVE_JOBS = [
    "STATUS_MOTORDREHZAHL",      # régimen del motor
    "STATUS_ABTRIEBSDREHZ",      # velocidad del eje de salida  <- clave
    "STATUS_LASTSIGNAL_DKG",     # señal de carga / mariposa
    "STATUS_UBATT",              # tensión
    "STATUS_GETRIEBETEMP",       # temperatura de caja
    "STATUS_EINSPRITZMENGE",     # cantidad de inyección
    "STATUS_KICKDOWN_SCHALTER",  # kickdown
    "STATUS_DIGITAL_LESEN",      # estados digitales: palanca, L1-L4, freno...
    "RAM_LESEN", "ROM_LESEN", "IDENT", "FS_LESEN", "FS_LOESCHEN",
]

# El byte de tipo de falla NO es el campo de bits del DME. El SGBD declara
# F_ART1_NR..F_ART8_NR con pares de textos A1_0/A1_1 .. A8_0/A8_1: cada bit
# elige uno de dos textos de FAULT_TYPES, y CUÁLES dos depende del código de
# falla vía la matriz FArtMatrix, que todavía no está decodificada.
#
# Por eso acá no se inventa semántica. Lo único que se afirma es el bit 7, que
# encaja con "falla esporádica" (índice 13 del vocabulario) y coincide con lo
# observado. El resto se reporta como posición de bit, sin traducir.
SPORADIC_BIT = 0x80

# Escalas del SGBD, no heredadas del DME. El DME usa ×40 para las rpm del
# freeze frame y (crudo−0x40)×0.75 para temperatura; el EGS usa ×32 y crudo−40.
# Aplicar las del motor acá daba números equivocados.
RPM_SCALE = 32.0
TEMP_OFFSET_SUB = 40.0


class EgsFault:
    """Un registro de falla del EGS, cinco bytes como en el DME."""

    __slots__ = ("number", "condition", "rpm_raw", "b3_raw", "frequency")

    def __init__(self, record: bytes) -> None:
        if len(record) != 5:
            raise ValueError(f"el registro debe ser de 5 bytes, no {len(record)}")
        self.number = record[0]
        self.condition = record[1]
        self.rpm_raw = record[2]
        self.b3_raw = record[3]
        self.frequency = record[4]

    @property
    def description(self) -> str:
        return EGS_CODES.get(self.number, "código desconocido — fuera de la tabla EGS 4.XX")

    @property
    def sporadic(self) -> bool:
        """Bit 7. Es la única posición cuyo significado se puede afirmar."""
        return bool(self.condition & SPORADIC_BIT)

    @property
    def conditions(self) -> list[str]:
        """Lo que se puede decir honestamente del byte de tipo de falla."""
        if self.condition == 0x00:
            return ["sin tipo de falla registrado"]
        out = ["falla esporádica" if self.sporadic else "falla estática"]
        others = [f"bit {b}" for b in range(7) if self.condition & (1 << b)]
        if others:
            out.append("además " + ", ".join(others)
                       + " (mapeo por FArtMatrix, sin decodificar)")
        return out

    @property
    def rpm(self) -> int:
        """Byte 2 leído como régimen de motor, con la escala del EGS (×32)."""
        return int(self.rpm_raw * RPM_SCALE)

    @property
    def output_rpm(self) -> int:
        """Byte 3 leído como velocidad de salida (n-ab), misma escala ×32.

        Para el código 100 (monitoreo de marcha) los dos lados de la relación
        son la lectura natural, y da un número coherente. Cuál condición
        ambiental corresponde a cada código sale de la matriz FUmweltTexte del
        SGBD, que todavía no está decodificada -- así que esto es inferencia,
        no certeza.
        """
        return int(self.b3_raw * RPM_SCALE)

    @property
    def ratio(self) -> float | None:
        """Relación motor/salida. Comparable contra 2.86 / 1.62 / 1.00 / 0.72."""
        o = self.output_rpm
        return (self.rpm / o) if o else None

    @property
    def temp_c(self) -> float:
        """Byte 3 leído como temperatura de aceite, si aplica a este código."""
        return self.b3_raw - TEMP_OFFSET_SUB

    def format(self) -> str:
        return "\n".join([
            f"  Código {self.number}: {self.description}",
            f"    condición 0x{self.condition:02X}: {', '.join(self.conditions)}",
            f"    ocurrencias: {self.frequency}",
            f"    freeze frame (escalas del SGBD): motor {self.rpm} rpm, "
            f"salida {self.output_rpm} rpm"
            + (f", relación {self.ratio:.2f}" if self.ratio else "")
            + f"   [crudo {self.rpm_raw:02X} {self.b3_raw:02X}]",
            f"    (byte 3 como temperatura daría {self.temp_c:.0f} °C — cuál de las "
            f"dos aplica sale de FUmweltTexte, sin decodificar)",
        ])


def decode(data: bytes) -> list[EgsFault]:
    """Parte el payload en registros de 5 bytes. Ignora una cola incompleta."""
    return [EgsFault(data[i : i + 5]) for i in range(0, len(data) - 4, 5)]


# ---------------------------------------------------------------------------
# Datos mecánicos de la caja, del manual de reparación Hydra-matic 4L30-E.
# Sirven para interpretar la relación que reporta el código 100.
# ---------------------------------------------------------------------------

# El manual lista DOS juegos de relaciones. 3ª y 4ª son iguales en ambos; solo
# 1ª y 2ª difieren. Cuál trae este auto no está resuelto: se calibra midiendo.
GEAR_RATIOS_BASE     = {1: 2.400, 2: 1.479, 3: 1.000, 4: 0.723, -1: 2.000}
GEAR_RATIOS_OPTIONAL = {1: 2.860, 2: 1.620, 3: 1.000, 4: 0.723, -1: 2.000}

# Estados de solenoide por marcha (Range Reference Chart del manual).
# El 1-2/3-4 es normalmente CERRADO; el 2-3 es normalmente ABIERTO.
#                   marcha: (1-2/3-4, 2-3)
SOLENOID_STATES = {
    "P-N": ("OFF", "ON"),
    "R":   ("OFF", "ON"),
    1:     ("OFF", "ON"),
    2:     ("ON",  "ON"),
    3:     ("ON",  "OFF"),
    4:     ("OFF", "OFF"),
}

# Lo que cada cambio le pide a los solenoides. Cruzado con el síntoma de este
# auto (1→2 anda, 2→3 y 3→4 fallan), los dos que fallan piden que un solenoide
# se APAGUE, y el único que anda pide que se PRENDA.
SHIFT_REQUIREMENTS = {
    "1-2": ("1-2/3-4", "energizar"),
    "2-3": ("2-3",     "desenergizar"),
    "3-4": ("1-2/3-4", "desenergizar"),
}

# Velocidad máxima de cambio permitida (convertidor de 245 mm): 6500 rpm en los
# tres cambios. Nuestra falla quedó a 3904 rpm, así que NO es la protección por
# sobre-régimen de cambio.
MAX_SHIFT_RPM = 6500


def match_gear(ratio: float, ratios: dict | None = None,
               tol: float = 0.06) -> tuple[int | None, str]:
    """¿A qué marcha corresponde una relación motor/salida?

    El convertidor de par siempre patina, así que la relación medida es SIEMPRE
    ≥ la relación mecánica. Por eso una lectura por encima de una marcha puede
    ser esa marcha patinando, mientras que una por debajo no puede serlo.

    Devuelve (marcha o None, explicación).
    """
    r = ratios or GEAR_RATIOS_OPTIONAL
    for g in (1, 2, 3, 4):
        if abs(ratio - r[g]) <= tol * r[g]:
            return g, f"coincide con {g}ª ({r[g]:.3f})"
    # Sin coincidencia: informar la marcha inmediatamente por debajo, que es la
    # candidata a estar patinando.
    below = [(g, r[g]) for g in (1, 2, 3, 4) if r[g] < ratio]
    if below:
        g, rr = max(below, key=lambda x: x[1])
        slip = (ratio / rr - 1) * 100
        return None, (f"ninguna marcha; la más cercana por debajo es {g}ª "
                      f"({rr:.3f}) con {slip:.0f}% de patinamiento")
    return None, "ninguna marcha; por debajo de la relación más corta"


# 3ª es 1.000 en AMBOS juegos de relaciones, así que es el punto de calibración
# perfecto: una lectura de ~1.00 confirma la escala Y que el convertidor está
# trabado. Cualquier desvío de 1.00 en 3ª es patinamiento puro del convertidor,
# medible, y sirve para corregir la lectura de las otras marchas.
CALIBRATION_NOTE = "3ª = 1.000 en ambos juegos: punto de calibración"
