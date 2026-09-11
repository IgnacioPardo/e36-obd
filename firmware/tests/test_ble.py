"""Host tests of the actual MicroPython BLE module; never access a serial port."""
import sys
import types
import unittest
from itertools import count
from pathlib import Path
from unittest.mock import patch


class BLEContractTests(unittest.TestCase):
    def setUp(self):
        bluetooth = types.ModuleType("bluetooth")
        bluetooth.UUID = lambda value: value
        bluetooth.FLAG_WRITE = 8
        bluetooth.FLAG_NOTIFY = 16
        self.kline = types.ModuleType("kline")
        self.kline.READ_FAULTS = 7
        self.kline.DISCONNECT = 6
        self.kline.NOMBRES = {}
        self.kline.conectar = lambda **kwargs: None
        self.kline.command = lambda command: [bytes([100, 0x68, 0, 0, 50])]
        self.kline.send_block = lambda title: None
        self.kline.desconectar = lambda: self.kline.send_block(self.kline.DISCONNECT)
        self.kline.keepalive = lambda: None
        scope = {}
        source = Path(__file__).resolve().parents[1] / "mp" / "ble.py"
        with patch.dict(sys.modules, {"bluetooth": bluetooth, "kline": self.kline}):
            exec(compile(source.read_text(), str(source), "exec"), scope)
        clock = count(0, 341)
        scope["time"] = types.SimpleNamespace(ticks_ms=lambda: next(clock), ticks_diff=lambda a, b: a-b, sleep_ms=lambda ms: None)
        self.scope = scope
        self.panel = scope["Panel"].__new__(scope["Panel"])
        self.panel._conn = 1
        self.panel._cmd = None
        self.panel._vivo = False
        self.panel._sesion = False

    def test_appends_intake_without_another_read(self):
        calls = []
        lines = []

        def read():
            calls.append(True)
            self.panel._cmd = "s"
            return dict(rpm=930, carga=.7, refrig=63.1, bateria=13.48, aire=23.7)

        self.kline.leer_core = read
        self.panel.enviar = lines.append
        self.panel.vivo()
        data = next(line for line in lines if line.startswith("D "))
        self.assertEqual(data, "D 930 0.70 63.1 13.48 341 23.7")
        self.assertEqual(data.split()[:6], "D 930 0.70 63.1 13.48 341".split())
        self.assertEqual(len(calls), 1)
        self.assertEqual(lines[-1], "detenido (1 muestras)")

    def test_notifications_remain_at_most_twenty_bytes(self):
        chunks = []
        self.panel._tx = 3
        self.panel._ble = types.SimpleNamespace(gatts_notify=lambda conn, handle, data: chunks.append(data))
        text = "Tensión y temperatura: áéíóú · " * 5
        self.panel.enviar(text)
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))
        self.assertEqual(b"".join(chunks).decode(), text + "\r\n")

    def test_help_is_queued_after_faults_start_even_on_error(self):
        for fail in [False, True]:
            lines = []

            def send(line):
                lines.append(line)
                if line == "abriendo sesion...":
                    self.panel._cmd = "?"

            def command(_):
                if fail:
                    raise OSError("sin respuesta")
                return [bytes([100, 0x68, 0, 0, 50])]

            self.panel.enviar = send
            self.kline.command = command
            self.panel.fallas()
            self.assertEqual(self.panel._cmd, "?")
            self.panel._cmd = None
            self.panel.ayuda()
            self.assertEqual(lines[-1], "?  esta ayuda")
            self.assertTrue(any(line.startswith("error:") if fail else line.startswith("cod 100") for line in lines))

    def test_advertises_name_not_service(self):
        packet = self.scope["_publicidad"]("E36-OBD")
        self.assertIn(b"E36-OBD", packet)
        self.assertLessEqual(len(packet), 31)

    def test_live_faults_live_closes_dme_before_each_new_handshake(self):
        # Reproduce the physical DME rejecting a wake-up over an open session.
        connected = False
        operations, lines = [], []

        def connect(**kwargs):
            nonlocal connected
            if connected:
                raise OSError("sin respuesta de la ECU")
            connected = True
            operations.append("open")

        def close(title):
            nonlocal connected
            self.assertEqual(title, self.kline.DISCONNECT)
            self.assertTrue(connected)
            connected = False
            operations.append("close")

        def read():
            self.assertTrue(connected)
            operations.append("sample")
            self.panel._cmd = "f"
            return dict(rpm=930, carga=.7, refrig=63.1, bateria=13.48, aire=23.7)

        def faults(title):
            self.assertTrue(connected)
            self.assertEqual(title, self.kline.READ_FAULTS)
            self.panel._cmd = "?"
            operations.append("faults")
            return [bytes([100, 0x68, 0, 0, 50, 36, 0x72, 0, 0, 50])]

        def send(line):
            if line.startswith("detenido (") or line == "?  esta ayuda":
                self.assertFalse(connected)
            lines.append(line)

        self.kline.conectar, self.kline.send_block = connect, close
        self.kline.leer_core, self.kline.command = read, faults
        self.panel.enviar = send
        for _ in range(3):
            self.panel._cmd = None
            self.panel.vivo()
            self.assertEqual(self.panel._cmd, "f")
            self.panel._cmd = None  # the worker consumes the pending command
            self.panel.fallas()
            self.assertEqual(self.panel._cmd, "?")
            self.panel._cmd = None
            self.panel.ayuda()
        self.assertEqual(operations, ["open", "sample", "close", "open", "faults", "close"] * 3)
        self.assertEqual(lines.count("cod 100  ocurr 50"), 3)
        self.assertEqual(lines.count("cod 36  ocurr 50"), 3)
        self.assertEqual(lines.count("detenido (1 muestras)"), 3)
        self.assertFalse(any(line.startswith("error:") for line in lines))

    def test_failed_open_is_not_closed_but_failed_reads_get_desktop_cleanup(self):
        def fail(*args, **kwargs):
            raise OSError("sin respuesta de la ECU")

        for operation, stage in [("vivo", "conectar"), ("fallas", "conectar"),
                                 ("vivo", "leer_core"), ("fallas", "command")]:
            with self.subTest(operation=operation, stage=stage):
                self.setUp()
                lines, writes = [], []
                self.panel.enviar = lines.append
                self.kline.send_block = writes.append
                setattr(self.kline, stage, fail)
                getattr(self.panel, operation)()
                expected = [] if stage == "conectar" else [self.kline.DISCONNECT] * (6 if operation == "vivo" else 1)
                self.assertEqual(writes, expected)
                self.assertFalse(self.panel._sesion)
                self.assertTrue(any("sin respuesta de la ECU" in line for line in lines))

    def test_failed_close_preserves_fault_result_and_queued_help(self):
        writes, lines = [], []

        def close(title):
            writes.append(title)
            raise OSError("no disconnect acknowledgement")

        def send(line):
            lines.append(line)
            if line == "abriendo sesion...":
                self.panel._cmd = "?"

        self.kline.send_block = close
        self.panel.enviar = send
        self.panel.fallas()
        self.assertEqual(self.panel._cmd, "?")
        self.assertFalse(self.panel._sesion)
        self.assertIn("cod 100  ocurr 50", lines)
        self.assertFalse(any(line.startswith("error:") for line in lines))
        self.panel._cmd = None
        self.panel.ayuda()
        self.panel.fallas()
        self.assertEqual(writes, [self.kline.DISCONNECT, self.kline.DISCONNECT])

    def test_ble_loss_closes_session_in_worker_after_inflight_sample(self):
        writes, lines = [], []
        self.kline.send_block = writes.append
        self.panel.enviar = lines.append
        self.panel._anunciar = lambda: None

        def read():
            self.panel._irq(self.scope["_IRQ_DISCONNECT"], ())
            self.assertFalse(writes)  # no K-line operations from the IRQ
            return dict(rpm=930, carga=.7, refrig=63.1, bateria=13.48, aire=23.7)

        self.kline.leer_core = read
        self.panel.vivo()
        self.assertEqual(writes, [self.kline.DISCONNECT])
        self.assertFalse(self.panel._sesion)
        self.assertFalse(self.panel._vivo)
        self.assertEqual(lines[-1], "detenido (1 muestras)")

    def test_live_recovers_ecu_without_ending_ble_capture(self):
        lines, operations = [], []
        connected = False
        opens = samples = 0
        failures = {38, 40}
        self.panel.enviar = lines.append

        def connect(**kwargs):
            nonlocal connected, opens
            self.assertFalse(connected)  # old ECU session must be closed first
            opens += 1
            operations.append("open")
            if opens == 2:
                raise OSError("no sync")
            connected = True

        def close():
            nonlocal connected
            self.assertTrue(connected)
            connected = False
            operations.append("close")

        def read():
            nonlocal samples
            self.assertTrue(connected)
            if samples in failures:
                failures.remove(samples)
                raise OSError("sin respuesta de la ECU")
            samples += 1
            if samples == 600:
                self.panel._cmd = "s"
            return dict(rpm=1490, carga=3, refrig=63.1, bateria=13.48, aire=23.7)

        self.kline.conectar, self.kline.desconectar, self.kline.leer_core = connect, close, read
        self.panel.vivo()
        self.assertEqual(sum(line.startswith("D ") for line in lines), 600)
        self.assertEqual(sum(line.startswith("recuperando DME (") for line in lines), 3)
        self.assertEqual(lines.count("en vivo. cualquier tecla corta."), 3)
        self.assertEqual(lines[-1], "detenido (600 muestras)")
        self.assertFalse(any(line.startswith(("se corto:", "error:")) for line in lines))
        self.assertEqual(self.panel._conn, 1)
        self.assertEqual(self.panel._cmd, "s")
        self.assertEqual(operations, ["open", "close", "open", "open", "close", "open", "close"])

    def test_stop_faults_and_ble_loss_cancel_recovery_wait(self):
        for command in ("s", "f", None):
            with self.subTest(command=command):
                self.setUp()
                calls, lines = [], []
                self.panel.enviar = lines.append
                self.kline.conectar = lambda **kwargs: calls.append("open")
                self.kline.desconectar = lambda: calls.append("close")

                def fail():
                    raise OSError("missing byte")

                def cancel(ms):
                    self.assertEqual(ms, 50)
                    if command:
                        self.panel._cmd = command
                    else:
                        self.panel._conn = None
                        self.panel._vivo = False

                self.kline.leer_core = fail
                self.scope["time"].sleep_ms = cancel
                self.panel.vivo()
                self.assertEqual(calls, ["open", "close"])
                self.assertEqual(self.panel._cmd, command)
                self.assertFalse(self.panel._vivo)
                self.assertEqual(lines[-1], "detenido (0 muestras)")

    def test_live_paces_ram_reads_with_keepalives_and_excludes_wait_from_ecu_ms(self):
        clock = [0]
        queries, nops, lines, sleeps = [], [], [], []

        def sleep(ms):
            sleeps.append(ms)
            clock[0] += ms

        self.scope['time'] = types.SimpleNamespace(
            ticks_ms=lambda: clock[0], ticks_diff=lambda a, b: a-b, sleep_ms=sleep)

        def read():
            queries.append(clock[0])
            clock[0] += 400
            if len(queries) == 40:
                self.panel._cmd = 's'
            return dict(rpm=1490, carga=3, refrig=63.1, bateria=13.48, aire=23.7)

        def nop():
            nops.append(clock[0])
            clock[0] += 80

        def send(line):
            lines.append(line)
            clock[0] += 24  # two BLE notifications, outside the ECU query

        self.kline.leer_core, self.kline.keepalive = read, nop
        self.panel.enviar = send
        self.panel.vivo()
        self.assertEqual(len(queries), 40)
        self.assertTrue(all(750 <= b-a < 900 for a, b in zip(queries, queries[1:])))
        self.assertTrue(all(any(a < n < b for n in nops) for a, b in zip(queries, queries[1:])))
        self.assertLessEqual(max(sleeps), 25)
        self.assertTrue(all(line.split()[5] == '400' for line in lines if line.startswith('D ')))
        self.assertEqual(lines[-1], 'detenido (40 muestras)')

    def test_keepalive_failure_recovers_before_another_ram_read(self):
        operations, lines = [], []
        self.panel.enviar = lines.append
        self.kline.conectar = lambda **kwargs: operations.append('open')
        self.kline.desconectar = lambda: operations.append('close')

        def read():
            operations.append('read')
            if operations.count('read') == 2:
                self.panel._cmd = 's'
            return dict(rpm=1490, carga=3, refrig=63.1, bateria=13.48, aire=23.7)

        def nop():
            operations.append('nop')
            raise OSError('keepalive sin respuesta')

        self.kline.leer_core, self.kline.keepalive = read, nop
        self.panel.vivo()
        self.assertEqual(operations, ['open', 'read', 'nop', 'close', 'open', 'read', 'close'])
        self.assertEqual(sum(line.startswith('D ') for line in lines), 2)
        self.assertEqual(sum(line.startswith('recuperando DME') for line in lines), 1)

    def test_stop_faults_and_ble_loss_cancel_pacing_without_another_query(self):
        for command in ('s', 'f', None):
            with self.subTest(command=command):
                self.setUp()
                clock = [0]
                operations = []
                self.panel.enviar = lambda line: None
                self.kline.keepalive = lambda: operations.append('nop')
                self.kline.desconectar = lambda: operations.append('close')

                def read():
                    operations.append('read')
                    clock[0] += 400
                    return dict(rpm=1490, carga=3, refrig=63.1, bateria=13.48, aire=23.7)

                def cancel(ms):
                    self.assertEqual(ms, 25)
                    clock[0] += ms
                    if command:
                        self.panel._cmd = command
                    else:
                        self.panel._conn = None

                self.scope['time'] = types.SimpleNamespace(
                    ticks_ms=lambda: clock[0], ticks_diff=lambda a, b: a-b, sleep_ms=cancel)
                self.kline.leer_core = read
                self.panel.vivo()
                self.assertEqual(operations, ['read', 'nop', 'close'])
                self.assertEqual(self.panel._cmd, command)


if __name__ == "__main__":
    unittest.main()
