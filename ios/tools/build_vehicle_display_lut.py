"""Compile Blender's AgX display transform into a runtime-only half-float LUT.

Authoring tool only: requires numpy and opencolorio. The app has no OCIO
dependency. The logarithmic input shaper matches e36PhotographicDisplay.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import PyOpenColorIO as ocio

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', type=Path, default=Path('/Applications/Blender.app/Contents/Resources/4.5/datafiles/colormanagement/config.ocio'))
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'E36OBD/VehicleScene')
args = parser.parse_args()
config = ocio.Config.CreateFromFile(str(args.config))
view = ocio.DisplayViewTransform(src='Linear Rec.709', display='sRGB', view='AgX')
look = ocio.LookTransform(src='Linear Rec.709', dst='Linear Rec.709', looks='AgX - Medium High Contrast')
transform = ocio.GroupTransform([look, view])
processor = config.getProcessor(transform).getDefaultCPUProcessor()
size, low, high = 64, -16., 16.
axis = .18 * np.exp2(np.linspace(low, high, size, dtype=np.float32))
b, g, r = np.meshgrid(axis, axis, axis, indexing='ij')
rgb = np.stack((r, g, b), axis=-1).astype(np.float32)
processor.applyRGB(rgb.reshape(-1, 3))
# Store display-linear values: the sRGB drawable performs the final transfer.
linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
lut = np.concatenate((linear, np.ones((*linear.shape[:-1], 1))), axis=-1).astype('<f2')
assert np.isfinite(lut).all() and lut.min() >= 0 and lut.max() <= 1.001
args.output.mkdir(exist_ok=True, parents=True)
path = args.output / 'AgXDisplay.rgba16f'
path.write_bytes(lut.tobytes())

# Check trilinear reconstruction against OCIO on reproducible scene-linear
# samples, including neutral patches and saturated paint/highlight colors.
rng = np.random.default_rng(36)
test = (.18 * np.exp2(rng.uniform(-12, 10, (20000, 3)))).astype(np.float32)
expected = test.copy()
processor.applyRGB(expected)
uvw = np.clip((np.log2(test / .18) - low) / (high - low), 0, 1) * (size - 1)
base = np.minimum(uvw.astype(int), size - 2)
f = uvw - base
actual = np.zeros_like(test)
for z in range(2):
    for y in range(2):
        for x in range(2):
            weight = (f[:, 0] if x else 1-f[:, 0]) * (f[:, 1] if y else 1-f[:, 1]) * (f[:, 2] if z else 1-f[:, 2])
            actual += lut[base[:, 2]+z, base[:, 1]+y, base[:, 0]+x, :3].astype(np.float32) * weight[:, None]
actual = np.where(actual <= .0031308, actual * 12.92, 1.055 * actual ** (1/2.4) - .055)
error = np.abs(actual - expected)
assert np.quantile(error, .99) < .012, 'Display transform interpolation regressed'
report = dict(size=size, encoding='RGBA16Float little endian, red fastest', input='Linear Rec.709', display='sRGB', view='AgX', look='AgX - Medium High Contrast', log2Range=[low, high], middleGrey=.18, ocioVersion=ocio.__version__, configSHA256=hashlib.sha256(args.config.read_bytes()).hexdigest(), lutSHA256=hashlib.sha256(path.read_bytes()).hexdigest(), validationSamples=len(test), displayError99th=float(np.quantile(error, .99)), displayErrorMaximum=float(error.max()))
(args.output / 'display-transform.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
