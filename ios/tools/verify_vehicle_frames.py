"""Verify a complete render sequence and make visual review artifacts.

Development-only dependencies: Pillow, NumPy, OpenCV.
python verify_vehicle_frames.py --frames PATH --source E36-316i.blend --output PATH
Optical-flow residuals rank pairs for human review; they are not a proof that all
reflection changes are defects or that no visible artifact can remain.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--frames', type=Path, required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.frames / 'manifest.json').read_text())
assert manifest['sourceSHA256'] == hashlib.sha256(args.source.read_bytes()).hexdigest(), 'Source hash differs'
count, width, height = manifest['frameCount'], manifest['width'], manifest['height']
x, y, cw, ch = manifest['crop']
expected = [f'e36-{i:02d}.png' for i in range(count)]
assert sorted(p.name for p in args.frames.glob('e36-*.png')) == sorted(expected)
assert set(manifest['frames']) == set(expected)
args.output.mkdir(parents=True, exist_ok=True)
background = np.array([12, 13, 14], dtype=np.float32)
small, masks, thumbs, records, hashes = [], [], [], [], set()
for i, name in enumerate(expected):
    path = args.frames / name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == manifest['frames'][name], f'Hash differs: {name}'
    assert digest not in hashes, f'Duplicate frame: {name}'
    hashes.add(digest)
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        assert im.size == (width, height) and im.mode == 'RGBA', name
        a = np.asarray(im)
    opaque = a[:, :, 3] > 240
    yy, xx = np.where(opaque)
    assert len(xx) > 10000, f'Empty vehicle: {name}'
    assert xx.min() > x and xx.max() < x + cw - 1 and yy.min() > y and yy.max() < y + ch - 1, f'Crop clips opaque content: {name}'
    a = a[y:y + ch, x:x + cw].astype(np.float32)
    alpha = a[:, :, 3:4] / 255
    rgb = (a[:, :, :3] * alpha + background * (1 - alpha)).clip(0, 255).astype(np.uint8)
    thumb = Image.fromarray(rgb).resize((552, 250), Image.Resampling.LANCZOS)
    thumbs.append(thumb)
    small.append(cv2.cvtColor(np.asarray(thumb), cv2.COLOR_RGB2GRAY))
    masks.append(cv2.resize(a[:, :, 3], (552, 250), interpolation=cv2.INTER_AREA) > 245)
    records.append({'name': name, 'bytes': path.stat().st_size, 'opaqueBounds': [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())], 'meanOpaqueRGB': a[:, :, :3][a[:, :, 3] > 245].mean(axis=0).tolist()})

gy, gx = np.mgrid[:250, :552].astype(np.float32)
pairs = []
for i in range(count):
    j = (i + 1) % count
    flow = cv2.calcOpticalFlowFarneback(small[i], small[j], None, .5, 3, 19, 3, 5, 1.2, 0)
    mapped = cv2.remap(small[j].astype(np.float32), gx + flow[:, :, 0], gy + flow[:, :, 1], cv2.INTER_LINEAR)
    mapped_mask = cv2.remap(masks[j].astype(np.uint8), gx + flow[:, :, 0], gy + flow[:, :, 1], cv2.INTER_NEAREST)
    valid = cv2.erode((masks[i] & mapped_mask.astype(bool)).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    difference = np.abs(small[i].astype(np.float32) - mapped)
    pairs.append({'from': i, 'to': j, 'alignedMeanAbsoluteLuma': float(difference[valid].mean()), 'alignedP95Luma': float(np.percentile(difference[valid], 95))})
worst = sorted(pairs, key=lambda v: v['alignedMeanAbsoluteLuma'], reverse=True)
report = {'sourceSHA256': manifest['sourceSHA256'], 'frames': count, 'uniqueHashes': len(hashes), 'dimensions': [width, height], 'crop': manifest['crop'], 'totalBytes': sum(r['bytes'] for r in records), 'verifiedPNGIntegrity': True, 'opaqueContentInsideCrop': True, 'loopTransition': pairs[-1], 'worstPairsForVisualReview': worst[:10], 'pairs': pairs, 'records': records}
(args.output / 'frame-validation.json').write_text(json.dumps(report, indent=2) + '\n')
board = Image.new('RGB', (3 * 552, 4 * 278), tuple(background.astype(int)))
draw = ImageDraw.Draw(board)
for n, i in enumerate(range(0, count, count // 12)):
    if n >= 12:
        break
    bx, by = (n % 3) * 552, (n // 3) * 278
    board.paste(thumbs[i], (bx, by))
    draw.text((bx + 20, by + 252), f'{i * 360 / count:.0f} degrees', fill=(175, 180, 184))
board.save(args.output / 'turntable.jpg', quality=94)
review = Image.new('RGB', (1104, 6 * 278), tuple(background.astype(int)))
draw = ImageDraw.Draw(review)
for n, pair in enumerate(worst[:6]):
    review.paste(thumbs[pair['from']], (0, n * 278))
    review.paste(thumbs[pair['to']], (552, n * 278))
    draw.text((18, n * 278 + 252), f"Frames {pair['from']} to {pair['to']} - aligned luma residual {pair['alignedMeanAbsoluteLuma']:.2f}/255", fill=(175, 180, 184))
review.save(args.output / 'rotation-review.jpg', quality=95)
print(json.dumps({k: report[k] for k in ['frames', 'uniqueHashes', 'totalBytes', 'opaqueContentInsideCrop', 'loopTransition']}, indent=2))
