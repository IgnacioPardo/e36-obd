"""Lossless vertex reindexing of the baked USD, plus its opacity channel.
Discard unused UV sets; preserve positions, every split normal and active UV.
"""
from pxr import Usd,UsdGeom,UsdShade,Sdf,Vt,UsdUtils
from pathlib import Path
import numpy as np,zipfile,json,hashlib,time,gc
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path,help='Output folder from bake_vehicle_lighting.py')
args=parser.parse_args()
O=args.directory.resolve();D=O/'unpacked';D.mkdir(exist_ok=True)
report=json.loads((O/'bake-report.json').read_text())
if report['type']!='diffuse_radiance_RGB_ambient_visibility_A' or report.get('diffuseEncoding')!='sqrt(linear / 4)':raise RuntimeError('Wrong bake encoding')
with zipfile.ZipFile(O/'E36-316i.usdz') as z:z.extractall(D);root=z.namelist()[0]
s=Usd.Stage.Open(str(D/root));prim=next(p for p in s.Traverse() if p.IsA(UsdGeom.Mesh) and len(UsdGeom.Mesh(p).GetPointsAttr().Get())>2_000_000);m=UsdGeom.Mesh(prim);pv=UsdGeom.PrimvarsAPI(prim)
a=np.load(O/'radiance-rgba.npy');points=np.asarray(m.GetPointsAttr().Get());ids=np.asarray(m.GetFaceVertexIndicesAttr().Get());normals=np.asarray(m.GetNormalsAttr().Get());st=pv.GetPrimvar('st');uv=np.array(st.ComputeFlattened())
if len(a)!=len(points) or len(normals)!=len(ids) or len(uv)!=len(ids):raise RuntimeError('Vertex channel mismatch')
print('REINDEX_START',len(points),len(ids),flush=True);start=time.monotonic()
key=np.empty((len(ids),6),dtype=np.uint32);key[:,0]=ids;key[:,1:4]=normals.view(np.uint32);key[:,4:6]=uv.view(np.uint32)
record=key.view(np.dtype([(str(i),'u4') for i in range(6)])).ravel();unique,first,inverse=np.unique(record,return_index=True,return_inverse=True);old=key[first,0].copy();del unique,record,key;gc.collect()
print('REINDEX_UNIQUE',len(old),time.monotonic()-start,flush=True)
# Exact corner reconstruction checks prove split normals and UV seams survived.
if not np.array_equal(normals[first][inverse],normals):raise RuntimeError('Normals changed')
if not np.array_equal(uv[first][inverse],uv):raise RuntimeError('UVs changed')
if not np.array_equal(points[old][inverse],points[ids]):raise RuntimeError('Positions changed')
m.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(points[old].copy()));m.GetFaceVertexIndicesAttr().Set(Vt.IntArray.FromNumpy(inverse.astype(np.int32)));m.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(normals[first].copy()));m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
st.Set(Vt.Vec2fArray.FromNumpy(uv[first].copy()));st.SetInterpolation(UsdGeom.Tokens.vertex);st.BlockIndices()
for x in list(pv.GetPrimvars()):
 if x.GetTypeName()==Sdf.ValueTypeNames.TexCoord2fArray and x.GetPrimvarName()!='st':prim.RemoveProperty(x.GetName());prim.RemoveProperty(str(x.GetName())+':indices')
pv.GetPrimvar('displayColor').Set(Vt.Vec3fArray.FromNumpy(a[old,:3].copy()))
pv.CreatePrimvar('displayOpacity',Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.vertex).Set(Vt.FloatArray.FromNumpy(a[old,3].copy()))
for p in s.Traverse():
 if p.IsA(UsdShade.Shader):
  v=UsdShade.Shader(p).GetInput('varname')
  if v:v.Set('st')
compact=D/'E36-Lighting.usdc';s.GetRootLayer().Export(str(compact));out=O/'E36-Baked.usdz'
if out.exists():out.unlink()
if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(compact)),str(out)):raise RuntimeError('USDZ packaging failed')
report.update(runtimeSHA256=hashlib.sha256(out.read_bytes()).hexdigest(),runtimeBytes=out.stat().st_size,packedVertices=len(old),corners=len(ids),reindexPreservesPositionsNormalsUVs=True)
(O/'bake-report.json').write_text(json.dumps(report,indent=2)+'\n');print('RUNTIME_USDZ',report['runtimeBytes'],report['runtimeSHA256'],flush=True)
