"""Fault code decoding for BMW DME M1.7 / M1.7.1 / M1.7.2 / M3.1 / M3.3.

Each stored code arrives as a 5-byte record:

    [0] fault code number (decimal)
    [1] condition bitfield -- see CONDITION_BITS
    [2] engine RPM at time of fault, x40
    [3] battery volts at time of fault, x0.0681
    [4] error frequency (how many times it has occurred)

Caveat on bytes 2-4: the source that documents this format also annotates byte 3
as doing double duty as a temperature reading in some captures (0x40 = 0 C,
0x60 = 24 C, 0x80 = 48 C, 0xA0 = 72 C). The freeze-frame fields are therefore
not fully pinned down, and implausible values there should be treated as a
decoding gap rather than as a real reading. Byte 0, the code number, is solid.
"""

from __future__ import annotations

# Code numbers are decimal. Entries flagged for a specific DME variant are noted
# inline, because several numbers are reused across the DME family.
FAULT_CODES: dict[int, str] = {
    1: "Fuel pump relay (EKP) or RPM signal",
    2: "Idle-speed controller",
    3: "Injectors (4cyl: 1,3)",
    4: "Injectors (DME 3.3.1 cyl 4,6)",
    5: "Injectors (DME 3.3.1 cyl 3,5)",
    6: "Injectors -- general",
    7: "VANOS relay, or injector cyl 6 (DME 1.7.2)",
    8: '"CHECK ENGINE" light failure (US models)',
    12: "Throttle position sensor (TPS); lambda sensor on M3.3.1",
    13: "Lambda probe",
    15: "Knock sensor 1 (1.7 / 3.1), or ignition fault (1.7.2)",
    16: "Ignition system, or cam/crank position sensor",
    17: "Camshaft position sensor",
    18: "DISA changeover valve (1.7.2)",
    19: "Electric fan output stage",
    20: "Cruise control",
    26: "Voltage supply",
    29: "Idle-speed controller / idle actuator",
    32: "Injectors (4cyl: 2,4)",
    36: "EVAP / tank-ventilation canister valve",
    37: "Oxygen-sensor heater relay",
    38: "Lambda heater relay",
    41: "Air mass flow sensor (AFM/MAF)",
    42: "Speed signal, or knock sensor 2 (1.7.x / 3.3.1)",
    46: "Electric fan",
    48: "A/C compressor shut-off",
    54: "Control-unit voltage supply B+",
    55: "Ignition (final stage)",
    63: "Torque-converter lockup clutch",
    64: "EGS->DME connection / ignition timing intervention",
    70: "Oxygen sensor (1.7.x / 3.1)",
    73: "Vehicle speed signal (VSS), or TPS",
    76: "Idle CO potentiometer / CO adjust",
    77: "Intake air temperature sensor",
    78: "Engine coolant temperature sensor",
    82: "MSR engine drag torque, or A/C compressor (1.7.2)",
    83: "ASC (EML)",
    100: "Amplifier/output stage 1 in DME",
    101: "Amplifier/output stage 2 in DME",
    200: "DME control unit",
    201: "Lambda regulation",
    202: "Control unit",
    255: "Control unit -- internal error",
}

# Several bits may be set at once.
CONDITION_BITS: list[tuple[int, str]] = [
    (0x01, "short to B+"),
    (0x02, "short to ground"),
    (0x04, "not allowed"),
    (0x08, "invalid working area"),
    (0x10, "exhaust-gas relevant"),
    (0x20, "stored after re-bouncing delay"),
    (0x40, "error present now (not historic)"),
    (0x80, "sporadic error"),
]

RPM_SCALE = 40
VOLTS_SCALE = 0.0681


class FaultCode:
    """One decoded fault record."""

    __slots__ = ("number", "condition", "rpm_raw", "volts_raw", "frequency")

    def __init__(self, record: bytes) -> None:
        if len(record) != 5:
            raise ValueError(f"fault record must be 5 bytes, got {len(record)}")
        self.number = record[0]
        self.condition = record[1]
        self.rpm_raw = record[2]
        self.volts_raw = record[3]
        self.frequency = record[4]

    @property
    def description(self) -> str:
        return FAULT_CODES.get(self.number, "unknown code -- not in the M1.7.x table")

    @property
    def conditions(self) -> list[str]:
        """Decode the condition bitfield. Empty bitfield means a static error."""
        if self.condition == 0x00:
            return ["open circuit / error not present / static error"]
        return [name for bit, name in CONDITION_BITS if self.condition & bit]

    @property
    def rpm(self) -> int:
        return self.rpm_raw * RPM_SCALE

    @property
    def volts(self) -> float:
        return self.volts_raw * VOLTS_SCALE

    def format(self) -> str:
        lines = [
            f"  Code {self.number}: {self.description}",
            f"    condition 0x{self.condition:02X}: {', '.join(self.conditions)}",
            f"    occurrences: {self.frequency}",
            f"    freeze frame (unverified scaling): "
            f"{self.rpm} rpm, {self.volts:.1f} V"
            f"   [raw {self.rpm_raw:02X} {self.volts_raw:02X}]",
        ]
        return "\n".join(lines)


def decode(data: bytes) -> list[FaultCode]:
    """Split a fault-code payload into 5-byte records and decode each.

    A trailing partial record is ignored rather than raising, so that an
    unexpected payload length still yields whatever codes could be read.
    """
    return [FaultCode(data[i : i + 5]) for i in range(0, len(data) - 4, 5)]
