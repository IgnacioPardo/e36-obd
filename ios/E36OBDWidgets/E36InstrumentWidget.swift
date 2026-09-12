import SwiftUI
import WidgetKit
import E36Core

struct InstrumentEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot
    let sensor: Sensor
}
struct InstrumentProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> InstrumentEntry { preview() }
    func snapshot(for configuration: E36WidgetConfiguration, in context: Context) async -> InstrumentEntry {
        context.isPreview ? preview(sensor: configuration.instrument.sensor) : read(configuration)
    }
    func timeline(for configuration: E36WidgetConfiguration, in context: Context) async -> Timeline<InstrumentEntry> {
        let entry = read(configuration)
        // WidgetKit owns the actual schedule. Dates stay visible even if a reload is delayed.
        return Timeline(entries: [entry], policy: .after(entry.date.addingTimeInterval(300)))
    }
    private func read(_ configuration: E36WidgetConfiguration) -> InstrumentEntry {
        let date = Date()
        let store = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: WidgetSnapshotStore.appGroup)
            .map { WidgetSnapshotStore(directory: $0) }
        let saved = try? store?.read(configuration.source.source)
        return InstrumentEntry(date: date,
            snapshot: saved ?? WidgetSnapshot(updatedAt: date, source: configuration.source.source), sensor: configuration.instrument.sensor)
    }
    private func preview(sensor: Sensor = .coolant) -> InstrumentEntry {
        let now = Date()
        return InstrumentEntry(date: now, snapshot: WidgetSnapshot(updatedAt: now, receivedAt: now,
            telemetry: Telemetry(rpm: 930, load: 2.7, coolant: 90, battery: 13.48, ecuMS: 341, intake: 28.5),
            capture: .recording, source: .demo), sensor: sensor)
    }
}

struct E36InstrumentWidget: Widget {
    let kind = WidgetSnapshotStore.kind
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: E36WidgetConfiguration.self, provider: InstrumentProvider()) { entry in
            E36WidgetFace(snapshot: entry.snapshot, sensor: entry.sensor, date: entry.date)
                .containerBackground(for: .widget) { Color(white: 0.035) }
        }
        .configurationDisplayName("Instrumento E36")
        .description("Una lectura con su antigüedad. Elegí el sensor; el iPhone controla cuándo se actualiza.")
        .supportedFamilies([.systemSmall])
        .contentMarginsDisabled()
        .containerBackgroundRemovable(true)
    }
}
@main struct E36WidgetBundle: WidgetBundle {
    var body: some Widget {
        E36InstrumentWidget()
        E36GarageWidget()
        E36OBCWidget()
        E36LiveActivity()
    }
}

#Preview(as: .systemSmall) {
    E36InstrumentWidget()
} timeline: {
    InstrumentEntry(date: .now, snapshot: WidgetSnapshot(updatedAt: .now, receivedAt: .now,
        telemetry: Telemetry(rpm: 930, load: 0.7, coolant: 112, battery: 13.48, ecuMS: 341, intake: 64),
        capture: .recording, alerts: [.coolant], source: .demo), sensor: .coolant)
    InstrumentEntry(date: .now, snapshot: WidgetSnapshot(updatedAt: .now), sensor: .coolant)
}
