"""App derivative: tuck the oversized connection behind the rear apron.

Keeps the authored hollow slash-cut tip, all UVs and normals. The original
native/reference model remains available; use this before the stance pass.
Requires usd-core. Output is a standalone USDZ, not a runtime geometry hack.
"""
import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, UsdUtils

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
a.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='e36-exhaust-') as directory:
    directory = Path(directory)
    with zipfile.ZipFile(a.source) as archive:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in archive.namelist())
        archive.extractall(directory)
        root = directory / archive.namelist()[0]
    stage = Usd.Stage.Open(str(root))
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y
    bounds = UsdGeom.BBoxCache(0, [UsdGeom.Tokens.default_])
    cache = UsdGeom.XformCache()
    report = {'sourceSHA256': hashlib.sha256(a.source.read_bytes()).hexdigest(), 'changes': []}
    for name, scale, translation in [
        ('Stock_muffler_connection', (0.26, 0.52, 0.72), (0, 0.105, 0.01)),
        ('Single_exhaust', (1, 1, 0.66), (0, 0.012, -0.04)),
    ]:
        prim = stage.GetPrimAtPath('/root/' + name)
        assert prim
        before = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
        center = before.GetMidpoint()
        delta = Gf.Matrix4d().SetTranslate(-center) * Gf.Matrix4d().SetScale(Gf.Vec3d(*scale)) * Gf.Matrix4d().SetTranslate(center + Gf.Vec3d(*translation))
        world = cache.GetLocalToWorldTransform(prim)
        parent = cache.GetLocalToWorldTransform(prim.GetParent())
        transform = UsdGeom.Xformable(prim)
        transform.ClearXformOpOrder()
        transform.AddTransformOp(opSuffix='tuckedExhaust').Set(world * delta * parent.GetInverse())
        bounds.Clear(); cache.Clear()
        after = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
        report['changes'].append({'object': name, 'before': str(before), 'after': str(after)})
    stage.GetRootLayer().Save()
    assert not a.output.exists(), 'Keep previous output; choose a fresh destination'
    assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(root)), str(a.output))
    report['outputSHA256'] = hashlib.sha256(a.output.read_bytes()).hexdigest()
    a.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
