#include <metal_stdlib>
#include <RealityKit/RealityKit.h>
using namespace metal;

struct E36DisplayVertex { float4 position [[position]]; float2 uv; };

vertex E36DisplayVertex e36DisplayVertex(uint id [[vertex_id]]) {
    float2 uv = float2((id << 1) & 2, id & 2);
    return {float4(uv * float2(2, -2) + float2(-1, 1), 0, 1), uv};
}

fragment half4 e36PhotographicDisplay(E36DisplayVertex in [[stage_in]],
    texture2d<half> hdr [[texture(0)]], texture3d<half> display [[texture(1)]]) {
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
    // Composite after AgX so the dashboard black never receives a film curve.
    // This is display-linear #0c0d0e, not a light source in the 3D scene.
    half3 background = half3(0.003677h, 0.004025h, 0.004391h);
    return half4(mix(background, color, half(alpha)), 1);
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
    if (controls.y < -0.5f) { params.surface().set_opacity(0); return; }
    float3 geometricNormal = n;
    if (controls.z > 0.5f && controls.z < 1.5f) {
        // The inner headlamp glass has a real fluting normal map. Preserve
        // its refraction-scale detail instead of replacing it with flat glass.
        float2 uv = params.geometry().uv0();
        uv.y = 1.0f - uv.y;
        constexpr sampler normalSampler(coord::normalized, address::repeat,
                                         filter::linear, mip_filter::linear);
        float3 mapped = float3(realitykit::unpack_normal(params.textures().normal().sample(normalSampler, uv).rgb));
        mapped = normalize(float3(mapped.xy * 0.35f, mapped.z));
        float3 p = params.geometry().world_position();
        float3 dp1 = dfdx(p), dp2 = dfdy(p);
        float2 dt1 = dfdx(uv), dt2 = dfdy(uv);
        float determinant = dt1.x * dt2.y - dt1.y * dt2.x;
        if (abs(determinant) > 1e-10f) {
            float3 t = normalize((dp1 * dt2.y - dp2 * dt1.y) * sign(determinant));
            t = normalize(t - n * dot(n, t));
            float3 b = normalize((-dp1 * dt2.x + dp2 * dt1.x) * sign(determinant));
            n = normalize(t * mapped.x + b * mapped.y + n * mapped.z);
        }
        // Match the 2.8 mm moulded ribs in the editable optical material.
        // USD Preview Surface omits this procedural bump. Fade it at a
        // subpixel footprint so the lens does not shimmer while orbiting.
        float phase = params.geometry().model_position().x * 2243.9949f;
        float resolved = 1.0f - smoothstep(1.0f, 3.14159f, fwidth(phase));
        float slope = 0.7f * 0.00011f * 2243.9949f * cos(phase) * resolved;
        float3 ribAxis = normalize((params.uniforms().model_to_world() * float4(1, 0, 0, 0)).xyz);
        ribAxis = normalize(ribAxis - n * dot(n, ribAxis));
        n = normalize(n - slope * ribAxis);
    }
    float3 v = normalize(params.geometry().view_direction());
    if (dot(n, v) < 0.0f) { n = -n; }
    if (dot(geometricNormal, v) < 0.0f) { geometricNormal = -geometricNormal; }
    float ndv = abs(dot(n, v));
    float fresnel = 0.0426f + 0.9574f * pow(1.0f - saturate(ndv), 5.0f);
    // Sample the renderer's own prefiltered environment so glass and paint
    // agree on sky/tree directions, exposure and filtering.
    half3 reflection = params.lighting().environment_radiance(
        half3(1), half(controls.w), 1.0h, 0.0h, n).specular;
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
        // the exiting ray onto the reflector region, roughly 40 mm behind
        // the authored lens. A flat parallel plate produces no angular bend.
        float3 inside = refract(-v, geometricNormal, 1.0f / 1.52f);
        float3 outgoing = refract(inside, n, 1.52f);
        if (dot(outgoing, outgoing) < 0.001f) {
            params.surface().set_emissive_color(reflection);
            params.surface().set_opacity(1);
            return;
        }
        float path = 0.040f / max(dot(outgoing, -geometricNormal), 0.15f);
        float3 hit = params.geometry().world_position() + outgoing * path;
        float4 projected = projection * worldToView * float4(hit, 1);
        float2 uv = projected.xy / projected.w * float2(0.5f, -0.5f) + 0.5f;
        float2 spread = float2(0.65f) / dimensions;
        half3 transmitted = background.sample(opticsSampler, uv).rgb * 0.4h;
        transmitted += (background.sample(opticsSampler, uv + float2(spread.x, 0)).rgb +
                        background.sample(opticsSampler, uv - float2(spread.x, 0)).rgb +
                        background.sample(opticsSampler, uv + float2(0, spread.y)).rgb +
                        background.sample(opticsSampler, uv - float2(0, spread.y)).rgb) * 0.15h;
        params.surface().set_emissive_color(transmitted * half(0.988f * (1-fresnel)) + reflection * half(fresnel));
        params.surface().set_opacity(1);
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
    surface.set_base_color(albedo);
    surface.set_metallic(half(constants.metallic_scale()));
    surface.set_ambient_occlusion(half(params.geometry().color().a));
    surface.set_emissive_color(half3(0));
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
    surface.set_base_color(albedo);
    surface.set_metallic(metal);
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
    surface.set_emissive_color(half3(0));
    surface.set_opacity(1.0h);
}
