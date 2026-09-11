import SwiftUI
import E36Core

enum ClusterTheme {
    static let background = Color(red: 0.047, green: 0.051, blue: 0.055)
    static let panel = Color(red: 0.080, green: 0.087, blue: 0.094)
    static let ink = Color(red: 0.94, green: 0.93, blue: 0.90)
    static let lcd = Color(red: 1, green: 0.65, blue: 0.34)
    static let accent = Color(red: 0.91, green: 0.57, blue: 0.31)
    static let ready = Color(red: 0.60, green: 0.76, blue: 0.66)
    static let scale = Color(red: 1, green: 0.34, blue: 0.23)
    static let unavailableScale = Color(red: 0.43, green: 0.21, blue: 0.17)
    static let needle = Color(red: 1, green: 0.46, blue: 0.23)
    static let muted = Color(red: 0.57, green: 0.60, blue: 0.62)
    static let dead = Color(red: 0.24, green: 0.26, blue: 0.27)
    static let danger = Color(red: 1, green: 0.38, blue: 0.22)
    static let line = Color.white.opacity(0.09)
}

struct CockpitSurface: ViewModifier {
    var radius: CGFloat = 20
    func body(content: Content) -> some View {
        content
            .background(LinearGradient(colors: [Color.white.opacity(0.045), Color.white.opacity(0.015)],
                                       startPoint: .topLeading, endPoint: .bottomTrailing),
                        in: RoundedRectangle(cornerRadius: radius))
            .overlay(RoundedRectangle(cornerRadius: radius).strokeBorder(
                LinearGradient(colors: [Color.white.opacity(0.10), Color.white.opacity(0.025)],
                               startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 0.5))
    }
}

struct Eyebrow: View {
    let title: String
    var body: some View {
        Text(title.uppercased()).font(.system(size: 9, weight: .semibold, design: .monospaced))
            .tracking(2).foregroundStyle(ClusterTheme.muted)
    }
}

/// Only available size determines these frames. Warning, link and panel state never do.
struct CockpitLayout {
    struct Placement: Identifiable {
        let sensor: Sensor
        let frame: CGRect
        let compact: Bool
        var id: Sensor { sensor }
    }
    let placements: [Placement]
    let display: CGRect?
    init(size: CGSize) {
        let w = size.width, h = size.height
        let landscape = w > h
        let displayHeight: CGFloat = 78
        let area = max(0, landscape ? h : h - displayHeight - 12)
        func dial(_ sensor: Sensor, x: CGFloat, y: CGFloat, side: CGFloat, compact: Bool = false) -> Placement {
            Placement(sensor: sensor, frame: CGRect(x: x - side / 2, y: y - side / 2, width: side, height: side), compact: compact)
        }
        if landscape {
            let main = min(w * 0.33 - 8, area)
            let flank = min(w * 0.17 - 8, main * 0.63)
            placements = [
                dial(.battery, x: w * 0.085, y: area * 0.65, side: flank, compact: true),
                dial(.load, x: w * 0.335, y: area / 2, side: main),
                dial(.rpm, x: w * 0.665, y: area / 2, side: main),
                dial(.coolant, x: w * 0.915, y: area * 0.65, side: flank, compact: true)
            ]
            display = nil
        } else {
            let main = min(w * 0.89, area * 0.63)
            let sub = min(w * 0.48, area - main - 6)
            let top = max(0, (area - main - sub - 6) / 2)
            placements = [
                dial(.rpm, x: w / 2, y: top + main / 2, side: main),
                dial(.load, x: w * 0.25, y: top + main + 6 + sub / 2, side: sub),
                dial(.coolant, x: w * 0.75, y: top + main + 6 + sub / 2, side: sub)
            ]
            display = CGRect(x: 10, y: h - displayHeight, width: w - 20, height: displayHeight)
        }
    }
}

struct OBCDisplay: View {
    @ObservedObject var model: AppModel
    var horizontal = false
    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 0) {
                if !horizontal {
                    reading(.battery)
                    Rectangle().fill(ClusterTheme.lcd.opacity(0.12)).frame(width: 1, height: 28)
                }
                reading(.intake)
                if horizontal {
                    Rectangle().fill(ClusterTheme.lcd.opacity(0.12)).frame(width: 1, height: 28)
                    recording.frame(maxWidth: .infinity)
                }
            }
            if !horizontal { recording }
        }
        .padding(.horizontal, horizontal ? 4 : 10).padding(.vertical, horizontal ? 0 : 8)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(horizontal ? Color.clear : Color.black.opacity(0.4), in: RoundedRectangle(cornerRadius: 4))
        .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(horizontal ? Color.clear : ClusterTheme.line, lineWidth: 0.5))
    }
    private func reading(_ sensor: Sensor) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(sensor.title.uppercased()).font(.system(size: 9, weight: .medium)).tracking(1.5)
                .foregroundStyle(ClusterTheme.lcd.opacity(0.65))
            HStack(alignment: .bottom, spacing: 5) {
                SegmentDisplay(text: sensor.formatted(model.displayTelemetry?[sensor]), height: horizontal ? 17 : 22,
                    color: model.stale ? ClusterTheme.muted : (sensor == .intake && model.activeAlerts.contains(.intake) ? ClusterTheme.danger : ClusterTheme.lcd))
                Text(sensor.unit).font(.system(size: 11, design: .monospaced))
            }
        }
        .foregroundStyle(model.stale ? ClusterTheme.muted : (sensor == .intake && model.activeAlerts.contains(.intake) ? ClusterTheme.danger : ClusterTheme.lcd))
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(sensor.title), \(sensor.formatted(model.displayTelemetry?[sensor])) \(sensor.unit)")
        .accessibilityIdentifier("reading-\(sensor.rawValue)")
    }
    private var recording: some View {
        HStack(spacing: 6) {
            let capturing = model.connected && model.phase == .live && !model.stale
            Circle().fill(model.storageError != nil ? ClusterTheme.danger : (model.recording == nil ? ClusterTheme.dead : ClusterTheme.lcd))
                .frame(width: 4, height: 4)
            if let session = model.recording, model.storageError == nil {
                Text(capturing ? "REC" : "PAUSA")
                Text(duration(model.recordingElapsed)).monospacedDigit()
                    .accessibilityIdentifier("recordingIndicator")
                    .accessibilityLabel("\(capturing ? "Grabando" : "Captura en pausa"), \(session.sampleCount) muestras")
            } else { Text(model.storageError == nil ? "REC —" : "REC ERROR") }
        }
        .font(.system(size: 11, weight: .medium, design: .monospaced)).tracking(0.4)
        .foregroundStyle(model.storageError != nil ? ClusterTheme.danger : ClusterTheme.lcd.opacity(0.7))
        .frame(height: 14)
    }
}

func duration(_ seconds: Double) -> String {
    let value = max(0, Int(seconds))
    return String(format: "%02d:%02d:%02d", value / 3600, value / 60 % 60, value % 60)
}

struct PhysicalButton: ButtonStyle {
    var selected = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.subheadline, weight: .semibold))
            .frame(maxWidth: .infinity, minHeight: 48)
            .foregroundStyle(selected ? ClusterTheme.background : ClusterTheme.ink)
            .background(selected ? ClusterTheme.ink : Color.white.opacity(configuration.isPressed ? 0.12 : 0.055), in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(ClusterTheme.line, lineWidth: 0.5))
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(configuration.isPressed ? 0.75 : 1)
    }
}
