import SwiftUI
import WatchConnectivity
import WidgetKit
import E36Core

private final class WatchDataReply: @unchecked Sendable {
    private let lock = NSLock()
    private var action: ((Data) -> Void)?
    init(_ action: @escaping (Data) -> Void) { self.action = action }
    func send() { lock.lock(); let reply = action; action = nil; lock.unlock(); reply?(Data()) }
}

private actor WatchObservationStorage {
    private let store: CompanionSnapshotStore?
    private var writePolicy = CompanionPublicationPolicy()
    private var reloadPolicy = CompanionPublicationPolicy()
    init() {
        store = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: CompanionSnapshotStore.appGroup)
            .map(CompanionSnapshotStore.init(directory:))
    }
    func load() -> [CompanionSnapshot] { WidgetSource.allCases.compactMap { try? store?.read($0) } }
    func save(_ snapshot: CompanionSnapshot) throws {
        guard let store else { throw CompanionSnapshot.CompanionError.invalidPayload }
        var nextWrite = writePolicy
        guard nextWrite.shouldPublish(snapshot, at: Date(), interval: 1) else { return }
        try store.write(snapshot); writePolicy = nextWrite
        if reloadPolicy.shouldPublish(snapshot, at: Date(), interval: 300) {
            WidgetCenter.shared.reloadTimelines(ofKind: CompanionSnapshotStore.kind)
        }
    }
}

@MainActor final class WatchModel: NSObject, ObservableObject, WCSessionDelegate {
    @Published private(set) var snapshot = CompanionSnapshot.empty()
    @Published private(set) var reachable = false
    @Published private(set) var message: String?
    @Published private(set) var commandPending = false
    @Published var source: WidgetSource = .reader {
        didSet {
            UserDefaults.standard.set(source.rawValue, forKey: "watchSource")
            snapshot = inbox.snapshot(for: source) ?? .empty(source: source)
            message = nil; request(.snapshot)
        }
    }
    @Published var selected = 0
    private let storage = WatchObservationStorage()
    private var inbox = CompanionInbox()
    private var session: WCSession?
    private var requestID: UUID?
    private var timeout: Task<Void, Never>?
    private var snapshotTask: Task<Void, Never>?
    private var pendingSave: [WidgetSource: CompanionSnapshot] = [:]
    private var saving: Task<Void, Never>?
    private var demoTask: Task<Void, Never>?
    private var isVisible = false
    private let localDemo: Bool

    override init() {
        localDemo = ProcessInfo.processInfo.arguments.contains("--demo")
        super.init()
        source = localDemo ? .demo : (WidgetSource(rawValue: UserDefaults.standard.string(forKey: "watchSource") ?? "") ?? .reader)
        selected = min(5, max(0, UserDefaults.standard.integer(forKey: "watchGauge")))
        if let preset = ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix("--watch-review=") })?.split(separator: "=").last {
            selected = Sensor.allCases.firstIndex { $0.rawValue == preset } ?? 5
        }
        Task {
            for saved in await storage.load() { _ = inbox.accept(saved) }
            snapshot = inbox.snapshot(for: source) ?? .empty(source: source)
            if localDemo { if isVisible { startDemo() }; return }
            let session = WCSession.default; self.session = session
            session.delegate = self; session.activate()
        }
    }
    func setVisible(_ visible: Bool) {
        isVisible = visible
        snapshotTask?.cancel(); snapshotTask = nil
        if localDemo {
            if visible { startDemo() } else { demoTask?.cancel(); demoTask = nil }
            return
        }
        guard visible else { return }
        request(.snapshot)
        // Streaming samples come from the phone. This bounded heartbeat only
        // recovers a missed reachability transition or a suspended counterpart.
        snapshotTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(10))
                guard !Task.isCancelled, let self else { return }
                if !self.snapshot.isFresh(at: .now) { self.request(.snapshot) }
            }
        }
    }
    func finishBackgroundDelivery() async {
        // Keep the system's WatchConnectivity task alive through delegate
        // delivery and the atomic widget-cache write, then return promptly.
        let deadline = Date().addingTimeInterval(20)
        while !Task.isCancelled, Date() < deadline {
            if let session, session.activationState == .activated, !session.hasContentPending {
                activated()
                await saving?.value
                return
            }
            try? await Task.sleep(for: .milliseconds(100))
        }
    }
    func open(_ url: URL) {
        guard url.scheme == "e36watch", let sensor = Sensor(rawValue: url.lastPathComponent) else { return }
        if let value = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == "source" })?.value,
           let source = WidgetSource(rawValue: value) { self.source = source }
        selected = Sensor.allCases.firstIndex(of: sensor) ?? 0
    }
    func request(_ action: CompanionRequest.Action) {
        guard !localDemo else { return }
        guard requestID == nil else { return }
        guard let session, session.activationState == .activated, session.isReachable else {
            reachable = false
            if action != .snapshot { message = "Abrí E36 en el iPhone" }
            return
        }
        let request = CompanionRequest(action: action, source: source)
        guard let data = try? JSONEncoder().encode(request) else { return }
        reachable = true; requestID = request.id; commandPending = true
        if action != .snapshot { message = nil }
        timeout?.cancel()
        timeout = Task { [weak self] in
            try? await Task.sleep(for: .seconds(12))
            guard !Task.isCancelled, let self, self.requestID == request.id else { return }
            self.requestID = nil; self.commandPending = false
            if action != .snapshot { self.message = "Sin confirmación. Revisá el iPhone." }
        }
        session.sendMessageData(data, replyHandler: { @Sendable [weak self] data in
            Task { @MainActor in self?.receiveReply(data, id: request.id) }
        }, errorHandler: { @Sendable [weak self] _ in
            Task { @MainActor in
                guard let self, self.requestID == request.id else { return }
                self.requestID = nil; self.commandPending = false; self.reachable = false
                self.timeout?.cancel()
                if action != .snapshot { self.message = "Sin confirmación. Revisá el iPhone." }
            }
        })
    }
    private func receiveReply(_ data: Data, id: UUID) {
        guard requestID == id else { return }
        timeout?.cancel(); requestID = nil; commandPending = false
        guard data.count <= 12288, let reply = try? JSONDecoder().decode(CompanionReply.self, from: data),
              let safe = try? CompanionSnapshot.decode(reply.snapshot.encoded()) else {
            message = "Respuesta no válida"; return
        }
        accept(safe)
        if !reply.accepted || reply.message != nil { message = reply.message ?? "Acción no disponible" }
    }
    private func accept(_ incoming: CompanionSnapshot) {
        guard inbox.accept(incoming) else { return }
        if incoming.source == source { snapshot = incoming }
        pendingSave[incoming.source] = incoming
        guard saving == nil else { return }
        saving = Task { [weak self] in
            guard let self else { return }
            while let (source, snapshot) = pendingSave.first {
                pendingSave.removeValue(forKey: source)
                do { try await storage.save(snapshot) }
                catch { message = "No se pudo guardar la última lectura" }
            }
            saving = nil
        }
    }
    private func activated() {
        guard let session else { return }
        reachable = session.activationState == .activated && session.isReachable
        for source in WidgetSource.allCases {
            if let data = session.receivedApplicationContext[source.rawValue] as? Data,
               let snapshot = try? CompanionSnapshot.decode(data) { accept(snapshot) }
        }
        if isVisible { request(.snapshot) }
    }
    private func startDemo() {
        guard demoTask == nil else { return }
        let arguments = ProcessInfo.processInfo.arguments
        let scenario = arguments.first { $0.hasPrefix("--scenario=") }?.split(separator: "=").last ?? "normal"
        let stream = UUID().uuidString; let start = Date(); var sequence: UInt64 = 0
        demoTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }; sequence += 1
                let date = Date(); let received = scenario == "stale" ? date.addingTimeInterval(-45) : date
                let telemetry: Telemetry = scenario == "off" ? .init(rpm: 0, load: 0, coolant: -32.5, battery: 0, ecuMS: 341, intake: -33.5)
                    : .init(rpm: scenario == "saturated" ? 2550 : 930, load: 0.7,
                            coolant: scenario == "heat" ? 112.5 : 90, battery: 13.48, ecuMS: 341, intake: scenario == "heat" ? 64 : 28.5)
                let reading = WidgetSnapshot(updatedAt: date, receivedAt: received, telemetry: telemetry,
                    capture: .recording, alerts: scenario == "heat" ? [.coolant, .intake, .lowLoad] : [.lowLoad], source: .demo)
                accept(.init(streamID: stream, sequence: sequence, observation: reading,
                    sessionID: "watch-demo", startedAt: start.addingTimeInterval(-120), sampleCount: Int(sequence), connected: true, phase: "live"))
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }
    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: (any Error)?) {
        Task { @MainActor [weak self] in self?.activated() }
    }
    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        Task { @MainActor [weak self] in self?.activated() }
    }
    nonisolated func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {
        let data = WidgetSource.allCases.compactMap { applicationContext[$0.rawValue] as? Data }
        Task { @MainActor [weak self] in
            for payload in data { if let snapshot = try? CompanionSnapshot.decode(payload) { self?.accept(snapshot) } }
        }
    }
    nonisolated func session(_ session: WCSession, didReceiveMessageData messageData: Data, replyHandler: @escaping (Data) -> Void) {
        let reply = WatchDataReply(replyHandler)
        Task { @MainActor [weak self] in
            if let snapshot = try? CompanionSnapshot.decode(messageData) { self?.accept(snapshot) }
            reply.send()
        }
    }
}
