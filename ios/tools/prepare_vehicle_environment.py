"""Align a Blender-authored equirectangular HDR with RealityKit/realitytool.

Requires NumPy and OpenImageIO in the development environment. The app has
neither dependency. Preserve the original HDR for Blender illumination bakes.

Blender Z-up -> app Y-up maps (x, y, z) to (x, z, -y). A six-direction RGB
gradient probe found that realitytool's equirectangular convention adds a
quarter-turn relative to that transform. Shifting columns right by width/4
removes it. Do not mirror the image or rotate the car/camera to compensate.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import OpenImageIO as oiio


def prepare(source: Path, output: Path):
    image = oiio.ImageInput.open(str(source))
    if image is None:
        raise RuntimeError(oiio.geterror())
    try:
        pixels = image.read_image(format=oiio.FLOAT)
    finally:
        image.close()
    height, width, channels = pixels.shape
    if width != height * 2 or width % 4 or channels < 3:
        raise ValueError('Expected a 2:1 RGB panorama with width divisible by four')
    if not np.isfinite(pixels).all():
        raise ValueError('HDR contains non-finite radiance')
    aligned = np.roll(pixels, width // 4, axis=1)
    # A column permutation keeps every radiance value, without resampling,
    # clipping bright emitters or altering the calibrated exposure/colour.
    assert np.array_equal(np.roll(aligned, -width // 4, axis=1), pixels)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = oiio.ImageOutput.create(str(output))
    spec = oiio.ImageSpec(width, height, channels, oiio.FLOAT)
    spec.attribute('oiio:ColorSpace', 'Linear')
    if not writer.open(str(output), spec):
        raise RuntimeError(writer.geterror())
    try:
        if not writer.write_image(aligned):
            raise RuntimeError(writer.geterror())
    finally:
        writer.close()
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        'sourceSHA256': sha(source), 'outputSHA256': sha(output),
        'sourceCoordinates': 'Blender equirectangular, Z-up authoring',
        'outputCoordinates': 'RealityKit/realitytool equirectangular input',
        'rightwardColumnShift': width // 4, 'yawCorrectionDegrees': 90,
        'dimensions': [width, height], 'radiancePermutationIsLossless': True,
        'linearRGBMaximum': float(aligned[:, :, :3].max()),
    }
    output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Keep the authoring HDR separate from the runtime derivative')
    print(json.dumps(prepare(args.source, args.output), indent=2))
