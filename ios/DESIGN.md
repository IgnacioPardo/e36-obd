# E36 instrument design review

The first version treated each requirement as another visible component. It needed a coherent instrument architecture.

## Critique

| Problem in the first version | Consequence | Design change |
| --- | --- | --- |
| Alerts, errors and discovered devices were conditional children of the main vertical stack. | Their appearance changed the available height and resized or moved the gauges precisely when attention mattered most. | Instrument frames depend only on the viewport. A fixed annunciator strip owns transient states; device lists belong to the connection inspector. |
| Every destination replaced the dashboard. | Reading faults or changing a threshold destroyed the driver's spatial reference. | The cockpit stays mounted. Inspectors cover it without translating or scaling it. Closing one reveals the same instrument positions. |
| The first version used orange for every UI role; the first redesign then made the scales white. | One lacked hierarchy; the other lost the illuminated E36 character. | Orange-red instrument markings, amber LCD readings, subdued unsupported RPM, and ordinary ivory/gray text in controls and inspectors. |
| Circular bezels, triangular hands and metallic hubs resembled separate watches. | The result did not resemble the supplied BMW cluster. | Shared matte black background, flat broad needles, large black hubs, and fan-shaped auxiliary scales. |
| Five equal rectangular buttons. | Starting a capture had the same prominence as opening settings. | One clear En vivo/Detener action, three quiet navigation controls, and connection access in the header. |
| The demo selector, firmware status sentences and link timing occupied the driving screen. | Test controls and implementation detail competed with the vehicle. | One fixed DEMO menu; ECU latency and reception rate in the BLE inspector. The main face retains the five channels, units and recording state. |
| A large amber panel occupied a separate row in landscape. | It reduced the available height for the main instruments. | Intake and recording status sit inside the existing bottom control bar; portrait uses a shallower, dark display. |
| Faults immediately exposed a running terminal; settings explained basic controls in paragraphs. | The app required reading before it could be scanned. | Fault records first, original messages behind Registro. Settings show thresholds and delivery controls; notifications, idle band and help are disclosed on demand. |
| Tests checked that screens existed, without checking stability. | A passing test did not establish good layout behavior. | UI tests compare the x/y/width/height of every main dial across warnings, multiple simultaneous alerts, engine-off, saturation, reconnection and panel dismissal. |

## Interpreting the brief

The supplied illuminated E36 photograph determines the instruments' visual language. The Apple and watchmaking references inform hierarchy and precision without substituting a watch face for the BMW cluster. These are design interpretations, not claims of an official collaboration.

The tachometer uses a 232-degree sweep, numerals 0–7, half-thousand minor marks, condensed slanted numerals, the two-line 1/min ×1000 legend, a broad orange hand and a matte black hub. Its upper red blocks follow the photographed face, but the entire range above 2550 remains dimmed and labeled unavailable. Color bands are visual face markings; they do not change the configurable alert rules.

The coolant and battery instruments use short fan-shaped scales and channel-specific symbols. The load instrument adapts the denser main scale to milliseconds; it does not present speed or fuel data. Small amber seven-segment readings preserve exact values and units without dominating the analog faces. All lettering, hands, bands and LCD segments are drawn natively.

The dashboard uses a single native instrument composition. Portrait and landscape have intentional layouts; transient app state cannot choose a third layout. Readout values and units remain explicit. The unavailable 2550–7000 RPM sector remains honest, and saturation has its own reserved indication.

Secondary panels use ordinary readable text. Essential operating information is retained even when hidden from the default face: the complete firmware log, fault conditions, reception timing, notification permissions and threshold explanations remain accessible.

Apple's guidance on [alerts](https://developer.apple.com/design/human-interface-guidelines/alerts) supports direct messages without explanations that repeat the controls. Its [gauges guidance](https://developer.apple.com/design/human-interface-guidelines/gauges) reinforces preserving a readable value within its represented range. The user's E36 cluster and OBC photographs remain the physical references.

## Acceptance criteria

- A warning, reader discovery or error cannot change a dial's frame.
- Opening and closing an inspector preserves orientation, instrument positions and the current capture.
- The main face contains no firmware log or instructions. Link timing belongs to the connection inspector and the quiet landscape footer.
- All five sensor channels and their units remain available in both orientations.
- Landscape intake and recording indicators fit within the bottom control bar; there is no separate OBC banner above it.
- Controls retain at least a 44 × 44 pt target; maximum Dynamic Type remains usable in scrollable inspectors.
- Original samples, alerts, fault text and CSV export retain their existing behavior.
- Review simulator captures in portrait, landscape, with warnings, and with inspectors open. Layout tests supplement visual review.

## Vehicle overview — September 9

The next weakness was the app's overall hierarchy: it opened like a diagnostic tool, with every screen sharing the same instrument texture. The supplied BMW and Tesla examples suggest a more personal starting point, a strong vehicle image, and a clear distinction between ownership information and driving instruments.

**Auto** now presents the user's Samoablau four-door E36, one observed connection state, three recent readings and two destinations: DME diagnostics and recorded journeys. It does not invent remote vehicle controls, health scores, or a successful diagnosis before the DME has been read. Starting En vivo opens **Instrumentos**. Switching either way preserves the same capture; the overview itself sends no ECU command.

The dashboard retains the BMW scales and layout. A barely visible recessed face provides depth without chrome bezels. Only the needles animate between received values, over 0.28 seconds with no overshoot; numeric values and stored samples remain exact. Reduce Motion disables those transitions. Satin black surfaces, ivory primary controls, restrained amber accents, and ordinary readable inspector text distinguish the app shell from the physical instruments.

Landscape places the car and telemetry side by side. Warnings stay in the lower bar. Portrait puts the car above the telemetry card and keeps the main capture action in a fixed dock. DME records and session charts use consistent inset surfaces, without adding explanatory paragraphs to the normal flow.

### Vehicle model and lighting

The overview renders the actual USDZ geometry through RealityKit's `RealityRenderer` in a Metal view. The traced early kidney outline is retained; the erroneous extra 16.7-degree mounting pitch is removed in the source geometry. Its connected carrier panel seats against the chrome without moving any grille piece. The M bumper contains hollow ducts tessellated from the owner's STEP model at its original dimensions, recessed into their seats, and a rounded lower return matching the softer edge in the photograph. The retained wheel casting remains an approximation of the reference.

The runtime combines baked diffuse illumination with live Metal specular, clearcoat and glass reflections. A daylight HDR gives the paint the sky and tree reflections visible in the reference photographs. Cycles traces the fixed-environment diffuse radiance and ambient visibility into vertex attributes; square-root RGB encoding retains detail in dark recesses. Runtime shaders decode that lighting without adding a second diffuse term. Glass uses smooth, transformed vertex normals rather than a flat derivative normal for every triangle. Its view-dependent dielectric reflection remains live.

The Samoablau pigment follows ICC-converted samples from three low-glare panels in the owner's RAW photograph. Reflective hood/fender samples are evaluated separately. Paint parameters and annotated sampling regions are retained with the asset; they are inferred rendering parameters, not a measured paint formula.

The rear badge is lower and inset from the trunk seam. The lower charcoal finish is limited to the central rectangular insert; the corner returns stay blue. The original black rubbing strip remains separate. The exhaust body is raised behind the apron. The portable exporter gives the rear insert a material boundary matching the native shader mask.

A transparent ambient shadow is derived from the car onto an eight-metre plane, with its outer edge feathered to zero opacity. It remains fixed in world space as the camera moves. The app car is actual geometry; the shadow contains no car pixels. Fixed illumination requires rebaking if the environment changes.

The [Blender scene](Design/Vehicle/E36-316i.blend) retains its full offline materials and separate HD previews. Native ray-traced glass and indirect lighting are richer than the mobile PBR approximation; an HD Blender render is not evidence of the app's appearance. Runtime quality is reviewed in actual app screenshots.

One-finger horizontal dragging orbits, pinching changes distance, two-finger dragging changes elevation, and double tapping restores the camera. VoiceOver offers 30-degree adjustment and reset. Vertical single-finger gestures remain available to scroll the overview. Camera pose survives orientation and tab changes without accessing acquisition, Bluetooth or SQLite.

The model and precompiled environment load asynchronously and are cached. The Metal view submits frames for camera/layout changes and a bounded initial shader warm-up, then stops drawing. It uses four-sample antialiasing, GPU event synchronization before presentation, and no acquisition-driven render loop. Backgrounding disables rendering; the capture manager retains its own lifecycle.

[Native Blender, GLB and USDZ files](Design/Vehicle/) and [HD previews](Design/Vehicle/HD/) are retained separately. Source attribution, regeneration instructions and reconstruction limits are in [CREDITS.md](Design/Vehicle/CREDITS.md) and the [asset README](Design/Vehicle/README.md).

### Simulator review

[Vehicle in portrait](Design/overview-portrait.jpg) · [Vehicle in landscape](Design/overview-landscape.jpg) · [Instrument panel](Design/instruments-portrait.jpg)

These are captures of the real app in its labeled demonstration mode. The interaction test rotates and resets the vehicle, starts a capture, switches Auto/Instrumentos and orientation, then verifies that it produced one session.
