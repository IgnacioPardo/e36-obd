"""Resilient live-value polling.

Reading while the engine runs is materially harder than reading with the
ignition merely on: ignition noise on the K-line corrupts the byte-level
handshake, and KWP71 has no error recovery -- one bad byte and the session is
finished. Observed behaviour on an M43B16 was a clean 252-byte read with the
engine off, and a session that died a few blocks in at idle.

So rather than nursing one long session, this reconnects around failures. A
dropped session costs about three seconds to rebuild, which is cheap compared
with losing the whole logging run.
"""

from __future__ import annotations

import logging
import time

from .kline import KLine, KLineError
from .kwp71 import KWP71Session
from .sensors import (CORE_LENGTH, CORE_SENSORS, CORE_START, EXTRA_SENSORS,
                      ROAD_SPEED_ADDR, ROAD_SPEED_SCALE, Sensor)

log = logging.getLogger(__name__)


class LiveReader:
    """Polls sensor values, rebuilding the session whenever it breaks."""

    def __init__(
        self,
        port: str,
        address: int = 0x10,
        timeout: float = 2.0,
        extras: bool = False,
        max_reconnects: int = 5,
        speed: bool = False,
    ) -> None:
        self.port = port
        self.address = address
        self.timeout = timeout
        self.extras = extras
        # Leer la velocidad cuesta un round trip extra porque vive fuera del
        # bloque contiguo. Opcional para no bajar la tasa sin querer.
        self.speed = speed
        self.max_reconnects = max_reconnects
        self._line: KLine | None = None
        self._session: KWP71Session | None = None
        self.reconnects = 0
        self.last_block: bytes = b""      # bloque crudo completo de la última lectura

    # ------------------------------------------------------------- session

    def _open(self) -> None:
        self._close()
        self._line = KLine(self.port, timeout=self.timeout)
        self._session = KWP71Session(self._line)
        self._session.connect(address=self.address)

    def _close(self) -> None:
        if self._session is not None:
            try:
                self._session.disconnect()
            except KLineError:
                pass
            self._session = None
        if self._line is not None:
            self._line.close()
            self._line = None

    def __enter__(self) -> "LiveReader":
        self._open()
        return self

    def __exit__(self, *exc: object) -> None:
        self._close()

    # -------------------------------------------------------------- polling

    @property
    def sensors(self) -> list[Sensor]:
        return CORE_SENSORS + (EXTRA_SENSORS if self.extras else [])

    def _sample_once(self) -> dict[str, int]:
        """One pass over the sensors. Raises KLineError if the session breaks."""
        assert self._session is not None
        raw: dict[str, int] = {}

        # The core block is one contiguous read -- one round trip, not five.
        block = self._session.read_ram(CORE_START, CORE_LENGTH)
        if len(block) != CORE_LENGTH:
            raise KLineError(f"core block short read: {len(block)}/{CORE_LENGTH}")
        # Guardar el bloque entero: seis bytes (0x39, 0x3A, 0x3B, 0x3D, 0x3E,
        # 0x3F) viajan en cada lectura y se descartaban. Son gratis y pueden
        # contener el byte alto de rpm, que es lo que limita la escala a 2550.
        self.last_block = block
        for sensor in CORE_SENSORS:
            raw[sensor.name] = block[sensor.address - CORE_START]

        if self.speed:
            data = self._session.read_ram(ROAD_SPEED_ADDR, 1)
            if not data:
                raise KLineError(f"lectura vacía en 0x{ROAD_SPEED_ADDR:04X}")
            raw["road_speed"] = data[0]

        if self.extras:
            for sensor in EXTRA_SENSORS:
                data = self._session.read_ram(sensor.address, 1)
                if not data:
                    raise KLineError(f"empty read at 0x{sensor.address:04X}")
                raw[sensor.name] = data[0]

        return raw

    def sample(self) -> dict[str, int] | None:
        """One sample, reconnecting on failure. None if it could not recover."""
        for attempt in range(self.max_reconnects + 1):
            try:
                return self._sample_once()
            except KLineError as exc:
                if attempt >= self.max_reconnects:
                    log.error("giving up after %d reconnects: %s", attempt, exc)
                    return None
                self.reconnects += 1
                log.debug("session lost (%s); reconnecting", exc)
                time.sleep(0.3)
                try:
                    self._open()
                except KLineError as reconnect_exc:
                    log.debug("reconnect failed: %s", reconnect_exc)
                    time.sleep(0.7)
        return None
