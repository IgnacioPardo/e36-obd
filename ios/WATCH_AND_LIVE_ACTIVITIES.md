# Watch and Live Activities — implementation plan

## Product

Keep the existing iPhone BLE transport, acquisition state machine, recording database, instrument cluster and vehicle renderer. Add a local iPhone companion for watchOS 11+, using the existing five readings. No second ESP32 connection, server, account or external dependency.

- Watch: six vertically paged screens — RPM, load, coolant, battery, intake and overview. Dials span almost the full Watch width, with identity and sensor captions inside the face, condensed numerals, orange-red needles and amber digits. Crown/swipe navigation; selected gauge persists. Every instrument includes a prominent sensor icon, its unit and connection/capture state; the overview repeats the same icons. The 7000 RPM dial retains the unavailable range above 2550, and saturation is explicit.
- Watch complications: configurable sensor, circular/rectangular/inline families and Smart Stack. Tapping opens that gauge. These are dated observations with visible age, not continuously updating watch faces. Simulation remains separated from reader data internally.
- Live Activity: one per recording session, created from the foreground; elapsed capture time, selected primary sensor, the other readings and alerts in the Lock Screen/expanded presentation. Compact Dynamic Island shows the primary reading and capture state. A small layout supports Watch Smart Stack. End on stop, explicit disconnect or storage failure; retain the same activity through DME fault pauses and reconnects.
- Settings: automatic Live Activities, primary sensor, permission/status feedback. Watch includes phone connection state and explicit capture controls if reachable; controls invoke the existing start/stop methods and are never replayed after disconnection.

## Data and lifecycle

A small versioned, bounded Codable observation carries original values, received time, source, capture state, session identity/start time, alert set and sequence. Shared display policy handles missing channels, unpopulated RAM, stale readings and saturation. Invalid or out-of-order deliveries cannot replace a newer valid observation.

The iPhone publishes after its existing ordered processing. Companion work runs asynchronously with a latest-value mailbox: WatchConnectivity, ActivityKit and companion disk I/O must not delay BLE commands, samples or SQLite transactions. Watch messages stream only while reachable; latest application context supplies opportunistic background refresh. At most one interactive transfer is outstanding. Context and complication reloads are throttled; errors do not turn off recording.

The Watch atomically caches observations in its own App Group container for its widget extension. The phone App Group does not synchronize across devices. A receiver restart loads the dated cache, then requests the current state. Interactive requests have IDs and expire, with bounded duplicate protection for capture controls. No fabricated workout, audio or extended background session is used to keep the Watch alive.

Live Activities use local ActivityKit updates, a stale date and bounded update cadence. There is no APNs dependency. Reconcile existing activities after restoration, finish obsolete sessions, respect user dismissal and disabled permissions, and never recreate a dismissed activity repeatedly. Source changes and new sessions cannot inherit another session's readings. Always On presentation dims and removes animation; delayed updates remain visibly dated.

## Implementation order

1. Finish and verify the left-hand-drive asset; deliver that correction independently.
2. Add shared observation/ordering/publication/lifecycle policies and meaningful unit tests.
3. Add WatchConnectivity phone/watch adapters and isolated persistence; wire a nonblocking publisher into the iPhone model.
4. Add the watchOS app, WidgetKit complication extension, entitlements, icons and shared scheme through the project generator.
5. Add ActivityKit attributes, lifecycle coordinator, extension layouts and iPhone settings.
6. Build phone/watch/simulator products; run core and targeted UI tests. Capture and inspect Watch gauges, missing/stale/alert/demo states, complication families, Lock Screen and Dynamic Island layouts. Check the existing iPhone capture flow still preserves one session.
7. Install on reachable paired hardware without uninstalling, preserving phone database rows. Report physical connectivity, widget scheduling and Always On checks separately from simulator validation.

## Platform references

- [Enable Developer Mode](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device): required separately on each development device.

- [WatchConnectivity](https://developer.apple.com/documentation/watchconnectivity/wcsession): immediate reachable messages and opportunistic latest application context have different delivery guarantees.
- [Live Activities](https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities): local lifecycle, foreground creation and background updates.
- [Live Activities on Apple Watch](https://developer.apple.com/videos/play/wwdc2024/10068/): small supplemental family, automatic synchronization, update budgets and reduced luminance.
- [Widget update policy](https://developer.apple.com/documentation/widgetkit/keeping-a-widget-up-to-date): system-controlled reload scheduling.

App gauge screens are not replacements for Apple's system watch faces. Complications and Live Activities remain subject to system refresh limits. Live BLE and Watch background delivery require hardware evidence; simulator success alone cannot validate them.

## Use

Build the shared `E36OBD` scheme for the iPhone; it embeds `E36Watch.app` and the Watch complication extension. Install E36 from the Watch app on the paired iPhone, or run the shared `E36Watch` scheme on a paired watchOS 11+ device. All four app/extension targets use the same development team and App Group entitlement. For local installation, Developer Mode must be enabled separately on the iPhone and on the Watch (Settings → Privacy & Security → Developer Mode, restart and confirm). Install the watchOS platform in Xcode before building either scheme.

On the Watch, swipe vertically or turn the Digital Crown through RPM, load, coolant, battery, intake and the overview. The overview has explicit En vivo/Detener controls when the iPhone is reachable. The iPhone must already be connected to the ESP32; the Watch never scans for it. The ellipsis menu chooses real-reader or demo data. Simulation and reader data remain separate.

Long-press the system watch face, edit a complication slot and select Instrumento E36. Circular, rectangular, inline and corner families are provided; available slots depend on the face. Configure the sensor and source. Smart Stack also supports the rectangular widget. Tapping a complication opens the selected instrument in E36. A complication is a cached observation with its age, subject to watchOS refresh scheduling; it is not a continuously running instrument.

En vivo in the iPhone starts a Live Activity automatically when allowed. Choose its primary sensor or disable automatic activities in Ajustes → A simple vista. iOS also controls permission under Settings → Apps → E36 → Live Activities. The Lock Screen and expanded Dynamic Island show the five sensors; the compact island shows the primary sensor. watchOS 11+ can present the small Live Activity in Smart Stack. Pauses and reconnects keep the same capture; explicit stop, disconnect or a storage failure ends it. Dismissing an activity does not stop recording, and it stays dismissed for that capture unless explicitly re-enabled in app settings.

Values retain units, missing-data dashes, the 2550 RPM saturation limit, and last-received time. A sample is stale after two seconds, and ActivityKit receives that stale date. The system controls when Lock Screen and Always On content is redrawn; the observation age remains visible even when that redraw is deferred. Complications always show observation age. Always On presentation dims. Neither companion feature changes Bluetooth acquisition, protocol commands, disk recording, or the iPhone instrument layout.

## Simulator review

The Watch accepts Debug launch arguments `--demo --watch-review=rpm` (also `load`, `coolant`, `battery`, `intake`, `overview`) and `--scenario=normal|heat|off|stale|saturated`. These generate local review data without contacting the reader. Production demo source uses the iPhone's demo observation stream.

## Verified delivery

The iPhone 17 Pro and Apple Watch Series 8 builds were installed locally on 11 September 2026. The Watch opens successfully on watchOS 26.6; the iPhone update preserves all recorded rows. The paired-simulator check exercises real WatchConnectivity with iPhone demo acquisition; it is separate from local Watch demo screenshots. See [validation](VALIDATION.md) and [Watch screens](Design/Companion/watch-preview.jpg). Physical BLE, long background capture and actual complication refresh scheduling remain hardware checks.
