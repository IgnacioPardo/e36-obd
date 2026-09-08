"""Four exploded views of revision E from its actual CAD meshes.

Blender -b --factory-startup -t 6 --python render_exploded.py
Optional view names after --: assembly reverse underside mounts.
Then run build_exploded_gallery.py with the CAD Python/Pillow environment.
"""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import render as R

OUT=HERE/'exports'/'exploded-views';OUT.mkdir(parents=True,exist_ok=True)
assert R.inline, 'These views are composed for the approved inline revision.'
scene=R.scene;camera=R.camera
scene.render.resolution_x=2400
scene.render.resolution_y=2000
scene.cycles.samples=48
scene.render.film_transparent=True
R.ground.hide_render=True
scene.render.image_settings.color_mode='RGBA'
# Prefer the locally available Metal device; fall back to CPU where unavailable.
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='METAL';prefs.get_devices()
    gpu=[d for d in prefs.devices if d.type=='METAL']
    if gpu:
        for d in prefs.devices:d.use=d.type=='METAL'
        scene.cycles.device='GPU'
        print('Rendering with',gpu[0].name,flush=True)
except (TypeError,ValueError):
    scene.cycles.device='CPU'
# Side and underside fill keep the black wall and screw detail legible.
R.area('Lower inspection fill',(.13,.02,-.30),.48,.25)
R.area('Back inspection fill',(-.23,.15,.18),.48,.22)

LIFTS={'base':0,'lid':.085,'lid_finish':.085,'electronics':.038,
       'keeper':.059,'keeper_hardware':.077,'pads':.0375,
       'base_hardware':-.036,'mount':-.054,'elm':-.098}
SPECS={
 'assembly':dict(title='Exploded assembly',subtitle='Lid, complete boards, base and ELM mounting stack',
                 camera=(.37,.21,.26),target=(0,-.004,.010),scale=.340),
 'reverse':dict(title='OBD end / opposite corner',subtitle='Converter retention and the original adapter beneath',
                camera=(.34,-.28,.25),target=(0,-.006,0),scale=.380),
 'underside':dict(title='Underside / hidden fasteners',subtitle='Four lid screws enter through the bottom of the case',
                  camera=(.34,.23,-.36),target=(0,0,.01),scale=.300),
 'mounts':dict(title='Board mounts / retention',subtitle='Buck keepers, ESP seats, floor entry and tie positions',
               camera=(.25,.14,.49),target=(0,0,.028),scale=.246),
}
requested=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(SPECS)
assert all(v in SPECS for v in requested)

for view in requested:
    spec=SPECS[view]
    bpy.data.lights['Lower inspection fill'].energy=1.4 if view=='underside' else .48
    for obj,group in R.objects:
        obj.location=(0,0,LIFTS.get(group,0))
        obj.hide_render=group in ('straps','esp_tie','illustrative_wires')
        if group=='pads':
            # Lower supports float between the board and their moulded seats;
            # upper keeper-toe pads remain paired with the lifted keepers.
            obj.location.z=.0585 if 'toe' in obj.name else .026
        if view=='underside':
            obj.hide_render=group not in ('base','lid','lid_finish','base_hardware')
            obj.location.z={'base':0,'lid':.080,'lid_finish':.080,'base_hardware':-.046}.get(group,0)
            if group in ('lid','lid_finish'):obj.location.x=-.065
        if view=='mounts':
            obj.hide_render=group in ('lid','lid_finish','elm','mount','base_hardware',
                                     'straps','esp_tie','illustrative_wires')
            # Spread complete PCB assemblies to either side so the base seats,
            # wire entry and retaining slots can actually be seen from above.
            if group=='electronics':obj.location.x=-.035 if 'buck' in obj.name.lower() or 'terminal' in obj.name.lower() else .035
            if group in ('keeper','keeper_hardware'):obj.location.x=-.035
            if group=='pads':
                obj.location.x=-.035 if obj.data.vertices and abs(obj.data.vertices[0].co.x)>.008 else .035
    # Leaders use true projected model coordinates, recorded with each view.
    guides=[]
    def leader_path(name,coords):
        R.wire(name,coords,'#778993',radius=.00014)
        guide=R.objects[-1][0];guide.hide_render=False;guides.append(guide)
    if view in ('assembly','reverse'):
        for x,y in ((-19,75.6),(19,-75.6)):
            # Small interrupted axis marks, not fictitious threaded rods.
            for z in range(30,99,7):leader_path('Assembly guide',[(x,y,z),(x,y,z+3)])
    camera.location=spec['camera']
    camera.rotation_euler=(Vector(spec['target'])-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=spec['scale']
    bpy.context.view_layer.update()
    anchors={
      'lid':(0,0,.1154),'buck':(0,-.032,.051),'esp':(0,.0455,.049),
      'base':(.023,0,.020),'elm':(0,-.042,-.11),
      'screw':(.019,.0756,-.035),
    }
    projected={k:list(world_to_camera_view(scene,camera,Vector(v)))[:2] for k,v in anchors.items()}
    # Keep the source hashes with the renders to identify the exact geometry.
    import hashlib
    meta={**spec,'view':view,'projected_anchors':projected,'source_scene_sha256':hashlib.sha256((HERE/'exports/scene.json').read_bytes()).hexdigest(),
          'dimensions_mm':[162,48,30.4],'explosion':'Display offsets only; printed geometry is unchanged.'}
    (OUT/(view+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
    scene.render.filepath=str(OUT/(view+'-raw.png'))
    bpy.ops.render.render(write_still=True)
    for obj in guides:obj.hide_render=True
    print('Rendered exploded view:',view,flush=True)
