#if DEBUG
import SwiftUI
import E36Core

/// Review the exact extension view at its two system presentation sizes.
/// This does not simulate ActivityKit scheduling or WatchConnectivity delivery.
struct CompanionReview: View {
    static var requested: Bool { ProcessInfo.processInfo.arguments.contains { $0.hasPrefix("--activity-face-review=") } }
    private var variant: String {
        ProcessInfo.processInfo.arguments.first { $0.hasPrefix("--activity-face-review=") }?.components(separatedBy: "=").last ?? "full"
    }
    private var snapshot: CompanionSnapshot {
        let date = Date()
        var snapshot = CompanionSnapshot(streamID: "review", sequence: 1,
            observation: .init(updatedAt: date, receivedAt: variant == "stale" ? date.addingTimeInterval(-45) : date,
                telemetry: .init(rpm: 930, load: 0.7, coolant: 112.5, battery: 13.48, ecuMS: 341, intake: 64),
                capture: variant == "paused" ? .paused : .recording,
                alerts: [.coolant, .intake, .lowLoad], source: .demo),
            sessionID: "review", startedAt: date.addingTimeInterval(-125), sampleCount: 341, connected: true, phase: variant == "paused" ? "faultBarrier" : "live")
        if variant == "off" { snapshot.observation.telemetry = .init(rpm: 0, load: 0, coolant: -32.5, battery: 0, ecuMS: 341, intake: -33.5) }
        return snapshot
    }
    var body: some View {
        ZStack {
            Color(white: 0.12).ignoresSafeArea()
            E36ActivityFace(snapshot: snapshot, stale: variant == "stale", small: variant == "small", island: variant == "island")
                .frame(width: variant == "small" ? 184 : 365)
                .clipShape(RoundedRectangle(cornerRadius: 24))
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("activityReviewFace")
        }.preferredColorScheme(.dark)
    }
}
#endif
