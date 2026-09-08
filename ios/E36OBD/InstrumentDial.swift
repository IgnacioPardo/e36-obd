import SwiftUI
import E36Core

struct InstrumentDial: View {
    let sensor: Sensor
    let value: Double?
    var stale = false
    var compact = false
    var warning = false
    private nonisolated var auxiliary: Bool { sensor == .coolant || sensor == .battery }
    private nonisolated var scale: (min: Double, max: Double, major: Double, minor: Double) {
        switch sensor {
        case .rpm: (0, 7000, 1000, 500)
        case .load: (0, 16, 2, 0.5)
        case .coolant: (40, 120, 40, 20)
        case .battery: (8, 16, 4, 2)
        case .intake: (0, 100, 25, 5)
        }
    }
    var body: some View {
        Canvas { context, size in
            let side = min(size.width, size.height)
            let radius = side * (auxiliary ? 0.43 : 0.46)
            let center = CGPoint(x: size.width / 2, y: side * (auxiliary ? 0.64 : 0.48))
            let sweep: Double = auxiliary ? 116 : 232
            func angle(_ value: Double) -> Double { -sweep / 2 + sweep * (value - scale.min) / (scale.max - scale.min) }
            func point(_ radius: CGFloat, _ angle: Double) -> CGPoint {
                .init(x: center.x + radius * sin(angle * .pi / 180), y: center.y - radius * cos(angle * .pi / 180))
            }
            func label(_ text: String, at position: CGPoint, size: CGFloat, color: Color, slanted: Bool = false) {
                let font = Font.system(size: size, weight: .semibold).width(.condensed)
                context.draw(Text(text).font(slanted ? font.italic() : font).foregroundStyle(color), at: position)
            }
            func band(_ from: Double, _ to: Double, color: Color, thickness: CGFloat) {
                var path = Path()
                let steps = max(2, Int(to - from))
                for i in 0...steps {
                    let p = point(radius, from + (to - from) * Double(i) / Double(steps))
                    if i == 0 { path.move(to: p) } else { path.addLine(to: p) }
                }
                for i in (0...steps).reversed() {
                    path.addLine(to: point(radius - thickness, from + (to - from) * Double(i) / Double(steps)))
                }
                path.closeSubpath(); context.fill(path, with: .color(color))
            }
            // The tachometer's original red blocks remain in the unavailable sector.
            // They are a face marking, not a new alert threshold or a fabricated reading.
            if sensor == .rpm {
                for (low, high) in [(6000.0, 6100.0), (6170.0, 6270.0), (6340.0, 6600.0), (6670.0, 7000.0)] {
                    band(angle(low), angle(high), color: Color(red: 0.46, green: 0.10, blue: 0.09), thickness: radius * 0.11)
                }
            } else if sensor == .coolant {
                band(-58, -43, color: Color(red: 0.16, green: 0.36, blue: 0.43), thickness: radius * 0.17)
                band(43, 58, color: Color(red: 0.60, green: 0.16, blue: 0.10), thickness: radius * 0.17)
            }
            for index in 0...Int((scale.max - scale.min) / scale.minor) {
                let number = scale.min + Double(index) * scale.minor
                let major = abs((number - scale.min).truncatingRemainder(dividingBy: scale.major)) < 0.01
                let color = sensor == .rpm && number > 2550 ? ClusterTheme.unavailableScale : ClusterTheme.scale
                var tick = Path()
                tick.move(to: point(radius, angle(number)))
                tick.addLine(to: point(radius * (major ? 0.88 : 0.93), angle(number)))
                context.stroke(tick, with: .color(color), style: StrokeStyle(lineWidth: max(1, side * (major ? 0.011 : 0.004)), lineCap: .butt))
                if major && !auxiliary {
                    label(String(Int(sensor == .rpm ? number / 1000 : number)), at: point(radius * 0.77, angle(number)),
                          size: max(11, side * 0.093), color: color, slanted: true)
                }
            }
            if sensor == .rpm {
                label("1/min", at: .init(x: center.x, y: center.y - side * 0.22), size: side * 0.047, color: ClusterTheme.scale, slanted: true)
                label("×1000", at: .init(x: center.x, y: center.y - side * 0.164), size: side * 0.041, color: ClusterTheme.scale, slanted: true)
                label("2550+ SIN DATO", at: .init(x: center.x, y: center.y + side * 0.18), size: max(8, side * 0.026), color: ClusterTheme.muted)
            } else if !auxiliary {
                label("CARGA", at: .init(x: center.x, y: center.y - side * 0.20), size: max(9, side * 0.047), color: ClusterTheme.scale)
                label("ms", at: .init(x: center.x, y: center.y - side * 0.14), size: max(8, side * 0.04), color: ClusterTheme.scale)
            } else {
                let symbol = sensor == .coolant ? "thermometer.and.liquid.waves" : "minus.plus.batteryblock"
                context.draw(Text(Image(systemName: symbol)).font(.system(size: max(13, side * 0.13))).foregroundStyle(ClusterTheme.scale),
                             at: .init(x: center.x, y: center.y - side * 0.20))
            }
            if let value {
                let a = angle(min(max(value, scale.min), sensor == .rpm ? 2550 : scale.max))
                let radians = a * .pi / 180, ux = sin(radians), uy = -cos(radians)
                let tip = point(radius * 0.985, a), half = side * (auxiliary ? 0.018 : 0.014)
                var hand = Path()
                hand.move(to: .init(x: center.x - uy * half, y: center.y + ux * half))
                hand.addLine(to: .init(x: tip.x - uy * half * 0.55, y: tip.y + ux * half * 0.55))
                hand.addLine(to: .init(x: tip.x + uy * half * 0.55, y: tip.y - ux * half * 0.55))
                hand.addLine(to: .init(x: center.x + uy * half, y: center.y - ux * half)); hand.closeSubpath()
                var lit = context
                lit.addFilter(.shadow(color: ClusterTheme.needle.opacity(stale ? 0 : 0.16), radius: 1.5))
                lit.fill(hand, with: .color(ClusterTheme.needle.opacity(stale ? 0.3 : 1)))
            }
            let hubRadius = side * (auxiliary ? 0.045 : 0.070)
            let hub = CGRect(x: center.x - hubRadius, y: center.y - hubRadius, width: hubRadius * 2, height: hubRadius * 2)
            context.fill(Path(ellipseIn: hub), with: .color(Color(white: 0.045)))
            var rim = Path()
            rim.addArc(center: center, radius: hubRadius, startAngle: .degrees(190), endAngle: .degrees(325), clockwise: false)
            context.stroke(rim, with: .color(Color(white: 0.09)), lineWidth: 0.6)

            let window = CGRect(x: side * (auxiliary ? 0.15 : 0.25), y: side * 0.81,
                                width: side * (auxiliary ? 0.70 : 0.50), height: max(23, side * 0.105))
            context.fill(Path(roundedRect: window, cornerRadius: 1), with: .color(.black.opacity(0.7)))
            let numberHeight = min(window.height - 8, max(13, side * 0.062))
            let unitWidth = max(18, side * 0.075)
            let number = CGRect(x: window.minX + 5, y: window.midY - numberHeight / 2, width: window.width - unitWidth - 10, height: numberHeight)
            SevenSegment.draw(sensor.formatted(value), in: number,
                              color: stale ? ClusterTheme.muted : (warning ? ClusterTheme.danger : ClusterTheme.lcd), context: context)
            label(sensor.unit, at: .init(x: window.maxX - unitWidth / 2 - 2, y: window.midY + 1),
                  size: max(8, side * 0.030), color: ClusterTheme.lcd.opacity(stale ? 0.3 : 0.8))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(sensor.title), \(sensor.formatted(value)) \(sensor.unit)\(stale ? ", dato desactualizado" : "")")
        .accessibilityIdentifier("gauge-\(sensor.rawValue)")
    }
}
