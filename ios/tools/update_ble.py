#!/usr/bin/env python3
"""Back up and verify ble.py; --include-kline also upgrades its ECU transport."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
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
    parser.add_argument('--include-kline', action='store_true', help='Update kline.py and ble.py together, backing up both first')
    parser.add_argument('--restore', type=Path, help='Restore a saved ble.py, or a backup directory containing both files')
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
    restore = args.restore.resolve() if args.restore else None
    bundle = args.include_kline or (restore is not None and restore.is_dir())
    names = ['kline.py', 'ble.py'] if bundle else ['ble.py']
    if bundle and restore is not None and not restore.is_dir():
        parser.error('Para restaurar ambos archivos indicá el directorio de respaldo.')
    sources = {name: (restore / name if bundle else restore) if restore else ROOT / 'firmware/mp' / name for name in names}
    for source in sources.values():
        if not source.is_file():
            parser.error('No existe el archivo de firmware: ' + str(source))
        compile(source.read_text(), str(source), 'exec')
    platform = subprocess.run([executable, 'connect', port, 'exec', 'import sys; print(sys.platform)'],
                              check=True, capture_output=True, text=True, timeout=45).stdout.strip()
    if platform != 'esp32':
        parser.error('El dispositivo no se identifica como MicroPython ESP32; no se modificó ble.py.')
    backup_dir = ROOT / '.context/firmware-backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup_dir.mkdir(parents=True)

    def remote(*command):
        subprocess.run([executable, 'connect', port, *map(str, command)], check=True, timeout=45)

    # Every file is backed up before the first write. main.py stays untouched.
    for name in names:
        original = backup_dir / name
        remote('fs', 'cp', ':' + name, original)
        if not original.is_file() or original.stat().st_size == 0:
            raise RuntimeError('El respaldo está vacío; no se modificó firmware.')
    ble = (backup_dir / 'ble.py').read_bytes()
    if b'E36-OBD' not in ble or b'6E400001-B5A3-F393-E0A9-E50E24DCCA9E' not in ble:
        raise RuntimeError('El BLE existente no corresponde al lector E36-OBD; respaldo conservado, sin reemplazar firmware.')
    if bundle:
        transport = (backup_dir / 'kline.py').read_text()
        if 'KWP71' not in transport or not re.search(r'^TX_PIN\s*=\s*17\b', transport, re.M) or not re.search(r'^RX_PIN\s*=\s*18\b', transport, re.M):
            raise RuntimeError('El transporte no corresponde al lector E36; no se modificó firmware.')
    try:
        for name, source in sources.items():
            check = backup_dir / ('verified-' + name)
            remote('fs', 'cp', source, ':' + name)
            remote('fs', 'cp', ':' + name, check)
            if source.read_bytes() != check.read_bytes():
                raise RuntimeError('La verificación de lectura no coincide: ' + name)
    except Exception:
        print('Falló la actualización. Restaurando el respaldo...', file=sys.stderr)
        for name in names:
            original = backup_dir / name
            check = backup_dir / ('restored-' + name)
            remote('fs', 'cp', original, ':' + name)
            remote('fs', 'cp', ':' + name, check)
            if original.read_bytes() != check.read_bytes():
                raise RuntimeError('La restauración no se pudo verificar. No reinicies el ESP32; respaldo: ' + str(original))
        remote('reset')
        raise
    (backup_dir / 'verification.json').write_text(json.dumps({
        'port': port,
        'files': {name: {'before': hashlib.sha256((backup_dir / name).read_bytes()).hexdigest(),
                         'installed': hashlib.sha256(source.read_bytes()).hexdigest()} for name, source in sources.items()}
    }, indent=2) + '\n')
    remote('reset')
    rollback = backup_dir if bundle else backup_dir / 'ble.py'
    print('Firmware verificado y reiniciado. Respaldo:', rollback)
    print('Para volver: python3 ios/tools/update_ble.py --restore', rollback)


if __name__ == '__main__':
    main()
