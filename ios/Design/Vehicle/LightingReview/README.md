# Vehicle lighting review — 29 September 2026

The same iPhone 17 Pro simulator on iOS 27.0 rendered `main` at `e7fd594` and this lighting branch. The full-resolution PNGs are native Metal screenshots; [review.jpg](review.jpg) only crops and scales them for comparison.

| Scene | Native screenshot |
| --- | --- |
| Grafito on `main` | [before-graphite-app.png](before-graphite-app.png) |
| Refined Grafito in the app | [after-graphite-app.png](after-graphite-app.png) |
| Refined Grafito, right-facing profile | [after-graphite-profile.png](after-graphite-profile.png) |
| Luz natural in the app | [after-daylight-app.png](after-daylight-app.png) |
| Luz natural, right-facing profile | [after-daylight-profile.png](after-daylight-profile.png) |

The original Grafito floor was a broad grey patch below the car. Its matte albedo, opacity and world-space spread are reduced, with a quieter backdrop sweep. A restrained, world-fixed white-card bounce lifts the E36's -X flank in the right-facing profile; the front three-quarter angle keeps its original highlight structure. Luz natural retains the parking HDR projection. The vehicle receives 0.35 stop more environment light, the visible projection 0.35 stop less, and the directional contact shadow is reduced to 65% opacity.

The Grafito floor now fades over a wider lower portion of the viewport, reaching the surrounding `#0c0d0e` background before the car bay ends. The softbox shadow is at 50% opacity so its shallow-angle projection does not read as a hard band in Perfil. The car itself stays opaque. The refreshed Grafito screenshots and comparison sheet show the final transition; a fresh Luz natural capture was pixel-identical to the previous one.

The branch's Debug-only `--vehicle-review=profile` launch argument selects the product's right-facing camera pose for repeatable lighting captures. `--scene-study=graphite` and `--scene-study=limestone` select stages. The `E36OBD` Debug scheme built successfully for iOS Simulator with Xcode 27.0; both stages loaded and rendered on the iPhone 17 Pro simulator. This review covers appearance in those views, not physical-device performance or live capture.
