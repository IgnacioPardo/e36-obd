"""Local instrument panel for the E36 DME.

Python stdlib plus pyserial only -- no framework, no CDN, nothing to install,
and it works with no internet.

The constraint that shapes all of this: the K-line is one serial port and only
one thing may own it. So exactly ONE thread ever touches serial. It maintains
the live session and, between samples, drains an action queue. HTTP handlers
never open the port -- they enqueue work and poll for the result. That is why
recording, fault reads, RAM dumps and the DS2 probe can coexist with live
polling without fighting over the device.

It is also useful with no car attached: captured CSV logs and saved fault
snapshots render fine offline, which is most of what you want when reviewing a
session afterwards.

Network exposure is opt-in and token-gated. Bound to localhost there is no
token; bound to the LAN so a phone can watch, every request must carry a
generated token. There is no user database here -- one shared secret, checked
in constant time, is the right weight for a tool on your own network.
"""

from __future__ import annotations

import csv
import glob
import hmac
import json
import logging
import os
import queue
import secrets
import socket
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .ds2 import COMMON_ADDRESSES as DS2_ADDRESSES
from .ds2 import DS2, DS2Error
from .egs import EGS_ADDRESS, EGS_BAUD, GEAR_RATIOS_BASE, GEAR_RATIOS_OPTIONAL
from .egs import decode as decode_egs
from .egs import match_gear
from .faults import decode as decode_faults
from .kline import KLine, KLineError
from .kwp71 import BlockType, KWP71Session
from .live import LiveReader
from .sensors import CORE_SENSORS, FINAL_DRIVE, ROAD_SPEED_SCALE, TYRE_CIRCUM_M
from .snapshot import Snapshot

log = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
MAX_EVENTS = 60
RAM_WINDOW = 252          # the largest single ReadRAM the ECU will answer


def stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def lan_ip() -> str:
    """Best guess at this machine's LAN address, for the QR-less phone case."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.1.1", 1))     # no packet is actually sent
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class Poller(threading.Thread):
    """The only thread that touches the serial port."""

    def __init__(self, port: str, address: int, interval: float, enabled: bool,
                 demo: bool = False, port_finder=None) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.port_finder = port_finder
        self.address = address
        self.interval = interval
        self.enabled = enabled
        self.demo = demo
        self._demo_t = 0.0

        self.lock = threading.Lock()
        self.actions: queue.Queue = queue.Queue()
        self._stop = threading.Event()

        self._reader: LiveReader | None = None
        self._csv_fh = None
        self._csv_writer = None
        self._rec_name = ""
        self._rec_started = 0.0
        self._rec_rows = 0
        self._last_raw_faults: bytes | None = None
        self._session_started = time.time()
        # Modo foco: el enlace no es de 1 Hz, es de 1 Hz PARA ONCE BYTES. KWP71
        # acusa cada byte con su inverso, así que el costo en cable es ~2× el
        # payload. Leyendo una sola dirección se sacan varios Hz, que es la
        # única palanca real sobre la resolución temporal.
        # A qué módulo apuntan las acciones de RAM y foco. El EGS vive en otra
        # dirección Y a otra velocidad, así que cambiar de objetivo obliga a
        # rearmar la sesión: no se pueden tener dos baudios en un puerto.
        self._target = "dme"
        # Vínculos de dirección para la vista de caja. Vacíos hasta que la
        # exploración de RAM encuentre dónde vive cada valor en el EGS; el resto
        # de la vista ya funciona y espera estos tres números.
        self._bindings: dict = self._load_bindings()
        self._speed_on = False
        self._alt_on = False          # alternar DME <-> EGS para leer la marcha
        self._alt_engine_secs = 20.0
        self._alt_next = 0.0
        self._alt_next_demo = 0.0     # mismo reloj, pero en tiempo de demo
        self._demo_gear = 0
        self._gear_state: dict | None = None
        self._trans_buf: list = []
        self._trans_seq = 0
        self._focus: dict | None = None
        self._focus_buf: list = []
        self._focus_seq = 0

        self.state: dict = {
            "connected": False,
            "status": "sin ECU" if enabled else "modo sin conexión",
            "live": None,
            "ecu_id": None,
            "faults": [],
            "faults_note": "",
            "recording": None,
            "events": [],
            "busy": "",
            "ds2": None,
            "egs": None,
            "ram": None,
            "uptime": 0,
            "samples": 0,
            "reconnects": 0,
            "focus": None,
            "target": "dme",
            "trans": None,
            "bindings": {},
            "speed_on": False,
            "drive": None,
            "alt": {"on": False, "engine_secs": 20.0},
            # Marcha REAL leída del EGS. Nunca puede ser simultánea con los
            # sensores del motor -- un cable, un hilo, dos velocidades -- así que
            # siempre viaja con su edad y el panel la muestra.
            "gear": None,
        }

    # ----------------------------------------------------------- publishing

    def publish(self, **kw) -> None:
        with self.lock:
            self.state.update(kw)

    def event(self, text: str, kind: str = "info") -> None:
        with self.lock:
            self.state["events"] = (
                [{"t": stamp(), "text": text, "kind": kind}] + self.state["events"]
            )[:MAX_EVENTS]

    def snapshot_state(self) -> dict:
        with self.lock:
            st = dict(self.state)
        st["uptime"] = int(time.time() - self._session_started)
        return st

    def submit(self, action: str, params: dict) -> None:
        self.actions.put((action, params))

    # ------------------------------------------------------------ main loop

    def run(self) -> None:
        while not self._stop.is_set():
            self._drain_actions()
            if self.demo:
                self._demo_tick()
                self._stop.wait(self.interval)
                continue
            if not self.enabled:
                self._offline_faults()
                self._stop.wait(0.4)
                continue
            try:
                self._session()
            except (KLineError, OSError) as exc:
                log.debug("session ended: %s", exc)
                self._teardown()
                self.publish(connected=False, live=None,
                             status=f"sin ECU ({type(exc).__name__})")
                self._offline_faults()
                self._stop.wait(5.0)

    def _resolve_port(self) -> str:
        """Re-look for the cable every attempt, so plugging it in later works."""
        if self.port and os.path.exists(self.port):
            return self.port
        found = self.port_finder() if self.port_finder else None
        if found and found != self.port:
            self.port = found
            self.event(f"cable detectado en {found}", "good")
        return self.port

    def _session(self) -> None:
        port = self._resolve_port()
        if not port:
            self.publish(connected=False, live=None, status="esperando el cable")
            self._offline_faults()
            self._stop.wait(3.0)
            return
        if self._target == "egs":
            self._egs_session(port)
            return
        self._reader = LiveReader(port, address=self.address, speed=self._speed_on)
        self._reader._open()
        session = self._reader._session
        ids = [s.decode("ascii", "replace").strip() for s in session.id_strings]
        self.publish(connected=True, status="conectada", ecu_id=ids,
                     target="dme")
        self.event(f"ECU conectada en 0x{self.address:02X}", "good")
        self._read_faults()

        count = 0
        t0 = time.monotonic()
        while not self._stop.is_set():
            self._drain_actions()
            if self._reader is None:          # an action tore the session down
                return
            if self._focus is not None:
                self._focus_tick()
                continue
            if self._alt_on and time.monotonic() >= self._alt_next:
                self._alt_next = time.monotonic() + self._alt_engine_secs
                self._read_gear_once(port)
                return            # el bucle principal rearma la sesión del DME
            sample = self._reader.sample()
            if sample is None:
                raise KLineError("se perdió la ECU")
            values = {s.name: round(s.scale(sample[s.name]), 3) for s in CORE_SENSORS}
            values["_raw"] = {s.name: sample[s.name] for s in CORE_SENSORS}
            values["_block"] = self._reader.last_block.hex()
            # Identidad de muestra. Sin esto el navegador, que consulta en su
            # propio reloj, no puede distinguir "llegó una muestra nueva" de
            # "sigo viendo la anterior" -- y durante una reconexión repetía el
            # valor viejo, dibujando una línea plana y confiada donde en
            # realidad no había datos.
            count += 1
            values["_seq"] = count
            values["_t"] = round(time.monotonic() - t0, 3)
            if "road_speed" in sample:
                values["speed_kmh"] = round(sample["road_speed"] * ROAD_SPEED_SCALE, 1)
            self.publish(connected=True, live=values, status="conectada",
                         samples=count, reconnects=self._reader.reconnects)
            self._write_row(values)
            self._stop.wait(self.interval)

    BINDINGS_FILE = "egs_bindings.json"
    TRANS_KEEP = 300

    def _load_bindings(self) -> dict:
        try:
            with open(self.BINDINGS_FILE) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _do_set_alternate(self, params: dict) -> None:
        """Alternar entre módulos para traer la marcha real cada tanto.

        No hay forma de tener ambos en vivo: cambiar de módulo cuesta ~5 s
        (2 s de bit-bang del init de 5 baudios + 2,6 s de bus en reposo que
        pide BMW), y el DME y el EGS comparten el hilo, así que tampoco sirve
        un segundo cable. La marcha va a llegar vieja; el panel lo dice.
        """
        self._alt_on = bool(params.get("on"))
        try:
            self._alt_engine_secs = max(5.0, float(params.get("engine_secs", 20)))
        except (TypeError, ValueError):
            self._alt_engine_secs = 20.0
        self._alt_next = time.monotonic() + self._alt_engine_secs
        self.publish(alt={"on": self._alt_on, "engine_secs": self._alt_engine_secs})
        self.event(
            f"alternancia {'activada' if self._alt_on else 'desactivada'}"
            + (f": {self._alt_engine_secs:.0f} s de motor entre lecturas de marcha"
               if self._alt_on else ""), "info")

    def _read_gear_once(self, port: str) -> None:
        """Una visita al EGS: leer la marcha y volver. Cuesta ~5 s de init."""
        b = self._bindings
        if "gear_addr" not in b and "status_addr" not in b:
            self.event("sin dirección de marcha vinculada: no se puede leer", "warn")
            self._alt_on = False
            self.publish(alt={"on": False, "engine_secs": self._alt_engine_secs})
            return
        addr = b.get("gear_addr", b.get("status_addr"))
        self._teardown()
        self.publish(status="leyendo marcha del EGS…")
        try:
            with KLine(port, baud=EGS_BAUD, timeout=1.5) as line:
                sess = KWP71Session(line)
                sess.connect(address=EGS_ADDRESS)
                val = sess.read_ram(addr, 1)[0]
                sess.disconnect()
        except (KLineError, OSError) as exc:
            self.event(f"lectura de marcha falló: {exc}", "bad")
            return
        self._gear_state = {"raw": val, "addr": addr, "at": time.time(),
                            "t": stamp()}
        self.publish(gear=self._gear_state)
        self.event(f"marcha del EGS: 0x{val:02X} desde 0x{addr:04X}", "good")

    def _do_set_speed(self, params: dict) -> None:
        """Enciende o apaga la lectura de velocidad.

        Cuesta un round trip extra por muestra, así que baja la tasa a la mitad.
        Se avisa, porque una tasa peor sin explicación parecería una falla.
        """
        self._speed_on = bool(params.get("on"))
        self.publish(speed_on=self._speed_on,
                     drive={"final": FINAL_DRIVE, "circum": TYRE_CIRCUM_M})
        self.event("velocidad de camino: "
                   + ("activadas — la tasa baja a la mitad" if self._speed_on
                      else "desactivadas"), "info")
        self._teardown()          # rearmar el lector con la opción nueva

    def _do_set_bindings(self, params: dict) -> None:
        """Guarda dónde vive cada valor en la RAM del EGS.

        Se persiste a disco: encontrar estas direcciones cuesta una sesión con
        el auto, así que perderlas al cerrar el panel sería inaceptable.
        """
        b = {}
        for k in ("rpm_addr", "out_addr", "status_addr", "gear_addr"):
            v = params.get(k)
            if v in (None, "", -1):
                continue
            try:
                b[k] = int(v)
            except (TypeError, ValueError):
                self.event(f"dirección inválida en {k}: {v!r}", "bad")
                return
        for k, default in (("rpm_scale", 32.0), ("out_scale", 32.0)):
            try:
                b[k] = float(params.get(k, default))
            except (TypeError, ValueError):
                b[k] = default
        b["ratios"] = params.get("ratios", "optional")
        self._bindings = b
        try:
            with open(self.BINDINGS_FILE, "w") as fh:
                json.dump(b, fh, indent=2)
        except OSError as exc:
            log.debug("no se pudieron guardar los vínculos: %s", exc)
        self.publish(bindings=b)
        self.event(f"vínculos de caja guardados: "
                   + ", ".join(f"{k}=0x{v:04X}" for k, v in b.items()
                               if k.endswith("_addr")), "good")

    def _trans_tick(self, session) -> None:
        """Una lectura de los valores vinculados, con relación y marcha."""
        b = self._bindings
        addrs = [b[k] for k in ("rpm_addr", "out_addr", "status_addr") if k in b]
        if not addrs:
            return
        lo, hi = min(addrs), max(addrs)
        span = hi - lo + 1
        if span > 32:                      # demasiado disperso: leer por separado
            vals = {}
            for k in ("rpm_addr", "out_addr", "status_addr"):
                if k in b:
                    vals[k] = session.read_ram(b[k], 1)[0]
        else:
            blk = session.read_ram(lo, span)
            vals = {k: blk[b[k] - lo] for k in
                    ("rpm_addr", "out_addr", "status_addr") if k in b}

        rpm = vals.get("rpm_addr", 0) * b.get("rpm_scale", 32.0)
        out = vals.get("out_addr", 0) * b.get("out_scale", 32.0)
        ratio = (rpm / out) if out else None
        ratios = (GEAR_RATIOS_BASE if b.get("ratios") == "base"
                  else GEAR_RATIOS_OPTIONAL)
        gear, why = match_gear(ratio, ratios) if ratio else (None, "sin velocidad de salida")

        self._trans_seq += 1
        now = time.monotonic()
        self._trans_buf.append({"t": round(now - self._trans_t0, 3),
                                "rpm": round(rpm), "out": round(out),
                                "ratio": round(ratio, 3) if ratio else None})
        if len(self._trans_buf) > self.TRANS_KEEP:
            del self._trans_buf[:len(self._trans_buf) - self.TRANS_KEEP]

        self.publish(trans={
            "seq": self._trans_seq, "raw": vals,
            "rpm": round(rpm), "out": round(out),
            "ratio": round(ratio, 3) if ratio else None,
            "gear": gear, "verdict": why,
            "status": vals.get("status_addr"),
            "ratios": {str(k): v for k, v in ratios.items() if k > 0},
            "samples": self._trans_buf[-240:],
        })

    def _egs_session(self, port: str) -> None:
        """Sesión dedicada al EGS: 0x6C a 4800.

        Con el objetivo en EGS no hay muestreo de sensores del motor -- son dos
        velocidades distintas y un solo puerto. El bucle mantiene la sesión viva
        y atiende acciones de RAM y foco contra la caja.
        """
        line = KLine(port, baud=EGS_BAUD, timeout=1.5)
        try:
            session = KWP71Session(line)
            kw = session.connect(address=EGS_ADDRESS)
            ids = [x.decode("ascii", "replace").strip() for x in session.id_strings]
            self.publish(connected=True, status=f"EGS 0x{EGS_ADDRESS:02X} @ {EGS_BAUD}",
                         ecu_id=ids, live=None, target="egs")
            self.event(f"objetivo EGS · keywords {' '.join(f'{b:02X}' for b in kw)}",
                       "good")

            # Un LiveReader falso: las acciones de RAM/foco usan _reader._session,
            # así que se les entrega esta sesión sin duplicar código.
            class _Holder:
                pass
            holder = _Holder()
            holder._session = session
            holder.last_block = b""
            holder.reconnects = 0
            holder.sample = lambda: None
            self._reader = holder
            self._trans_t0 = time.monotonic()
            self._trans_buf = []
            self.publish(bindings=self._bindings)

            while not self._stop.is_set() and self._target == "egs":
                self._drain_actions()
                if self._reader is None:
                    return
                if self._focus is not None:
                    self._focus_tick()
                    continue
                if any(k in self._bindings for k in
                       ("rpm_addr", "out_addr", "status_addr")):
                    self._trans_tick(session)
                    continue
                # Sin nada que hacer, un bloque vacío mantiene viva la sesión:
                # KWP71 se cae si el intercambio se detiene.
                session.keepalive()
                self._stop.wait(0.25)
        finally:
            self._reader = None
            line.close()
            if self._target != "egs":
                self.publish(target=self._target)

    def _do_set_target(self, params: dict) -> None:
        t = params.get("target")
        if t not in ("dme", "egs"):
            self.event(f"objetivo inválido: {t}", "bad")
            return
        if t == self._target:
            return
        self._target = t
        self._focus = None
        self.publish(focus=None, target=t, connected=False, live=None,
                     status=f"cambiando a {t.upper()}…")
        self._teardown()      # obliga a rearmar la sesión a la velocidad correcta
        self.event(f"objetivo -> {t.upper()}", "info")

    FOCUS_KEEP = 400          # muestras retenidas del lado del servidor

    def _focus_tick(self) -> None:
        """Una lectura corta, lo más seguido que el enlace permita.

        El navegador consulta a 1 Hz, así que el servidor guarda las muestras en
        un anillo y las entrega en lote: sin eso, muestrear rápido no serviría
        de nada porque el cliente vería una de cada cinco.
        """
        f = self._focus
        try:
            data = self._reader._session.read_ram(f["address"], f["length"])
        except KLineError as exc:
            self.event(f"foco perdido en 0x{f['address']:04X}: {exc}", "bad")
            self._focus = None
            self.publish(focus=None)
            raise
        now = time.monotonic()
        self._focus_seq += 1
        self._focus_buf.append({"t": round(now - f["t0"], 4), "v": list(data)})
        if len(self._focus_buf) > self.FOCUS_KEEP:
            del self._focus_buf[:len(self._focus_buf) - self.FOCUS_KEEP]

        # Publicar en lote, no por muestra: tomar el lock a varios Hz sería peor
        # que el ahorro.
        if now - f.get("published", 0) >= 0.35:
            f["published"] = now
            span = self._focus_buf[-1]["t"] - self._focus_buf[0]["t"]
            hz = (len(self._focus_buf) - 1) / span if span > 0 else 0
            self.publish(focus={
                "address": f["address"], "length": f["length"],
                "hz": round(hz, 2), "seq": self._focus_seq,
                "samples": self._focus_buf[-240:],
            })

    def _do_focus_start(self, params: dict) -> None:
        if self._reader is None and not self.demo:
            self.event("sin ECU: no se puede enfocar", "warn")
            return
        addr = int(params.get("address", 0))
        length = max(1, min(int(params.get("length", 1)), 8))
        self._focus = {"address": addr, "length": length,
                       "t0": time.monotonic(), "published": 0}
        self._focus_buf = []
        self._focus_seq = 0
        self.event(f"foco en 0x{addr:04X} ({length} byte/s) — muestreo máximo", "good")

    def _do_focus_stop(self, params: dict) -> None:
        if self._focus is None:
            return
        n = len(self._focus_buf)
        self._focus = None
        self.publish(focus=None)
        self.event(f"foco detenido ({n} muestras)", "info")

    def _teardown(self) -> None:
        if self._reader is not None:
            self._reader._close()
            self._reader = None

    # -------------------------------------------------------------- actions

    def _drain_actions(self) -> None:
        while True:
            try:
                action, params = self.actions.get_nowait()
            except queue.Empty:
                return
            handler = getattr(self, f"_do_{action}", None)
            if handler is None:
                self.event(f"acción desconocida: {action}", "bad")
                continue
            self.publish(busy=action)
            try:
                handler(params)
            except Exception as exc:                      # noqa: BLE001
                log.debug("action %s failed: %s", action, exc)
                self.event(f"{action} falló: {exc}", "bad")
            finally:
                self.publish(busy="")

    # --- recording ---------------------------------------------------------

    def _do_record_start(self, params: dict) -> None:
        if self._csv_writer is not None:
            self.event("ya se está grabando", "warn")
            return
        name = os.path.basename(params.get("name") or f"rec_{datetime.now():%Y%m%d-%H%M%S}.csv")
        if not name.endswith(".csv"):
            name += ".csv"
        self._csv_fh = open(name, "w", newline="")
        self._csv_writer = csv.writer(self._csv_fh)
        self._csv_writer.writerow(
            ["timestamp", "elapsed_s"] + [s.name for s in CORE_SENSORS])
        self._rec_name, self._rec_started, self._rec_rows = name, time.monotonic(), 0
        self.publish(recording={"name": name, "rows": 0})
        self.event(f"grabando en {name}", "good")

    def _do_record_stop(self, params: dict) -> None:
        if self._csv_writer is None:
            return
        self._csv_fh.close()
        self._csv_writer = self._csv_fh = None
        self.publish(recording=None)
        self.event(f"grabación detenida: {self._rec_name} ({self._rec_rows} muestras)", "good")

    def _write_row(self, values: dict) -> None:
        if self._csv_writer is None:
            return
        self._csv_writer.writerow(
            [datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
             f"{time.monotonic() - self._rec_started:.3f}"]
            + [values[s.name] for s in CORE_SENSORS])
        self._csv_fh.flush()
        self._rec_rows += 1
        self.publish(recording={"name": self._rec_name, "rows": self._rec_rows})

    # --- fault memory ------------------------------------------------------

    def _do_refresh_faults(self, params: dict) -> None:
        if self._reader is None:
            self.event("sin ECU: no se pueden releer fallas", "warn")
            return
        self._read_faults()

    def _read_faults(self) -> None:
        try:
            raw = b"".join(self._reader._session.read_fault_codes())
        except KLineError as exc:
            self.event(f"lectura de fallas falló: {exc}", "bad")
            return
        codes = decode_faults(raw)
        self._last_raw_faults = raw
        self.publish(faults=self._encode(codes), faults_note="leído de la ECU")
        self.event(f"{len(codes)} código(s) leídos de la ECU", "good")

    def _do_clear_faults(self, params: dict) -> None:
        """Erase stored codes. Destroys evidence, so it demands an explicit flag."""
        if self._reader is None:
            self.event("sin ECU: no se pueden borrar fallas", "warn")
            return
        if not params.get("confirm"):
            self.event("borrado cancelado: falta confirmación", "warn")
            return
        # Always snapshot first -- the counters are the only record of how often
        # each fault occurred, and clearing throws that away permanently.
        if self._last_raw_faults:
            self._save_snapshot(self._last_raw_faults, "auto, justo antes de borrar")
        try:
            self._reader._session.erase_fault_codes()
        except KLineError as exc:
            self.event(f"borrado falló: {exc}", "bad")
            return
        self.event("memoria de fallas borrada (snapshot guardado antes)", "warn")
        self._read_faults()

    def _do_snapshot(self, params: dict) -> None:
        if self._last_raw_faults is None:
            self.event("no hay lectura de fallas para guardar", "warn")
            return
        self._save_snapshot(self._last_raw_faults, params.get("note") or "manual")

    def _save_snapshot(self, raw: bytes, note: str) -> None:
        os.makedirs("snapshots", exist_ok=True)
        path = os.path.join("snapshots", f"{datetime.now():%Y%m%d-%H%M%S}.json")
        Snapshot.capture(raw, note=note).save(path)
        self.event(f"snapshot guardado: {path}", "good")

    # --- scanner -----------------------------------------------------------

    def _do_read_ram(self, params: dict) -> None:
        """Dump a window of ECU RAM for the address explorer."""
        if self._reader is None:
            self.event("sin ECU: no se puede leer RAM", "warn")
            return
        start = int(params.get("start", 0))
        length = max(1, min(int(params.get("length", 64)), RAM_WINDOW))
        try:
            data = self._reader._session.read_ram(start, length)
        except KLineError as exc:
            self.event(f"lectura de RAM 0x{start:04X} falló: {exc}", "bad")
            return
        self.publish(ram={"start": start, "length": len(data), "hex": data.hex(),
                          "t": stamp()})
        self.event(f"RAM 0x{start:04X}..0x{start+len(data)-1:04X} leída "
                   f"({len(data)} bytes)", "info")

    def _do_ds2_scan(self, params: dict) -> None:
        """Probe DS2 modules. Needs the port, so the KWP71 session steps aside.

        DS2 is 8E1 with no init and cannot share a session with the KWP71 DME,
        which is exactly why a 5-baud address sweep never found the gearbox.
        """
        self._teardown()
        self.publish(connected=False, live=None, status="buscando módulos DS2…")
        self.event("buscando módulos DS2 (EGS, ABS…)", "info")

        addrs = params.get("addresses") or DS2_ADDRESSES
        hits: list[dict] = []
        try:
            with DS2(self.port, timeout=1.0) as bus:
                for addr in addrs:
                    reply = bus.probe(addr)
                    if reply is None:
                        continue
                    text = reply.decode("ascii", "replace").strip()
                    entry = {"address": f"0x{addr:02X}", "id": text, "raw": reply.hex(" ")}
                    self.event(f"módulo en 0x{addr:02X}: {text or reply.hex(' ')}", "good")
                    try:
                        faults = bus.read_faults(addr)
                        entry["faults"] = faults.hex(" ")
                        self.event(f"  fallas 0x{addr:02X}: {faults.hex(' ')}", "info")
                    except DS2Error as exc:
                        self.event(f"  sin memoria de fallas en 0x{addr:02X}: {exc}", "warn")
                    hits.append(entry)
                    time.sleep(0.1)
        except Exception as exc:                          # noqa: BLE001
            self.event(f"escaneo DS2 falló: {exc}", "bad")

        if not hits:
            self.event("ningún módulo DS2 respondió", "warn")
        self.publish(ds2=hits)

    def _do_egs_read(self, params: dict) -> None:
        """Lee la computadora de la caja.

        El EGS habla KWP71 igual que el motor pero en 0x6C **a 4800 baudios**,
        así que necesita su propia sesión a otra velocidad: hay que bajar la del
        DME, hablar con la caja, y dejar que el bucle principal reconstruya la
        del motor después.
        """
        port = self._resolve_port()
        if not port:
            self.event("sin cable: no se puede leer el EGS", "warn")
            return

        self._teardown()
        self.publish(connected=False, live=None, status="leyendo el EGS…")
        self.event(f"conectando al EGS en 0x{EGS_ADDRESS:02X} a {EGS_BAUD} baudios", "info")

        out: dict = {"address": f"0x{EGS_ADDRESS:02X}", "baud": EGS_BAUD,
                     "id": [], "faults": [], "raw": "", "t": stamp()}
        try:
            with KLine(port, baud=EGS_BAUD, timeout=1.5) as line:
                session = KWP71Session(line)
                keywords = session.connect(address=EGS_ADDRESS)
                out["keywords"] = " ".join(f"{b:02X}" for b in keywords)
                out["id"] = [s.decode("ascii", "replace").strip()
                             for s in session.id_strings]
                self.event(f"EGS conectado · keywords {out['keywords']}", "good")
                raw = b"".join(session.read_fault_codes())
                out["raw"] = raw.hex(" ")
                codes = decode_egs(raw)
                out["faults"] = [{
                    "number": c.number, "description": c.description,
                    "condition": c.condition, "conditions": c.conditions,
                    "frequency": c.frequency, "rpm": c.rpm,
                    "output_rpm": c.output_rpm,
                    "ratio": round(c.ratio, 2) if c.ratio else None,
                    "temp_c": round(c.temp_c, 1),
                    "raw_rpm": c.rpm_raw, "raw_b3": c.b3_raw,
                } for c in codes]
                self.event(f"EGS: {len(codes)} código(s) — {raw.hex(' ') or 'memoria vacía'}",
                           "good" if codes else "info")
                session.disconnect()
        except KLineError as exc:
            self.event(f"lectura del EGS falló: {exc}", "bad")
            out["error"] = str(exc)
        except Exception as exc:                      # noqa: BLE001
            self.event(f"lectura del EGS falló: {exc}", "bad")
            out["error"] = str(exc)

        self.publish(egs=out)
        try:
            os.makedirs("snapshots", exist_ok=True)
            path = os.path.join("snapshots", f"egs-{datetime.now():%Y%m%d-%H%M%S}.json")
            with open(path, "w") as fh:
                json.dump(out, fh, indent=2, ensure_ascii=False)
            self.event(f"lectura del EGS guardada: {path}", "good")
        except OSError as exc:
            log.debug("no se pudo guardar la lectura del EGS: %s", exc)

    def _do_raw_block(self, params: dict) -> None:
        """Send an arbitrary KWP71 block. For probing undocumented commands."""
        if self._reader is None:
            self.event("sin ECU: no se puede enviar bloque", "warn")
            return
        try:
            title = int(params.get("title"), 0) if isinstance(params.get("title"), str) \
                else int(params.get("title"))
            payload = bytes(int(b, 16) for b in (params.get("payload") or []))
        except (TypeError, ValueError) as exc:
            self.event(f"bloque inválido: {exc}", "bad")
            return
        # Writes are out of scope for this tool by design.
        if title in (BlockType.WRITE_RAM, BlockType.WRITE_EEPROM,
                     BlockType.ACTIVATE_ACTUATOR):
            self.event(f"bloque 0x{title:02X} bloqueado: este panel no escribe "
                       f"ni acciona nada", "warn")
            return
        try:
            blocks = self._reader._session.command(title, payload)
        except KLineError as exc:
            self.event(f"bloque 0x{title:02X} falló: {exc}", "bad")
            return
        joined = b"".join(blocks)
        self.event(f"bloque 0x{title:02X} -> {joined.hex(' ') or '(sin datos)'}", "good")

    # ----------------------------------------------------------------- demo

    def _demo_tick(self) -> None:
        """Synthetic but physically plausible data, for working on the panel
        with no car attached. Values follow real behaviour: coolant warms
        asymptotically toward the thermostat, load tracks rpm, and a couple of
        RAM bytes wander so the change-detection in the explorer can be seen.
        """
        import math
        import random

        self._demo_t += self.interval
        t = self._demo_t

        # A throttle blip every ~40 s, decaying over a couple of seconds.
        phase = t % 40.0
        blip = max(0.0, 1.0 - phase / 2.5) if phase < 2.5 else 0.0
        rpm = 900 + 2600 * blip + random.uniform(-25, 25)
        # Newton cooling toward 92 C from a 20 C cold start.
        coolant = 92 - 72 * math.exp(-t / 240)
        iat = 24 + 6 * (1 - math.exp(-t / 400)) + random.uniform(-.4, .4)
        batt = 13.95 + 0.08 * math.sin(t / 7) - 0.35 * blip + random.uniform(-.03, .03)
        load = 2.75 + 4.2 * blip + random.uniform(-.06, .06)
        if blip == 0 and 2.5 <= phase < 4.5:      # overrun fuel cut after the blip
            load = 1.1 + random.uniform(-.05, .05)

        values = {"rpm": round(rpm, 0), "coolant_temp": round(coolant, 1),
                  "intake_air_temp": round(iat, 1), "battery": round(batt, 2),
                  "load": round(load, 2)}
        values["_seq"] = int(t / self.interval)
        values["_t"] = round(t, 3)

        # La alternancia con el EGS es imposible de ver sin auto, así que el
        # modo demo también la simula: un byte que cambia y una edad que crece.
        # El encabezado ya dice DEMO, así que no puede confundirse con un dato.
        if self._alt_on and t >= self._alt_next_demo:
            self._alt_next_demo = t + self._alt_engine_secs
            self._demo_gear = (self._demo_gear % 4) + 1
            self._gear_state = {"raw": self._demo_gear, "addr": None,
                                "at": time.time(), "t": stamp()}
            self.publish(gear=self._gear_state)
        self.publish(connected=True, status="demo", live=values,
                     ecu_id=["DEMO", "sin ECU real"],
                     samples=int(t / self.interval))
        self._write_row(values)

        # A RAM window where the known addresses carry the real scaled values
        # and two unknown bytes move with the throttle -- exactly the signature
        # the explorer is meant to catch.
        buf = bytearray(128)
        buf[0x36] = max(0, min(255, int(batt / 0.0681)))
        buf[0x37] = max(0, min(255, int((iat + 33.5) / 0.65)))
        buf[0x38] = max(0, min(255, int((coolant + 32.5) / 0.65)))
        buf[0x3C] = max(0, min(255, int(rpm / 10)))
        buf[0x40] = max(0, min(255, int(load / 0.05)))
        buf[0x2A] = int(30 + 200 * blip)                       # pretend TPS
        buf[0x51] = int(40 + 60 * math.sin(t / 11) + 60)       # pretend speed
        self.publish(ram={"start": 0, "length": len(buf), "hex": bytes(buf).hex(),
                          "t": stamp()})

        # En demo el foco simula un contacto de mariposa: cerrado en ralentí,
        # que se abre en el acelerón y vuelve a cerrar. Es lo que hay que cazar.
        if self._focus is not None:
            f = self._focus
            for k in range(6):                      # ~6 muestras por tick
                self._focus_seq += 1
                tt = t + k * (self.interval / 6)
                ph = tt % 40.0
                open_throttle = ph < 3.0
                # una caída intermitente de 250 ms cada ~20 s, que es el evento
                glitch = (tt % 20.0) < 0.25
                bit = 0 if (open_throttle or glitch) else 1
                self._focus_buf.append({"t": round(tt, 4),
                                        "v": [(bit << 4) | (0x0A if open_throttle else 0x02)]})
            if len(self._focus_buf) > self.FOCUS_KEEP:
                del self._focus_buf[:len(self._focus_buf) - self.FOCUS_KEEP]
            span = self._focus_buf[-1]["t"] - self._focus_buf[0]["t"]
            self.publish(focus={
                "address": f["address"], "length": f["length"],
                "hz": round((len(self._focus_buf) - 1) / span, 2) if span > 0 else 0,
                "seq": self._focus_seq, "samples": self._focus_buf[-240:]})

        # Demo de la vista de caja: acelera por 1ª y 2ª, y el 2→3 NO entra --
        # la relación se queda entre marchas, que es el síntoma de este auto.
        # Sirve para verificar la visualización sin el auto.
        if any(k in self._bindings for k in ("rpm_addr", "out_addr")):
            for k in range(4):
                tt = t + k * (self.interval / 4)
                ph = tt % 24.0
                if ph < 5:            g, out = 1, 200 + ph * 180
                elif ph < 11:         g, out = 2, 1100 + (ph - 5) * 160
                elif ph < 17:         g, out = None, 2060 + (ph - 11) * 30   # 2→3 falla
                else:                 g, out = 2, 2240 - (ph - 17) * 200
                base = {1: 2.86, 2: 1.62, None: 2.03}[g]
                rpm = out * base * (1.0 + 0.02 * math.sin(tt * 3))
                self._trans_seq += 1
                self._trans_buf.append({"t": round(tt, 3), "rpm": round(rpm),
                                        "out": round(out),
                                        "ratio": round(rpm / out, 3)})
            if len(self._trans_buf) > self.TRANS_KEEP:
                del self._trans_buf[:len(self._trans_buf) - self.TRANS_KEEP]
            last = self._trans_buf[-1]
            gear, why = match_gear(last["ratio"], GEAR_RATIOS_OPTIONAL)
            self.publish(trans={
                "seq": self._trans_seq, "raw": {},
                "rpm": last["rpm"], "out": last["out"], "ratio": last["ratio"],
                "gear": gear, "verdict": why,
                "status": 0x12 if gear == 2 else 0x30,
                "ratios": {str(k): v for k, v in GEAR_RATIOS_OPTIONAL.items() if k > 0},
                "samples": self._trans_buf[-240:]})
            self.publish(bindings=self._bindings)

        if self._demo_t <= self.interval:
            self.event("modo demo: datos sintéticos, sin ECU real", "warn")
            self._offline_faults()

    # -------------------------------------------------------------- offline

    def _offline_egs(self) -> None:
        """Recuperar la última lectura del EGS guardada, para verla sin el auto."""
        if self.state.get("egs"):
            return
        for path in sorted(glob.glob("snapshots/egs-*.json"), reverse=True):
            try:
                with open(path) as fh:
                    data = json.load(fh)
                if "faults" in data:
                    data["from_file"] = os.path.basename(path)
                    self.publish(egs=data)
                    return
            except (OSError, ValueError):
                continue

    def _offline_faults(self) -> None:
        self._offline_egs()
        if self.state.get("faults"):
            return
        files = sorted(glob.glob("snapshots/*.json")) + sorted(glob.glob("*.json"))
        for path in reversed(files):
            try:
                with open(path) as fh:
                    data = json.load(fh)
                if "codes" in data:
                    self.publish(faults=data["codes"],
                                 faults_note=f"de {os.path.basename(path)}")
                    return
            except (OSError, ValueError, KeyError):
                continue

    @staticmethod
    def _encode(codes) -> list[dict]:
        return [{
            "number": c.number, "description": c.description,
            "condition": c.condition, "conditions": c.conditions,
            "frequency": c.frequency, "rpm": c.rpm, "raw_rpm": c.rpm_raw,
            "raw_b3": c.volts_raw,
        } for c in codes]

    def stop(self) -> None:
        self._stop.set()
        self._do_record_stop({})


# --------------------------------------------------------------------- HTTP


def make_handler(poller: Poller, token: str | None):
    ALLOWED = {"record_start", "record_stop", "refresh_faults", "snapshot",
               "clear_faults", "ds2_scan", "read_ram", "raw_block",
               "focus_start", "focus_stop", "egs_read", "set_target",
               "set_bindings", "set_speed", "set_alternate"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "e36obd"

        def log_message(self, *args) -> None:
            pass

        # -- auth -----------------------------------------------------------

        def _authorised(self, query: dict) -> bool:
            """Constant-time token check. No token configured means localhost."""
            if token is None:
                return True
            supplied = (query.get("t") or [""])[0] \
                or (self.headers.get("X-Token") or "") \
                or self._cookie_token()
            return hmac.compare_digest(supplied, token)

        def _cookie_token(self) -> str:
            raw = self.headers.get("Cookie") or ""
            for part in raw.split(";"):
                k, _, v = part.strip().partition("=")
                if k == "e36t":
                    return v
            return ""

        def _deny(self) -> None:
            self.send_response(403)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("403 — token inválido o ausente\n".encode())

        # -- plumbing -------------------------------------------------------

        def _send(self, body: bytes, ctype: str, cookie: str | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie",
                                 f"e36t={cookie}; Path=/; SameSite=Strict")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj) -> None:
            self._send(json.dumps(obj).encode(), "application/json")

        # -- routes ---------------------------------------------------------

        def do_POST(self) -> None:
            route = urlparse(self.path)
            if not self._authorised(parse_qs(route.query)):
                return self._deny()
            if route.path != "/api/action":
                return self.send_error(404)
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json({"ok": False, "error": "json inválido"})
            action = body.get("action", "")
            if action not in ALLOWED:
                return self._json({"ok": False, "error": f"acción no permitida: {action}"})
            poller.submit(action, body.get("params") or {})
            self._json({"ok": True, "queued": action})

        def do_GET(self) -> None:
            route = urlparse(self.path)
            query = parse_qs(route.query)
            if not self._authorised(query):
                return self._deny()

            if route.path in ("/", "/index.html"):
                path = os.path.join(STATIC_DIR, "dashboard.html")
                with open(path, "rb") as fh:
                    # Hand the token back as a cookie so deep links keep working
                    # without pasting ?t= on every request.
                    self._send(fh.read(), "text/html; charset=utf-8",
                               cookie=(query.get("t") or [None])[0] if token else None)

            elif route.path == "/api/state":
                self._json(poller.snapshot_state())

            elif route.path == "/api/logs":
                out = []
                for name in sorted(glob.glob("*.csv"), reverse=True):
                    try:
                        st = os.stat(name)
                        out.append({"name": name, "size": st.st_size,
                                    "mtime": int(st.st_mtime)})
                    except OSError:
                        continue
                self._json(out)

            elif route.path == "/api/log":
                name = (query.get("name") or [""])[0]
                # Only CSVs in the working directory -- no traversal.
                if not name or os.path.basename(name) != name or not name.endswith(".csv"):
                    return self._json([])
                try:
                    with open(name, newline="") as fh:
                        self._json(list(csv.DictReader(fh)))
                except OSError:
                    self._json([])

            elif route.path == "/api/snapshots":
                out = []
                # SOLO snapshots del DME. Los del EGS (egs-*.json) usan otra tabla
                # de códigos y compararlos contra los del motor daría un resultado
                # que parece válido y es basura -- el 100 significa cosas distintas
                # en cada módulo.
                paths = [p for p in glob.glob("snapshots/*.json")
                         if not os.path.basename(p).startswith("egs-")]
                for path in sorted(paths, reverse=True):
                    try:
                        with open(path) as fh:
                            data = json.load(fh)
                        out.append({"file": os.path.basename(path),
                                    "taken_at": data.get("taken_at", ""),
                                    "note": data.get("note", ""),
                                    "codes": data.get("codes", [])})
                    except (OSError, ValueError):
                        continue
                self._json(out)

            elif route.path == "/api/sensors":
                self._json([{ "key": s.name, "unit": s.unit,
                              "address": f"0x{s.address:04X}" } for s in CORE_SENSORS])
            else:
                self.send_error(404)

    return Handler


def serve(port: str, http_port: int = 8036, address: int = 0x10,
          interval: float = 1.0, live: bool = True, lan: bool = False,
          demo: bool = False, port_finder=None) -> None:
    token = secrets.token_urlsafe(16) if lan else None
    bind = "0.0.0.0" if lan else "127.0.0.1"

    poller = Poller(port, address, interval, enabled=live, demo=demo,
                    port_finder=port_finder)
    poller.start()
    server = ThreadingHTTPServer((bind, http_port), make_handler(poller, token))

    print()
    if lan:
        print(f"  Local:   http://127.0.0.1:{http_port}/?t={token}")
        print(f"  Red:     http://{lan_ip()}:{http_port}/?t={token}")
        print( "           (protegido por token; cualquiera en tu red que")
        print( "            tenga el link puede ver y operar el panel)")
    else:
        print(f"  Panel:   http://127.0.0.1:{http_port}")
    print(f"  ECU:     {'DEMO (datos sintéticos)' if demo else (('polling ' + port if port else 'esperando el cable') if live else 'desactivado (--no-live)')}")
    print( "  Ctrl-C para salir\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ncerrando…")
    finally:
        poller.stop()
        server.server_close()
