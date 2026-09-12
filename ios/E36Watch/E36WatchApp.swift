import SwiftUI

@main struct E36WatchApp: App {
    @StateObject private var model = WatchModel()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            Group {
#if DEBUG
                if WatchComplicationReview.requested { WatchComplicationReview() }
                else { WatchDashboard(model: model) }
#else
                WatchDashboard(model: model)
#endif
            }
                .onOpenURL { model.open($0) }
                .onAppear { model.setVisible(scenePhase == .active) }
                .onChange(of: scenePhase) { _, phase in model.setVisible(phase == .active) }
        }
        .backgroundTask(.watchConnectivity) { await model.finishBackgroundDelivery() }
    }
}
