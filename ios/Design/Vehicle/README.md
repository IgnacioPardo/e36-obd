# Vehicle reconstruction

The editable asset reconstructs the owner's Samoablau four-door 1994 E36 316i from photographs. Open `E36-316i.blend` for the vehicle and native Cycles materials. `ReferenceLighting.blend` links that vehicle into three photographic camera studies. The photographs provide appearance and camera landmarks; they are not a dimensional scan or a measured lighting environment. The retained wheel casting remains an approximation.

## Geometry and finish

The accepted early kidney outline is preserved. The erroneous additional 16.7-degree pitch has been removed without changing the traced front silhouette. The M front bumper contains hollow air ducts tessellated from the supplied `FogIntake.step` at its original scale, with a mirrored opposite side. Body badges and wheel caps use the supplied artwork. The rear 316i lettering follows the trunk surface, inset from its top crease and outside seam. The stock rear bumper has a separate black rubbing strip and a central charcoal lower insert; its lower corner returns remain body blue. The exhaust body is tucked behind the apron so the short outlet remains visible.

The Samoablau pigment is inferred from three low-glare panels in the owner's RAW photograph after EXIF orientation and Display P3-to-sRGB conversion. Sky-reflection samples are kept separate. The linear pigment is `(0.1110, 0.1420, 0.2123)`, with metallic coverage `0.22`, base roughness `0.30` and clearcoat roughness `0.055`. These are rendering parameters, not a measured paint formula. `paint-samples.jpg`, `paint-samples.json` and `paint-calibration.json` preserve the sampling evidence.

The native source retains layered Samoablau paint, optical glass, lamp optics, rubber, cast aluminum, chrome and fabric materials. `HD/` contains separate Cycles previews. These are offline renders, not screenshots of the iPhone renderer. See each manifest for the exact source revision used; older previews must not be treated as evidence of a newer runtime revision.

## App rendering

`../../E36OBD/VehicleScene/` contains the actual geometry rendered by Swift, RealityKit and Metal. Horizontal dragging orbits continuously, pinching zooms, two-finger dragging changes elevation, and double tapping resets the view. Camera pose survives orientation and tab changes. The renderer does not access Bluetooth or recording and stops submitting frames while idle or in the background.

The bundled USDZ differs from the portable source export. Fixed-environment diffuse illumination and ambient visibility are ray traced into vertex attributes. RGB uses `sqrt(linear radiance / 4)` encoding to retain dark surface detail; alpha stores visibility. Metal decodes those channels and computes view-dependent specular, clearcoat and glass reflections. Smooth world-space glazing normals avoid triangle-shaped reflections. A transparent world-space contact shadow is derived from the vehicle geometry; the shadow contains no car pixels.

The paint and glass share a prefiltered daylight HDR environment. The model remains freely viewable geometry; it is not an image turntable. Fixed illumination means changing the light arrangement requires a new diffuse bake. Portable GLB/USDZ files use standard PBR approximations and do not depend on the app's shaders.

## Regeneration

Use Blender 4.5 with Metal on macOS. No Python runtime, Blender installation or network service is required by the app.

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --disable-autoexec \
  ios/Design/Vehicle/E36-316i.blend --python ios/tools/export_vehicle.py

/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --disable-autoexec \
  --python ios/tools/bake_vehicle_lighting.py -- \
  --output .context/vehicle-lighting --exposure 0.65

python3 ios/tools/pack_vehicle_lighting.py .context/vehicle-lighting
```

The packing tool needs NumPy and Pixar's `usd-core` in the development Python environment. It preserves corner positions, split normals and UV seams exactly while removing unused UV sets and consolidating redundant vertex indices. Review the baked model in the simulator before replacing the bundled model. The bake report records source/environment hashes, exposure, encoding and output hashes; keep it beside the corresponding USDZ.

Prefilter the HDR for iOS with Xcode's `realitytool`:

```sh
xcrun realitytool image --platform iphoneos --deployment-target 18.0 \
  --cube-face-size 1024 --specular-size 1024 --diffuse-size 64 \
  --ibl-sampling-quality high \
  --output-reality-asset ios/E36OBD/VehicleScene/StudioEnvironment.realityenv \
  ios/E36OBD/VehicleScene/StudioEnvironment.exr
```

Debug simulator builds accept `--demo --vehicle-review=nose` (or `rear`, `side`) to render a fixed photo-matched camera. These review views are excluded from Release and do not alter the normal dashboard. Compare actual Metal screenshots, not only Blender previews, when evaluating runtime materials.

`ios/tools/render_vehicle.py` produces an optional offline turntable under `.context/vehicle-turntable`; it does not populate app resources. `ios/tools/render_vehicle_references.py` regenerates the photographic studies. Source attribution and reconstruction limits are in [CREDITS.md](CREDITS.md); validation is in [../../VALIDATION.md](../../VALIDATION.md).
