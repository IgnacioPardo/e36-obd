import SwiftUI
import WidgetKit
import E36Core

struct WatchInstrumentProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> WatchInstrumentEntry { preview() }
    func snapshot(for configuration: E36WatchConfiguration, in context: Context) async -> WatchInstrumentEntry {
        context.isPreview ? preview(configuration.instrument.sensor) : read(configuration)
    }
    func timeline(for configuration: E36WatchConfiguration, in context: Context) async -> Timeline<WatchInstrumentEntry> {
        let entry = read(configuration)
        return Timeline(entries: [entry], policy: .after(entry.date.addingTimeInterval(300)))
    }
    func recommendations() -> [AppIntentRecommendation<E36WatchConfiguration>] {
        WatchInstrumentChoice.allCases.map { choice in
            let configuration = E36WatchConfiguration(); configuration.instrument = choice
            return AppIntentRecommendation(intent: configuration, description: choice.sensor.title)
        }
    }
    private func read(_ configuration: E36WatchConfiguration) -> WatchInstrumentEntry {
        let now = Date()
        let store = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: CompanionSnapshotStore.appGroup)
            .map(CompanionSnapshotStore.init(directory:))
        let snapshot = (try? store?.read(configuration.source.source)) ?? .empty(source: configuration.source.source)
        return .init(date: now, snapshot: snapshot, sensor: configuration.instrument.sensor)
    }
    private func preview(_ sensor: Sensor = .coolant) -> WatchInstrumentEntry {
        let date = Date()
        return .init(date: date, snapshot: .init(streamID: "preview", sequence: 1,
            observation: .init(updatedAt: date, receivedAt: date,
                telemetry: .init(rpm: 930, load: 2.7, coolant: 90, battery: 13.48, ecuMS: 341, intake: 28.5),
                capture: .recording, source: .demo), connected: true), sensor: sensor)
    }
}

struct E36WatchWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: CompanionSnapshotStore.kind, intent: E36WatchConfiguration.self, provider: WatchInstrumentProvider()) { entry in
            WatchComplicationFace(entry: entry)
                .containerBackground(.black, for: .widget)
                .widgetURL(URL(string: "e36watch://sensor/\(entry.sensor.rawValue)?source=\(entry.snapshot.source.rawValue)"))
        }
        .configurationDisplayName("Instrumento E36")
        .description("Última lectura del iPhone con su antigüedad. Tocá para abrir el instrumento.")
        .supportedFamilies([.accessoryCircular, .accessoryRectangular, .accessoryInline, .accessoryCorner])
    }
}

@main struct E36WatchWidgetBundle: WidgetBundle {
    var body: some Widget { E36WatchWidget() }
}
