"""Exercise backup/verification/rollback without opening a serial port."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('update_ble', ROOT / 'ios/tools/update_ble.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class BLEUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'firmware/mp/ble.py'
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes((ROOT / 'firmware/mp/ble.py').read_bytes())
        self.original = b'# E36-OBD 6E400001-B5A3-F393-E0A9-E50E24DCCA9E\nOLD = True\n'
        self.remote = self.original
        self.transport_source = self.source.with_name('kline.py')
        self.transport_source.write_bytes((ROOT / 'firmware/mp/kline.py').read_bytes())
        self.transport_original = b'# KWP71\nTX_PIN = 17\nRX_PIN = 18\nOLD = True\n'
        self.remote_transport = self.transport_original
        self.bundle = False
        self.corrupt_file = None
        self.corrupt_once = False
        self.device_platform = 'esp32'
        self.writes = self.resets = 0

    def command(self, args, **kwargs):
        if args[1:] == ['connect', 'list']:
            return SimpleNamespace(stdout='/dev/cu.usbmodem123 ESP32\n')
        if args[3] == 'exec':
            return SimpleNamespace(stdout=self.device_platform + '\n')
        if args[3] == 'reset':
            self.resets += 1
            return SimpleNamespace(stdout='')
        self.assertEqual(args[3:5], ['fs', 'cp'])
        source, destination = args[5:7]
        if source.startswith(':'):
            Path(destination).write_bytes(self.remote if source == ':ble.py' else self.remote_transport)
        else:
            # The original must already be backed up before any write to the device.
            backups = list((self.root / '.context/firmware-backups').glob('*/ble.py'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), self.original)
            if self.bundle:
                self.assertEqual(backups[0].with_name('kline.py').read_bytes(), self.transport_original)
            self.writes += 1
            data = Path(source).read_bytes()
            if self.corrupt_once or destination == self.corrupt_file:
                data += b'\n# corrupted transfer'
                self.corrupt_once = False
                self.corrupt_file = None
            if destination == ':ble.py':
                self.remote = data
            else:
                self.remote_transport = data
        return SimpleNamespace(stdout='')

    def invoke(self, *arguments):
        with patch.object(updater, 'ROOT', self.root), patch('sys.argv', ['update_ble', *arguments]), \
             patch.object(updater.shutil, 'which', return_value='mpremote'), \
             patch.object(updater.subprocess, 'run', side_effect=self.command):
            updater.main()

    def test_backup_precedes_write_and_verified_update(self):
        self.invoke()
        self.assertEqual(self.remote, self.source.read_bytes())
        self.assertEqual((self.writes, self.resets), (1, 1))

    def test_corrupted_transfer_restores_original_before_reset(self):
        self.corrupt_once = True
        with self.assertRaisesRegex(RuntimeError, 'verificación'):
            self.invoke()
        self.assertEqual(self.remote, self.original)
        self.assertEqual((self.writes, self.resets), (2, 1))

    def test_wrong_platform_does_not_write(self):
        self.device_platform = 'rp2'
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertEqual((self.writes, self.resets), (0, 0))

    def test_unrelated_ble_is_backed_up_but_not_replaced(self):
        self.original = self.remote = b'# another project\n'
        with self.assertRaisesRegex(RuntimeError, 'no corresponde'):
            self.invoke()
        self.assertEqual((self.writes, self.resets), (0, 0))

    def test_transport_bundle_backs_up_both_before_first_write(self):
        self.bundle = True
        self.invoke('--include-kline')
        self.assertEqual(self.remote, self.source.read_bytes())
        self.assertEqual(self.remote_transport, self.transport_source.read_bytes())
        self.assertEqual((self.writes, self.resets), (2, 1))

    def test_bundle_failure_in_second_file_restores_both(self):
        self.bundle = True
        self.corrupt_file = ':ble.py'
        with self.assertRaisesRegex(RuntimeError, 'verificación'):
            self.invoke('--include-kline')
        self.assertEqual(self.remote, self.original)
        self.assertEqual(self.remote_transport, self.transport_original)
        self.assertEqual((self.writes, self.resets), (4, 1))

    def test_unrelated_transport_is_not_replaced(self):
        self.remote_transport = self.transport_original = b'# another transport\n'
        with self.assertRaisesRegex(RuntimeError, 'no corresponde'):
            self.invoke('--include-kline')
        self.assertEqual((self.writes, self.resets), (0, 0))

    def test_restore_directory_restores_the_complete_pair(self):
        restore = self.root / 'saved'
        restore.mkdir()
        (restore / 'ble.py').write_bytes(self.original)
        (restore / 'kline.py').write_bytes(self.transport_original)
        self.bundle = True
        self.invoke('--restore', str(restore))
        self.assertEqual(self.remote, self.original)
        self.assertEqual(self.remote_transport, self.transport_original)
        self.assertEqual((self.writes, self.resets), (2, 1))


if __name__ == '__main__':
    unittest.main()
