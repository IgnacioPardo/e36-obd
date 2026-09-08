"""Render the actual exported scene meshes with Blender, no external assets.

/Applications/Blender.app/Contents/MacOS/Blender -b -t 6 --python render.py
"""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OUT = HERE / 'exports'
scene_data = json.loads((OUT / 'scene.json').read_text())
inline = scene_data['parameters'].get('layout') == 'inline'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 40
scene.cycles.use_denoising = True
scene.render.resolution_x = 1400
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.world.use_nodes=True
world_bg=scene.world.node_tree.nodes.get('Background')
world_bg.inputs['Color'].default_value=(0.08,0.08,0.08,1)
world_bg.inputs['Strength'].default_value=0.3
scene.view_settings.view_transform = 'AgX'
scene.view_settings.exposure = 0
objects = []
materials = {}

def material(hex_color, metallic=0):
    key = (hex_color, metallic)
    if key not in materials:
        m = bpy.data.materials.new(hex_color)
        m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        srgb = tuple(int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5))
        rgb = tuple(c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4 for c in srgb)
        bs.inputs['Base Color'].default_value = (*rgb, 1)
        bs.inputs['Roughness'].default_value = 0.35 if metallic else 0.57
        bs.inputs['Metallic'].default_value = metallic
        if hex_color in ('#101112','#080909','#141619','#1b1d1f','#252728','#292c32','#161b22'):
            bs.inputs['Roughness'].default_value=0.5
            bs.inputs['Specular IOR Level'].default_value=0.22
            noise=m.node_tree.nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value=350
            noise.inputs['Detail'].default_value=2
            bump=m.node_tree.nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value=0.16
            bump.inputs['Distance'].default_value=0.000045
            m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height'])
            m.node_tree.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
        materials[key] = m
    return materials[key]

for item in scene_data['parts']:
    mesh = bpy.data.meshes.new(item['name'])
    mesh.from_pydata([[v / 1000 for v in p] for p in item['vertices']], [], item['triangles'])
    mesh.update()
    obj = bpy.data.objects.new(item['name'], mesh)
    bpy.context.collection.objects.link(obj)
    metal = 0.7 if any(s in item['name'].lower() for s in ('screw', 'shield', 'usb', 'pin', 'capacitor')) else 0
    if item['group']=='lid_finish': metal=0.55
    obj.data.materials.append(material(item['color'], metal))
    objects.append((obj, item['group']))

# A small service loop depicts the user harness route. Illustrative only.
def wire(name, coords, color, radius=0.00065):
    c = bpy.data.curves.new(name, 'CURVE')
    c.dimensions = '3D'
    c.bevel_depth, c.bevel_resolution, c.resolution_u = radius, 3, 12
    sp = c.splines.new('BEZIER')
    sp.bezier_points.add(len(coords)-1)
    for bp, co in zip(sp.bezier_points, coords):
        bp.co = [v / 1000 for v in co]
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    o = bpy.data.objects.new(name, c)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material(color))
    objects.append((o, 'illustrative_wires'))

for dx, color in ((-0.8, '#9264cd'), (0, '#e0dccd'), (0.8, '#393842')):
    if inline:
        wire('Illustrative tail harness',[(dx,-3,-16),(dx-5,4,-9),
             (dx-9,6,0),(dx-7,7,7),(dx+11,6,8.5),
             (dx+12.7,20,5.5),(dx+12.7,37.96,5.9)],color,0.00045)
    else:
        wire('Illustrative tail harness', [(dx, 23, -16), (dx-5, 34, -9),
             (dx-12, 40, 0), (dx-9, 35, 6), (dx, 25, 8.5),
             (dx+5.3, 30, 5.5), (dx+5.3, 38.46, 5.9)], color)

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.053))
ground = bpy.context.object
ground.name = 'Ground'
ground.data.materials.append(material('#92979a'))

def area(name, location, energy, size):
    light = bpy.data.lights.new(name, 'AREA')
    light.energy, light.shape, light.size = energy, 'DISK', size
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((0, 0, 0.025))-obj.location).to_track_quat('-Z', 'Y').to_euler()

area('Key', (0.12, -0.18, 0.35), 0.8, 0.18)
area('Fill', (-0.23, -0.08, 0.16), 0.18, 0.28)
area('Rim', (0.05, 0.20, 0.30), 0.9, 0.12)
bpy.ops.object.camera_add()
camera = bpy.context.object
camera.data.type = 'ORTHO'
camera.data.lens = 50
scene.camera = camera

def render_standard_views():
    views = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['assembled', 'interior', 'exploded','black']
    assert all(v in ('assembled', 'interior', 'exploded','black') for v in views)
    for view in views:
        elm_bottom=-(scene_data['parameters']['mounting_pad_thickness']+
                     scene_data['parameters']['elm_body_height_reference'])/1000
        ground.location.z=elm_bottom+((-0.050 if inline else -0.020) if view=='exploded' else (0 if view=='interior' else -0.001))
        for obj, group in objects:
            obj.location.z = 0
            obj.hide_render = False
            if view == 'interior' and group in ('lid', 'lid_finish', 'lid_hardware','base_hardware'):
                obj.hide_render = True
            if view=='interior' and not inline and group=='straps': obj.hide_render=True
            if view=='black' and group=='lid_finish': obj.hide_render=True
            if view == 'exploded':
                lift = {'lid': 0.073, 'lid_finish':0.073, 'lid_hardware': 0.089, 'keeper': 0.038,
                        'keeper_hardware': 0.053, 'electronics': 0.019,
                        'pads': 0.019, 'elm': -0.020, 'mount': -0.009}
                if inline:
                    lift={'lid':.055,'lid_finish':.055,'base_hardware':-.030,'keeper':.028,
                          'keeper_hardware':.040,'electronics':.018,'pads':.018,'elm':-.050,'mount':-.032}
                obj.location.z = lift.get(group, 0)
                if group in ('straps', 'esp_tie', 'illustrative_wires'):
                    obj.hide_render = True
        target = Vector((0, -0.007, 0.038 if view == 'exploded' else 0.004))
        camera.location = (0.22, 0.31, 0.37 if view != 'interior' else 0.55)
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = 0.270 if view == 'exploded' else 0.198
        if inline:
            target=Vector((0,-.006,.010 if view=='exploded' else .001))
            camera.location=(.36,.22,.34 if view!='interior' else .62)
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=.295 if view=='exploded' else .215
        scene.render.filepath = str(OUT / (view + '.png'))
        bpy.ops.render.render(write_still=True)
        print('Rendered', view, flush=True)


if __name__ == '__main__':
    render_standard_views()
