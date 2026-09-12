"""Downsample the original scene-linear panorama for the visible HDR backdrop.
Requires OpenImageIO. Store radiance / 16 to keep the sun finite in half float;
the shader decodes that common scale before the display transform.
"""
from pathlib import Path
import OpenImageIO as oiio

root = Path(__file__).resolve().parents[1]
source = oiio.ImageBuf(str(root / 'E36OBD/VehicleScene/StudioEnvironment.exr'))
output = oiio.ImageBuf(oiio.ImageSpec(2048, 1024, 3, oiio.FLOAT))
oiio.ImageBufAlgo.resize(output, source)
oiio.ImageBufAlgo.mul(output, output, (1 / 16, 1 / 16, 1 / 16))
output.set_write_format(oiio.HALF)
path = root / 'E36OBD/VehicleScene/ParkingBackdrop.exr'
assert output.write(str(path)), output.geterror()
print(path)
