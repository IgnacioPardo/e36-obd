"""Host tests of the actual MicroPython BLE module; never access a serial port."""
import sys
import types
import unittest
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
        self.kline.NOMBRES = {}
        self.kline.conectar = lambda **kwargs: None
        self.kline.command = lambda command: [bytes([100, 0x68, 0, 0, 50])]
        scope = {}
        source = Path(__file__).resolve().parents[1] / "mp" / "ble.py"
        with patch.dict(sys.modules, {"bluetooth": bluetooth, "kline": self.kline}):
            exec(compile(source.read_text(), str(source), "exec"), scope)
        clock = iter([0, 341])
        scope["time"] = types.SimpleNamespace(ticks_ms=lambda: next(clock), ticks_diff=lambda a, b: a-b, sleep_ms=lambda ms: None)
        self.scope = scope
        self.panel = scope["Panel"].__new__(scope["Panel"])
        self.panel._conn = 1
        self.panel._cmd = None
        self.panel._vivo = False

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


if __name__ == "__main__":
    unittest.main()
