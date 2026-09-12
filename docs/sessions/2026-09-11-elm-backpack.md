# E36 inline adapter enclosure — session handoff

This records the enclosure-design chat through the user's 2026-09-11 request to commit and push the workspace and this session's context. The approved design is **revision E, the long enclosure** in `hardware/elm-backpack/`. It houses the separate buck converter and ESP32-S3 next to the existing ELM Bluetooth adapter. It is distinct from the later custom PCB and case in `hardware/onboard/`.

- [Readable conversation](2026-09-11-elm-backpack-transcript.md)
- [Original eight reference images](../../hardware/elm-backpack/references/README.md), with SHA-256 mapping in `manifest.json`
- [Detailed design and measurement sources](../../hardware/elm-backpack/PLAN.md)
- [Printing, hardware, assembly and regeneration](../../hardware/elm-backpack/README.md)
- [Offline 3D viewer](../../hardware/elm-backpack/viewer.html)

## User decisions

The original request was to plan, find measurements and model a printable enclosure for the photographed converter and ESP, using the existing wire hole at the bottom/tail of the ELM shell. The user then authorized removing the ESP headers and soldering directly, requested USB facing the opposite direction, and asked for a 1990s BMW engine-bay appearance.

The wide prototypes looked too much like a retro desktop computer. The user retained the BMW lettering and parallel stripes and wanted a black ECU-adapter enclosure. “Diagnose” was removed; the accepted long version has BMW lettering and ribs without a secondary lid caption. Merely changing the wide case's finish was rejected. Revision E changed the physical layout to end-to-end boards and put screws and mounting straps underneath. The user explicitly approved it: **“The long one is cool af.”** Keep this shape and styling when continuing this enclosure.

The latest design task was four exploded views: a labelled assembly, opposite corner, underside fasteners and board mounts. Those have been rendered from the actual CAD, inspected, and delivered. No further geometry change was requested after approval.

## Approved packaging

| Item | Revision E |
|---|---|
| Enclosure | **162 long × 48 wide × 30.4 high mm**; 41% narrower and 52 mm longer than D |
| Boards | Buck and ESP end-to-end; component sides toward lid |
| ESP connections | Headerless/direct solder; USB at tail, away from OBD plug |
| Buck reference PCB | 63.5 × 27.5 × 1.6; 18 mm component allowance above PCB, 3 mm solder below |
| ESP reference | 65 × 28 overall; 57 mm carrier body, 6.5 antenna overhang, 1.5 USB overhang |
| Floor wire entry | Rounded 16 × 12 at x=-9, y=6, between the boards; adjacent strain-relief anchor |
| Lid closure | Four M3 × 25 from underneath; 2.6 mm printed blind pilots, nominal engagement 4.5 mm |
| Buck retention | Four padded edge keepers with M3 × 6 screws; toes contact outer 1 mm of PCB |
| ESP retention | Padded central seats, guides, and a sleeved tie over the RF shield |
| ELM mounting | Two 10 mm straps through recessed floor slots beneath buck; four 3 mm pads at x=±10, y=-72/-31 |
| Extended tail | Separate rear support-tie slots at y=54; reference tail overhang is 84 mm |
| Finish | Black body/hardware; BMW and long parallel ribs; optional silver paint on raised faces |
| Print layout | 1 base + 1 lid + 4 keepers; approximately 110 × 182 mm before brim |

The base prints at 48 × 162 × 28 mm. The inverted lid is 48 × 162 × 9.9 mm including its inward screw bosses; those nest inside the base, giving 30.4 mm assembled height. Normal walls/floor are 2.4 mm; recessed strap lanes leave 1.4 mm floor skin under approximately 1 mm straps. The 0.4 mm lid field leaves 2 mm skin outside through-vents. The rear USB-window roof needs local removable print support.

Nominal clearances: 2 mm over buck components, 14 over ESP components, 3.5 below ESP solder joints for wires, 1 below buck solder, and 0.35 per side at the lid rim. The capacitor allowance sets case height; do not lower it without measuring the real converter.

## Deliverables and reproduction

- [Printable 3MF](../../hardware/elm-backpack/exports/print-layout.3mf), individual STL/STEP parts, and [fit gauge](../../hardware/elm-backpack/exports/fit-gauge.stl).
- [Reference assembly STEP](../../hardware/elm-backpack/exports/assembly-with-references.step). Electronics, ELM, pads, straps and optional paint are reference objects, not printable parts.
- [Revision E delivery ZIP](../../hardware/elm-backpack/elm-backpack-rev-e.zip); earlier B/C/D deliveries and profiles remain available.
- [Four exploded views](../../hardware/elm-backpack/exports/exploded-views/all-views.png) and [image bundle](../../hardware/elm-backpack/elm-backpack-exploded-views.zip). Individual plates are 2400 × 2320; transparent renders are 2400 × 2000; the overview sheet is 3200 × 3260.
- `model.py` and `parameters.json` generate geometry using build123d 0.11.1/Python 3.12. `package.py` validates meshes and produces the geometry-only 3MF.
- `render.py` generates standard views with Blender. `render_exploded.py` generates four inspection angles and uses Metal if available. `build_visuals.py` and `build_exploded_gallery.py` compose the viewer and image sheets; they use Pillow.

Run from the repository root using the existing ignored CAD environment:

```sh
PYTHONDONTWRITEBYTECODE=1 ./.cadenv/bin/python hardware/elm-backpack/model.py
python3 hardware/elm-backpack/package.py
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -t 6 --python hardware/elm-backpack/render.py
PYTHONDONTWRITEBYTECODE=1 ./.cadenv/bin/python hardware/elm-backpack/build_visuals.py
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -t 6 --python hardware/elm-backpack/render_exploded.py
PYTHONDONTWRITEBYTECODE=1 ./.cadenv/bin/python hardware/elm-backpack/build_exploded_gallery.py
```

Exploded spacing is for presentation. Complete boards remain together; straps and illustrative wiring are hidden. The underside angle also hides electronics/ELM and shifts the lid sideways; the mount angle spreads the boards outward to expose seats and slots. Per-view JSON records the source CAD scene hash. Geometry was not changed for these views.

## Verification and remaining physical work

The saved CAD report contains one valid solid per printed part and zero checked interferences. Mesh reports show closed, consistently wound, connected, positive-volume parts at z=0. The 3MF contains three mesh definitions and six placements in millimetres. These reports were re-read during the archive request. The exploded-view ZIP was previously reopened and CRC-checked, and each render was checked against the approved source-scene hash. This is not a physical-fit or machine-slicing claim.

Before full fabrication, check the actual board outlines, capacitor and solder heights, antenna/USB position, clear pad/contact areas, existing ELM hole, strap thickness, screw heads, cable bends, and vehicle space for the longer tail and USB lead. Support that tail at a suitable existing mount. Temperature and Wi-Fi/BLE performance need testing in the actual installation; vents do not provide weather sealing or an output-current rating. The enclosure has not been physically fit-tested in this chat.

## Workspace save request

The user explicitly requested **all current workspace changes committed and pushed**, plus this chat's context, on the existing branch `IgnacioPardo/esp32-buck-case`. Do not rename the branch or merge it to `main` as part of that request. The enclosure and exploded-view files were already tracked; the new archival files preserve the conversation, decisions and original attachments outside the ignored `.context` directory.

At the save request, additional work from other sessions was present under `ios/`, `hardware/onboard/` and the project documentation. Preserve that work as part of the requested workspace snapshot. See the other handoff/session notes for its design history; the enclosure approval does not imply approval or physical validation of those separate designs.

Checks run for this save: **34 Python firmware tests**, **15 XCTest-based Swift package tests**, and **22 Swift Testing tests** all passed. The firmware tests use simulated hardware; no device firmware was modified. This save did not rerun the full Xcode simulator/UI suite or fabricate a PCB/case. Large existing design assets use the repository's Git LFS rules. Local credentials, build caches and runtime scratch files remain ignored.
