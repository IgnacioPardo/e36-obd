import SwiftUI
import WidgetKit
import E36Core

struct E36WidgetFace: View {
    let snapshot: WidgetSnapshot
    let sensor: Sensor
    let date: Date
    @Environment(\.widgetRenderingMode) private var renderingMode
    @Environment(\.showsWidgetContainerBackground) private var showsBackground
    private var accent: Color {
        renderingMode == .fullColor ? Color(red: 1, green: 0.64, blue: 0.28) : .primary
    }
    private var scaleColor: Color {
        renderingMode == .fullColor ? Color(red: 1, green: 0.34, blue: 0.23) : .primary
    }
    private var secondaryColor: Color { renderingMode == .fullColor ? Color(white: 0.60) : .secondary }
    private var value: Double? { snapshot.value(for: sensor) }
    private var valueText: String {
        if sensor == .rpm, let value, value >= 2550 { return "2550+" }
        return sensor.formatted(value)
    }
    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 2) {
                HStack(spacing: 4) {
                    Text("E36").font(.system(size: 15, weight: .bold).width(.condensed)).tracking(0.5)
                    Spacer(minLength: 0)
                    Button(intent: RefreshE36WidgetIntent()) {
                        Image(systemName: "arrow.clockwise").font(.system(size: 13, weight: .semibold))
                            .frame(width: 32, height: 28).contentShape(Rectangle())
                    }.buttonStyle(.plain).foregroundStyle(accent)
                        .accessibilityLabel("Actualizar última lectura")
                }.frame(height: 28)
                ZStack(alignment: .bottom) {
                    WidgetNeedle(sensor: sensor, value: value, color: scaleColor).accessibilityHidden(true)
                    HStack(alignment: .firstTextBaseline, spacing: 3) {
                        Text(valueText).font(.system(size: min(42, geometry.size.width * 0.255), weight: .semibold).width(.condensed))
                            .monospacedDigit().minimumScaleFactor(0.7).lineLimit(1)
                        Text(sensor.unit).font(.system(size: 12, weight: .medium))
                    }
                    .foregroundStyle(snapshot.hasWarning(for: sensor) && !snapshot.isOld(at: date) ? scaleColor : accent)
                    .widgetAccentable()
                    .opacity(snapshot.isOld(at: date) && value != nil ? 0.6 : 1)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(sensor.title), última lectura: \(valueText) \(sensor.unit)")
                }.frame(maxHeight: .infinity)
                Text(sensor.title).font(.system(size: 12, weight: .medium)).lineLimit(1)
                if let receivedAt = snapshot.receivedAt {
                    HStack(spacing: 3) {
                        Image(systemName: "clock")
                        Text(snapshot.observationLabel(at: date))
                        Text(receivedAt, style: .relative).monospacedDigit()
                    }
                    .font(.system(size: 10)).foregroundStyle(secondaryColor).lineLimit(1).minimumScaleFactor(0.8)
                    .accessibilityLabel("Lectura recibida \(receivedAt.formatted(date: .abbreviated, time: .standard))")
                } else {
                    Text(snapshot.source == .demo ? "Iniciá una simulación en E36" : "Conectá el lector en E36")
                        .font(.system(size: 10)).foregroundStyle(secondaryColor).lineLimit(1).minimumScaleFactor(0.8)
                }
            }
        }
        .foregroundStyle(renderingMode == .fullColor ? Color(white: 0.89) : .primary)
        .padding(showsBackground ? 12 : 8)
        .widgetURL(URL(string: "e36://dashboard"))
    }
}

private struct WidgetNeedle: View {
    let sensor: Sensor
    let value: Double?
    let color: Color
    private var range: ClosedRange<Double> {
        switch sensor {
        case .rpm: 0...7000
        case .load: 0...16
        case .coolant: 40...120
        case .battery: 8...16
        case .intake: 0...100
        }
    }
    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width / 2, y: size.height * 0.40)
            let radius = min(size.width * 0.42, size.height * 0.36)
            func point(_ fraction: Double, radius: Double) -> CGPoint {
                let angle = (-100 + 200 * fraction) * .pi / 180
                return .init(x: center.x + radius * sin(angle), y: center.y - radius * cos(angle))
            }
            for tick in 0...10 {
                let fraction = Double(tick) / 10
                var line = Path(); line.move(to: point(fraction, radius: radius))
                line.addLine(to: point(fraction, radius: radius * (tick.isMultiple(of: 2) ? 0.80 : 0.89)))
                context.stroke(line, with: .color(color.opacity(sensor == .rpm && fraction > 2550 / 7000 ? 0.3 : 1)), lineWidth: tick.isMultiple(of: 2) ? 2 : 1)
            }
            if let value {
                let upper = sensor == .rpm ? 2550 : range.upperBound
                let fraction = (min(max(value, range.lowerBound), upper) - range.lowerBound) / (range.upperBound - range.lowerBound)
                var needle = Path(); needle.move(to: center); needle.addLine(to: point(fraction, radius: radius * 0.96))
                context.stroke(needle, with: .color(color), style: StrokeStyle(lineWidth: 3, lineCap: .butt))
            }
            context.fill(Path(ellipseIn: CGRect(x: center.x - 4, y: center.y - 4, width: 8, height: 8)), with: .color(color.opacity(0.2)))
        }.widgetAccentable()
    }
}
