#include <metal_stdlib>
#include <RealityKit/RealityKit.h>
using namespace metal;

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

static half3 bakedDiffuse(realitykit::surface_parameters params) {
    // The square-root encoding preserves dark cabin detail even when the
    // asset loader stores vertex colors at normalized fixed precision.
    half3 encoded = half3(params.geometry().color().rgb);
    return 4.0h * encoded * encoded;
}

[[visible]]
void e36MetallicPaint(realitykit::surface_parameters params) {
    auto surface = params.surface();
    auto constants = params.material_constants();
    float3 p = params.geometry().world_position() * 1800.0f;
    float footprint = max(length(dfdx(p)), length(dfdy(p)));
    float resolved = 1.0f - smoothstep(0.35f, 1.5f, footprint);
    half pigment = half((pigmentNoise(p) - 0.5f) * resolved);
    half3 albedo = half3(constants.base_color_tint()) * (1.0h + pigment * 0.025h);
    surface.set_base_color(mix(half3(0.04h), albedo, half(constants.metallic_scale())));
    surface.set_metallic(1.0h);
    surface.set_ambient_occlusion(half(params.geometry().color().a));
    surface.set_emissive_color(bakedDiffuse(params));
    surface.set_roughness(half(clamp(constants.roughness_scale() + float(pigment) * 0.025f, 0.18f, 0.40f)));
    surface.set_specular(0.5h);
    surface.set_clearcoat(1.0h);
    surface.set_clearcoat_roughness(half(constants.clearcoat_roughness_scale()));
    surface.set_clearcoat_normal(half3(0, 0, 1));
    surface.set_opacity(1.0h);
}

// A dielectric interface: reflect F of the environment and transmit 1-F of
// the already rendered cabin/lamp. Using a lit transparent material applies
// Fresnel twice, losing the reflections and making lenses look frosted.
[[visible]]
void e36OpticalGlass(realitykit::surface_parameters params) {
    float3 n = normalize(params.geometry().custom_attribute().xyz);
    float4 controls = params.uniforms().custom_parameter();
    if (controls.z > 0.5f) {
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
    float ndv = abs(dot(n, v));
    float fresnel = 0.0426f + 0.9574f * pow(1.0f - saturate(ndv), 5.0f);
    // Sample the renderer's own prefiltered environment so glass and paint
    // agree on sky/tree directions, exposure and filtering.
    half3 reflection = params.lighting().environment_radiance(
        half3(1), half(controls.w), 1.0h, 0.0h, n).specular;
    float opacity = fresnel + controls.x * (1.0f - fresnel);
    params.surface().set_emissive_color(reflection * half(fresnel / opacity));
    params.surface().set_opacity(half(opacity));
}

// Diffuse radiance is ray traced into the mesh. The native renderer still
// evaluates the view-dependent microfacet BRDF, using the material's actual F0.
// Metallic=1 suppresses the duplicate runtime diffuse term; the specular base
// colour is the equivalent dielectric/conductor F0, not the diffuse albedo.
[[visible]]
void e36BakedSurface(realitykit::surface_parameters params) {
    constexpr sampler materialSampler(coord::normalized, address::repeat,
                                       filter::linear, mip_filter::linear);
    float2 uv = params.geometry().uv0();
    uv.y = 1.0f - uv.y;
    auto textures = params.textures();
    auto constants = params.material_constants();
    auto surface = params.surface();
    half3 albedo = textures.base_color().sample(materialSampler, uv).rgb * half3(constants.base_color_tint());
    half metal = textures.metallic().sample(materialSampler, uv).r * constants.metallic_scale();
    surface.set_base_color(mix(half3(0.04h), albedo, metal));
    surface.set_metallic(1.0h);
    surface.set_roughness(textures.roughness().sample(materialSampler, uv).r * constants.roughness_scale());
    surface.set_normal(float3(realitykit::unpack_normal(textures.normal().sample(materialSampler, uv).rgb)));
    surface.set_specular(constants.specular_scale());
    surface.set_ambient_occlusion(half(params.geometry().color().a));
    surface.set_emissive_color(bakedDiffuse(params));
    surface.set_opacity(1.0h);
}
