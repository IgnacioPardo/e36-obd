#if DEBUG
import SwiftUI
import WidgetKit
import E36Core

struct WatchComplicationReview: View {
    static var requested: Bool { ProcessInfo.processInfo.arguments.contains { $0.hasPrefix("--complication-review=") } }
    private var circular: Bool { ProcessInfo.processInfo.arguments.contains("--complication-review=circular") }
    private let date = Date()
    var body: some View {
        let snapshot = CompanionSnapshot(streamID: "preview", sequence: 1,
            observation: .init(updatedAt: date, receivedAt: date.addingTimeInterval(-45),
                telemetry: .init(rpm: 930, load: 0.7, coolant: 90, battery: 13.48, ecuMS: 341, intake: 28),
                capture: .recording, source: .demo), connected: true)
        VStack(spacing: 22) {
            Text("COMPLICACIÓN").font(.system(size: 9, weight: .medium)).tracking(1.5).foregroundStyle(.secondary)
            WatchComplicationFace(entry: .init(date: date, snapshot: snapshot, sensor: .coolant),
                                  previewFamily: circular ? .accessoryCircular : .accessoryRectangular)
                .frame(width: circular ? 58 : 160, height: circular ? 58 : 76)
            Text("Vista de revisión").font(.system(size: 10)).foregroundStyle(.secondary)
        }.frame(maxWidth: .infinity, maxHeight: .infinity).background(.black)
    }
}
#endif
