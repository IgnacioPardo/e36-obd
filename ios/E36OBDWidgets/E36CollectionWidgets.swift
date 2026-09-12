import SwiftUI
import WidgetKit

struct E36GarageWidget: Widget {
    let kind = E36WidgetKinds.garage
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: E36WidgetConfiguration.self, provider: InstrumentProvider()) { entry in
            E36CollectionFace(style: .garage, snapshot: entry.snapshot, sensor: entry.sensor, date: entry.date)
                .containerBackground(for: .widget) { Color(white: 0.035) }
        }
        .configurationDisplayName("Garage E36")
        .description("Tu 316i, con la última lectura del sensor que elijas.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
        .contentMarginsDisabled()
        .containerBackgroundRemovable(true)
    }
}

struct E36OBCWidget: Widget {
    let kind = E36WidgetKinds.obc
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: E36WidgetConfiguration.self, provider: InstrumentProvider()) { entry in
            E36CollectionFace(style: .obc, snapshot: entry.snapshot, sensor: entry.sensor, date: entry.date)
                .containerBackground(for: .widget) { Color(white: 0.035) }
        }
        .configurationDisplayName("OBC E36")
        .description("Los cinco sensores en un display ámbar. Elegí la lectura principal.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
        .contentMarginsDisabled()
        .containerBackgroundRemovable(true)
    }
}
