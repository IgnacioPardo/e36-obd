#!/usr/bin/env python3
"""Back up, replace and verify only ble.py on a USB-attached MicroPython ESP32."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Use one of the USB ports printed by --list')
    parser.add_argument('--list', action='store_true', help='Discover USB ports without changing the device')
    parser.add_argument('--restore', type=Path, help='Restore a previously saved ble.py backup')
    args = parser.parse_args()
    executable = shutil.which('mpremote')
    if not executable:
        parser.error('mpremote no está instalado. Ejecutá: uv tool install mpremote')
    listing = subprocess.run([executable, 'connect', 'list'], check=True, capture_output=True, text=True).stdout
    ports = [line.split()[0] for line in listing.splitlines() if re.match(r'^/dev/cu\.(usbserial|usbmodem|wchusbserial)', line)]
    if args.list:
        print('\n'.join(ports) or 'No hay lectores USB conectados. Usá el conector COM del ESP32.')
        return
    if args.port:
        if args.port not in ports:
            parser.error('El puerto indicado no está en la lista actual de dispositivos USB; ejecutá --list.')
        port = args.port
    elif len(ports) == 1:
        port = ports[0]
    else:
        parser.error('Conectá el ESP32 por USB y elegí --port si hay más de uno: ' + ', '.join(ports))
    source = args.restore.resolve() if args.restore else ROOT / 'firmware/mp/ble.py'
    if not source.is_file():
        parser.error('No existe el archivo de firmware: ' + str(source))
    compile(source.read_text(), str(source), 'exec')
    platform = subprocess.run([executable, 'connect', port, 'exec', 'import sys; print(sys.platform)'],
                              check=True, capture_output=True, text=True, timeout=45).stdout.strip()
    if platform != 'esp32':
        parser.error('El dispositivo no se identifica como MicroPython ESP32; no se modificó ble.py.')
    backup_dir = ROOT / '.context/firmware-backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup_dir.mkdir(parents=True)
    original = backup_dir / 'ble.py'
    check = backup_dir / 'verified.py'

    def remote(*command):
        subprocess.run([executable, 'connect', port, *map(str, command)], check=True, timeout=45)

    # No firmware change occurs until a complete local backup exists.
    remote('fs', 'cp', ':ble.py', original)
    if not original.is_file() or original.stat().st_size == 0:
        raise RuntimeError('El respaldo está vacío; no se modificó ble.py.')
    if b'E36-OBD' not in original.read_bytes() or b'6E400001-B5A3-F393-E0A9-E50E24DCCA9E' not in original.read_bytes():
        raise RuntimeError('El BLE existente no corresponde al lector E36-OBD; respaldo conservado, sin reemplazar firmware.')
    try:
        remote('fs', 'cp', source, ':ble.py')
        remote('fs', 'cp', ':ble.py', check)
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(check.read_bytes()).digest():
            raise RuntimeError('La verificación de lectura no coincide con el archivo enviado.')
    except Exception:
        print('Falló la actualización. Restaurando el respaldo...', file=sys.stderr)
        remote('fs', 'cp', original, ':ble.py')
        remote('fs', 'cp', ':ble.py', check)
        if original.read_bytes() != check.read_bytes():
            raise RuntimeError('La restauración no se pudo verificar. No reinicies el ESP32; respaldo: ' + str(original))
        remote('reset')
        raise
    remote('reset')
    print('Firmware verificado y reiniciado. Respaldo:', original)
    print('Para volver: python3 ios/tools/update_ble.py --restore', original)


if __name__ == '__main__':
    main()
