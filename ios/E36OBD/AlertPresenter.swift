import UIKit
import UserNotifications
import AVFAudio
import E36Core

@MainActor final class AlertPresenter: NSObject, @preconcurrency UNUserNotificationCenterDelegate {
    private var player: AVAudioPlayer?
    override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }
    func requestPermission() async -> String {
        let center = UNUserNotificationCenter.current()
        do {
            let settings = await center.notificationSettings()
            if settings.authorizationStatus == .notDetermined { _ = try await center.requestAuthorization(options: [.alert, .sound]) }
            let updated = await center.notificationSettings()
            return updated.authorizationStatus == .authorized ? "Notificaciones habilitadas" : "Avisos dentro de la app; revisá permisos de notificación"
        } catch { return "No se pudo solicitar permiso: \(error.localizedDescription)" }
    }
    func present(_ transition: AlertTransition, settings: AlertSettings, foreground: Bool, demo: Bool, title: String? = nil) {
        guard transition.started, !ProcessInfo.processInfo.arguments.contains("--uitesting") else { return }
        if foreground {
            guard transition.audible else { return }
            if settings.haptics { UINotificationFeedbackGenerator().notificationOccurred(.warning) }
            if settings.sound, let url = Bundle.main.url(forResource: "alert", withExtension: "wav") {
                try? AVAudioSession.sharedInstance().setCategory(.ambient, mode: .default, options: [.mixWithOthers])
                player = try? AVAudioPlayer(contentsOf: url); player?.play()
            }
        } else {
            let content = UNMutableNotificationContent()
            content.title = title ?? transition.rule.title
            content.body = transition.message
            content.threadIdentifier = "e36-alerts"
            if settings.sound && transition.audible { content.sound = UNNotificationSound(named: UNNotificationSoundName("alert.wav")) }
            // Background haptics are controlled by iOS notification settings, not a background feedback generator.
            let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
            UNUserNotificationCenter.current().add(request)
        }
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                               withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([])
    }
}
