import SwiftUI

@MainActor final class AppDelegate: NSObject, UIApplicationDelegate {
    let model = AppModel()
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        model.boot(restoration: launchOptions?[.bluetoothCentrals] != nil)
#if DEBUG
        if model.isDemo, ProcessInfo.processInfo.arguments.contains("--companion-system-review") {
            Task { [weak model] in
                for _ in 0..<40 {
                    guard let model else { return }
                    if model.canStart { model.start(); return }
                    try? await Task.sleep(for: .milliseconds(250))
                }
            }
        }
#endif
        return true
    }
}

@main struct E36OBDApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    var body: some Scene {
        WindowGroup {
#if DEBUG
            if WidgetCollectionReview.requested {
                WidgetCollectionReview()
            } else if CompanionReview.requested {
                CompanionReview()
            } else if VehicleReferenceReview.requested {
                VehicleReferenceReview()
            } else {
                RootView(model: delegate.model)
            }
#else
            RootView(model: delegate.model)
#endif
        }
    }
}
