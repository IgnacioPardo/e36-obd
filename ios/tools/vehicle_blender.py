import bpy

def configure(samples=128):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    available = False
    for device in prefs.devices:
        device.use = device.type == 'METAL'
        available |= device.use
        print('DEVICE', device.name, device.type, device.use, flush=True)
    if not available:
        raise RuntimeError('No Metal device available for this render')
    scene.cycles.device = 'GPU'
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_min_samples = 32
    scene.cycles.adaptive_threshold = .008
    scene.cycles.use_denoising = True
    scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    scene.cycles.seed = 42
    scene.cycles.use_animated_seed = False
    scene.cycles.sample_clamp_indirect = 0
    scene.render.use_persistent_data = True
    return scene
