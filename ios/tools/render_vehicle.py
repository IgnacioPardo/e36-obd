"""Render an offline vehicle turntable from its editable Blender studio.

/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --disable-autoexec --python ios/tools/render_vehicle.py

Optional after --: --output PATH --start N --end N --samples N --resume.
A manifest is written only when the complete sequence is present. Partial jobs
can resume without changing the live app model. Blender 4.5 / Cycles.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
FRAME_COUNT = 180
WIDTH, HEIGHT = 1200, 700
CROP = [48, 130, 1104, 500]
START_ANGLE = .58

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ROOT / 'ios/Design/Vehicle/E36-316i.blend')
parser.add_argument('--output', type=Path, default=ROOT / '.context/vehicle-turntable')
parser.add_argument('--start', type=int, default=0)
parser.add_argument('--end', type=int)
parser.add_argument('--samples', type=int, default=256)
parser.add_argument('--frames', type=int, default=FRAME_COUNT)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
if args.frames < 12 or args.frames > 360:
    parser.error('Expected 12 <= frames <= 360')
if args.end is None:
    args.end = args.frames
FRAME_COUNT = args.frames
if not 0 <= args.start < args.end <= FRAME_COUNT:
    parser.error(f'Expected 0 <= start < end <= {FRAME_COUNT}')

bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    gpu = False
    for device in prefs.devices:
        device.use = device.type == 'METAL'
        gpu |= device.use
    scene.cycles.device = 'GPU' if gpu else 'CPU'
except Exception as error:
    print(f'Metal unavailable; CPU render: {error}', flush=True)
    scene.cycles.device = 'CPU'

# The seed, lighting, camera height, focal length and crop remain fixed. No
# per-view exposure or automatic framing can cause a brightness or pivot jump.
scene.cycles.samples = args.samples
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_min_samples = 64
scene.cycles.adaptive_threshold = .006
scene.cycles.use_denoising = True
scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
scene.cycles.seed = 42
scene.cycles.use_animated_seed = False
scene.cycles.sample_clamp_indirect = 10
scene.render.use_border = False
scene.render.use_crop_to_border = False
scene.render.use_persistent_data = True
scene.render.resolution_x = WIDTH
scene.render.resolution_y = HEIGHT
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '8'
scene.render.image_settings.compression = 55
scene.camera.data.type = 'PERSP'
scene.camera.data.lens = 62
scene.camera.data.sensor_width = 36
scene.camera.data.sensor_fit = 'HORIZONTAL'
scene.camera.data.dof.use_dof = False
args.output.mkdir(parents=True, exist_ok=True)
settings = {
    'sourceSHA256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
    'frameCount': FRAME_COUNT, 'width': WIDTH, 'height': HEIGHT, 'crop': CROP,
    'samples': args.samples, 'seed': 42, 'indirectClamp': 10,
    'startAngleRadians': START_ANGLE,
    'lensMM': 62, 'cameraRadiusM': 9.5, 'cameraHeightM': 1.85,
}
settings_path = args.output / 'render-settings.json'
existing_settings = json.loads(settings_path.read_text()) if settings_path.exists() else None
if any(args.output.glob('e36-*.png')) and existing_settings != settings:
    raise RuntimeError('Existing frames have different or unknown settings; use a new output folder.')
if args.resume:
    if existing_settings != settings:
        raise RuntimeError('Resume settings differ; use a new output folder to avoid mixing frames.')
else:
    if args.start != 0 and (not settings_path.exists() or json.loads(settings_path.read_text()) != settings):
        raise RuntimeError('A partial range needs the same existing render settings.')
    settings_path.write_text(json.dumps(settings, indent=2) + '\n')

def valid_png(path):
    if not path.is_file():
        return False
    try:
        with path.open('rb') as file:
            if file.read(8) != b'\x89PNG\r\n\x1a\n':
                return False
            first, has_pixels = True, False
            while chunk := file.read(8):
                if len(chunk) != 8:
                    return False
                length, kind = struct.unpack('>I4s', chunk)
                if length > WIDTH * HEIGHT * 8:
                    return False
                payload, checksum = file.read(length), file.read(4)
                if len(payload) != length or len(checksum) != 4:
                    return False
                if zlib.crc32(kind + payload) != struct.unpack('>I', checksum)[0]:
                    return False
                if first:
                    if (kind != b'IHDR' or len(payload) != 13
                            or struct.unpack('>II', payload[:8]) != (WIDTH, HEIGHT)
                            or payload[8:10] != bytes([8, 6])):
                        return False
                    first = False
                has_pixels |= kind == b'IDAT' and length > 0
                if kind == b'IEND':
                    return length == 0 and has_pixels and not file.read(1)
    except OSError:
        return False
    return False

for index in range(args.start, args.end):
    path = args.output / f'e36-{index:02d}.png'
    if args.resume and valid_png(path):
        print(f'FRAME {index:03d} REUSED', flush=True)
        continue
    # An interrupted replacement must never retain a manifest for old pixels.
    (args.output / 'manifest.json').unlink(missing_ok=True)
    angle = START_ANGLE + index * math.tau / FRAME_COUNT
    scene.camera.location = (math.sin(angle) * 9.5, -math.cos(angle) * 9.5, 1.85)
    scene.camera.rotation_euler = (Vector((0, 0, .64)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    temporary = args.output / f'.e36-{index:02d}.png'
    scene.render.filepath = str(temporary.resolve())
    bpy.ops.render.render(write_still=True)
    if not valid_png(temporary):
        raise RuntimeError(f'Invalid rendered frame: {temporary}')
    temporary.replace(path)
    print(f'FRAME {index:03d} COMPLETE', flush=True)

paths = [args.output / f'e36-{index:02d}.png' for index in range(FRAME_COUNT)]
if hashlib.sha256(args.source.read_bytes()).hexdigest() != settings['sourceSHA256']:
    raise RuntimeError('Native source changed during rendering; use a new output folder.')
if all(valid_png(path) for path in paths):
    manifest = {
        'frameCount': FRAME_COUNT, 'width': WIDTH, 'height': HEIGHT, 'crop': CROP,
        'startAngleRadians': START_ANGLE, 'angleStepDegrees': 360 / FRAME_COUNT,
        'renderer': 'Blender 4.5 / Cycles', 'samples': args.samples, 'seed': 42,
        'sourceSHA256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'frames': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
    }
    temporary = args.output / '.manifest.json'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(args.output / 'manifest.json')
    print('COMPLETE SEQUENCE VERIFIED', flush=True)
else:
    print('Partial sequence; manifest not changed.', flush=True)
