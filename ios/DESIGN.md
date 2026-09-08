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
- The main face contains no firmware log, instructions or ECU transport timings.
- All five sensor channels and their units remain available in both orientations.
- Landscape intake and recording indicators fit within the bottom control bar; there is no separate OBC banner above it.
- Controls retain at least a 44 × 44 pt target; maximum Dynamic Type remains usable in scrollable inspectors.
- Original samples, alerts, fault text and CSV export retain their existing behavior.
- Review simulator captures in portrait, landscape, with warnings, and with inspectors open. Layout tests supplement visual review.
