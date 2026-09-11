"""Export the portable GLB and USDZ without altering the editable Cycles scene.

blender --background --factory-startup --disable-autoexec \
  ios/Design/Vehicle/E36-316i.blend --python ios/tools/export_vehicle.py

The native Blender file retains optical glass and procedural finish shaders.
Portable exports use PBR glass approximations and a baked tyre normal map.
No decimation is applied to the repaired coachwork or cast wheel surfaces.
"""
import argparse
import json
import math
import re
import shutil
import sys
import struct
import tempfile
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'ios/Design/Vehicle')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = args.output.resolve()
TEXTURES = Path(tempfile.mkdtemp(prefix='e36-vehicle-textures-'))
if not bpy.data.filepath or Path(bpy.data.filepath).name != 'E36-316i.blend':
    raise RuntimeError('Open the finished E36-316i.blend before exporting.')
scene = bpy.context.scene
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'METAL'
    scene.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
except Exception as error:
    print(f'Metal unavailable; CPU bake: {error}', flush=True)
    scene.cycles.device = 'CPU'
vehicle = bpy.data.collections.get('Vehicle')
if vehicle is None:
    raise RuntimeError('The finished scene must contain the Vehicle collection.')
objects = [o for o in vehicle.all_objects if o.type in {'MESH', 'FONT', 'CURVE'} and not o.hide_render]

# USD instancing of converted curves can create a self-reference beneath the
# original curve prim. Evaluate the raised badge into a real mesh first.
depsgraph = bpy.context.evaluated_depsgraph_get()
for obj in objects:
    if obj.type in {'CURVE', 'FONT'}:
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),
                                               preserve_all_data_layers=True,
                                               depsgraph=depsgraph)
        replacement = bpy.data.objects.new(obj.name + ' mesh', mesh)
        replacement.matrix_world = obj.matrix_world.copy()
        for collection in obj.users_collection:
            collection.objects.link(replacement)
        objects[objects.index(obj)] = replacement
        bpy.data.objects.remove(obj, do_unlink=True)

# Give the rocker finish a real material boundary. It previously used a world-Z
# shader mask, which a portable PBR exporter cannot express.
body = bpy.data.objects['e36_limo_body_color']
depsgraph = bpy.context.evaluated_depsgraph_get()
body.data = bpy.data.meshes.new_from_object(body.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
body.modifiers.clear()
paint = bpy.data.materials['car_body']
dark = bpy.data.materials.new('Factory dark rocker PBR')
dark.use_nodes = True
p = dark.node_tree.nodes.get('Principled BSDF')
p.inputs['Base Color'].default_value = (.010, .013, .016, 1)
p.inputs['Roughness'].default_value = .57
body.data.materials.clear()
body.data.materials.append(paint)
body.data.materials.append(dark)
bm = bmesh.new()
bm.from_mesh(body.data)
bm.transform(body.matrix_world)
bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                      dist=.000001, plane_co=(0, 0, .329), plane_no=(0, 0, 1))
for face in bm.faces:
    face.material_index = 1 if face.calc_center_median().z < .329 else 0
bm.transform(body.matrix_world.inverted())
bm.to_mesh(body.data)
bm.free()

# The lower rear insert is a central rectangle with short bevelled upper
# corners. Its shader mask must not turn the blue corner returns charcoal.
# Split the portable material boundary in world space, retaining the full mesh.
rear = bpy.data.objects['e36_bumper_rear_stock_SUB3']
rear_finish = rear.data.materials[0]
if rear_finish.name == 'Rear paint and factory charcoal apron':
    depsgraph = bpy.context.evaluated_depsgraph_get()
    rear.data = bpy.data.meshes.new_from_object(rear.evaluated_get(depsgraph),
                                               preserve_all_data_layers=True,
                                               depsgraph=depsgraph)
    rear.modifiers.clear()
    insert = bpy.data.materials.new('Factory rear central insert PBR')
    insert.use_nodes = True
    p = insert.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (.012, .014, .017, 1)
    p.inputs['Roughness'].default_value = .60
    rear.data.materials.clear()
    rear.data.materials.append(paint)
    rear.data.materials.append(insert)
    bm = bmesh.new()
    bm.from_mesh(rear.data)
    bm.transform(rear.matrix_world)
    bevel = .025 / .034
    planes = [((0, 0, .419), (0, 0, 1)),
              ((0, 2.0, 0), (0, 1, 0)),
              ((.620, 0, 0), (1, 0, 0)),
              ((-.620, 0, 0), (1, 0, 0)),
              ((.620, 0, .385), (1, 0, bevel)),
              ((-.620, 0, .385), (-1, 0, bevel))]
    for origin, normal in planes:
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                              dist=.000001, plane_co=origin, plane_no=normal)
    for face in bm.faces:
        center = face.calc_center_median()
        half_width = .620 - max(center.z - .385, 0) * bevel
        face.material_index = int(center.z < .419 and center.y > 2.0
                                  and abs(center.x) < half_width)
    bm.transform(rear.matrix_world.inverted())
    bm.to_mesh(rear.data)
    bm.free()

# Bake both the moulded sidewall and the tread into one portable tangent map.
# Explicit input UV layers keep the authored shader mapping unchanged during the bake.
tyres = [o for o in objects if o.name.startswith('Road tyre continuous casing')]
if tyres:
    tyre = tyres[0]
    mesh = tyre.data
    uv = mesh.uv_layers.new(name='Portable tyre normal')
    ring_size = 720
    ring_count = len(mesh.vertices) // ring_size
    if ring_count * ring_size != len(mesh.vertices):
        raise RuntimeError('Unexpected tyre topology; update the normal bake UV layout.')
    for face in mesh.polygons:
        ids = [mesh.loops[li].vertex_index for li in face.loop_indices]
        rings = [vi // ring_size for vi in ids]
        angles = [(vi % ring_size) / ring_size for vi in ids]
        angular_seam = max(angles) - min(angles) > .5
        profile_seam = max(rings) - min(rings) > ring_count / 2
        for li, ring, angle in zip(face.loop_indices, rings, angles):
            if angular_seam and angle < .5:
                angle += 1
            if profile_seam and ring == 0:
                ring = ring_count
            uv.data[li].uv = (angle, ring / ring_count)
    mesh.uv_layers.active = uv
    uv.active_render = True
    normal = bpy.data.images.new('E36 tyre relief baked', width=2048, height=2048, alpha=False)
    normal.colorspace_settings.name = 'Non-Color'
    material = mesh.materials[0]
    native_rubber = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    rubber_color = tuple(native_rubber.inputs['Base Color'].default_value)
    rubber_roughness = native_rubber.inputs['Roughness'].default_value
    rubber_specular = native_rubber.inputs['Specular IOR Level'].default_value
    target = material.node_tree.nodes.new('ShaderNodeTexImage')
    target.image = normal
    material.node_tree.nodes.active = target
    bpy.ops.object.select_all(action='DESELECT')
    tyre.hide_set(False)
    tyre.select_set(True)
    bpy.context.view_layer.objects.active = tyre
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.render.bake.margin = 12
    scene.render.bake.use_selected_to_active = False
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
    normal.filepath_raw = str(TEXTURES / 'e36-tyre-normal.png')
    normal.file_format = 'PNG'
    normal.save()
    normal.pack()
    n, links = material.node_tree.nodes, material.node_tree.links
    n.clear()
    p = n.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = rubber_color
    p.inputs['Roughness'].default_value = rubber_roughness
    p.inputs['Specular IOR Level'].default_value = rubber_specular
    tx = n.new('ShaderNodeTexImage')
    tx.image = normal
    coord = n.new('ShaderNodeUVMap')
    coord.uv_map = uv.name
    nm = n.new('ShaderNodeNormalMap')
    nm.uv_map = uv.name
    output = n.new('ShaderNodeOutputMaterial')
    links.new(coord.outputs[0], tx.inputs[0])
    links.new(tx.outputs[0], nm.inputs['Color'])
    links.new(nm.outputs[0], p.inputs['Normal'])
    links.new(p.outputs[0], output.inputs[0])

# Flatten thin optical interface graphs to explicitly supported PBR controls.
# This is an interchange approximation; HD renders use the native shaders.
materials = {m for o in objects for m in o.data.materials if m}
for material in materials:
    if not material.use_nodes:
        continue
    nodes, links = material.node_tree.nodes, material.node_tree.links
    output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if output is None or not output.inputs['Surface'].links:
        continue
    root = output.inputs['Surface'].links[0].from_node
    if root.type == 'BSDF_PRINCIPLED':
        continue
    p = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if p is None:
        p = nodes.new('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = (.07, .105, .09, 1) if material.name == 'WCWINDOW' else (.8, .85, .88, 1)
        p.inputs['Alpha'].default_value = .24 if material.name == 'WCWINDOW' else .12
        p.inputs['Metallic'].default_value = .10
        p.inputs['Roughness'].default_value = .075
    links.new(p.outputs[0], output.inputs['Surface'])

# Package actual PNG data rather than relabelling a packed DDS path.
images = {}
for material in materials:
    if not material.use_nodes:
        continue
    for node in material.node_tree.nodes:
        if node.type != 'TEX_IMAGE' or node.image is None:
            continue
        original = node.image
        if original.name not in images:
            if original.size[0] == 0:
                raise RuntimeError(f'Missing texture: {original.name}')
            color_space = original.colorspace_settings.name
            if max(original.size) > 2048:
                scale = 2048 / max(original.size)
                original.scale(round(original.size[0] * scale), round(original.size[1] * scale))
            filename = re.sub(r'[^a-zA-Z0-9_-]', '_', original.name) + '.png'
            path = TEXTURES / filename
            original.filepath_raw = str(path)
            original.file_format = 'PNG'
            original.save()
            replacement = bpy.data.images.load(str(path), check_existing=False)
            replacement.colorspace_settings.name = color_space
            replacement.pack()
            images[original.name] = replacement
        node.image = images[original.name]

# Shared wheel meshes remain instanced. Avoid a decimator that changes highlights
# and reintroduces slivers on the casting's rounded openings.
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:
    obj.hide_set(False)
    obj.select_set(True)
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'E36-316i.glb'), export_format='GLB',
                          use_selection=True, export_apply=True, export_animations=False,
                          export_cameras=False, export_lights=False, export_yup=True,
                          export_copyright='Sedan: MacedoSTI / Base Model: (ac by Mats). '
                          'Tyre normal derivative: Nothing Software, CC BY-NC 4.0. '
                          'Owner-supplied E36.blend and reference photographs. '
                          'Full sources and modifications: accompanying CREDITS.md.')
# Blender 4.5 exports the AO image but drops this MixRGB albedo multiplier.
# Preserve it explicitly in glTF's standard baseColorFactor; binary buffer
# offsets remain relative to the untouched BIN chunk.
color_factors = {}
for material in materials:
    if not material.use_nodes:
        continue
    tint = material.node_tree.nodes.get('Charcoal albedo beneath baked ambient occlusion')
    if tint:
        color_factors[material.name] = list(tint.inputs[2].default_value[:3])
if color_factors:
    path = OUT / 'E36-316i.glb'
    data = path.read_bytes()
    length, kind = struct.unpack_from('<I4s', data, 12)
    if kind != b'JSON':
        raise RuntimeError('Expected the glTF JSON chunk first.')
    document = json.loads(data[20:20 + length])
    for material in document['materials']:
        if material.get('name') in color_factors:
            pbr = material.setdefault('pbrMetallicRoughness', {})
            alpha = pbr.get('baseColorFactor', [1, 1, 1, 1])[3]
            pbr['baseColorFactor'] = color_factors[material['name']] + [alpha]
    payload = json.dumps(document, separators=(',', ':')).encode()
    payload += b' ' * (-len(payload) % 4)
    remainder = data[20 + length:]
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, 20 + len(payload) + len(remainder))
                     + struct.pack('<I4s', len(payload), b'JSON') + payload + remainder)
# USD Preview Surface has opacity but does not preserve Principled transmission.
# Leaving a clear lens at alpha=1 produces four opaque white discs in Quick Look.
for material in materials:
    if not material.use_nodes:
        continue
    for p in material.node_tree.nodes:
        if p.type == 'BSDF_PRINCIPLED' and p.inputs['Transmission Weight'].default_value > .5:
            p.inputs['Alpha'].default_value = .12
            p.inputs['Transmission Weight'].default_value = 0
            p.inputs['Base Color'].default_value = (.70, .78, .80, 1)
            p.inputs['Metallic'].default_value = .05
bpy.ops.wm.usd_export(filepath=str(OUT / 'E36-316i.usdz'), selected_objects_only=True,
                      export_materials=True, export_textures=True, overwrite_textures=True,
                      generate_preview_surface=True, convert_orientation=True,
                      export_global_up_selection='Y', export_global_forward_selection='NEGATIVE_Z',
                      export_custom_properties=False, export_lights=False, export_cameras=False,
                      triangulate_meshes=True, use_instancing=True)
print('PORTABLE EXPORTS COMPLETE', flush=True)
shutil.rmtree(TEXTURES)
