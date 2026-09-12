"""Bake fixed-environment diffuse radiance and ambient visibility into a USDZ.
Run with Blender 4.5, --background --factory-startup --disable-autoexec.
The app keeps view-dependent Metal specular, clearcoat and glass reflections.
Pack the result with pack_vehicle_lighting.py; no source geometry is decimated.
"""
import bpy,sys,json,hashlib,numpy as np,time
from pathlib import Path
import argparse
R=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',type=Path,default=R/'ios/Design/Vehicle/E36-316i.usdz')
parser.add_argument('--environment',type=Path,default=R/'ios/E36OBD/VehicleScene/StudioEnvironment.exr')
parser.add_argument('--output',type=Path,default=R/'.context/vehicle-lighting')
parser.add_argument('--exposure',type=float,default=.65)
parser.add_argument('--ambient-only',action='store_true',help='Live PBR renderer only needs baked ambient visibility')
parser.add_argument('--skip-native-save',action='store_true',help='Do not write the disposable merged Blender intermediate')
parser.add_argument('--hybrid-studio',action='store_true',help='Bake diffuse for the matched live Metal studio materials')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
O=args.output.resolve();O.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vehicle_blender import configure
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=str(args.model),support_scene_instancing=True)
s=configure(96);s.cycles.adaptive_min_samples=32
s.world=bpy.data.worlds.new('Ambient bake');s.world.use_nodes=True
s.world.color=(1,1,1);s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
s.render.bake.target='VERTEX_COLORS';s.render.bake.use_clear=True;s.render.bake.use_selected_to_active=False
if args.hybrid_studio:
 for material in bpy.data.materials:
  if not material.use_nodes:continue
  shader=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
  if shader is None:continue
  key=material.name.lower().replace(' ','_')
  if key=='car_body' or 'painted_fog_intake_duct' in key:
   shader.inputs['Metallic'].default_value=.50
   shader.inputs['Roughness'].default_value=.22
   shader.inputs['Coat Weight'].default_value=1
   shader.inputs['Coat Roughness'].default_value=.055
# Merge only opaque render meshes: one bake avoids rebuilding the full BVH for
# hundreds of tiny trim pieces. Object joining preserves UVs and split normals.
objects=[o for o in s.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
opaque=[]
for o in objects:
 o.hide_set(False)
 names=[m.name.lower() for m in o.data.materials if m]
 if any('glass' in n or n=='wcwindow' or n in ['material__58','_03___default'] for n in names):continue
 o.select_set(True);opaque.append(o)
bpy.context.view_layer.objects.active=opaque[0];bpy.ops.object.join();merged=bpy.context.object;merged.name='E36 baked opaque surfaces'
selected=[merged]
ca=merged.data.color_attributes.get('displayColor') or merged.data.color_attributes.new(name='displayColor',type='FLOAT_COLOR',domain='POINT')
merged.data.color_attributes.active_color=ca;merged.data.color_attributes.render_color_index=list(merged.data.color_attributes).index(ca)
s.world.light_settings.distance=.8
print('BAKE_START',len(selected),len(merged.data.vertices),flush=True)
t=time.monotonic();bpy.ops.object.bake(type='AO',target='VERTEX_COLORS',use_clear=True)
ao=np.empty(len(ca.data)*4,dtype=np.float32);ca.data.foreach_get('color',ao);ao=ao.reshape(-1,4)[:,0].copy()
print('AO_FINISHED',time.monotonic()-t,flush=True)
# Fixed studio illumination is ray traced into the diffuse vertex channel;
# view-dependent specular and clearcoat are still evaluated by Metal at runtime.
world=s.world;nodes=world.node_tree.nodes;links=world.node_tree.links
tex=nodes.new('ShaderNodeTexEnvironment');tex.image=bpy.data.images.load(str(args.environment));links.new(tex.outputs[0],nodes['Background'].inputs['Color']);nodes['Background'].inputs['Strength'].default_value=2**args.exposure
# Restore the source dashboard albedo graph omitted by USD Preview Surface.
for m in merged.data.materials:
 if not m or m.name.lower()!='interior_dash_plastic':continue
 n=m.node_tree.nodes;l=m.node_tree.links;p=next(n for n in n if n.type=='BSDF_PRINCIPLED');inp=p.inputs['Base Color']
 if inp.is_linked:
  source=inp.links[0].from_socket;mul=n.new('ShaderNodeMixRGB');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1;mul.inputs[2].default_value=(.025,.030,.036,1);l.new(source,mul.inputs[1]);l.new(mul.outputs[0],inp)
bpy.ops.mesh.primitive_plane_add(size=8,location=(0,0,-.003));ground=bpy.context.object;ground.data.materials.append(bpy.data.materials.new('Studio matte ground'));ground.data.materials[0].diffuse_color=(.12,.13,.15,1) if args.hybrid_studio else (.008,.008,.008,1)
bpy.ops.object.select_all(action='DESELECT');merged.select_set(True);bpy.context.view_layer.objects.active=merged
if not args.ambient_only:
 s.cycles.samples=192
 bpy.ops.object.bake(type='DIFFUSE',pass_filter={'DIRECT','INDIRECT','COLOR'},target='VERTEX_COLORS',use_clear=True)
gi=np.zeros((len(ca.data),4),dtype=np.float32)
if not args.ambient_only:ca.data.foreach_get('color',gi.ravel())
if gi[:,:3].max()>4:raise RuntimeError('Diffuse radiance exceeds the encoded HDR range')
gi[:,:3]=np.sqrt(np.maximum(gi[:,:3],0)/4);gi[:,3]=np.maximum(ao,.035);ca.data.foreach_set('color',gi.ravel());bpy.data.objects.remove(ground,do_unlink=True)
np.save(O/'radiance-rgba.npy',gi)
print('GI_FINISHED',time.monotonic()-t,flush=True)
report={'sourceSHA256':hashlib.sha256((args.model).read_bytes()).hexdigest(),'occlusionSamples':96,'diffuseSamples':192,'type':'diffuse_radiance_RGB_ambient_visibility_A','diffuseEncoding':'sqrt(linear / 4)','environmentIntensityExponent':args.exposure,'environmentSHA256':hashlib.sha256((args.environment).read_bytes()).hexdigest(),'meshes':[]}
report['diffuseSamples']=0 if args.ambient_only else 192
report['liveEnvironmentLighting']=args.ambient_only
report['studioDiffuse']=args.hybrid_studio and not args.ambient_only
for o in selected:
 ca=o.data.color_attributes.active_color;a=np.empty(len(ca.data)*4,dtype=np.float32);ca.data.foreach_get('color',a);a=a.reshape(-1,4)
 if not np.isfinite(a).all():raise RuntimeError('Nonfinite bake')
 report['meshes'].append({'name':o.name,'vertices':len(o.data.vertices),'minimum':float(a[:,:3].min()),'mean':float(a[:,:3].mean()),'maximum':float(a[:,:3].max())})
 # Preserve a modest light floor, avoiding completely black fabric/recesses.
 ca.data.foreach_set('color',a.ravel())
print('BAKE_FINISHED',time.monotonic()-t,flush=True)
if not args.skip_native_save:bpy.ops.wm.save_as_mainfile(filepath=str(O/'RuntimeOcclusion.blend'),compress=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.usd_export(filepath=str(O/'E36-316i.usdz'),selected_objects_only=True,export_materials=True,export_textures=True,overwrite_textures=True,generate_preview_surface=True,export_mesh_colors=True,export_custom_properties=False,export_lights=False,export_cameras=False,triangulate_meshes=True,use_instancing=True)
report['outputSHA256']=hashlib.sha256((O/'E36-316i.usdz').read_bytes()).hexdigest();report['outputBytes']=(O/'E36-316i.usdz').stat().st_size;report['seconds']=time.monotonic()-t
(O/'bake-report.json').write_text(json.dumps(report,indent=2)+'\n');print('OCCLUSION_EXPORT_COMPLETE',flush=True)
