"""Renders de la caja con la placa adentro (Blender 4.x, motor Workbench).

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python hardware/onboard/render_case.py

Entrada: case/board.glb (kicad-cli pcb export glb --drill-origin), case/_base-assembly.stl,
case/_lid-assembly.stl, case/_connector-ref.stl. Salida: case/render-*.png.
"""
import math, os, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.join(HERE, "case")
PCB_BOTTOM, BOARD_W, BOARD_H = 3.0, 90.0, 48.0        # coordenadas de case.py

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi

def material(name, rgb, rough=0.6, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*rgb, 1.0); m.roughness = rough; m.metallic = metal
    return m

def import_stl(path, mat):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before]
    for o in objs:
        o.data.materials.clear(); o.data.materials.append(mat)
        for p in o.data.polygons: p.use_smooth = False
    return objs

# ------------------------------------------------------------------ placa
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(CASE, "board.glb"))
board = [o for o in bpy.data.objects if o not in before]
meshes = [o for o in board if o.type == "MESH"]
lo, hi = bbox(meshes)
size = hi - lo
if size.x < 1.0:                                       # glTF en metros
    for o in board:
        if o.parent is None: o.scale *= 1000.0
    bpy.context.view_layer.update(); lo, hi = bbox(meshes); size = hi - lo
# la placa de 90 x 48: el objeto cuyo bbox XY coincide con el contorno
slab = None
for o in meshes:
    l, h = bbox([o]); s = h - l
    if abs(s.x - BOARD_W) < 1.0 and abs(s.y - BOARD_H) < 1.0:
        slab = (l, h); break
if slab is None:
    slab = (lo, Vector((lo.x + BOARD_W, lo.y + BOARD_H, lo.z + 1.6)))
    print("aviso: no encontre el cuerpo de la placa, uso el bbox total")
sl, sh = slab
shift = Vector((0.0 - sl.x, -BOARD_H - sl.y, PCB_BOTTOM - sl.z))
root = bpy.data.objects.new("board_root", None); scene.collection.objects.link(root)
for o in board:
    if o.parent is None:
        o.parent = root
root.location = shift
bpy.context.view_layer.update()
print("placa: bbox %s -> %s" % (tuple(round(v, 1) for v in bbox(meshes)[0]), tuple(round(v, 1) for v in bbox(meshes)[1])))

# ------------------------------------------------------------------- caja
m_case = material("caja", (0.05, 0.05, 0.055), 0.55)
m_conn = material("conector", (0.03, 0.03, 0.03), 0.5)
base = import_stl(os.path.join(CASE, "_base-assembly.stl"), m_case)
lid = import_stl(os.path.join(CASE, "_lid-assembly.stl"), m_case)
conn = import_stl(os.path.join(CASE, "_connector-ref.stl"), m_conn)
everything = meshes + base + lid + conn

# ------------------------------------------------------------ luz y camara
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_shadows = True; sh.show_cavity = True
sh.cavity_type = "BOTH"; sh.curvature_ridge_factor = 0.8; sh.curvature_valley_factor = 1.0
sh.shadow_intensity = 0.35; sh.show_specular_highlight = True
scene.display.render_aa = "16"
world = bpy.data.worlds.new("W"); scene.world = world; world.color = (0.86, 0.87, 0.9)
scene.render.resolution_x, scene.render.resolution_y = 2000, 1300
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam); scene.camera = cam
cam_data.lens = 60

def shoot(name, direction, objs, lid_dz=0.0, margin=1.12):
    for o in lid: o.location.z = lid_dz
    bpy.context.view_layer.update()
    lo, hi = bbox(objs); center = (lo + hi) / 2; radius = (hi - lo).length / 2
    d = Vector(direction).normalized()
    fov = 2 * math.atan(cam_data.sensor_width / (2 * cam_data.lens))
    dist = radius * margin / math.sin(fov / 2)
    cam.location = center + d * dist
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    scene.render.filepath = os.path.join(CASE, "render-%s.png" % name)
    bpy.ops.render.render(write_still=True)
    print("render", name)

shoot("assembled", (-1.0, -1.35, 0.95), everything)
shoot("open", (-1.0, -1.35, 1.1), everything, lid_dz=38.0, margin=1.05)
shoot("connector-end", (-1.0, -0.25, 0.35), everything)
shoot("rear", (1.0, 1.2, 0.8), everything)
shoot("board", (-0.9, -1.2, 1.3), meshes + conn, lid_dz=200.0)
