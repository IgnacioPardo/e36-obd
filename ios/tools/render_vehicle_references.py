"""Render the three editable photo studies linked to the native vehicle.

blender --background --factory-startup --disable-autoexec \
  --python ios/tools/render_vehicle_references.py -- --output /tmp/e36-references

The studied camera and lighting are reconstructed from the owner's photographs,
not recovered camera calibration or a measured HDR lighting capture.
"""
import argparse
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'ios/Design/Vehicle')
parser.add_argument('--view', choices=['nose', 'side', 'rear', 'all'], default='all')
parser.add_argument('--samples', type=int, default=384)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'ios/Design/Vehicle/ReferenceLighting.blend'))
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'METAL'
except Exception:
    pass
args.output.mkdir(parents=True, exist_ok=True)
for scene in bpy.data.scenes:
    view = scene.get('reference_view')
    if not view or args.view not in {'all', view}:
        continue
    bpy.context.window.scene = scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU' if any(d.use and d.type == 'METAL' for d in prefs.devices) else 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.adaptive_min_samples = 64
    scene.cycles.adaptive_threshold = .006
    scene.cycles.seed = 42
    scene.cycles.use_animated_seed = False
    scene.cycles.sample_clamp_indirect = 10
    scene.render.resolution_percentage = 100
    scene.render.filepath = str((args.output / f'reference-{view}.png').resolve())
    bpy.ops.render.render(write_still=True)
