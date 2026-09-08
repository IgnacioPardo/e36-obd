# BMW inline ECU adapter — revision E

**162 × 48 × 30.4 mm**, with the buck and ESP32-S3 arranged end-to-end. The body is **41% narrower and 52 mm longer** than revision D. The long BMW ribbed lid has no straps or visible screws across its face. Black printed parts, black hardware; silver paint on the BMW lettering and ribs is optional.

The ESP headers are removed for direct soldering. **Both ESP USB sockets face the tail, away from the OBD plug.** The converter remains above the original ELM housing; the ESP occupies the extended tail. Two straps pass through recessed floor slots under the buck and wrap beneath the ELM. A separate rear tie position supports the extended tail against an existing suitable mounting point.

**First-fit prototype:** the board dimensions, ELM housing and installed vehicle clearance remain provisional. Print the gauge and measure the actual parts before the full enclosure. [PLAN.md](PLAN.md) records the measurement sources and decisions.

![Current inline enclosure, internal layout and exploded assembly](exports/preview.png)

[Compare the previous wide case with this revision](exports/comparison.png).

## Files

| File | Purpose |
|---|---|
| [Exploded views](exports/exploded-views/all-views.png) / [full-resolution ZIP](elm-backpack-exploded-views.zip) | Four angles: labelled assembly, OBD end, underside fasteners and board mounts |
| [viewer.html](viewer.html) | Offline interactive CAD viewer: orbit, open lid, explode, switch silver paint on/off |
| [print-layout.3mf](exports/print-layout.3mf) | Geometry only: **1 base + 1 lid + 4 buck keepers**, flat on the bed |
| [fit-gauge.stl](exports/fit-gauge.stl) | First print to check both board outlines and screw holes |
| [base.stl](exports/base.stl), [lid.stl](exports/lid.stl), [buck-keeper.stl](exports/buck-keeper.stl) | Millimetre meshes in print orientation; print four keepers |
| [base.step](exports/base.step), [lid.step](exports/lid.step), [buck-keeper.step](exports/buck-keeper.step) | Individual editable solids, in print orientation |
| [assembly-with-references.step](exports/assembly-with-references.step) | Assembled CAD, including named electronics, ELM, pads, straps and optional paint references. Do not print these references. |
| [dimensions.svg](exports/dimensions.svg) | Inline layout and longitudinal section |
| [black.png](exports/black.png) | Same printable geometry without silver paint |
| [parameters.json](parameters.json), [model.py](model.py) | Editable dimensions and CAD generator |

## Parts and hardware

| Quantity | Item | Use |
|---|---|---|
| 4 | Black M3 × 25 screws, head diameter ≤5.6 mm, head height ≤2 mm | Insert from **underneath** through the base into the lid's blind 2.6 mm pilots; nominal thread engagement 4.5 mm |
| 4 | M3 × 6 screws, head diameter ≤5.6 mm | Buck keepers |
| 2 | 10 mm-wide reusable straps, about 1 mm thick and 250 mm long | Through floor slots beneath buck, around ELM; trim after checking closure overlap |
| 1 | Suitable nylon tie or 10 mm strap | Rear floor slots to a suitable existing support; choose length after checking installed route |
| 1 each | Nylon ties approximately 2.5 × 150 and 2.5 × 100 mm | ESP retention and internal harness strain relief |
| 4 | Insulating silicone pads, 10 × 16 × 3 mm | Case-to-ELM spacing |
| 4 + 4 | 0.5 mm silicone pads, about 1 × 5 mm | Buck support edges and keeper toes; upper pads compress into a 0.3 mm gap |
| 2 | 0.5 mm silicone pads, 14 × 6 mm | Central ESP underside supports |
| As needed | Insulating sleeve for ties and protection for the drilled ELM hole | Protect wires and board contact areas |

The lid screws travel through 3.4 mm base holes and engage the lid from z=20.5 to 25 mm. Their heads sit below the floor, within the 3 mm mounting-pad gap. Use the specified low heads; taller heads need more spacing. This closure requires detaching the case from the ELM for lid service.

The keeper toes only overlap the PCB's outer 1 mm. Check all four support patches on the real converter; reposition `buck_clamp_fraction` if a lead or component occupies one. The ESP's central supports stay between its two solder rows.

## Print and check

1. Print **fit-gauge.stl** at 100% in millimetres. With the connecting bar and raised hole bosses at the far end, the left pocket is the buck and the right is the ESP. Pockets add 0.3 mm clearance per side. Left screw sample: 2.6 mm pilot; right: 3.4 mm clearance. Test an M3 screw gently by hand and adjust hole diameters for your printer if necessary.
2. Check the **63.5 × 27.5 mm buck PCB** and **65 × 28 mm overall ESP envelope** against the pockets. Measure the buck's maximum component height above its PCB, solder protrusions, the ESP carrier-PCB ends and antenna overhang, USB position, and clear support patches. The gauge does not establish height or connector fit.
3. Measure available space for the **162 mm case plus USB cable** in the actual vehicle position. The reference ELM body ends 84 mm before the case tail. Locate a suitable support for that extension rather than leaving the OBD connection to carry the full cantilever. The case can be repositioned slightly on the ELM; check both strap locations remain over its body and clear of the plug.
4. Starting print settings: 0.4 mm nozzle, 0.20 mm layers, 4 walls, 5 top/bottom layers, 30% gyroid. Base: floor down. Lid: detailed outer face down, locating rim and blind screw bosses upward. Keepers: flat. Use a smooth plate for the lid detail. The recessed field closes with short bridges between the ribs/letters; inspect them in the slicer. Side vents span 2 mm, and the harness anchor spans 3 mm. The recessed **floor** strap channels are open from above and need no bridge across their 12 mm length. Add removable local support under the 32 mm rear USB-window roof.
5. Import the 3MF as geometry and select your own printer/material profile. Base: **48 × 162 × 28 mm**. Inverted lid: **48 × 162 × 9.9 mm**, including its inward screw bosses. Those bosses nest inside the base, so assembled case height is **30.4 mm**. The arranged bed allowance is approximately **110 × 182 mm**, before brim/exclusion zones. No G-code or printer profile is included.
6. Prefer unfilled ASA for the intended car enclosure, following the material manufacturer's profile and enclosed-printing requirements; see [Prusa's ASA guide](https://help.prusa3d.com/article/asa_1809). PETG can serve for a cool bench fit check. Confirm actual operating temperature with the enclosure closed; the vents establish neither weather sealing nor a continuous converter-output rating.

## Assembly, unpowered

1. Test the empty lid and all eight screw positions. Its rim has 0.35 mm clearance per side. The four lid bosses enter relieved base corners with 0.35 mm radial clearance and a 0.3 mm axial gap to the base posts. Do not force or bottom out screws.
2. **Thread the two 10 mm mounting straps before fitting the buck.** Their crossbars sit in the 1 mm-deep floor recesses at y=-55 and -9.3 mm. The straps should sit flush with the normal inner floor, leaving 1 mm below the assumed buck solder envelope. Keep closures below the ELM, clear of its OBD plug. Prepare a separate tie in the rear slots at y=54 if needed for installation support.
3. Protect the existing ELM hole, label the wires, remove the ESP headers/jumper housings and feed the harness through the **16 × 12 mm floor entry** between the boards. Solder directly to pads or very short pin stubs, insulate each joint, and follow the existing [wiring diagram](../../docs/cableado.html).
4. Apply the small buck support pads. Place the converter component side up, with **input terminal/DC-jack end toward the gap between the boards**. Fit the four padded keepers with M3 × 6 screws; tighten only enough to retain the board. Check support and toe contact on the actual PCB edges.
5. Fit the two ESP pads and the ESP component side up, USB facing the tail window. Route insulated wires parallel to its underside. The nominal 1.5 mm solder envelope leaves 3.5 mm for wires. Guide the sleeved 2.5 mm retaining tie through the two small floor slots and over the metal RF shield; keep the antenna, buttons and nearby components free. Snug without bending the PCB.
6. Tie the insulated harness to the small bridge anchor between the boards. Keep slack back to the ELM hole. Reserve the converter's end spaces for terminal-wire bends, and keep wires clear of the lid rim and screw bosses. Rendered wires show routing intent only.
7. Seat the lid and insert its four M3 × 25 screws **from below**. Apply the four 3 mm mounting pads between the ELM's plain back and the case, at x=±10, y=-72/-31 in the reference layout. Keep straps, screw heads, the small ESP tie and hole clear of the pads.
8. Position the case so the floor entry lies just beyond the ELM tail hole. Wrap the two already-threaded straps beneath the ELM and fasten them. Support the extended ESP end through its rear slots using a suitable existing mounting point; check the complete adapter can be unplugged and serviced.
9. Confirm both real USB cable overmolds enter the rear window and mate fully. Check wiring, then run the intended load with the lid closed and verify temperature and Wi-Fi/BLE reception in its actual installation position.

## What was verified

- Each printed CAD part is a single valid solid. All STL meshes are closed, consistently wound, have one connected component and positive volume, and begin at z=0.
- No detected interference between printed parts, the provisional board/component/solder/USB-plug envelopes, mounting straps and ESP retaining tie. Buck-to-ESP envelopes and straps-to-ELM references are checked separately. [CAD results](exports/cad-validation.json).
- The 3MF was reopened and checked for millimetres, three mesh definitions and six placed parts. It has not been sliced for a specific printer. [Mesh results](exports/mesh-validation.json).
- Actual exported mesh renders and the interactive viewer are inspected. Board measurements, detailed cable bends, pad contact, the drilled hole, thermal/RF performance and available vehicle space require physical checks.

Nominal clearances: **2 mm over the buck**, **14 mm over the ESP**, **3.5 mm below ESP solder joints**, **1 mm below buck solder**, **0.35 mm per side of the lid rim**. These are design allowances, not measurements of the user's hardware.

## Cover and finish

The 136 × 25 mm field runs along the case. Nine parallel ribs surround the BMW lettering. The field is recessed 0.4 mm into the 2.4 mm lid, leaving 2 mm skin outside through-vents. Forty-eight segmented openings between ribs provide about 716 mm² of open area; 15 side vents per wall above the buck add 480 mm². Segmented lid slots retain solid bridges along the long ribs. These areas are geometric, not a thermal rating.

Print all six parts in black. For the illustrated silver detail, highlight only the rib tops and BMW letter faces with compatible silver paint. Keep the field dark and the vents open. There is no extra caption, coloured badge or second filament. Fine plastic grain in the renders is illustrative; paint surfaces and texture are excluded from the print meshes. The optional paint is separately named in the STEP and toggleable in the viewer.

## Regenerate

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 ./.cadenv/bin/python hardware/elm-backpack/model.py
python3 hardware/elm-backpack/package.py
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -t 6 --python hardware/elm-backpack/render.py
PYTHONDONTWRITEBYTECODE=1 ./.cadenv/bin/python hardware/elm-backpack/build_visuals.py
```

CAD uses build123d 0.11.1 on Python 3.12; the packager uses Python's standard library; contact sheets use Pillow. The viewer embeds all meshes and works offline. Dimensions are editable in `parameters.json`; regenerate and resolve any reported clash before printing. Arial Bold outlines are baked into the exported geometry; regeneration uses the macOS font where available.

`auto_height` uses the taller board envelope plus 2 mm. The current 18 mm buck allowance is measured **above the PCB top**. A verified 14 mm component height would reduce overall height to 26.4 mm. Do not reduce it from an estimate.

Previous profiles are preserved in `profiles/rev-d.json`, `rev-c.json`, `rev-b.json` and `headers.json`; previous ZIP deliveries remain separate. Current exports and viewer are **revision E**. Older profiles may be regenerated to a separate output directory with `model.py --parameters ... --out ...`; the current dimension-sheet template describes the inline layout.

## Additional exploded views

The [four-view set](exports/exploded-views/all-views.png) uses the actual revision E meshes. Boards remain complete assemblies. Straps and illustrative wiring are hidden for clarity; the underside view also hides electronics and the ELM, and offsets the lid sideways. The board-mount view moves complete boards outward to expose the base seats and floor slots. These are display offsets only; printable geometry is unchanged. Individual plates are 2400 × 2320 PNGs, with transparent 2400 × 2000 source renders in the [view bundle](elm-backpack-exploded-views.zip).

Regenerate after the main CAD export:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -t 6 --python hardware/elm-backpack/render_exploded.py
PYTHONDONTWRITEBYTECODE=1 ./.cadenv/bin/python hardware/elm-backpack/build_exploded_gallery.py
```
