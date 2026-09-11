"""Renders de la caja con la placa adentro (Blender 4.x, EEVEE).

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python hardware/onboard/render_case.py

Entrada: case/board.glb (kicad-cli pcb export glb --drill-origin --subst-models), case/_base-assembly.stl,
case/_lid-assembly.stl, case/_badge-plate.stl, case/_badge-relief.stl, case/_connector-ref.stl.
Salida: case/render-*.png.
"""
import math, os
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.join(HERE, "case")
PCB_BOTTOM, BOARD_W, BOARD_H = 3.0, 90.0, 50.0        # coordenadas de case.py

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi

def material(name, rgb, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*rgb, 1.0); m.roughness = rough; m.metallic = metal
    return m

def smooth(objs, angle=0.6):
    for o in objs:
        for p in o.data.polygons: p.use_smooth = True
        try:
            with bpy.context.temp_override(object=o, selected_editable_objects=[o], active_object=o):
                bpy.ops.object.shade_smooth_by_angle(angle=angle)
        except Exception:
            pass

def import_stl(path, mat, do_smooth=True):
    if not os.path.exists(path): return []
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before]
    for o in objs:
        o.data.materials.clear(); o.data.materials.append(mat)
    if do_smooth: smooth(objs)
    return objs

# ------------------------------------------------------------------ placa
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(CASE, "board.glb"))
board = [o for o in bpy.data.objects if o not in before]
meshes = [o for o in board if o.type == "MESH"]
lo, hi = bbox(meshes)
if (hi - lo).x < 1.0:                                  # glTF en metros
    for o in board:
        if o.parent is None: o.scale *= 1000.0
    bpy.context.view_layer.update(); lo, hi = bbox(meshes)
slab = None
for o in meshes:
    l, h = bbox([o]); s = h - l
    if abs(s.x - BOARD_W) < 1.0 and abs(s.y - BOARD_H) < 1.0:
        slab = (l, h); break
if slab is None:
    slab = (lo, hi); print("aviso: no encontre el cuerpo de la placa, uso el bbox total")
sl, sh = slab
root = bpy.data.objects.new("board_root", None); scene.collection.objects.link(root)
for o in board:
    if o.parent is None: o.parent = root
root.location = Vector((0.0 - sl.x, -BOARD_H - sl.y, PCB_BOTTOM - sl.z))
bpy.context.view_layer.update()
print("placa: bbox %s -> %s" % (tuple(round(v, 1) for v in bbox(meshes)[0]), tuple(round(v, 1) for v in bbox(meshes)[1])))

# ------------------------------------------------------------------- caja
m_case = material("caja", (0.018, 0.018, 0.02), 0.42)
m_conn = material("conector", (0.012, 0.012, 0.012), 0.55)
m_plate = material("emblema_plato", (0.02, 0.02, 0.022), 0.5)   # campo negro, relieve plata
m_silver = material("emblema_relieve", (0.78, 0.78, 0.8), 0.28, 1.0)
base = import_stl(os.path.join(CASE, "_base-assembly.stl"), m_case)
lid = import_stl(os.path.join(CASE, "_lid-assembly.stl"), m_case)
conn = import_stl(os.path.join(CASE, "_connector-ref.stl"), m_conn)
badge = import_stl(os.path.join(CASE, "_badge-plate.stl"), m_plate) + import_stl(os.path.join(CASE, "_badge-relief.stl"), m_silver)
if not badge: badge = import_stl(os.path.join(CASE, "_badge-assembly.stl"), m_silver)
lid = lid + badge                                       # el emblema se levanta con la tapa
everything = meshes + base + lid + conn

# ------------------------------------------------------------ piso y luces
floor_mesh = bpy.data.meshes.new("floor"); floor_obj = bpy.data.objects.new("floor", floor_mesh)
floor_mesh.from_pydata([(-600, -600, -2.4), (600, -600, -2.4), (600, 600, -2.4), (-600, 600, -2.4)], [], [(0, 1, 2, 3)])
floor_obj.data.materials.append(material("piso", (0.42, 0.43, 0.45), 0.85)); scene.collection.objects.link(floor_obj)

def sun(name, direction, energy, angle_deg, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "SUN"); l.energy = energy; l.angle = math.radians(angle_deg); l.color = color
    o = bpy.data.objects.new(name, l); scene.collection.objects.link(o)
    d = Vector(direction).normalized(); o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()   # la luz mira hacia -Z local
    return o
sun("key", (-0.6, -0.8, 1.2), 2.8, 6.0, (1.0, 0.97, 0.92))
sun("fill", (1.0, 0.6, 0.7), 1.4, 30.0, (0.85, 0.9, 1.0))
sun("rim", (0.3, 1.0, 0.5), 1.4, 8.0)
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.55, 0.57, 0.62, 1.0); bg.inputs[1].default_value = 0.9

for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = eng; break
    except Exception:
        continue
try:
    scene.eevee.taa_render_samples = 96
    scene.eevee.use_shadows = True
    scene.eevee.use_raytracing = True
    scene.eevee.shadow_ray_count = 2; scene.eevee.shadow_step_count = 4
except Exception as exc:
    print("ajuste eevee:", exc)
try:
    scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.render.resolution_x, scene.render.resolution_y = 2000, 1300
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam); scene.camera = cam
cam_data.lens = 70

def shoot(name, direction, objs, lid_dz=0.0, margin=1.08):
    for o in lid: o.location.z = lid_dz
    bpy.context.view_layer.update()
    lo, hi = bbox(objs); center = (lo + hi) / 2; radius = (hi - lo).length / 2
    d = Vector(direction).normalized()
    fov = 2 * math.atan(cam_data.sensor_width / (2 * cam_data.lens))
    cam.location = center + d * (radius * margin / math.sin(fov / 2))
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    scene.render.filepath = os.path.join(CASE, "render-%s.png" % name)
    bpy.ops.render.render(write_still=True)
    print("render", name)

shoot("assembled", (-1.0, -1.35, 0.85), everything)
shoot("open", (-1.0, -1.35, 1.1), everything, lid_dz=38.0, margin=1.02)
shoot("connector-end", (-1.0, -0.35, 0.45), everything)
shoot("rear", (1.0, 1.2, 0.75), everything)
shoot("board", (-0.9, -1.2, 1.3), meshes + conn, lid_dz=200.0)
