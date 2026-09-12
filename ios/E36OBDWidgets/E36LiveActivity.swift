import ActivityKit
import SwiftUI
import WidgetKit
import E36Core

struct E36LiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: E36ActivityAttributes.self) { context in
            E36LiveActivityContent(context: context)
                .activityBackgroundTint(.black)
                .activitySystemActionForegroundColor(CompanionAppearance.amber)
                .widgetURL(URL(string: "e36://dashboard"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.bottom) {
                    E36ActivityFace(snapshot: context.state.snapshot, stale: context.isStale, small: false, island: true)
                }
            } compactLeading: {
                Image(systemName: context.state.snapshot.observation.capture == .recording && !context.isStale ? "record.circle" : "pause.circle")
                    .foregroundStyle(CompanionAppearance.amber)
                    .accessibilityLabel("Captura E36")
            } compactTrailing: {
                let snapshot = context.state.snapshot
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(context.isStale ? "—" : snapshot.formatted(snapshot.primarySensor)).monospacedDigit()
                    Text(snapshot.primarySensor.unit).font(.system(size: 9))
                }.font(.system(size: 14, weight: .semibold).width(.condensed)).foregroundStyle(CompanionAppearance.amber)
            } minimal: {
                Image(systemName: context.isStale ? "pause.circle" : "tachometer").foregroundStyle(CompanionAppearance.amber)
            }
            .widgetURL(URL(string: "e36://dashboard"))
            .keylineTint(CompanionAppearance.amber)
        }
        .supplementalActivityFamilies([.small])
    }
}
private struct E36LiveActivityContent: View {
    let context: ActivityViewContext<E36ActivityAttributes>
    @Environment(\.activityFamily) private var family
    var body: some View {
        E36ActivityFace(snapshot: context.state.snapshot, stale: context.isStale, small: family == .small)
    }
}
