"""Normalize a captured studio HDR without changing its relative colours.
Requires OpenImageIO and NumPy. Source: Poly Haven Studio Small 09 (CC0).
"""
from pathlib import Path
import OpenImageIO as oiio
import numpy as np
import json,hashlib,argparse

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=root / '.context/vehicle-3d/sources/studio_small_09_2k.hdr', help='Downloaded Studio Small 09 HDR from Poly Haven')
parser.add_argument('--rotation-degrees', type=float, default=135, help='World-space probe rotation from the initial captured-studio study')
parser.add_argument('--exposure', type=float, default=.75, help='Stops above the 0.45 mean-radiance baseline')
args = parser.parse_args()

source = args.source.resolve()
image = oiio.ImageBuf(str(source))
rgb = image.get_pixels(oiio.FLOAT)[:, :, :3]
h,w,_ = rgb.shape
weight = np.sin((np.arange(h) + .5) / h * np.pi)[:, None]
luma = rgb @ np.array([.2126,.7152,.0722])
mean = float((luma * weight).sum() / (w * weight.sum()))
target = .45 * 2 ** args.exposure
scale = target / mean
rgb *= scale
# The chosen native study places the reflected doorway across the bonnet
# and shoulder. Equirectangular shift has the opposite sign to a Y-up probe.
shift = .12 - args.rotation_degrees / 360
rgb = np.roll(rgb, round(w * shift), axis=1)
out = oiio.ImageBuf(oiio.ImageSpec(w,h,3,oiio.FLOAT)); out.set_pixels(oiio.ROI(0,w,0,h,0,1,0,3),rgb)
path = root / 'ios/Design/Vehicle/SoftboxEnvironment.exr'
assert out.write(str(path)),out.geterror()
source_label = str(source.relative_to(root)) if source.is_relative_to(root) else source.name
path.with_suffix('.json').write_text(json.dumps({'source':source_label,'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'sphericalMeanBefore':mean,'sphericalMeanAfter':target,'commonExposureMultiplier':scale,'longitudeShiftTurns':shift,'worldRotationDegrees':args.rotation_degrees,'exposureStops':args.exposure,'noPerChannelColourAdjustment':True},indent=2))
print('PHOTOGRAPHIC_STUDIO_READY',mean,scale)
