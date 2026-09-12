import ActivityKit
import Foundation
import Combine
import E36Core

@MainActor final class CompanionCoordinator: ObservableObject {
    @Published private(set) var watchStatus = "Apple Watch · pendiente"
    @Published private(set) var activityStatus = "Se inicia con En vivo"
    @Published var activitiesEnabled: Bool {
        didSet {
            defaults.set(activitiesEnabled, forKey: "liveActivitiesEnabled")
            if activitiesEnabled && !oldValue { activities.allowExplicitRestart() }
            resubmit()
        }
    }
    @Published var primarySensor: Sensor {
        didSet { defaults.set(primarySensor.rawValue, forKey: "liveActivitySensor"); resubmit() }
    }
    private let defaults: UserDefaults
    private let watch = PhoneWatchBridge()
    private let activities: CaptureActivityCoordinator
    private var pending: (CompanionSnapshot, Bool)?
    private var latest: (CompanionSnapshot, Bool)?
    private var consumer: Task<Void, Never>?
    private var activated = false

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        activitiesEnabled = defaults.object(forKey: "liveActivitiesEnabled") as? Bool ?? true
        primarySensor = Sensor(rawValue: defaults.string(forKey: "liveActivitySensor") ?? "") ?? .coolant
        activities = CaptureActivityCoordinator(defaults: defaults)
        watch.onStatus = { [weak self] in self?.watchStatus = $0 }
        activities.onStatus = { [weak self] in self?.activityStatus = $0 }
    }
    func activate(onRequest: @escaping @MainActor (CompanionRequest) async -> CompanionReply) {
        guard !activated else { return }; activated = true
        watch.onRequest = onRequest; watch.activate()
    }
    /// Called after ordered app processing. ActivityKit suspension never holds
    /// the acquisition consumer; obsolete observations coalesce to the latest.
    func publish(_ incoming: CompanionSnapshot, foreground: Bool) {
        var snapshot = incoming; snapshot.primarySensor = primarySensor
        latest = (snapshot, foreground)
        watch.publish(snapshot)
        pending = (snapshot, foreground)
        guard consumer == nil else { return }
        consumer = Task { [weak self] in
            guard let self else { return }
            while let (snapshot, foreground) = self.pending {
                self.pending = nil
                let arguments = ProcessInfo.processInfo.arguments
                let testing = arguments.contains("--uitesting") || ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil
                if testing && !arguments.contains("--live-activity-review") { continue }
                await self.activities.update(snapshot, foreground: foreground, enabled: self.activitiesEnabled)
            }
            self.consumer = nil
        }
    }
    private func resubmit() {
        if let (snapshot, foreground) = latest { publish(snapshot, foreground: foreground) }
    }
}

@MainActor final class CaptureActivityCoordinator {
    var onStatus: (@MainActor (String) -> Void)?
    private let defaults: UserDefaults
    private var active: Activity<E36ActivityAttributes>?
    private var observer: Task<Void, Never>?
    private var publication = CompanionPublicationPolicy()
    private var lastCreated: String?
    private var lastAttempt: String?
    private var retryAfter = Date.distantPast
    private var lifecycle = CaptureActivityPolicy()

    init(defaults: UserDefaults) {
        self.defaults = defaults
        lastCreated = defaults.string(forKey: "lastLiveActivitySession")
        if let lastCreated { lifecycle.suppress(lastCreated) }
    }
    func allowExplicitRestart() {
        lastCreated = nil; defaults.removeObject(forKey: "lastLiveActivitySession"); retryAfter = .distantPast
        lifecycle = CaptureActivityPolicy()
    }
    func update(_ snapshot: CompanionSnapshot, foreground: Bool, enabled: Bool) async {
        let available = ActivityAuthorizationInfo().areActivitiesEnabled
        let running = snapshot.sessionID != nil && snapshot.observation.capture != .interrupted
            && snapshot.observation.capture != .stopped
        let matching = Activity<E36ActivityAttributes>.activities.filter {
            $0.attributes.sessionID == snapshot.sessionID && $0.attributes.source == snapshot.source
                && ($0.activityState == .active || $0.activityState == .stale)
        }
        if let active, active.attributes.sessionID != snapshot.sessionID || active.attributes.source != snapshot.source || !enabled || !available || !running {
            await finish(active, with: snapshot)
        }
        // After a relaunch, terminate orphan activities and adopt this capture's
        // existing one instead of requesting a duplicate.
        for old in Activity<E36ActivityAttributes>.activities where old.id != matching.first?.id || !running || !enabled || !available {
            if old.activityState == .active || old.activityState == .stale { await finish(old, with: snapshot) }
        }
        guard enabled, available, running else {
            onStatus?(!enabled ? "Desactivadas" : (!available ? "Desactivadas en Ajustes del iPhone" : "Se inicia con En vivo"))
            return
        }
        if active == nil, let existing = matching.first { adopt(existing) }
        if active == nil {
            guard foreground else { onStatus?("Abrí E36 para mostrar esta captura"); return }
            guard lifecycle.canStart(snapshot, foreground: foreground, enabled: enabled) else { onStatus?("Cerrada para esta captura"); return }
            if lastAttempt != snapshot.sessionID { retryAfter = .distantPast; lastAttempt = snapshot.sessionID }
            guard Date() >= retryAfter else { return }
            do {
                let activity = try Activity.request(attributes: E36ActivityAttributes(sessionID: snapshot.sessionID!, source: snapshot.source),
                    content: content(snapshot), pushType: nil)
                lastCreated = snapshot.sessionID; defaults.set(lastCreated, forKey: "lastLiveActivitySession")
                lifecycle.suppress(snapshot.sessionID!)
                adopt(activity)
            } catch {
                retryAfter = Date().addingTimeInterval(30)
                onStatus?("No se pudo iniciar la actividad: \(error.localizedDescription)")
                return
            }
        }
        guard let active else { return }
        if active.activityState == .dismissed || active.activityState == .ended {
            self.active = nil; observer?.cancel(); observer = nil
            onStatus?("Cerrada para esta captura"); return
        }
        var next = publication
        if next.shouldPublish(snapshot, at: Date(), interval: 1) {
            await Self.updateActivity(id: active.id, content: content(snapshot))
            publication = next
        }
        onStatus?("Captura en pantalla bloqueada")
    }
    private func content(_ snapshot: CompanionSnapshot) -> ActivityContent<E36ActivityAttributes.ContentState> {
        let stale = snapshot.receivedAt?.addingTimeInterval(2) ?? snapshot.observation.updatedAt
        return ActivityContent(state: .init(snapshot: snapshot), staleDate: stale,
                               relevanceScore: snapshot.observation.alerts.isEmpty ? 50 : 90)
    }
    private func adopt(_ activity: Activity<E36ActivityAttributes>) {
        observer?.cancel(); active = activity; publication = CompanionPublicationPolicy()
        observer = Task { [weak self, weak activity] in
            guard let activity else { return }
            for await state in activity.activityStateUpdates {
                guard !Task.isCancelled, let self, self.active?.id == activity.id else { return }
                if state == .dismissed || state == .ended {
                    self.active = nil; self.onStatus?("Cerrada para esta captura"); return
                }
            }
        }
    }
    private func finish(_ activity: Activity<E36ActivityAttributes>, with snapshot: CompanionSnapshot) async {
        if active?.id == activity.id { observer?.cancel(); observer = nil; active = nil }
        var final = activity.content.state.snapshot
        // A newly started capture must never replace the ended capture's values.
        if final.source == snapshot.source && (snapshot.sessionID == nil || final.sessionID == snapshot.sessionID) {
            final.observation = snapshot.observation
            if final.sessionID == snapshot.sessionID { final.sampleCount = snapshot.sampleCount }
        }
        final.observation.capture = snapshot.observation.capture == .interrupted ? .interrupted : .stopped
        final.observation.updatedAt = .now
        final.connected = false; final.canStart = false
        await Self.endActivity(id: activity.id, content: ActivityContent(state: .init(snapshot: final), staleDate: nil))
    }
    // ActivityKit's Activity reference is not Sendable in the iOS 18 SDK
    // contract. Cross the async boundary with IDs and value content; obtain
    // the framework handle locally rather than sending UI-owned references.
    private nonisolated static func updateActivity(id: String, content: ActivityContent<E36ActivityAttributes.ContentState>) async {
        guard let activity = Activity<E36ActivityAttributes>.activities.first(where: { $0.id == id }) else { return }
        await activity.update(content)
    }
    private nonisolated static func endActivity(id: String, content: ActivityContent<E36ActivityAttributes.ContentState>) async {
        guard let activity = Activity<E36ActivityAttributes>.activities.first(where: { $0.id == id }) else { return }
        await activity.end(content, dismissalPolicy: .after(Date().addingTimeInterval(60)))
    }
}
