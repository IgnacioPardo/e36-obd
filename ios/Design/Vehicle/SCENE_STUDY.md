# Scene presentation study — 11 September 2026

The old presentation combined outdoor tree/sky reflections, a nearly black ground shadow and an opaque black viewport. Those three cues described different surroundings. A fixed camera distance also allowed the car to cross the viewport at some rotations and zoom levels. These are presentation problems; adding polygons alone would not address them.

## References and practical decisions

| Primary reference | What it demonstrates | Application here |
| --- | --- | --- |
| [Rivian / Unreal, 2024](https://www.unrealengine.com/spotlights/rivian-brings-adventurous-spirit-to-new-display-ui-powered-by-unreal-engine) | A deliberately illustrated vehicle and environment, custom shaders and interactive scenes. It is not a photographic rendering target. | Match the visual language of the vehicle and its surroundings; keep the real 3D interaction. |
| [Porsche AR Visualizer, 2019](https://newsroom.porsche.com/en/2019/digital/porsche-augmented-reality-visualizer-app-car-configuration-17619.html) | Places the configured vehicle on a surface in the user's real surroundings. | A legible ground plane helps establish contact, scale and depth. This is a design inference, not a claim that our app implements AR. |
| [Epic automotive studio guide, 2021](https://www.unrealengine.com/tech-blog/build-studio-render-in-production-with-ue4?lang=zh-CN) | Controlled environment lighting, restrained rectangular sources, manual exposure and inspection from multiple angles. Warns that excessive large lights flatten form. | Compare neutral softboxes and a captured photographic studio; retain dark fill between reflected sources; use a lit matte receiving surface. |
| [Epic HDRI Backdrop guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/hdri-backdrop-visualization-tool-in-unreal-engine) | Pairs an HDR background with image-based lighting, ground projection and shadow catching. | Outdoor option samples the same source HDR used by paint and glass, projected onto a world-fixed dome and floor. |

## Runtime alternatives

- **Original**: retained only as a DEBUG comparison (`--scene-study=original`). Outdoor reflections against the old black void.
- **Grafito**: captured [Studio Small 09](https://polyhaven.com/a/studio_small_09) illumination, a lit charcoal floor and a restrained background sweep. The owner selected studio as the preferred direction. The handmade rectangular-light environment was coherent but still looked flat; the final studio uses the photographed doorway, ceiling and dark fill. Native comparisons at eight angle/exposure combinations selected a 135-degree world rotation and +0.75 stops from the normalized baseline. All channels receive one common exposure multiplier; the Samoablau pigment is unchanged.
- **Luz natural**: Park Parking surroundings and reflections from the same world-fixed HDR source, with ground projection at an assumed 1.65 m capture height. This is a finite HDR projection, not reconstructed park geometry; near objects can distort during large camera movements.

The environment edges blend into the interface; car pixels are never faded to hide clipping. Production camera distance fits all eight corners of the model bounds to both dimensions of the viewport. Pinch stops at a framing that keeps the whole vehicle visible. The original camera intent survives orientation changes.

The stationary studio has a 192-sample ray-traced direct/indirect diffuse bake. Metal removes the native diffuse lobe while retaining its specular F0, then adds the decoded diffuse bake. Specular reflections, clearcoat and optical glass still change live with the camera. The outdoor alternative uses the complete live PBR response and only geometry-baked ambient visibility. A separate Cycles render under the same camera, materials and environment provides an offline comparison; it is not substituted into the app. The studio shadow catcher spans 20 m and only its distant edge fades, eliminating the visible boundary of the old 8 m quad.

The car, materials, cameras and environment still render through RealityRenderer and Metal. There is no substituted photo or pre-rendered orbit sequence. AgX display transform, world-fixed lighting, idle suspension and Reduce Motion behavior remain in place. The stage menu changes presentation only, never BLE, recording or readings.

## Scope and limits

These comparisons assess coherence, contact and framing. They are not proof that the reconstruction is indistinguishable from a photograph. The mesh remains a reconstruction; paint reflectance was not spectrally measured, optics use screen-space approximations, ground shadows are precomputed for the stationary car, and the HDR backdrop has finite resolution and projected depth.

The app-only asset receives another 10 mm front / 5 mm rear drop (30 / 15 mm total against the reference model). Wheels retain their transforms, track and tyre size. The oversized muffler connection is narrowed and tucked behind the apron; the existing hollow slash-cut outlet is shortened and raised. Reference/native model files remain available unchanged.

Screenshots and validation results accompany this file in `SceneStudy/`.

## Reproducible evidence

`SceneStudy/iteration-comparison.jpg` compares the rejected handmade studio with the final native rendering. `SceneStudy/lighting-angles.jpg` and `lighting-exposure.jpg` record the native lighting studies. `SceneStudy/cycles-reference.png` is explicitly an offline ray-traced reference, while `studio.png`, `outdoor.png` and the app layout captures are native simulator screenshots. The final material, environment and geometry hashes are recorded in `scene-settings.json` and `bake-report.json`.
