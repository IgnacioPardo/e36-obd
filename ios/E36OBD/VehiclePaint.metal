#include <metal_stdlib>
#include <RealityKit/RealityKit.h>
using namespace metal;

struct E36DisplayVertex { float4 position [[position]]; float2 uv; };

vertex E36DisplayVertex e36DisplayVertex(uint id [[vertex_id]]) {
    float2 uv = float2((id << 1) & 2, id & 2);
    return {float4(uv * float2(2, -2) + float2(-1, 1), 0, 1), uv};
}

fragment half4 e36PhotographicDisplay(E36DisplayVertex in [[stage_in]],
    texture2d<half> hdr [[texture(0)]], texture3d<half> display [[texture(1)]],
    constant uint &transparentExport [[buffer(0)]], constant float4 &stageBackdrop [[buffer(1)]]) {
    constexpr sampler linearSampler(coord::normalized, address::clamp_to_edge, filter::linear);
    // Resolve radiance before the nonlinear display transform. Four taps
    // suppress subpixel specular breakup without temporal trails.
    float2 pixel = 0.375f / float2(hdr.get_width(), hdr.get_height());
    half4 scene = (hdr.sample(linearSampler, in.uv + pixel) +
                  hdr.sample(linearSampler, in.uv - pixel) +
                  hdr.sample(linearSampler, in.uv + pixel * float2(1,-1)) +
                  hdr.sample(linearSampler, in.uv + pixel * float2(-1,1))) * 0.25h;
    float alpha = saturate(float(scene.a));
    float3 radiance = max(float3(scene.rgb) / max(alpha, 0.0001f), 0.0f);
    float3 logColor = saturate((log2(max(radiance, 0.00000274658f) / 0.18f) + 16.0f) / 32.0f);
    float3 uvw = (logColor * 63.0f + 0.5f) / 64.0f;
    half3 color = display.sample(linearSampler, uvw).rgb;
    if (transparentExport != 0) { return half4(color, half(alpha)); }
    // Composite after AgX so the dashboard black never receives a film curve.
    // This is display-linear #0c0d0e, not a light source in the 3D scene.
    half3 background = half3(0.003677h, 0.004025h, 0.004391h);
    // A broad, quiet sweep, seamless with the surrounding interface. Only
    // the environment blends vertically into the interface; never fade the car.
    float2 q = (in.uv - float2(0.5f, 0.52f)) / float2(0.56f, 0.48f);
    float sweep = pow(saturate(1.0f - dot(q, q)), 1.5f);
    background += half3(stageBackdrop.rgb * sweep);
    return half4(mix(background, color, half(alpha)), 1);
}

// A world-space matte surface supplies scale and a receiving surface for the
// mesh's contact shadow. No tiled grid, mirror floor, or camera-locked decal.
[[visible]]
void e36PresentationGround(realitykit::surface_parameters params) {
    float2 p = params.geometry().world_position().xz;
    float falloff = 1.0f - smoothstep(3.2f, 9.0f, length(p));
    float mottling = sin(p.x * 1.31f + sin(p.y * 0.73f)) * sin(p.y * 1.77f) * 0.015f;
    half3 matte = params.lighting().environment_radiance(
        half3(params.uniforms().custom_parameter().rgb), 1.0h, 0.0h, 0.0h, float3(0, 1, 0)).diffuse;
    params.surface().set_emissive_color(matte * half(1.0f + mottling));
    float4 clip = params.uniforms().view_to_projection() * params.uniforms().world_to_view() * float4(params.geometry().world_position(), 1);
    float2 ndc = abs(clip.xy / clip.w);
    // Keep the ground continuous to both screen edges, with no side vignette.
    float edge = 1.0f - smoothstep(0.82f, 1.0f, ndc.y);
    params.surface().set_opacity(half(falloff * 0.82f * edge));
}

// Same source radiance and world orientation as the paint/glass IBL. Direct
// texture sampling avoids BRDF-dependent exposure or a grazing-normal pole.
// Flatten the lower dome onto a ground plane around the HDR capture height.
[[visible]]
void e36OutdoorBackdrop(realitykit::surface_parameters params) {
    float3 p = params.geometry().world_position();
    float3 direction = normalize(p - float3(0, 1.65f, 0));
    float2 uv = float2(-atan2(-direction.z, direction.x) / 6.2831853f + 0.5f, acos(clamp(direction.y, -1.0f, 1.0f)) / 3.14159265f);
    constexpr sampler panoramaSampler(coord::normalized, s_address::repeat, t_address::clamp_to_edge, filter::linear, mip_filter::linear);
    float3 radiance = float3(params.textures().custom().sample(panoramaSampler, uv).rgb) * (16.0f * exp2(0.15f));
    // Finite RGBA16Float render target. This limit is far above display white.
    params.surface().set_emissive_color(half3(min(radiance, 60000.0f)));
    float4 clip = params.uniforms().view_to_projection() * params.uniforms().world_to_view() * float4(p, 1);
    float2 ndc = abs(clip.xy / clip.w);
    float edge = 1.0f - smoothstep(0.82f, 1.0f, ndc.y);
    params.surface().set_opacity(half(edge));
}

// Carry the authored smooth normal into world space. A derivative cross
// product gives a separate flat normal per triangle, making curved glazing
// break into facets as reflected trees and sky cross the mesh.
[[visible]]
void e36OpticalGeometry(realitykit::geometry_parameters params) {
    float4x4 inverse = params.uniforms().world_to_model();
    float3x3 normalMatrix = transpose(float3x3(inverse[0].xyz, inverse[1].xyz, inverse[2].xyz));
    float3 normal = normalize(normalMatrix * params.geometry().normal());
    params.geometry().set_custom_attribute(float4(normal, 0));
}

// World-locked pigment variation. Attenuating subpixel detail by its pixel
// footprint prevents metallic flakes from sparkling as the camera moves.
static float pigmentNoise(float3 p) {
    float3 i = floor(p), f = fract(p);
    f = f * f * (3.0f - 2.0f * f);
    float n = dot(i, float3(1, 57, 113));
    float4 a = fract(sin(n + float4(0, 1, 57, 58)) * 43758.5453f);
    float4 b = fract(sin(n + float4(113, 114, 170, 171)) * 43758.5453f);
    return mix(mix(mix(a.x, a.y, f.x), mix(a.z, a.w, f.x), f.y),
               mix(mix(b.x, b.y, f.x), mix(b.z, b.w, f.x), f.y), f.z);
}

// Integrate unresolved normal variance into the microfacet lobe. MSAA only
// filters coverage; it cannot prevent a tiny curved chrome edge sparkling.
static half filteredRoughness(float roughness, float3 normal) {
    float3 dx = dfdx(normal), dy = dfdy(normal);
    float variance = min(0.5f * (dot(dx, dx) + dot(dy, dy)), 0.12f);
    return half(sqrt(saturate(roughness * roughness + variance)));
}

// A dielectric interface: reflect F of the environment and transmit 1-F of
// the already rendered cabin/lamp. Using a lit transparent material applies
// Fresnel twice, losing the reflections and making lenses look frosted.
[[visible]]
void e36OpticalGlass(realitykit::surface_parameters params) {
    float3 n = normalize(params.geometry().custom_attribute().xyz);
    float4 controls = params.uniforms().custom_parameter();
    // Shade both optical interfaces on the front-facing shell. The rear
    // shell must not compete with its front face in the transparent depth pass.
    if (controls.y < -0.5f || (controls.z > 1.5f && controls.z < 2.5f)) {
        params.surface().set_opacity(0); return;
    }
    float3 geometricNormal = n;
    bool headlampCover = controls.z > 2.5f && params.geometry().world_position().z > 1.7f;
    if (headlampCover) {
        // The complete rectangular pressed-glass cover sits ahead of both
        // round optics. Its fine moulding catches one continuous reflection
        // across the black spaces between them, rather than disappearing like
        // an anti-reflective sheet. Filter relief as it becomes subpixel.
        float3 p = params.geometry().world_position();
        float2 phase = float2(abs(p.x), p.y) * float2(1570.7963f, 2094.3951f);
        float2 resolved = 1.0f - smoothstep(float2(1.2f), float2(3.14159f), fwidth(phase));
        float2 slope = cos(phase) * resolved * float2(0.040f, 0.008f);
        float3 tangent = normalize(cross(float3(0, 1, 0), n));
        float3 vertical = normalize(cross(n, tangent));
        n = normalize(n - tangent * slope.x - vertical * slope.y);
    }
    if (controls.z > 0.5f && controls.z < 1.5f) {
        // The circular moulding has a clear shoulder and zoned optical ribs.
        // Derive position from the authored lens UV rectangle; the optical
        // zones follow the owner photo instead of the donor normal atlas.
        float2 lens = (params.geometry().uv0() - float2(0.465f, 0.545f))
                    / float2(0.48f, 0.34f) * 2.0f - 1.0f;
        float radius = length(lens);
        float2 mm = lens * 61.0f;
        bool inboard = abs(params.geometry().model_position().x) < 0.5f;
        float band = smoothstep(-0.44f, -0.35f, lens.y)
                   * (1.0f - smoothstep(0.25f, 0.34f, lens.y));
        float lower = 1.0f - smoothstep(-0.35f, -0.20f, lens.y);
        float zone = inboard ? mix(0.075f, 0.34f, band) : mix(0.035f, 0.24f, lower);
        float phase = mm.x * (6.2831853f / 3.8f);
        float resolved = 1.0f - smoothstep(1.2f, 3.14159f, fwidth(phase));
        float shoulder = 1.0f - smoothstep(0.89f, 0.95f, radius);
        float2 slope = float2(cos(phase) * zone * resolved * shoulder, 0);
        // Two shallow circular moulding returns catch highlights around the
        // edge; all relief fades with pixel footprint rather than sparkling.
        float ringPhase = (radius - 0.925f) * 170.0f;
        float ringResolved = 1.0f - smoothstep(1.2f, 3.14159f, fwidth(ringPhase));
        float ring = smoothstep(0.87f, 0.91f, radius)
                   * (1.0f - smoothstep(0.975f, 1.0f, radius));
        slope += lens / max(radius, 0.001f) * cos(ringPhase) * 0.90f * ring * ringResolved;
        float3 t = normalize((params.uniforms().model_to_world() * float4(1, 0, 0, 0)).xyz);
        t = normalize(t - geometricNormal * dot(t, geometricNormal));
        float3 b = normalize((params.uniforms().model_to_world() * float4(0, 0, 1, 0)).xyz);
        b = normalize(b - geometricNormal * dot(b, geometricNormal));
        // Orient the interface toward the incoming ray before applying
        // relief, consistently on the mirrored lamps.
        if (dot(n, params.geometry().view_direction()) < 0) { n = -n; }
        n = normalize(n - slope.x * t - slope.y * b);
    }
    float3 v = normalize(params.geometry().view_direction());
    if (dot(n, v) < 0.0f) { n = -n; }
    if (dot(geometricNormal, v) < 0.0f) { geometricNormal = -geometricNormal; }
    float ndv = abs(dot(n, v));
    float fresnel = 0.0426f + 0.9574f * pow(1.0f - saturate(ndv), 5.0f);
    // Both air/glass interfaces reflect. Their combined return matters on
    // the large flat cover, particularly when looking nearly straight at it.
    if (headlampCover) { fresnel = 2.0f * fresnel / (1.0f + fresnel); }
    // Sample the renderer's own prefiltered environment so glass and paint
    // agree on sky/tree directions, exposure and filtering.
    half3 reflection = params.lighting().environment_radiance(
        half3(1), filteredRoughness(headlampCover ? 0.11f : controls.w, n), 1.0h, 0.0h, n).specular;
    if (controls.y > 0.5f) {
        // Refract the current frame's actual reflector image through the
        // moulded lens normal. This is a screen-space optical approximation:
        // off-screen geometry and internal multiple bounces are not traced.
        auto background = params.textures().custom();
        constexpr sampler opticsSampler(coord::normalized, address::clamp_to_edge, filter::linear);
        float2 dimensions = float2(background.get_width(), background.get_height());
        float4x4 worldToView = params.uniforms().world_to_view();
        float4x4 projection = params.uniforms().view_to_projection();
        // Air -> smooth front glass -> moulded rear glass -> air. Project
        // the exiting ray onto the reflector. A flat parallel plate
        // produces no angular bend.
        float3 inside = refract(-v, geometricNormal, 1.0f / 1.52f);
        float3 outgoing = refract(inside, n, 1.52f);
        bool totalInternalReflection = dot(outgoing, outgoing) < 0.001f;
        // Keep the derivative calculation below on a uniform path. A finite
        // fallback ray lets adjacent pixels filter safely at a TIR boundary;
        // those pixels ultimately display reflection alone.
        outgoing = totalInternalReflection ? -geometricNormal : outgoing;
        // Intersect the authored 43 mm-deep parabolic cup, rather than
        // sampling a flat plane through its middle. The polished lens is
        // about 8 mm ahead of the 59.3 mm-radius reflector lip.
        float2 lensXY = ((params.geometry().uv0() - float2(0.465f, 0.545f))
                       / float2(0.48f, 0.34f) * 2.0f - 1.0f) * 0.0611f;
        float3 tangent = normalize((params.uniforms().model_to_world() * float4(1, 0, 0, 0)).xyz);
        tangent = normalize(tangent - geometricNormal * dot(tangent, geometricNormal));
        float3 vertical = normalize((params.uniforms().model_to_world() * float4(0, 0, 1, 0)).xyz);
        vertical = normalize(vertical - geometricNormal * dot(vertical, geometricNormal));
        float2 rayXY = float2(dot(outgoing, tangent), dot(outgoing, vertical));
        float curvature = 0.043f / (0.0593f * 0.0593f);
        float a = curvature * dot(rayXY, rayXY);
        float b = max(dot(outgoing, -geometricNormal), 0.05f) + 2.0f * curvature * dot(lensXY, rayXY);
        float c = curvature * dot(lensXY, lensXY) - 0.051f;
        float discriminant = max(b * b - 4.0f * a * c, 0.0f);
        float path = max(0.0f, (-2.0f * c) / max(b + sqrt(discriminant), 0.0001f));
        float3 hit = params.geometry().world_position() + outgoing * min(path, 0.10f);
        float4 projected = projection * worldToView * float4(hit, 1);
        float2 uv = projected.xy / projected.w * float2(0.5f, -0.5f) + 0.5f;
        // Filter the refracted footprint, which can stretch across several
        // source pixels at a rib. A fixed subpixel blur leaves broken bright
        // stripes when the narrow optical cells minify during an orbit.
        float2 limit = float2(4.0f) / dimensions;
        float2 dx = clamp(dfdx(uv) * 0.40f, -limit, limit);
        float2 dy = clamp(dfdy(uv) * 0.40f, -limit, limit);
        half3 transmitted = (background.sample(opticsSampler, uv + dx + dy).rgb +
                             background.sample(opticsSampler, uv + dx - dy).rgb +
                             background.sample(opticsSampler, uv - dx + dy).rgb +
                             background.sample(opticsSampler, uv - dx - dy).rgb) * 0.25h;
        half3 opticalColor = transmitted * half(0.988f * (1-fresnel)) + reflection * half(fresnel);
        params.surface().set_emissive_color(mix(opticalColor, reflection, half(totalInternalReflection)));
        params.surface().set_opacity(1);
        return;
    }
    if (headlampCover) {
        // A small, broad return from the unresolved pressed-glass structure
        // softens the cups without turning the cover into an opaque white cap.
        half3 scatter = params.lighting().environment_radiance(
            half3(1), 0.32h, 1.0h, 0.0h, geometricNormal).specular;
        float scatterWeight = 0.065f * (1.0f - fresnel);
        float opacity = fresnel + scatterWeight + 0.015f;
        params.surface().set_emissive_color((reflection * half(fresnel) + scatter * half(scatterWeight)) / half(opacity));
        params.surface().set_opacity(half(opacity));
        return;
    }
    float opacity = fresnel + controls.x * (1.0f - fresnel);
    params.surface().set_emissive_color(reflection * half(fresnel / opacity));
    params.surface().set_opacity(half(opacity));
}

// Evaluate diffuse and specular together from the same live environment.
// The vertex alpha retains only geometry-dependent ambient visibility.
[[visible]]
void e36MetallicPaint(realitykit::surface_parameters params) {
    auto surface = params.surface();
    auto constants = params.material_constants();
    float3 p = params.geometry().world_position() * 1800.0f;
    float footprint = max(length(dfdx(p)), length(dfdy(p)));
    float resolved = 1.0f - smoothstep(0.35f, 1.5f, footprint);
    half pigment = half((pigmentNoise(p) - 0.5f) * resolved);
    half3 albedo = half3(constants.base_color_tint()) * (1.0h + pigment * 0.025h);
    half metallic = half(constants.metallic_scale());
    bool studioDiffuse = params.uniforms().custom_parameter().w > 0.5f;
    // Keep exactly the same specular F0, but omit the renderer's diffuse lobe
    // when the static studio's ray-traced diffuse is supplied below. This
    // avoids counting diffuse twice and retains native clearcoat/reflections.
    surface.set_base_color(studioDiffuse ? mix(half3(0.04h), albedo, metallic) : albedo);
    surface.set_metallic(studioDiffuse ? 1.0h : metallic);
    surface.set_ambient_occlusion(half(params.geometry().color().a));
    half3 encoded = half3(params.geometry().color().rgb);
    surface.set_emissive_color(studioDiffuse ? 4.0h * encoded * encoded : half3(0));
    surface.set_roughness(filteredRoughness(clamp(constants.roughness_scale() + float(pigment) * 0.025f, 0.18f, 0.40f), params.geometry().normal()));
    surface.set_specular(0.5h);
    surface.set_clearcoat(1.0h);
    surface.set_clearcoat_roughness(filteredRoughness(constants.clearcoat_roughness_scale(), params.geometry().normal()));
    surface.set_clearcoat_normal(half3(0, 0, 1));
    surface.set_opacity(1.0h);
}

[[visible]]
void e36VehicleSurface(realitykit::surface_parameters params) {
    constexpr sampler materialSampler(coord::normalized, address::repeat,
                                       filter::linear, mip_filter::linear);
    float2 uv = params.geometry().uv0();
    uv.y = 1.0f - uv.y;
    auto textures = params.textures();
    auto constants = params.material_constants();
    auto surface = params.surface();
    half3 albedo = textures.base_color().sample(materialSampler, uv).rgb * half3(constants.base_color_tint());
    half metal = textures.metallic().sample(materialSampler, uv).r * constants.metallic_scale();
    bool studioDiffuse = params.uniforms().custom_parameter().w > 0.5f;
    half dielectricF0 = half(0.16f * constants.specular_scale() * constants.specular_scale());
    surface.set_base_color(studioDiffuse ? mix(half3(dielectricF0), albedo, metal) : albedo);
    surface.set_metallic(studioDiffuse ? 1.0h : metal);
    float roughness = textures.roughness().sample(materialSampler, uv).r * constants.roughness_scale();
    surface.set_roughness(filteredRoughness(roughness, params.geometry().normal()));
    surface.set_normal(float3(realitykit::unpack_normal(textures.normal().sample(materialSampler, uv).rgb)));
    surface.set_specular(half(constants.specular_scale()));
    // Imported clearcoat parameters must be applied explicitly in a custom
    // shader. Preserve the lacquer on lamp covers, badges and painted wheels.
    surface.set_clearcoat(textures.clearcoat().sample(materialSampler, uv).r * half(constants.clearcoat_scale()));
    surface.set_clearcoat_roughness(textures.clearcoat_roughness().sample(materialSampler, uv).r * half(constants.clearcoat_roughness_scale()));
    surface.set_clearcoat_normal(half3(realitykit::unpack_normal(textures.clearcoat_normal().sample(materialSampler, uv).rgb)));
    surface.set_ambient_occlusion(half(params.geometry().color().a));
    half3 encoded = half3(params.geometry().color().rgb);
    surface.set_emissive_color(studioDiffuse ? 4.0h * encoded * encoded : half3(0));
    surface.set_opacity(1.0h);
}

// A coloured optical return under the existing smooth indicator cover.
// The relief is evaluated in millimetres and stays attached to the lamp;
// no light is emitted and no blinking or vehicle state is fabricated.
[[visible]]
void e36SignalReflector(realitykit::surface_parameters params) {
    float3 p = params.geometry().world_position();
    float3 n = normalize(params.geometry().custom_attribute().xyz);
    float3 v = normalize(params.geometry().view_direction());
    if (dot(n, v) < 0) { n = -n; }
    float3 t = normalize(cross(float3(0, 1, 0), n));
    float3 b = normalize(cross(n, t));
    float2 phase = float2(abs(p.x), p.y) * float2(1570.7963f, 2094.3951f);
    float2 resolved = 1.0f - smoothstep(float2(1.2f), float2(3.14159f), fwidth(phase));
    float2 relief = cos(phase) * resolved * float2(0.31f, 0.18f);
    float2 bowl = p.z > 1.8f ? float2((abs(p.x) - 0.713f) / 0.062f, (p.y - 0.634f) / 0.061f) : float2(0);
    float direction = p.x >= 0 ? 1.0f : -1.0f;
    n = normalize(n - t * direction * (relief.x + bowl.x * 0.32f) - b * (relief.y + bowl.y * 0.24f));
    float path = 1.0f + 0.32f * min(dot(bowl, bowl), 2.0f);
    half3 amber = half3(exp(-float3(0.55f, 1.80f, 5.1f) * path));
    auto radiance = params.lighting().environment_radiance(amber,
        filteredRoughness(0.12f, n), 0.78h, 0.0h, n);
    params.surface().set_emissive_color((radiance.diffuse + radiance.specular)
        * half(params.geometry().color().a));
    params.surface().set_opacity(1);
}
