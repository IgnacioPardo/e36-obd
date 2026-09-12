#!/usr/bin/env python3
"""Compose native vehicle + shadow exports without clipping the shadow at PNG edges.

Usage: python3 prepare-car.py full-scene.png vehicle-only.png output.png
Requires Pillow and NumPy. Both inputs must use the same native camera and size.
Only the shadow contribution is feathered; vehicle color and opacity are retained.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image


def prepare(full_path, vehicle_path, output_path):
    full_image = Image.open(full_path).convert('RGBA')
    vehicle_image = Image.open(vehicle_path).convert('RGBA')
    if full_image.size != vehicle_image.size:
        raise ValueError('Export both passes at the same viewport size')
    full = np.asarray(full_image, dtype=np.float32) / 255
    vehicle = np.asarray(vehicle_image, dtype=np.float32) / 255
    y, x = np.where(vehicle[:, :, 3] > 0)
    margin = max(24, round((x.max() - x.min() + 1) * 0.045))
    box = (max(0, int(x.min()) - margin), max(0, int(y.min()) - margin),
           min(full.shape[1], int(x.max()) + 1 + margin), min(full.shape[0], int(y.max()) + 1 + margin))
    left, top, right, bottom = box
    full = full[top:bottom, left:right]
    vehicle = vehicle[top:bottom, left:right]
    height, width = full.shape[:2]
    yy, xx = np.mgrid[:height, :width]
    edge = np.minimum.reduce([xx, width - 1 - xx, yy, height - 1 - yy])
    t = np.clip(edge / (margin * 2), 0, 1)
    feather = (t * t * (3 - 2 * t))[:, :, None]
    # Separate the shadow's premultiplied contribution from the native vehicle.
    # Feathering the entire RGBA image would also erase tires and body edges.
    car_alpha, full_alpha = vehicle[:, :, 3:], full[:, :, 3:]
    alpha = car_alpha + np.maximum(0, full_alpha - car_alpha) * feather
    car_rgb = vehicle[:, :, :3] * car_alpha
    premultiplied = car_rgb + (full[:, :, :3] * full_alpha - car_rgb) * feather
    color = np.divide(premultiplied, alpha, out=np.zeros_like(premultiplied), where=alpha > 0)
    rgba = np.concatenate([color, alpha], axis=2)
    image = Image.fromarray(np.uint8(np.clip(rgba * 255 + 0.5, 0, 255)))
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    image.save(output_path, optimize=True)
    a = np.asarray(image)[:, :, 3]
    assert max(a[0].max(), a[-1].max(), a[:, 0].max(), a[:, -1].max()) == 0, 'All image edges must be transparent'
    return dict(renderer='Native RealityRenderer / Metal, AgX final pass, two transparent exports',
                sourceDimensions=full_image.size, crop=box, dimensions=image.size,
                assetSHA256=hashlib.sha256(Path(output_path).read_bytes()).hexdigest(),
                sourceSHA256=hashlib.sha256(Path(full_path).read_bytes()).hexdigest(),
                vehicleSHA256=hashlib.sha256(Path(vehicle_path).read_bytes()).hexdigest(),
                shadowFeatherPixels=margin * 2, edgeAlphaMaximum=int(max(a[0].max(), a[-1].max(), a[:, 0].max(), a[:, -1].max())),
                noColorRetouch=True, cropPurpose='Preserve the vehicle and contact shadow with fully transparent edges; no rectangular floor crop')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    print(json.dumps(prepare(*map(Path, sys.argv[1:])), indent=2))
