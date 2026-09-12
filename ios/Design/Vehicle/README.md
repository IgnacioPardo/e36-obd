# Vehicle reconstruction

The editable asset reconstructs the owner's 295 Samoablau Metallic four-door 1994 E36 316i from photographs. Open `E36-316i.blend` for the vehicle and native Cycles materials. `ReferenceLighting.blend` links that vehicle into three photographic camera studies. The photographs provide appearance and camera landmarks; they are not a dimensional scan or a measured lighting environment. The retained wheel casting remains an approximation.

## Geometry and finish

The accepted early kidney outline is preserved. The erroneous additional 16.7-degree pitch has been removed without changing the traced front silhouette. The original hood, nose carrier and upper bumper alignment is restored exactly. Grille depth follows the untouched carrier surface; two narrow recessed mounting returns close the aperture gaps behind the chrome. The traced X/Z outline and object rotations stay unchanged. `alignment-validation.json` verifies zero displacement across all 215,709 evaluated body vertices and 14,628 upper bumper vertices. The earlier whole-carrier deformation was rejected. The M front bumper contains hollow air ducts tessellated from the supplied `FogIntake.step` at its original scale, with a mirrored opposite side. Their flanges are recessed 4.5 mm into the bumper seats. The lower bumper has a rounded moulded return instead of the previous thin, sharply folded edge. `front-fit-validation.json` records these geometry changes and the reviewed close-up angles.

Body badges and wheel caps use the supplied artwork. The hood and trunk roundels have shallow convex faces, rolled metal rims and locally fitted native recesses. The white quadrants are enamel; the lettering and dividers have a metallic mask and fine relief normal map. `BadgeReview/` records the accepted model detail review. The two rear headrests have been removed while preserving the bench and front seats. The rear 316i lettering follows the trunk surface, inset from its top crease and outside seam. The stock rear bumper has a separate black rubbing strip and a central charcoal lower insert; its lower corner returns remain body blue. The exhaust body is tucked behind the apron so the short outlet remains visible.

The cabin is left-hand drive: steering wheel, column, pedals and instrument pod are on the vehicle's left, with the glovebox on the right and the center console facing the driver. The steering roundel, dial markings and control labels retain their readable orientation. This corrects the original donor interior without reflecting the car. `left-hand-drive-validation.json` records unchanged exterior geometry, normals, UVs, materials, seats and ride height. Both linked Blender scenes and the portable/app exports use the corrected cabin; the app's ambient visibility has been rebaked.

The model is frozen at the user's request for the scene/material pass. The badge pocket edits leave the main carrier and upper bumper vertices exactly unchanged; the bonnet front boundary differs by at most 0.043 mm through subdivision. `FrontFit/` is the earlier alignment review, not a render of the latest badges. See the source hashes in each gallery.

The final app has a separately requested stance variant: the sprung body drops 30 mm at the front axle and 15 mm at the rear, adding about 0.32° of forward rake. All body parts receive the same rigid transform, preserving their alignment. Wheel, tyre, brake and lower suspension transforms remain fixed. The source `.blend`, GLB and portable USDZ retain the reference ride height. `prepare_vehicle_stance.py` creates the app derivative and verifies unchanged mesh/normal/UV data and tyre transforms; its report accompanies the runtime. The sampled arch-crown gap reduces from about 61 to 32 mm at the front and 67 to 52 mm at the rear.

The Samoablau pigment is inferred from three low-glare panels in the owner's RAW photograph after EXIF orientation and Display P3-to-sRGB conversion. Sky-reflection samples are kept separate. The linear pigment is `(0.1110, 0.1420, 0.2123)`, with metallic coverage `0.22`, base roughness `0.30` and clearcoat roughness `0.055`. These are rendering parameters, not a measured paint formula. `paint-samples.jpg`, `paint-samples.json` and `paint-calibration.json` preserve the sampling evidence.

The native source retains layered Samoablau paint, optical glass, lamp optics, rubber, cast aluminum, chrome and fabric materials. `HD/` contains separate Cycles previews. These are offline renders, not screenshots of the iPhone renderer. See each manifest for the exact source revision used; older previews must not be treated as evidence of a newer runtime revision.

## App rendering

`../../E36OBD/VehicleScene/` contains the actual geometry rendered by Swift, RealityKit and Metal. Horizontal dragging orbits continuously, pinching zooms, two-finger dragging changes elevation, and double tapping resets the view. Camera pose survives orientation and tab changes. The renderer does not access Bluetooth or recording and stops submitting frames while idle or in the background.

The bundled USDZ differs from the portable source export. Ambient visibility is ray traced into vertex alpha. The fixed studio also has a direct/indirect diffuse bake in vertex RGB, matched to the final studio environment, pose and material parameters. Metal supplies the live specular and clearcoat reflections. It preserves the original specular F0 while suppressing the native diffuse lobe, then adds the decoded bake; diffuse is counted once. The daylight alternative evaluates the complete live PBR response and uses only baked ambient visibility. No body geometry, split normal or UV is decimated during packing. Smooth world-space glazing normals avoid triangle-shaped reflections. Ground shadows contain no car pixels.

The default **Grafito** scene uses Poly Haven Studio Small 09, rotated and exposed after native camera comparisons. The imported Samoablau pigment is unchanged. The matte receiving floor is lit by the same probe, and the studio shadow covers 20 m with a distant edge fade. The optional **Luz natural** scene pairs Park Parking reflections with its corresponding world-fixed background. [Scene study](SCENE_STUDY.md) records the comparisons, sources and limits.

In the daylight alternative, paint and glass share a prefiltered Park Parking HDR environment. Its spherical mean luminance matches the previous probe, preserving the pigment calibration while changing the sky, ground and directional light. The model remains freely viewable geometry; it is not an image turntable. A lighting change requires regenerating the ground shadow; a stance change also requires refreshing geometry-dependent occlusion. Portable GLB/USDZ files use standard PBR approximations and do not depend on the app's shaders. `AppLighting.blend` is the separate app-stance lighting scene; `AppLighting/` contains its offline previews.

The app renders into a scene-linear RGBA16Float target, then applies a compiled AgX Medium High Contrast display transform. The 64³ half-float LUT is generated from Blender's OCIO configuration; the app does not load OCIO. Highlights remain HDR until the final display conversion. The display stage composites dashboard black after tone mapping. Up to 1.5× spatial supersampling (2560-pixel long-edge cap), four-tap linear-radiance resolve and 4× coverage MSAA reduce fine-edge breakup. No temporal history or motion trails are used, and the GPU still rests when idle.

Runtime paint uses metallic coverage 0.50, base roughness 0.22 and clearcoat roughness 0.055, with derivative-based microfacet filtering. The sampled Samoablau pigment remains unchanged. The image-based lighting exponent is 0.15, half a stop below the prior 0.65 setting. This balances deeper panel shading with clearer metallic reflections; it is a visual calibration of the mobile BRDF, not a measured paint composition. Dielectric reflectance respects the imported specular control rather than assigning every surface the same F0. The headlamps use two synchronized scene passes: the first captures the reflectors without the optical shells, and the second refracts that HDR image through the molded lens before adding Fresnel reflection. Both air/glass/air interfaces are evaluated on the front shell; the rear shell is hidden. Circular lenses draw before the rectangular cover in a `ModelSortGroup` with a post-pass depth stage, and the glass does not write depth during shading. This corrects the cover hiding most of the lens treatment while retaining the opaque bodywork's depth test. Zoned 3.8 mm ribs distinguish the two optics, and filtered circular relief defines their molded edges.

The refracted ray is projected onto the existing 43 mm-deep parabolic cup with a 59.3 mm radius and roughly 8 mm clearance at its lip. These dimensions describe the existing model, not measurements of the physical headlamp. The passes use the same camera snapshot and no prior-frame history; rear and side views skip the hidden headlamp pass. This screen-space approximation cannot trace off-screen geometry or multiple internal bounces. The front and side indicators now have a prismatic amber return beneath their existing clear cover. Absorption and relief approximate the reference appearance; they do not emit light or indicate vehicle lamp state. Reflectors retain their imported surface parameters. Taillight covers use the same dielectric Fresnel treatment instead of the imported semitransparent metallic material; red/amber plastic has a single surface-reflection layer. `MetalReview/` contains actual simulator frames and revision hashes, including a close camera for the complete headlamp and indicator. [Before/after](../headlamp-comparison.jpg), [close-up](../headlamp-closeup.jpg) and `optics-validation.json` document this pass. Simulator results do not establish iPhone frame rate or thermal performance.

## Regeneration

Use Blender 4.5 with Metal on macOS. No Python runtime, Blender installation or network service is required by the app.

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --disable-autoexec \
  ios/Design/Vehicle/E36-316i.blend --python ios/tools/export_vehicle.py

python3 ios/tools/prepare_vehicle_exhaust.py \
  ios/Design/Vehicle/E36-316i.usdz \
  .context/vehicle-exhaust/E36-Tucked.usdz

python3 ios/tools/prepare_photographic_studio.py

python3 ios/tools/prepare_vehicle_stance.py \
  --source .context/vehicle-exhaust/E36-Tucked.usdz \
  --output .context/vehicle-stance --front-mm 30 --rear-mm 15

/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --disable-autoexec \
  --python ios/tools/bake_vehicle_lighting.py -- \
  --model .context/vehicle-stance/E36-AppStance.usdz \
  --environment ios/Design/Vehicle/SoftboxEnvironment.exr \
  --output .context/vehicle-lighting --exposure 0 --hybrid-studio --skip-native-save

python3 ios/tools/pack_vehicle_lighting.py .context/vehicle-lighting
```

Download the CC0 [Studio Small 09 HDR](https://polyhaven.com/a/studio_small_09) and pass its path to `prepare_photographic_studio.py --source` when the local source cache is absent. That tool requires OpenImageIO and NumPy.

The exhaust, stance and packing tools need NumPy and Pixar's `usd-core` in the development Python environment. Packing preserves corner positions, split normals and UV seams exactly while removing unused UV sets and consolidating redundant vertex indices. Validate the bake against the stance derivative, not the original ride-height export. Review the baked model in the simulator before replacing the bundled model. The bake and stance reports record source/environment hashes, exposure, encoding and output hashes; keep them beside the corresponding USDZ. When changing ride height or lighting, regenerate both ground shadows with `prepare_vehicle_shadows.py` from the same transformed geometry and environment.

Regenerate the display LUT with `python ios/tools/build_vehicle_display_lut.py` in an authoring environment containing NumPy and `opencolorio`. The generator validates interpolation against 20,000 deterministic OCIO samples and writes its configuration hash, domain and error statistics beside the LUT.

Prepare the runtime coordinate conversion before prefiltering with Xcode’s `realitytool`. A six-direction RGB-gradient probe found a 90° equirectangular convention offset after converting Blender Z-up to the app’s Y-up. The preparation tool shifts columns without interpolation or clipping; it preserves the original HDR for Blender bakes. `environment-orientation-validation.json` records the uncorrected failure and corrected axes.

```sh
python3 ios/tools/prepare_vehicle_environment.py \
  --source ios/E36OBD/VehicleScene/StudioEnvironment.exr \
  --output .context/vehicle-lighting/RealityKitEnvironment.exr

xcrun realitytool image --platform iphoneos --deployment-target 18.0 \
  --cube-face-size 1024 --specular-size 1024 --diffuse-size 64 \
  --ibl-sampling-quality high \
  --output-reality-asset ios/E36OBD/VehicleScene/StudioEnvironment.realityenv \
  .context/vehicle-lighting/RealityKitEnvironment.exr
```

The environment preparation tool requires NumPy and OpenImageIO during authoring. Keep its report with the compiled resource hashes in `scene-settings.json`.

Debug simulator builds accept `--demo --vehicle-review=nose` (or `rear`, `side`, `optics`) to render a fixed photo-matched camera. `--vehicle-review=cabin` checks the driving position from between the front seats with the complete model visible. These review views are excluded from Release and do not alter the normal dashboard. Compare actual Metal screenshots, not only Blender previews, when evaluating runtime materials.

`ios/tools/render_vehicle.py` produces an optional offline turntable under `.context/vehicle-turntable`; it does not populate app resources. `ios/tools/render_vehicle_references.py` regenerates the photographic studies. Source attribution and reconstruction limits are in [CREDITS.md](CREDITS.md); validation is in [../../VALIDATION.md](../../VALIDATION.md).

### Rear lower insert (11 September)

The lower central apron now meets the underside of the bumper corners. Its previous 34 mm downward bow is removed, with a smooth transition into the corners and the exhaust notch retained. This is a local mesh correction; the upper seam, paint/black boundaries, other 386 meshes, left-hand-drive cabin and wheel stance are unchanged. The app USDZ, ambient visibility and ground shadow were regenerated from the corrected source. See `rear-apron-validation.json`. The `--vehicle-review=apron` Debug camera inspects the actual Metal asset from behind.

The rectangular headlamp cover now carries a combined front/back dielectric reflection, a broad low-intensity return, and derivative-filtered moulding across the complete assembly. This keeps the outer glass visible between the two circular optics. The correction is limited to the front headlamp covers; paint, cabin glass, amber plastic, and the vehicle geometry are unchanged. See [the Metal close-up](../Widgets/headlamp-detail.png).
