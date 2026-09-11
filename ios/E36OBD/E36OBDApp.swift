import SwiftUI

@MainActor final class AppDelegate: NSObject, UIApplicationDelegate {
    let model = AppModel()
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        model.boot(restoration: launchOptions?[.bluetoothCentrals] != nil)
        return true
    }
}

@main struct E36OBDApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    var body: some Scene {
        WindowGroup {
#if DEBUG
            if VehicleReferenceReview.requested {
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
