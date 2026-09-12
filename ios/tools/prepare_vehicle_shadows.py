"""Render matched contact shadows for the final app stance under both IBLs.
Blender --background --python ... -- --model path.usdz --output directory
"""
import argparse, bpy, sys, numpy as np
from pathlib import Path
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
from vehicle_blender import configure
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=str(args.model), support_scene_instancing=True)
scene = configure(64)
for obj in scene.objects:
    if obj.type == 'MESH': obj.visible_camera = False
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, -.003))
floor = bpy.context.object
floor.is_shadow_catcher = True
material = bpy.data.materials.new('Neutral shadow receiver')
material.diffuse_color = (.5, .5, .5, 1)
floor.data.materials.append(material)
bpy.ops.object.camera_add(location=(0, 0, 10))
camera = bpy.context.object
camera.data.type = 'ORTHO'; camera.data.ortho_scale = 8
scene.camera = camera
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.world = bpy.data.worlds.new('Matched IBL')
scene.world.use_nodes = True
nodes = scene.world.node_tree.nodes
texture = nodes.new('ShaderNodeTexEnvironment')
scene.world.node_tree.links.new(texture.outputs[0], nodes['Background'].inputs[0])
args.output.mkdir(parents=True, exist_ok=True)
for name, source, exposure in [
    ('ContactShadow', root / 'E36OBD/VehicleScene/StudioEnvironment.exr', .15),
    ('SoftboxShadow', root / 'Design/Vehicle/SoftboxEnvironment.exr', 0),
]:
    extent = 20 if name == 'SoftboxShadow' else 8
    floor.scale = (extent / 8, extent / 8, 1)
    camera.data.ortho_scale = extent
    scene.render.resolution_x = scene.render.resolution_y = 1536 if name == 'SoftboxShadow' else 1024
    texture.image = bpy.data.images.load(str(source))
    nodes['Background'].inputs[1].default_value = 2 ** exposure
    scene.render.filepath = str(args.output / (name + '.png'))
    bpy.ops.render.render(write_still=True)
    # Studio illumination casts faint shadows beyond an 8 m catcher. Keep
    # its far boundary outside the car and fade that boundary smoothly.
    # This texture contains shadow opacity only, never vehicle pixels.
    if name == 'SoftboxShadow':
        image = bpy.data.images.load(scene.render.filepath)
        width,height = image.size
        pixels = np.empty(width*height*4,dtype=np.float32)
        image.pixels.foreach_get(pixels);pixels=pixels.reshape(height,width,4)
        yy,xx=np.mgrid[:height,:width]
        edge=np.maximum(abs((xx+.5)/width*2-1),abs((yy+.5)/height*2-1))
        t=np.clip((edge-.85)/.15,0,1)
        pixels[:,:,3] *= 1-t*t*(3-2*t)
        image.pixels.foreach_set(pixels.ravel());image.save()
    print('SHADOW_COMPLETE', name, flush=True)
