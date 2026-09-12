#if os(watchOS)
import SwiftUI
import WidgetKit
import E36Core

struct WatchInstrumentEntry: TimelineEntry {
    let date: Date
    let snapshot: CompanionSnapshot
    let sensor: Sensor
}
struct WatchComplicationFace: View {
    let entry: WatchInstrumentEntry
    var previewFamily: WidgetFamily? = nil
    @Environment(\.widgetFamily) private var systemFamily
    private var family: WidgetFamily { previewFamily ?? systemFamily }
    @Environment(\.widgetRenderingMode) private var renderingMode
    private var snapshot: CompanionSnapshot { entry.snapshot }
    private var sensor: Sensor { entry.sensor }
    private var tint: Color { renderingMode == .fullColor ? CompanionAppearance.amber : .primary }
    var body: some View {
        Group {
            switch family {
            case .accessoryInline:
                if let received = snapshot.receivedAt {
                    Text("\(snapshot.formatted(sensor)) \(sensor.unit) · ") + Text(received, style: .relative)
                } else { Text("E36 · Sin lectura") }
            case .accessoryRectangular:
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text("E36").font(.caption2.weight(.bold))
                        Spacer(minLength: 0)
                        Image(systemName: CompanionAppearance.symbol(sensor))
                    }.foregroundStyle(.secondary)
                    HStack(alignment: .firstTextBaseline, spacing: 3) {
                        Text(snapshot.formatted(sensor)).font(.system(.title2, design: .rounded, weight: .semibold)).monospacedDigit()
                        Text(sensor.unit).font(.caption)
                        Spacer(minLength: 1)
                        age.font(.system(size: 10)).foregroundStyle(.secondary)
                    }.foregroundStyle(tint)
                    Text(sensor.title).font(.caption2).foregroundStyle(.secondary)
                }
            case .accessoryCorner:
                Text(snapshot.formatted(sensor)).font(.system(.title3, design: .rounded, weight: .semibold)).monospacedDigit()
                    .widgetLabel { Text("\(sensor.unit) · ") + age }
            default:
                ZStack {
                    AccessoryWidgetBackground()
                    Gauge(value: CompanionAppearance.fraction(sensor, value: snapshot.value(for: sensor))) { EmptyView() }
                        .gaugeStyle(.accessoryCircularCapacity).tint(tint)
                    VStack(spacing: 0) {
                        Text(snapshot.formatted(sensor)).font(.system(size: 15, weight: .semibold).width(.condensed)).monospacedDigit()
                        Text(sensor.unit).font(.system(size: 8))
                        age.font(.system(size: 7)).foregroundStyle(.secondary)
                    }.minimumScaleFactor(0.7)
                }
            }
        }
        .widgetAccentable()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(sensor.title), última lectura: \(snapshot.formatted(sensor)) \(sensor.unit)")
        .accessibilityValue(snapshot.receivedAt?.formatted(date: .abbreviated, time: .standard) ?? "Sin lecturas")
    }
    private var age: Text {
        if let date = snapshot.receivedAt { Text(date, style: .relative) }
        else { Text("—") }
    }
}

#endif
