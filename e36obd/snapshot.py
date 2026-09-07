"""Fault-code snapshots and differencing.

Polling live values over KWP71 tops out around 1 Hz because every sample costs
a full command/response round trip at 9600 baud. That is far too slow to catch
a sensor dropout lasting a few hundred milliseconds.

The DME, however, counts occurrences internally at its own rate: each stored
fault carries a frequency byte. So instead of trying to witness the dropout, we
snapshot the fault memory before and after a drive and compare the counters. A
code whose count rose during a drive where the symptom appeared is strong
correlating evidence -- and it costs two reads rather than a high-rate capture.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .faults import FaultCode, decode


@dataclass
class Snapshot:
    """Fault memory at a point in time."""

    taken_at: str
    raw: str
    note: str = ""
    codes: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def capture(cls, data: bytes, note: str = "") -> "Snapshot":
        return cls(
            taken_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            raw=data.hex(),
            note=note,
            codes=[
                {
                    "number": c.number,
                    "description": c.description,
                    "condition": c.condition,
                    "conditions": c.conditions,
                    "frequency": c.frequency,
                    "rpm": c.rpm,
                    "volts": round(c.volts, 2),
                    # Crudos del freeze frame. El contador satura (visto en 50),
                    # pero el freeze frame se sigue actualizando en cada
                    # ocurrencia -- así que con el contador clavado sigue siendo
                    # la única evidencia de que la falla volvió a pasar.
                    "raw_rpm": c.rpm_raw,
                    "raw_b3": c.volts_raw,
                }
                for c in decode(data)
            ],
        )

    def save(self, path: str) -> None:
        with open(path, "w") as fh:
            json.dump(self.__dict__, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "Snapshot":
        with open(path) as fh:
            return cls(**json.load(fh))

    def by_number(self) -> dict[int, dict[str, Any]]:
        return {c["number"]: c for c in self.codes}


def diff(before: Snapshot, after: Snapshot) -> list[str]:
    """Human-readable comparison of two snapshots.

    Reports codes that appeared, disappeared, whose occurrence counter moved,
    or -- crucially -- whose freeze frame moved while the counter stayed put.
    The counter saturates (50 observed on this DME), so on a pegged code the
    freeze frame is the only remaining evidence that it happened again.
    """
    lines: list[str] = []
    a, b = before.by_number(), after.by_number()

    for number in sorted(set(a) | set(b)):
        old, new = a.get(number), b.get(number)

        if old is None:
            lines.append(
                f"  NEW      code {number}: {new['description']}\n"
                f"           first seen, count {new['frequency']}"
            )
        elif new is None:
            lines.append(
                f"  GONE     code {number}: {old['description']}\n"
                f"           was count {old['frequency']}, now absent "
                f"(aged out, displaced, or cleared)"
            )
        elif new["frequency"] != old["frequency"]:
            delta = new["frequency"] - old["frequency"]
            arrow = "+" if delta > 0 else ""
            lines.append(
                f"  CHANGED  code {number}: {new['description']}\n"
                f"           count {old['frequency']} -> {new['frequency']} ({arrow}{delta})"
                + ("   <-- RE-OCCURRED" if delta > 0 else "")
            )
        else:
            moved = [
                (k, old.get(k), new.get(k))
                for k in ("raw_rpm", "raw_b3")
                if old.get(k) is not None and old.get(k) != new.get(k)
            ]
            if moved:
                detail = ", ".join(f"{k} {o}->{n}" for k, o, n in moved)
                lines.append(
                    f"  CHANGED  code {number}: {new['description']}\n"
                    f"           count pegged at {new['frequency']}, but the freeze "
                    f"frame moved ({detail})\n"
                    f"           <-- RE-OCCURRED (counter saturated, frame is the evidence)"
                )

    if not lines:
        lines.append("  no change -- no stored fault re-occurred between snapshots")
    return lines
