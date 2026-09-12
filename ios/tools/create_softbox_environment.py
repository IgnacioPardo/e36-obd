"""Author the app's neutral photographic softboxes with Blender's image API.

Run: blender --background --python ios/tools/create_softbox_environment.py
Then compile the generated EXR with xcrun realitytool image.
Only the radiance environment is generated; the owner-approved mesh and paint
are untouched. No new runtime dependency. Output is scene-linear OpenEXR.
"""
from pathlib import Path
import bpy
import numpy as np

root = Path(__file__).resolve().parents[1]
width, height = 1024, 512
u, v = np.meshgrid((np.arange(width) + .5) / width, (np.arange(height) + .5) / height)
rgb = np.full((height, width, 3), .10, dtype=np.float32)

def box(center, size, power, color):
    dx = np.abs((u - center[0] + .5) % 1 - .5) / size[0]
    dy = np.abs(v - center[1]) / size[1]
    # Broad diffusers with soft perimeter, separated by dark negative fill.
    falloff = np.exp(-np.power(dx, 8) - np.power(dy, 8))
    rgb[:] += falloff[..., None] * power * np.array(color)

# Image rows are bottom-up in Blender. Upper hemisphere = v > .5.
box((.93, .70), (.115, .10), 4.5, (1.0, .98, .95))
box((.41, .68), (.035, .16), 3.0, (.92, .97, 1.0))
box((.64, .88), (.20, .045), 1.8, (1, 1, 1))
rgba = np.concatenate([rgb, np.ones((height, width, 1), dtype=np.float32)], axis=2)
image = bpy.data.images.new('Neutral photographic softboxes', width=width, height=height, float_buffer=True)
image.pixels.foreach_set(rgba.ravel())
image.filepath_raw = str(root / 'Design/Vehicle/SoftboxEnvironment.exr')
image.file_format = 'OPEN_EXR'
image.save()
print(image.filepath_raw)
