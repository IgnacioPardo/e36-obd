"""Exercise the real MicroPython transport with a scripted UART, without hardware."""
import importlib.util
import sys
import types
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import patch


class Clock:
    def __init__(self):
        self.ms = 0
        self.sleeps = []

    def ticks_ms(self):
        return self.ms

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    def sleep_ms(self, ms):
        self.sleeps.append(ms)
        self.ms += ms


class UART:
    def __init__(self, clock):
        self.clock = clock
        self.rx = deque()
        self.steps = deque()
        self.future = []
        self.writes = []
        self.closed = False

    def any(self):
        while self.future and self.future[0][0] <= self.clock.ms:
            _, data = self.future.pop(0)
            self.rx.extend(data)
        return len(self.rx)

    def read(self, count):
        return bytes([self.rx.popleft()])

    def readinto(self, target):
        if not self.rx:
            return None
        target[0] = self.rx.popleft()
        return 1

    def write(self, data):
        value = data[0]
        self.writes.append(value)
        if self.steps:
            expected, received = self.steps.popleft()
            if value != expected:
                raise AssertionError('expected TX %02X, got %02X' % (expected, value))
            self.rx.extend(received)
        else:
            self.rx.append(value)  # the physical frontend always echoes TX
        return len(data)

    def deinit(self):
        self.closed = True

    def tester_block(self, block, next_byte):
        for i, value in enumerate(block):
            reply = [value]
            if i < len(block) - 1:
                reply.append(value ^ 0xFF)
            elif next_byte is not None:
                reply.append(next_byte)
            self.steps.append((value, reply))

    def ecu_block(self, block):
        # Its first byte is already queued by the preceding tester block.
        for value, following in zip(block, block[1:]):
            self.steps.append((value ^ 0xFF, [value ^ 0xFF, following]))


class KLineTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.uart = UART(self.clock)
        self.pin_values = []
        pin_values = self.pin_values

        class Pin:
            OUT = 1

            def __init__(self, number, mode, value):
                pin_values.append(value)

            def value(self, value):
                pin_values.append(value)

        self.uart_options = []

        def open_uart(*args, **kwargs):
            self.uart_options.append(kwargs)
            return self.uart

        machine = types.SimpleNamespace(Pin=Pin, UART=open_uart)
        path = Path(__file__).resolve().parents[1] / 'mp/kline.py'
        spec = importlib.util.spec_from_file_location('firmware_kline', path)
        self.kline = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'machine': machine}):
            spec.loader.exec_module(self.kline)
        self.kline.time = self.clock
        self.kline._uart = self.uart

    def queue_sample(self):
        # Captured RAM values; four KWP71 blocks, not five individual reads.
        payload = bytes.fromhex('C9 52 5C 1C 55 18 61 F1 05 F7 3C')
        self.uart.tester_block([6, 8, 1, 11, 0, 0x36, 3], 14)
        self.uart.ecu_block(bytes([14, 9, 0xFE]) + payload + b'\x03')
        self.uart.tester_block([3, 10, 9, 3], 3)
        self.uart.ecu_block([3, 11, 9, 3])
        self.kline._seq = 7
        return payload

    def test_same_readram_exchange_as_desktop_client(self):
        payload = self.queue_sample()
        self.assertEqual(self.kline.read_ram(0x36, 11), payload)
        expected_writes = list(self.uart.writes)
        self.assertFalse(self.uart.steps)
        self.assertEqual(self.kline._seq, 11)
        self.assertEqual(self.clock.sleeps.count(50), 2)  # request and response ACK

        self.setUp()
        self.queue_sample()
        # Use the actual desktop block engine over the same scripted wire.
        with patch.dict(sys.modules, {'serial': types.ModuleType('serial')}):
            from e36obd.kwp71 import KWP71Session
            line = types.SimpleNamespace(write_byte=self.kline._tx,
                                         read_byte=lambda timeout=None: self.kline._rx())
            session = KWP71Session(line)
            session.connected, session.seq = True, 7
            with patch('e36obd.kwp71.time.sleep'):
                self.assertEqual(session.read_ram(0x36, 11), payload)
        self.assertEqual(self.uart.writes, expected_writes)
        self.assertFalse(self.uart.steps)

    def test_unread_ecu_bytes_are_never_silently_flushed(self):
        self.uart.rx.extend([0xFE, 0x55])
        with self.assertRaisesRegex(self.kline.KLineError, 'eco malo'):
            self.kline._tx(0xA5)
        self.assertEqual(list(self.uart.rx), [0x55, 0xA5])
        # The old _tx discarded FE and 55, then reported a successful write.

    def test_response_after_1200ms_uses_desktop_timeout(self):
        self.uart.future = [(1400, b'\x03')]
        self.assertEqual(self.kline._rx(), 3)
        self.assertEqual(self.clock.ms, 1400)
        with self.assertRaises(self.kline.KLineError):
            self.kline._rx()
        self.assertEqual(self.clock.ms, 3400)

    def test_missing_byte_fails_instead_of_publishing_partial_values(self):
        self.queue_sample()
        # Drop the final data byte after its predecessor has been acknowledged.
        steps = list(self.uart.steps)
        index = 7 + 12  # response's penultimate payload ACK
        expected, received = steps[index]
        steps[index] = (expected, received[:1])
        self.uart.steps = deque(steps)
        with self.assertRaisesRegex(self.kline.KLineError, 'sin respuesta'):
            self.kline.leer_core()

    def test_cleanup_attempts_disconnect_then_releases_even_when_no_ack(self):
        # Matches LiveReader._close(): best effort farewell, then close UART.
        self.kline.desconectar()
        self.assertEqual(self.uart.writes, [3])  # no next byte without its ACK
        self.assertTrue(self.uart.closed)
        self.assertIsNone(self.kline._uart)
        self.assertEqual(self.pin_values[-1], 1)
        self.assertEqual(self.clock.ms, 300)
        self.kline.desconectar()
        self.assertEqual(self.uart.writes, [3])

    def test_disconnect_deadline_is_shared_across_echoes_and_acks(self):
        def slow_write(data):
            value = data[0]
            self.uart.writes.append(value)
            self.uart.rx.append(value)
            self.uart.future.append((self.clock.ms + 200, bytes([value ^ 0xFF])))
            return 1

        self.uart.write = slow_write
        self.kline.desconectar()
        self.assertEqual(self.uart.writes, [3, 1])
        self.assertEqual(self.clock.ms, 300)  # not 300 ms for each byte
        self.assertTrue(self.uart.closed)
        self.assertIsNone(self.kline._uart)

    def test_healthy_disconnect_still_sends_complete_block(self):
        self.uart.tester_block([3, 1, 6, 3], None)
        self.kline.desconectar()
        self.assertEqual(self.uart.writes, [3, 1, 6, 3])
        self.assertFalse(self.uart.steps)
        self.assertEqual(self.clock.ms, 8)
        self.assertTrue(self.uart.closed)

    def test_incomplete_identification_is_not_a_successful_connection(self):
        self.kline.init = lambda *args, **kwargs: [0, 0x81]
        self.kline.recv_block = lambda: (_ for _ in ()).throw(self.kline.KLineError('missing ID'))
        with self.assertRaisesRegex(self.kline.KLineError, 'missing ID'):
            self.kline.conectar(verbose=False)
        self.assertTrue(self.uart.closed)
        self.assertIsNone(self.kline._uart)

    def test_sync_ignores_leading_noise_and_checks_keyword_echo(self):
        self.kline._uart = None
        self.uart.future = [(4500, bytes([0, 0xFF, 0x55, 0, 0x81]))]
        self.uart.steps.append((0x7E, [0x7E]))
        self.assertEqual(self.kline.init(verbose=False), [0, 0x81])
        self.assertEqual(self.uart.writes, [0x7E])
        self.assertEqual(self.clock.ms, 4505)
        self.assertEqual(self.uart_options[-1]['timeout'], 0)
        self.assertEqual(self.uart_options[-1]['timeout_char'], 0)

    def test_nonblocking_read_without_a_byte_keeps_its_original_deadline(self):
        self.uart.any = lambda: 1
        self.uart.readinto = lambda target: None
        with self.assertRaisesRegex(self.kline.KLineError, 'sin respuesta'):
            self.kline._rx(17)
        self.assertEqual(self.clock.ms, 17)

    def test_keepalive_is_a_complete_turn_and_preserves_next_read_sequence(self):
        self.kline._seq = 5
        self.uart.tester_block([3, 6, 9, 3], 3)
        self.uart.ecu_block([3, 7, 9, 3])
        self.kline.keepalive()
        self.assertEqual(self.kline._seq, 7)
        self.assertFalse(self.uart.steps)
        payload = self.queue_sample()
        self.assertEqual(self.kline.read_ram(0x36, 11), payload)
        self.assertFalse(self.uart.steps)

    def test_failed_uart_write_never_consumes_an_ecu_byte_as_echo(self):
        self.uart.rx.append(0x42)
        self.uart.write = lambda data: None
        with self.assertRaisesRegex(self.kline.KLineError, 'no acepto'):
            self.kline._tx(3)
        self.assertEqual(list(self.uart.rx), [0x42])

    def test_bad_trailer_and_nack_reject_payload(self):
        for block in ([4, 1, 0xFE, 0x42, 0xFF], [3, 1, 0x0A, 3]):
            with self.subTest(block=block):
                self.setUp()
                self.uart.rx.append(block[0])
                self.uart.ecu_block(block)
                if block[-1] != 3:
                    with self.assertRaisesRegex(self.kline.KLineError, 'terminador'):
                        self.kline.recv_block()
                else:
                    self.kline.send_block = lambda *args: None
                    with self.assertRaisesRegex(self.kline.KLineError, 'no soporta'):
                        self.kline.command(self.kline.READ_RAM)


if __name__ == '__main__':
    unittest.main()
