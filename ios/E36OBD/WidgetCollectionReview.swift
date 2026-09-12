#if DEBUG
import SwiftUI
import WidgetKit
import E36Core

/// The shipped widget faces, for deterministic visual checks at native sizes.
struct WidgetCollectionReview: View {
    static var requested: Bool { ProcessInfo.processInfo.arguments.contains { $0.hasPrefix("--widget-face-review=") } }
    private var variant: String {
        ProcessInfo.processInfo.arguments.first { $0.hasPrefix("--widget-face-review=") }?.components(separatedBy: "=").last ?? "gallery"
    }
    private var date: Date { .now }
    private var snapshot: WidgetSnapshot {
        let now = Date()
        return WidgetSnapshot(updatedAt: now, receivedAt: variant == "empty" ? nil : now.addingTimeInterval(variant == "stale" ? -500 : -8),
            telemetry: variant == "empty" ? nil : Telemetry(rpm: variant == "off" ? 0 : 930, load: variant == "off" ? 0 : 2.7,
                coolant: variant == "off" ? -32.5 : 90, battery: variant == "off" ? 0 : 13.48, ecuMS: 341, intake: variant == "off" ? -33.5 : 28.5),
            capture: variant == "stale" ? .paused : .recording, source: .demo)
    }
    var body: some View {
        VStack(spacing: 18) {
            Text("E36 / WIDGETS").font(.system(size: 11, weight: .medium, design: .monospaced)).tracking(3).foregroundStyle(.secondary)
            if variant.hasPrefix("large") {
                E36CollectionFace(style: variant.contains("obc") ? .obc : .garage,
                    snapshot: snapshot, sensor: .rpm, date: date, previewFamily: .systemLarge)
                    .frame(width: variant.contains("compact") ? 329 : 364,
                           height: variant.contains("compact") ? 345 : 382)
                    .background(Color(white: 0.035), in: RoundedRectangle(cornerRadius: 26))
            } else {
                HStack(spacing: 16) {
                    card(.garage, small: true)
                    card(.obc, small: true)
                }
                card(.garage, small: false)
                card(.obc, small: false)
            }
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(white: 0.11).ignoresSafeArea()).preferredColorScheme(.dark)
            .accessibilityIdentifier("widgetCollectionReview")
    }
    private func card(_ style: E36CollectionFace.Style, small: Bool) -> some View {
        E36CollectionFace(style: style, snapshot: snapshot, sensor: .rpm, date: date, previewFamily: small ? .systemSmall : .systemMedium)
            .frame(width: small ? 170 : 356, height: 170)
            .background(Color(white: 0.035), in: RoundedRectangle(cornerRadius: 24))
    }
}
#endif
