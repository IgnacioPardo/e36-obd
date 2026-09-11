# E36 vehicle asset

The reference is the owner's Samoablau four-door 1994 E36 316i. This is an editable reconstruction from photographs, not a dimensional scan. The wheel reference supplies nominal `7Jx15 IS47` dimensions; its spoke contours remain approximate. The owner identifies the finish as Samoablau. Material color is inferred from ICC-converted RAW panel samples; spectral paint reflectance and original camera calibration were not measured.

## Vehicle sources

**BMW - E36 Sedan**, publicly released by **MacedoSTI**, December 2, 2023. Original credit: **“Base Model: (ac by Mats)”**. [Source release](https://www.patreon.com/posts/bmw-e36-sedan-93974872), attachment `lm_e36_sedan_2_1_01.zip`, `e36.kn5`.

The release requests “Please Keep Credits”. It does not state a standard Creative Commons or open-source license. The sedan topology, interior, and original lamp/interior textures retain that source attribution.

Gray seat geometry and the initial headlamp fluting texture come from the owner's supplied `E36.blend`. Wheel castings, tyre casing, early kidneys, optical lenses/reflectors, single exhaust and 316i lettering were rebuilt or revised for this reconstruction. The body has an M-style front bumper, stock-style dark rockers and a central charcoal rear insert with body-blue corner returns, black trim and mirrors, no plate holder and no washers. The hollow fog-position air ducts use the owner-supplied `dolot_w_hujogenie-Part.step`, retained as `FogIntake.step`, at original scale with a mirrored opposite side.

The body badges and 18-spoke wheel caps use the owner's supplied BMW SVG letter outlines, with proportions, blue enamel, chrome dividers and material masks adapted to the supplied badge and cap photographs. The original and derived vectors are retained in `ReferenceLogos/`. The latest wheel revision is retained at the owner's request to continue the project; it is not an exact reproduction of the photographed casting.

**BMW E36 318ti**, **Nothing Software**, [original Sketchfab asset](https://sketchfab.com/3d-models/bmw-e36-318ti-f1097224b2c240e3903b20ec46d471b5), **CC BY-NC 4.0**, as recorded in the supplied GLB's embedded `asset.extras`. Owner-provided copy: [webxr_demos/bmw_e36_318ti.glb](https://github.com/IgnacioPardo/webxr_demos/blob/main/models/bmw_e36_318ti.glb). Only a cropped tyre tread normal texture is used; its donor sidewall lettering and vehicle geometry are not used. The crop is remapped to the rebuilt casing and combined with authored sidewall relief. [License](https://creativecommons.org/licenses/by-nc/4.0/).

## Lighting and surfaces

- **AgX display transform**, based on Troy Sobotka's AgX and the Blender configuration developed by Zijun Eary Zhou, Mark Faderbauer and Sakari Kapanen. The app LUT is compiled from Blender 4.5.1's [OCIO configuration](https://github.com/blender/blender/blob/v4.5.1/release/datafiles/colormanagement/config.ocio). The configuration's referenced [OCIO license text](https://github.com/blender/blender/blob/1f46da922a98c6badf6e2de13304358b3b0b7576/release/text/ocio-license.txt) is bundled as `VehicleScene/AgX-LICENSE.txt`. OCIO is an authoring dependency only.

- **Pine Picnic**, Greg Zaal / Jenelle van Heerden, [Poly Haven](https://polyhaven.com/a/pine_picnic), CC0.
- **Park Parking**, Andreas Mischok, [Poly Haven](https://polyhaven.com/a/park_parking), CC0. The app environment is normalized to the previous probe's spherical mean luminance; the original HDR dynamic range is retained.
- **Studio Small 09**, Sergej Majboroda, [Poly Haven](https://polyhaven.com/a/studio_small_09), CC0.
- **Asphalt 02**, Rob Tuytel, [Poly Haven](https://polyhaven.com/a/asphalt_02), CC0.

The original reference-model studio combines Pine Picnic with softened Studio Small 09 lighting. Its HD previews render reflections and shadows together in Cycles. The app scene uses Park Parking daylight, with its radiance range preserved, to provide blue sky and pavement rather than overcast lawn reflections. Ambient visibility is baked from the actual geometry; Metal evaluates diffuse, specular, clearcoat and glass together from the live environment. The runtime prefilter input includes the verified 90° equirectangular convention correction so it agrees with the native scene. A separate transparent ground-shadow texture contains no car pixels. The app does not use an offline car-image sequence.

The separate photo studies use Pine Picnic, reconstructed sun/camera settings and a background crop of the owner's trees. The tree crop contains no car pixels. The depicted car is rendered geometry. These studies approximate the photographs' perspective and daylight; the original camera calibration and measured lighting environment are unavailable.

## Deliverables and runtime

- `E36-316i.blend`: editable native scene, packed textures, procedural paint and optical glass.
- `E36-316i.glb` / `E36-316i.usdz`: portable PBR exports. They approximate the native glass and procedural shaders; the tyre normal map is baked. No casting/body decimation is applied.
- `ReferenceLighting.blend`: three editable photo lighting/camera studies linked to `E36-316i.blend`.
- `reference-comparison.jpg`: reference photographs beside their reconstructed views.
- `../../E36OBD/VehicleScene/`: bundled USDZ model, HDR studio illumination and source hashes. Native RealityKit/Metal rendering uses the model geometry, with custom Metal paint, glass and cabin shaders.

The iOS app renders the model through RealityKit and Metal. Orbit, elevation and zoom move a perspective camera continuously. Blender produces the separate HD previews and editable source; Python and Blender are development tools, neither required by the app. Full source and regeneration commands are in [README.md](README.md).
