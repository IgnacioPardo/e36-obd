# E36 instrument design review

The first version treated each requirement as another visible component. It needed a coherent instrument architecture.

## Critique

| Problem in the first version | Consequence | Design change |
| --- | --- | --- |
| Alerts, errors and discovered devices were conditional children of the main vertical stack. | Their appearance changed the available height and resized or moved the gauges precisely when attention mattered most. | Instrument frames depend only on the viewport. A fixed annunciator strip owns transient states; device lists belong to the connection sheet. |
| Navigation either rebuilt the dashboard or covered it with cards that resembled dismissible trays. | Gauges lost their position, or selected tabs appeared to open temporary overlays. | Full content pages share a persistent dock. The dashboard stays mounted and hidden; returning reveals the same instrument positions. Only connection uses a native sheet. |
| The first version used orange for every UI role; the first redesign then made the scales white. | One lacked hierarchy; the other lost the illuminated E36 character. | Orange-red instrument markings, amber LCD readings, subdued unsupported RPM, and ordinary ivory/gray text in controls and secondary pages. |
| Circular bezels, triangular hands and metallic hubs resembled separate watches. | The result did not resemble the supplied BMW cluster. | Shared matte black background, flat broad needles, large black hubs, and fan-shaped auxiliary scales. |
| Five equal rectangular buttons. | Starting a capture had the same prominence as opening settings. | One clear En vivo/Detener action, three quiet navigation controls, and connection access in the header. |
| The demo selector, firmware status sentences and link timing occupied the driving screen. | Test controls and implementation detail competed with the vehicle. | One fixed DEMO menu; ECU latency and reception rate in the connection sheet. The main face retains the five channels, units and recording state. |
| A large amber panel occupied a separate row in landscape. | It reduced the available height for the main instruments. | Intake and recording status sit inside the existing bottom control bar; portrait uses a shallower, dark display. |
| Faults immediately exposed a running terminal; settings explained basic controls in paragraphs. | The app required reading before it could be scanned. | Fault records first, original messages behind Registro. Settings show thresholds and delivery controls; notifications, idle band and help are disclosed on demand. |
| Tests checked that screens existed, without checking stability. | A passing test did not establish good layout behavior. | UI tests compare the x/y/width/height of every main dial across warnings, multiple simultaneous alerts, engine-off, saturation, reconnection and navigation. |

## Interpreting the brief

The supplied illuminated E36 photograph determines the instruments' visual language. The Apple and watchmaking references inform hierarchy and precision without substituting a watch face for the BMW cluster. These are design interpretations, not claims of an official collaboration.

The tachometer uses a 232-degree sweep, numerals 0–7, half-thousand minor marks, condensed slanted numerals, the two-line 1/min ×1000 legend, a broad orange hand and a matte black hub. Its upper red blocks follow the photographed face, but the entire range above 2550 remains dimmed and labeled unavailable. Color bands are visual face markings; they do not change the configurable alert rules.

The coolant and battery instruments use short fan-shaped scales and channel-specific symbols. The load instrument adapts the denser main scale to milliseconds; it does not present speed or fuel data. Small amber seven-segment readings preserve exact values and units without dominating the analog faces. All lettering, hands, bands and LCD segments are drawn natively.

The dashboard uses a single native instrument composition. Portrait and landscape have intentional layouts; transient app state cannot choose a third layout. Readout values and units remain explicit. The unavailable 2550–7000 RPM sector remains honest, and saturation has its own reserved indication.

Secondary pages use ordinary readable text. Essential operating information is retained even when hidden from the default face: the complete firmware log, fault conditions, reception timing, notification permissions and threshold explanations remain accessible.

Apple's guidance on [alerts](https://developer.apple.com/design/human-interface-guidelines/alerts) supports direct messages without explanations that repeat the controls. Its [gauges guidance](https://developer.apple.com/design/human-interface-guidelines/gauges) reinforces preserving a readable value within its represented range. The user's E36 cluster and OBC photographs remain the physical references.

## Acceptance criteria

- A warning, reader discovery or error cannot change a dial's frame.
- Changing pages or dismissing the connection sheet preserves orientation, instrument positions and the current capture.
- Fallas, Sesiones and Ajustes remain selected when tapped again. Only one destination appears selected; pages have no close button, floating card or dimmed dashboard backdrop.
- Page scroll position, a selected session and unsaved settings survive switching tabs. Connection dismissal returns to the current page.
- The main face contains no firmware log or instructions. Link timing belongs to the connection sheet and the quiet landscape footer.
- All five sensor channels and their units remain available in both orientations.
- Landscape intake and recording indicators fit within the bottom control bar; there is no separate OBC banner above it.
- Controls retain at least a 44 × 44 pt target; maximum Dynamic Type remains usable in scrollable pages and the connection sheet.
- Original samples, alerts, fault text and CSV export retain their existing behavior.
- Review simulator captures in portrait, landscape, with warnings, and across page/sheet navigation. Layout tests supplement visual review.

## Vehicle overview — September 9

The next weakness was the app's overall hierarchy: it opened like a diagnostic tool, with every screen sharing the same instrument texture. The supplied BMW and Tesla examples suggest a more personal starting point, a strong vehicle image, and a clear distinction between ownership information and driving instruments.

**Auto** presents the user's Samoablau four-door E36, one observed connection state and three recent readings. DME diagnostics and recorded journeys remain accessible in the fixed dock. It does not invent remote vehicle controls, health scores, or a successful diagnosis before the DME has been read. Starting En vivo opens **Instrumentos**. Switching either way preserves the same capture; the overview itself sends no ECU command.

The dashboard retains the BMW scales and layout. A barely visible recessed face provides depth without chrome bezels. Only the needles animate between received values, over 0.28 seconds with no overshoot; numeric values and stored samples remain exact. Reduce Motion disables those transitions. Satin black surfaces, ivory primary controls, restrained amber accents, and ordinary readable secondary text distinguish the app shell from the physical instruments.

Landscape places the car and telemetry side by side. Warnings stay in the lower bar. Portrait puts the car above the telemetry rail and keeps the main capture action in a fixed dock. DME records use plain text and a fine amber rule; session charts retain their existing surfaces and interactions.

### Scene-led revision — September 11

The first vehicle overview still gave its large E36 heading and repeated navigation rows the same prominence as the car. The rounded telemetry card made the scene feel like an illustration inserted into a utility screen. The revision gives the car a wider stage, a compact **316i / E36 / 1994** identity and a Samoablau finish label. Fine rules, restrained monospace captions and ivory typography connect the overview to the precision of the original instruments without redrawing them.

The overview removes the duplicate Fallas/Sesiones destinations. Three exact readings form an open telemetry rail; connection and capture state sit underneath. A reserved portrait warning slot prevents alerts from resizing the composition. Large text can reflow telemetry into a vertical, scrollable layout. In landscape, identity and finish controls sit at the edges of the scene, leaving more height for the actual car.

The **360°** control expands the exterior within the dashboard bay. Front, profile and rear presets supplement the existing orbit, zoom and reset gestures. The fixed En vivo/Detener and navigation controls remain accessible, as do capture status and warnings. Landscape moves camera presets to a side column. Camera pose lives in the root UI, surviving tab and orientation changes; expanding or closing the exterior never starts, stops or polls acquisition.

Secondary pages use the same fine dividers and restrained typography. The DME's unqueried state remains explicit. Session rows now lead with day/month, time, duration and counts; complete dates remain available to VoiceOver. Graphs, exports, threshold values and all commands are unchanged.

The revision deliberately leaves `CockpitLayout`, `InstrumentDial`, `OBCDisplay`, the shared instrument palette, the entire acquisition stack, and the car's model/shaders unchanged. There is no idle scene animation or new recurring timer.

### Consistent navigation — September 11

The floating inspectors mixed permanent tab selection with temporary-overlay affordances: rounded cards, an X and a dimmed dashboard. They also changed shape between portrait and landscape without gaining real sheet gestures. Fallas, Sesiones and Ajustes now occupy the whole content bay on the same matte background as the app. Portrait stacks the title above the content; landscape places the title beside it, preserving height for records and controls. Neither presentation has a card boundary or close button.

The dock stays in place. Selecting a destination again keeps it open; Auto and Instrumentos return to the dashboard, and their selection marks disappear while another page is active. Destinations mount on first use and retain their state afterward, including session detail, scroll position and unsaved thresholds. Moving the portrait annunciator into the dashboard bay makes page geometry independent of the last dashboard surface while preserving the instruments' available size and position.

Connection is a focused utility presented with SwiftUI's native sheet: system drag indicator, medium/large detents, a close control and the system's landscape adaptation. Swiping it away or closing it returns to the same selected page. This presentation owns no navigation selection and sends no connection or capture command when opened or dismissed. CSV export retains the existing native share sheet.

At accessibility text sizes, threshold labels and their complete value/unit move onto separate lines. The landscape page heading becomes shorter so the content remains scrollable. Pages have explicit accessibility containers and heading traits. [Before/after](Design/navigation-comparison.jpg) · [Three destinations](Design/navigation-pages.jpg) · [Native connection sheet](Design/connection-portrait.jpg).

### Vehicle model and lighting

The overview renders the actual USDZ geometry through RealityKit's `RealityRenderer` in a Metal view. The traced early kidney outline is retained; the erroneous extra 16.7-degree mounting pitch is removed in the source geometry. Its original hood, nose carrier and upper bumper seams are preserved exactly. Grille depth follows the existing panel, with narrow recessed mounting returns closing the aperture gaps. The earlier whole-carrier deformation is removed; the traced grille outline and object rotations remain unchanged. The M bumper contains hollow ducts tessellated from the owner's STEP model at its original dimensions, recessed into their seats, and a rounded lower return matching the softer edge in the photograph. The retained wheel casting remains an approximation of the reference.

The runtime evaluates diffuse, specular, clearcoat and glass from one live HDR environment, retaining geometry-baked ambient visibility in vertex alpha. A verified 90° equirectangular conversion aligns RealityKit with the native Blender scene and its ground shadow. The older baked RGB illumination is no longer sampled, avoiding uneven vertex shading. Glass uses smooth world-space normals, Fresnel reflection and two-pass current-frame Snell refraction through the fluted headlamp lens.

The lamp material pass corrects a separate transparency-order defect: the rectangular cover previously hid much of the circular lens shading. The optical shells now render in a defined order, with refraction evaluated on the front shell and opaque bodywork still respected. Zoned glass ribs, molded lens rims and a prismatic amber return give the headlamps and indicators internal detail without changing paint or vehicle geometry. [Optical comparison](Design/headlamp-comparison.jpg) · [close-up in the app](Design/headlamp-closeup.jpg).

The Samoablau pigment follows ICC-converted samples from three low-glare panels in the owner's RAW photograph. Reflective hood/fender samples are evaluated separately. Paint parameters and annotated sampling regions are retained with the asset; they are inferred rendering parameters, not a measured paint formula.

The subsequent material review addressed washed-out body colour and weak reflections in the app. Environment intensity is half a stop lower, while the runtime paint uses metallic 0.50, roughness 0.22 and clearcoat roughness 0.055. The imported pigment, geometry and environment orientation remain intact. Three alternatives were compared at identical front, profile and rear cameras; the selected balance keeps readable shaded panels and clearer sky/tree reflections without making the body uniformly dark. These are visual PBR adjustments, not measurements of the physical coating. [Before and after in the app](Design/paint-lighting-comparison.jpg).

The rear badge is lower and inset from the trunk seam. The lower charcoal finish is limited to the central rectangular insert; the corner returns stay blue. The original black rubbing strip remains separate. The exhaust body is raised behind the apron. The portable exporter gives the rear insert a material boundary matching the native shader mask.

A transparent ambient shadow is derived from the car onto an eight-metre plane, with its outer edge feathered to zero opacity. It remains fixed in world space as the camera moves. The app car is actual geometry; the shadow contains no car pixels. Fixed illumination requires rebaking if the environment changes.

The [Blender scene](Design/Vehicle/E36-316i.blend) retains its full offline materials and separate HD previews. Native ray-traced glass and indirect lighting are richer than the mobile PBR approximation; an HD Blender render is not evidence of the app's appearance. Runtime quality is reviewed in actual app screenshots.

One-finger horizontal dragging orbits, pinching changes distance, two-finger dragging changes elevation, and double tapping restores the camera. VoiceOver offers 30-degree adjustment and reset. Vertical single-finger gestures remain available to scroll the overview. Camera pose survives orientation and tab changes without accessing acquisition, Bluetooth or SQLite.

The model and precompiled environment load asynchronously and are cached. The Metal view submits frames for camera/layout changes and a bounded initial shader warm-up, then stops drawing. The scene renders to an HDR half-float target with four-sample coverage antialiasing and up to 1.5× spatial supersampling, capped at a 2560-pixel long edge. A final Metal pass resolves radiance and applies the AgX Medium High Contrast display transform. GPU events synchronize both stages before presentation. There is no acquisition-driven render loop. Backgrounding disables rendering; the capture manager retains its own lifecycle.

[Native Blender, GLB and USDZ files](Design/Vehicle/) and [HD previews](Design/Vehicle/HD/) are retained separately. Source attribution, regeneration instructions and reconstruction limits are in [CREDITS.md](Design/Vehicle/CREDITS.md) and the [asset README](Design/Vehicle/README.md).

### Simulator review

[Overview](Design/preview.jpg) · [Vehicle in portrait](Design/overview-portrait.jpg) · [Vehicle in landscape](Design/overview-landscape.jpg) · [Expanded exterior](Design/exterior-landscape.jpg) · [Session archive](Design/sessions-portrait.jpg) · [Instrument panel](Design/instruments-portrait.jpg)

These are captures of the real app in its labeled demonstration mode. Interaction tests rotate and reset the vehicle, exercise the exterior presets, start a capture, switch Auto/Instrumentos and orientation, then verify that each flow produced one session. Separate captures review maximum accessibility text with readable units and the archive in both orientations.
