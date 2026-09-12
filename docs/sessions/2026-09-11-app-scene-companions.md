# E36 session context — 11 September 2026

This is the continuation handoff for the long iPhone/vehicle-rendering conversation, including the latest free-camera and widget fixes. It preserves the user's decisions, implementation state, evidence and remaining checks. It is a working summary, not a verbatim chat transcript. Original attachments, build caches and raw device backups remain in the originating workspace's ignored `.context/` directory; the source assets and selected review evidence are versioned in this repository.

The [visible conversation export](../../sessions/codex/01a07e40-ac26-7072-b6db-2e6874e66e4d-visible-2026-09-11.jsonl) preserves the actual user/assistant messages through this checkpoint, with short credentials redacted. Its metadata identifies the export cutoff; internal instructions, private reasoning and tool payloads are not part of that export.

At the user's subsequent request, a [raw-format message/tool archive](../../sessions/codex/01a07e40-ac26-7072-b6db-2e6874e66e4d-raw-records-2026-09-11.jsonl.gz) was also added. It includes command inputs, tool responses and embedded images while retaining exclusions for private reasoning/instructions and credentials. See its [manifest](../../sessions/codex/01a07e40-ac26-7072-b6db-2e6874e66e4d-raw-records-2026-09-11.manifest.json) for the later cutoff and verification details.

## Where to resume

- Repository: `IgnacioPardo/e36-obd`; working branch at handoff: `IgnacioPardo/esp32-buck-case`; comparison/PR base: `origin/main`. Do not rename the branch implicitly.
- Original workspace: `/Users/ignaciopardo/conductor/workspaces/E36_OBD/nassau`. The Conductor workspace display name can differ from this directory.
- The user explicitly requested committing and pushing **all pending workspace changes**, including the context of this chat. This includes the pending onboard PCB/fabrication work as well as the app and 3D assets. That request does not request merging or publishing a release.
- Latest app update is **installed on the iPhone 17 Pro**. The final launch attempt failed because the phone was locked. Unlock and open E36 to see the update and request widget refresh.
- Final in-place installation preserved every original row: **10 sessions, 780 samples, 17,998 events**; SQLite `quick_check` returned `ok`. No session was recording before installation.
- The model is considered done for now by the user. Focus on the scene, materials and crafted interface when asked; do not restart modeling from scratch.

## Product contract and boundaries

The original September 7 handoff in [HANDOFF-app-ios.md](../HANDOFF-app-ios.md) is historical. Its four-value MVP and lack of companion UI were superseded by the full native app plan and later requests.

The native app uses SwiftUI, CoreBluetooth and local SQLite, with iOS 18 minimum and no external runtime dependency. It supports five available DME channels: RPM, injection/load in milliseconds, coolant temperature, battery voltage and intake temperature. DME faults, local sessions, aligned graphs, CSV export, alerts, recovery and background capture belong to the first-version scope. Do not invent oil temperature, vehicle speed, fuel level, gearbox position or unavailable diagnoses.

Preserve the BLE acquisition, instrument cluster and actual readings during visual work. The ESP32 has one BLE central connection. The Watch, widgets and Live Activities consume observations from the phone; none opens another connection to the ESP32. Keep simulated and real observations/storage separate even though the user requested removing visible `DEMO` labels. Simulation remains an explicit selectable source.

Important BLE details to retain:

- Foreground scan without a service filter; select the `E36-OBD` name, then verify NUS and subscribe to TX before commands. Do not rely on a fresh name scan for background recovery.
- NUS service `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`; RX/write `...0002...`; TX/notify `...0003...`. Write individual command characters with response and serialize operations.
- Sensor contract: old `D <rpm> <load> <coolant> <battery> <ecu_ms>`; extended version appends `<intake>`. Preserve the original fields and accept both formats. Example: `D 930 0.70 63.1 13.48 341 23.7`.
- Accumulate bytes to newline before decoding UTF-8. NUS fragments can be 20 bytes. Reject invalid/nonfinite values without replacing the last valid reading; bound lines to 4 KiB and resynchronize after overflow. Reset partial data at connection changes.
- A command interrupts acquisition: do not send periodic queries during live capture. Fault reads pause the same session, use the established firmware/help completion handshake, preserve original text and resume only if live intent remains. An error is not a successful zero-fault result.
- Show query milliseconds separately from receive frequency. Mark samples stale after two seconds. Preserve interruption/recovery events and never show successful REC after storage failure.
- RPM saturates at 2550. Keep the classic 7000 RPM dial, with the unavailable upper range and saturation explicit. Empty RAM can produce zero RPM/load/battery and converted-zero temperatures (−32.5/−33.5 °C), or an all-zero handoff; display DME/no-data state and suppress sensor alerts.
- Initial user-adjustable alerts: load below 1.5 ms at 600–1200 RPM; coolant at least 110 °C for two seconds; intake at least 60 °C for two seconds. Keep existing hysteresis, absent/stale/no-data exclusions and 30-second sound/haptic separation. These are user thresholds, not official BMW limits.

Earlier live-stream stalls, fault errors and gaps under revving were investigated against actual traces and the desktop client. Firmware recovery, bounded cleanup and UART timing changes are documented chronologically in [ios/VALIDATION.md](../../ios/VALIDATION.md), especially the September 9 entries. The user explicitly said the wiring is good and asked to stop repetitive vehicle tests and diagnose from existing data. Do not revive a wiring hypothesis or demand another drive without new evidence. No firmware file was changed by the final camera/widget work.

## Design decisions that must survive future revisions

The intended feel is a collaboration between BMW, Apple and TAG Heuer: restrained, precise, low-copy and recognizably an E36. Keep the 1990s BMW cluster: matte black, amber display, condensed markings, orange-red needles, legible numeric values and units. Instruments must not rearrange when unrelated panels appear. The landscape alert strip belongs in the bottom status area, not a large orange banner.

Current navigation is four ordered bottom tabs: **Auto, Fallas, Sesiones, Ajustes**. All four retain the **same live 3D scene**. Only the adjacent/below content changes. Portrait puts the scene above the content; landscape places it beside the content. The scene reaches the screen edges; text/buttons retain safe readable insets. **En vivo, Instrumentos and the wireless connection icon** stay above. The user specifically rejected replacing that icon with the text `BLE`.

Each successive tab advances the camera by a negative 90-degree step. Auto starts at azimuth 0.58 radians; subsequent tabs subtract π/2 each. Skipping Auto → Ajustes travels −270°, not the shortest +90° path. Reversing tab direction reverses the orbit; retargeting uses the current animation frame. Manual exterior presets retain the shortest arc. Starting capture leaves the selected tab visible; closing Instruments returns to that tab. Session selection and unsaved settings survive navigation. A single renderer survives tab changes, orientation and expansion. Instruments and the connection sheet pause the hidden scene.

### Latest expanded-camera behavior

- One finger orbits in azimuth **and elevation**; vertical drags are accepted in expanded mode.
- Two fingers pan both the camera and its focus in the camera's screen plane. Pan and pinch can operate together.
- Pinch changes world-space distance. It is no longer constrained by the dashboard's 0.8–1.1 zoom range or whole-car bounding-box fit. The only bounds are numerical stability guards (2 mm to 100 km); elevation stops just short of the poles to keep the horizon upright.
- Once navigating, distance/focus stay fixed through orbit and phone rotation; auto-fit does not undo close-ups. The lens near/far planes adapt for inspection.
- The visible reset button, double tap, or exterior presets recover a fitted composition. Expanded single taps do not unexpectedly change the angle.
- Expanded camera state is separate from the ordinary dashboard. Closing it removes free translation/distance and restores safe framing. Selecting a tab also closes it and preserves the ordered tab rotation.

Implementation: [VehicleSceneView.swift](../../ios/E36OBD/VehicleSceneView.swift), [VehicleOverview.swift](../../ios/E36OBD/VehicleOverview.swift), [RootView.swift](../../ios/E36OBD/RootView.swift). `VehicleCameraPose`, `VehicleFreeNavigation`, `VehicleCameraFraming` and `VehicleCameraFlight` hold the camera behavior. Keep `cameraChanged` bound to the current SwiftUI binding when switching camera modes.

## The user's actual car and accepted geometry

The asset is the user's **blue four-door 1994 E36 316i**, left-hand drive, paint **295 Samoablau Metallic**. Never substitute the compact/318ti, a generic coupe or a photograph cutout. The user provided `E36.blend`, GLB bases from their `webxr_demos` repository, many car photos, a BMW roundel SVG, badge/center-cap close-ups and a STEP model of the foglight air duct.

Preserve these corrections and the reasons behind them:

- M-style front bumper, no license plate holder and no foglight/headlamp squirters. Lower front lip should blend into the bumper instead of ending in a sharp cut.
- Early 1990–94 kidney shape, traced to the supplied reference. The outer contour follows the nose-panel lines. **No forward tilt or exaggerated oblique mounting.** The user clarified that “slant” meant the outline, not rotating the complete grilles. Close the gap to the body and preserve hood/nose/bumper alignment.
- Foglight openings contain air-vent ducts, not flush solid caps. Use the provided STEP shape and keep their mounting flush with the bumper opening.
- Wheel spokes are rounded with a U-shaped section, not flat slabs. Use the supplied correct roundel on the center caps. After several iterations the user accepted moving on while explicitly noting the wheels were still imperfect; do not describe them as an exact recreation.
- Hood and trunk roundels need slight doming and the supplied artwork. Do not invent a different emblem.
- No rear-seat headrests. The cabin is left-hand drive.
- Rear `316i` badge is inset from the trunk edges according to the photos.
- Only the lower middle rear-bumper rectangle is black; surrounding bumper areas are body color. Its underside must meet the bumper sides without a downward bulge.
- Exhaust is tucked up, with only its short tip protruding; avoid the previously oversized hanging shape.
- More aggressive final app stance: approximately 30 mm front / 15 mm rear reduction from the source ride height, with regenerated contact shadows. Do not silently lower the source/reference model instead of the app derivative.

The most useful late attachment groups in the original workspace are `bn4A5W`/`ikYeBE`/`gPagQZ`/`YXFhoR`/`v1Ktyx` (car/wheels), `Yy0zYq` and `GWNbiY` (kidney outline), `IMqah3` (duct STEP), `CXaNbr`/`zY5tEq` and `yjGUqg`/`DcL6ru` (roundels/badges), `0lXGWa` (rear bumper/exhaust), `zqQugV`/`MXpH6O` (later reference photos), `FnpxP5` (headlamp cover issue), and `0a2Jif` (widget shadow rectangle). These attachment IDs are local references, not files guaranteed in a new clone.

## Rendering and widget export

The app renders real geometry with RealityKit's RealityRenderer and custom Metal, not a baked turntable or Blender process at runtime. World lighting and the car remain fixed as the camera moves. The user rejected the “video-game asset in a black void” appearance, excessive brightness, flat paint and disappearing headlamp glass. They preferred the studio composition, with believable shadows and Samoablau color.

The current studio combines baked diffuse/ambient visibility with live PBR specular, clearcoat, glass, environment lighting and an AgX display pass. The alternate outdoor scene must agree with its visible surroundings. Keep the established environment-coordinate correction; don't make light rotate with the camera. Complete rectangular headlamp covers, molded glass, circular inner optics and amber indicators must remain legible. The optics use a screen-space two-pass approximation, not full path tracing; do not claim photograph-equivalent accuracy or measured device performance.

Canonical sources: `ios/Design/Vehicle/E36-316i.blend`, portable GLB/USDZ and lighting scenes. Runtime: `ios/E36OBD/VehicleScene/E36-316i.usdz`, **4,745,251 triangles**, SHA-256 `02fffd0543ab1a3184ca6f33b2ee19e440995f8cfd5512e4418037f69efc74bb` at this handoff. Keep reports beside matching derivatives. [Vehicle README](../../ios/Design/Vehicle/README.md) has the export/stance/bake/pack commands; [CREDITS](../../ios/Design/Vehicle/CREDITS.md) records sources. [Scene study](../../ios/Design/Vehicle/SCENE_STUDY.md) records explored environments. Inspect actual Metal screenshots as well as offline HD renders.

Garage widgets use a bounded transparent PNG rendered by the same native scene. The latest reported rectangle was the studio shadow cut off at the bitmap's crop, not the widget layout. The fix exports two identical native cameras: vehicle+shadow, then vehicle-only (`--widget-car-only`). `ios/Design/Widgets/prepare-car.py` isolates and feathers only the shadow contribution in premultiplied alpha, preserving the car. All four PNG edges must have zero alpha. The shipped bitmap is 1024 × 587, SHA-256 `7e95e3e60976500b5e0b1248400f5e6a542f0fd4cac9aa2ff86ec499fb6717f3`. [Widget README](../../ios/Design/Widgets/README.md) and `car-render.json` contain the reproducible workflow. Do not restore a simple hard crop of the full shadow or feather the car itself.

## Watch, widgets and Live Activities

The Watch has large sensor-specific gauges, sensor icons, a selected-gauge deep link from complications, and an overview with explicit capture controls. Its pages are app screens, not replacements for Apple's system watch faces. Complications and widgets show dated observations; system scheduling is not continuous BLE.

Live Activities show the capture on the Lock Screen, Dynamic Island and supported Watch presentation. Same-session pauses/reconnects preserve identity; stop, explicit disconnect and storage failure end the activity. User dismissal stays dismissed. WatchConnectivity uses bounded/versioned observations, sequence validation, latest-value delivery and source separation; companion work must not stall phone acquisition or SQLite.

There are Instrument, Garage (car image) and OBC widget variants. Garage/OBC have small, medium and large iPhone families; `systemLarge` is the largest iPhone family used here. The small widgets support the applicable CarPlay widget surface; this is not a standalone CarPlay dashboard entitlement. The app/Watch icon is the supplied BMW roundel. See [WATCH_AND_LIVE_ACTIVITIES.md](../../ios/WATCH_AND_LIVE_ACTIVITIES.md), [WIDGETS.md](../../ios/WIDGETS.md) and `ios/Design/Companion/`.

## Latest validation and installation evidence

- Final camera/widget run: **11 selected tests passed, 0 failed**: seven camera-math tests, two widget-contract tests and two UI navigation/capture tests. After the last expanded-to-tab transition adjustment, the expanded-camera UI test passed again, including reset settling, leaving expansion via a tab and recovery of dashboard framing.
- Commit preparation also reran `swift test --package-path ios/Core`: **22 tests passed across four suites**. This does not expand the physical-hardware validation claim.
- Reviewed actual simulator close-up, landscape orbit, settled reset, restored dashboard and small/medium/large/compact-large widget screenshots. Also checked the image on three contrasting backgrounds. Camera evidence is in [ios/Design/Camera](../../ios/Design/Camera/); widget evidence is in [ios/Design/Widgets](../../ios/Design/Widgets/). Pixel geometry is not substituted by a retouched photo.
- Simulator and signed iPhone builds succeeded; `codesign --verify --deep --strict` passed. The camera/widget work did not change the instrument layout, firmware or sensor values.
- Last physical install: 11 September around 19:53 ART. CoreDevice accepted the app; launch returned `Locked`. All saved rows remained identical afterward. [Camera validation](../../ios/Design/Camera/validation.json) records this state.
- Earlier the Watch build was installed/opened on the Series 8. Recheck connection/developer state before the next deployment; old “connected” observations are not current evidence.
- These latest results validate local rendering/UI and installation/data preservation. They do **not** validate physical BLE continuity, phone/watch background scheduling, 30-minute capture, wireless CarPlay coexistence, thermal behavior or frame rate.

Originating workspace evidence (ignored, useful while this workspace exists): `.context/free-camera-sep11/FreeCamera.xcresult`, `FreeCameraFinal.xcresult`, `test-summary.json`, `final-test-summary.json`, `phone-final-install.json`, `phone-final-launch.json`, `phone-preservation.json`; earlier ordered-tab results in `.context/navigation-scene-sep11/OrderedOrbit.xcresult`. Build logs, original exports and device backups are in the same directories. Source and selected screenshots/reports above are the portable handoff.

## Build and safe continuation

At the last check Xcode 26.2 was used; the local simulator was iPhone 17 Pro / iOS 26.2, UUID `DE703C07-9225-4F24-BE34-C0A9E39D0155`. The physical iPhone 17 Pro ran iOS 27 beta; the Series 8 ran watchOS 26.6. Rediscover with `xcrun simctl list devices available` / `xcrun devicectl list devices` instead of assuming availability. The iPhone CoreDevice ID was `425B1D9A-9787-5C13-8BDB-8B7BFBA97160`; the Watch was `B43CEF41-A170-58B9-A34E-25033A0404D3`.

```sh
swift test --package-path ios/Core

xcodebuild -project ios/E36OBD.xcodeproj -scheme E36OBD \
  -configuration Debug -destination 'platform=iOS Simulator,id=SIMULATOR_UUID' \
  -derivedDataPath .context/ios-build \
  CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=- test

xcodebuild -project ios/E36OBD.xcodeproj -scheme E36OBD \
  -configuration Debug -destination generic/platform=iOS \
  -derivedDataPath .context/ios-device -allowProvisioningUpdates build
```

Use `ios/Local.xcconfig` for the local signing team; `Signing.xcconfig` includes it optionally. Do not commit signing credentials/profiles. The original workspace's reusable build directories are `.context/watch-icons-sep11/build` and `.context/watch-sep11/device-signed`; disk space was low at handoff, so reuse them rather than creating another complete cache. All necessary SDKs, including watchOS, must be installed. Do not apply a global `-sdk iphonesimulator` to the multi-platform scheme.

During the later transcript export, regenerable module/intermediate caches and the cached simulator/iPhone build products in those two build directories were removed to free space. Rebuild before expecting those products to exist. Installed apps, source assets and device/session data were preserved.

**Never uninstall the physical app to fix an install problem. Never pass `--uitesting` or `--demo` to the physical iPhone/Watch.** UI-testing initialization can reset test storage. Before updating the phone, copy `Library/Application Support/E36` from its app container, including SQLite WAL/SHM; verify `sessions.ended IS NULL` is empty; preserve and compare full-row hashes after an in-place update. The user authorized installation and remote screenshots, but do not interrupt an active capture. Install normally using `devicectl device install app`, then launch without review arguments. Locked phones require the user to unlock them.

For visual iteration: verify one concrete change in native screenshots, keep controls at least 44 pt, preserve both orientations and large text, and run focused checks. Avoid repeating lengthy car tests or broad UI suites after passing checks without a new reason. Review the newest dated evidence rather than an earlier failed attempt or an unfinished animation frame. Follow the existing session-preservation procedure and report hardware gaps honestly.

## Onboard hardware included in this checkpoint

The user's “everything” request also covers the workspace's existing `hardware/onboard/` changes: updated KiCad PCB/project, OBD2 right-angle footprint, board generator, BOM, Gerbers/renderings, JLCPCB pricing script/report and PCBWay sample-order package/script. Keep those artifacts together; do not regenerate the PCB or reorder parts as part of an app-only task. The source-specific notes and current DRC report remain under `hardware/onboard/`. Pricing/availability documents are dated snapshots, not current quotes or proof of purchase. Committing their package is not authorization to place an order.

During this checkpoint, the separate hardware session committed its work as `c003392a`. The app/context commit builds on that commit. Its stored DRC report has zero unconnected items and 60 warning-level violations; commit preparation did not rerun a hardware design review.
