"""Make the app-only ride-height variant without editing the reference model.

Requires usd-core and NumPy in the authoring environment. Meshes, UVs, normals,
wheel track and tyre contact positions are preserved. Only sprung-body object
transforms change; the whole coachwork shares one rigid pitch/drop transform.
"""
import argparse
import hashlib
import json
import math
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdUtils

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ROOT / 'ios/Design/Vehicle/E36-316i.usdz')
parser.add_argument('--output', type=Path, default=ROOT / '.context/vehicle-stance')
parser.add_argument('--front-mm', type=float, default=20)
parser.add_argument('--rear-mm', type=float, default=10)
args = parser.parse_args()
assert 0 <= args.rear_mm <= args.front_mm <= 35
args.output.mkdir(parents=True, exist_ok=True)
wheel_names = {'Left_front_wheel', 'Right_front_wheel', 'Left_rear_wheel', 'Right_rear_wheel'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def geometry_digest(stage):
    digest = hashlib.sha256()
    triangles = 0
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        digest.update(prim.GetPath().pathString.encode())
        for attr in prim.GetAttributes():
            if attr.GetName() in {'points', 'normals', 'faceVertexCounts', 'faceVertexIndices'} or attr.GetName().startswith('primvars:'):
                value = attr.Get()
                if value is not None:
                    digest.update(attr.GetName().encode())
                    digest.update(np.asarray(value).tobytes())
        triangles += len(mesh.GetFaceVertexCountsAttr().Get())
    return digest.hexdigest(), triangles

with tempfile.TemporaryDirectory(prefix='e36-app-stance-') as temporary:
    folder = Path(temporary)
    with zipfile.ZipFile(args.source) as archive:
        for name in archive.namelist():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
        archive.extractall(folder)
        root_layer = folder / archive.namelist()[0]
    stage = Usd.Stage.Open(str(root_layer))
    up_axis = UsdGeom.GetStageUpAxis(stage)
    assert up_axis in {UsdGeom.Tokens.y, UsdGeom.Tokens.z}
    to_z_up = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), 90)) if up_axis == UsdGeom.Tokens.y else Gf.Matrix4d(1)
    root = stage.GetPrimAtPath('/root')
    cache = UsdGeom.XformCache()
    wheels = {name: stage.GetPrimAtPath('/root/' + name) for name in wheel_names}
    assert all(wheels.values()), 'Expected the four authored wheel groups'
    wheel_world = {name: cache.GetLocalToWorldTransform(prim) for name, prim in wheels.items()}
    front = to_z_up.Transform(wheel_world['Left_front_wheel'].ExtractTranslation())
    rear = to_z_up.Transform(wheel_world['Left_rear_wheel'].ExtractTranslation())
    angle = math.asin((args.front_mm - args.rear_mm) / 1000 / (rear[1] - front[1]))
    pivot = Gf.Vec3d(0, rear[1], rear[2])
    delta = (Gf.Matrix4d().SetTranslate(-pivot)
             * Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), math.degrees(angle)))
             * Gf.Matrix4d().SetTranslate(pivot + Gf.Vec3d(0, 0, -args.rear_mm / 1000)))
    delta = to_z_up * delta * to_z_up.GetInverse()
    actual_front_drop = front[2] - to_z_up.Transform(delta.Transform(wheel_world['Left_front_wheel'].ExtractTranslation()))[2]
    actual_rear_drop = rear[2] - to_z_up.Transform(delta.Transform(wheel_world['Left_rear_wheel'].ExtractTranslation()))[2]
    assert abs(actual_front_drop - args.front_mm / 1000) < 1e-7
    assert abs(actual_rear_drop - args.rear_mm / 1000) < 1e-7
    before_digest, triangles = geometry_digest(stage)
    moved, fixed = [], []
    root_inverse = cache.GetLocalToWorldTransform(root).GetInverse()
    for prim in root.GetChildren():
        if not prim.IsA(UsdGeom.Xform) or not any(p.IsA(UsdGeom.Mesh) for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())):
            continue
        if prim.GetName() in wheel_names or prim.GetName().startswith(('Disk_', 'susp_')):
            fixed.append(prim.GetPath().pathString)
            continue
        local = cache.GetLocalToWorldTransform(prim) * delta * root_inverse
        xform = UsdGeom.Xformable(prim)
        xform.ClearXformOpOrder()
        xform.AddTransformOp(opSuffix='appStance').Set(local)
        moved.append(prim.GetPath().pathString)
    cache.Clear()
    assert all(cache.GetLocalToWorldTransform(wheels[name]) == value for name, value in wheel_world.items())
    assert geometry_digest(stage) == (before_digest, triangles), 'Stance must not edit meshes or shading attributes'
    minimum_body_height = math.inf
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh) or not any(prim.GetPath().HasPrefix(Sdf.Path(path)) for path in moved):
            continue
        points = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get())
        matrix = np.asarray(cache.GetLocalToWorldTransform(prim))
        vertical = 1 if up_axis == UsdGeom.Tokens.y else 2
        height = points @ matrix[:3, vertical] + matrix[3, vertical]
        minimum_body_height = min(minimum_body_height, float(height.min()))
    assert minimum_body_height > 0, 'Lowered coachwork intersects the ground'
    stage.GetRootLayer().Save()
    output = args.output / 'E36-AppStance.usdz'
    if output.exists():
        output.unlink()
    assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(root_layer)), str(output))
    report = dict(referenceSHA256=sha(args.source), outputSHA256=sha(output), frontDropMillimetres=args.front_mm,
                  rearDropMillimetres=args.rear_mm, bodyPitchDegrees=math.degrees(angle),
                  wheelbaseMetres=rear[1]-front[1], geometrySHA256=before_digest, triangles=triangles,
                  wheelTransformsUnchanged=True, meshNormalsAndUVsUnchanged=True,
                  minimumBodyGroundClearanceMetres=minimum_body_height, movedObjects=moved, fixedObjects=fixed,
                  scope='App-only stance derivative; reference native and portable files are untouched')
    (args.output / 'stance-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('APP_STANCE_PREPARED', json.dumps({k: v for k, v in report.items() if k not in {'movedObjects', 'fixedObjects'}}))
