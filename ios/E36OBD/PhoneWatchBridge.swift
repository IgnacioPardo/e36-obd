import Foundation
import WatchConnectivity
import E36Core

/// WCSession may call replies from any queue. This box transfers a one-shot
/// reply to MainActor while keeping the Objective-C callback out of actor state.
private final class WatchReplySender: @unchecked Sendable {
    private let lock = NSLock()
    private var callback: ((Data) -> Void)?
    init(_ callback: @escaping (Data) -> Void) { self.callback = callback }
    func send(_ data: Data) {
        lock.lock(); let action = callback; callback = nil; lock.unlock()
        action?(data)
    }
}

@MainActor final class PhoneWatchBridge: NSObject, WCSessionDelegate {
    var onRequest: (@MainActor (CompanionRequest) async -> CompanionReply)?
    var onStatus: (@MainActor (String) -> Void)?
    private var session: WCSession?
    private var latest: CompanionSnapshot?
    private var cached: [WidgetSource: CompanionSnapshot] = [:]
    private var contextPolicy = CompanionPublicationPolicy()
    private var streamPolicy = CompanionPublicationPolicy()
    private var sending = false
    private var completed: [UUID: Data] = [:]
    private var order: [UUID] = []
    private var pending: [UUID: [WatchReplySender]] = [:]

    func activate() {
        guard WCSession.isSupported() else { onStatus?("Apple Watch no disponible"); return }
        let session = WCSession.default
        self.session = session; session.delegate = self; session.activate()
    }
    func publish(_ snapshot: CompanionSnapshot) {
        latest = snapshot; cached[snapshot.source] = snapshot
        flush()
    }
    private func flush(force: Bool = false) {
        guard let session, session.activationState == .activated, session.isPaired, session.isWatchAppInstalled,
              let latest else { return }
        let now = Date()
        var contextNext = contextPolicy
        if force || contextNext.shouldPublish(latest, at: now, interval: 15) {
            do {
                let context = try Dictionary(uniqueKeysWithValues: cached.map { ($0.key.rawValue, try $0.value.encoded()) })
                try session.updateApplicationContext(context)
                contextPolicy = contextNext
            } catch { onStatus?("Sincronización pendiente") }
        }
        guard session.isReachable, !sending else { return }
        var streamNext = streamPolicy
        guard force || streamNext.shouldPublish(latest, at: now, interval: 1), let data = try? latest.encoded() else { return }
        sending = true; streamPolicy = streamNext
        session.sendMessageData(data, replyHandler: { @Sendable [weak self] _ in
            Task { @MainActor in self?.sending = false; self?.flush() }
        }, errorHandler: { @Sendable [weak self] _ in
            Task { @MainActor in self?.sending = false; self?.onStatus?("Reloj sin conexión en vivo") }
        })
    }
    private func changedSession() {
        guard let session else { return }
        if !session.isPaired { onStatus?("Sin reloj enlazado") }
        else if !session.isWatchAppInstalled { onStatus?("Instalá E36 en el reloj") }
        else { onStatus?(session.isReachable ? "Reloj conectado" : "Reloj · sincronización en segundo plano") }
        flush(force: true)
    }
    private func receive(_ data: Data, reply: WatchReplySender) async {
        guard data.count <= 2048, let request = try? JSONDecoder().decode(CompanionRequest.self, from: data) else {
            reply.send(Data()); return
        }
        if let previous = completed[request.id] { reply.send(previous); return }
        if pending[request.id] != nil { pending[request.id]?.append(reply); return }
        guard request.isValid(at: .now) else {
            let response = CompanionReply(snapshot: cached[request.source] ?? .empty(source: request.source),
                                          message: "Solicitud vencida. Volvé a intentarlo.", accepted: false)
            reply.send((try? JSONEncoder().encode(response)) ?? Data()); return
        }
        pending[request.id] = [reply]
        let response = await onRequest?(request) ?? CompanionReply(snapshot: cached[request.source] ?? .empty(source: request.source),
                                                                  message: "Abrí E36 en el iPhone", accepted: false)
        let result = (try? JSONEncoder().encode(response)) ?? Data()
        completed[request.id] = result; order.append(request.id)
        if order.count > 32 { completed.removeValue(forKey: order.removeFirst()) }
        let waiters = pending.removeValue(forKey: request.id) ?? []
        waiters.forEach { $0.send(result) }
    }
    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: (any Error)?) {
        Task { @MainActor [weak self] in self?.changedSession() }
    }
    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        Task { @MainActor [weak self] in self?.changedSession() }
    }
    nonisolated func sessionWatchStateDidChange(_ session: WCSession) {
        Task { @MainActor [weak self] in self?.changedSession() }
    }
    nonisolated func sessionDidBecomeInactive(_ session: WCSession) {}
    nonisolated func sessionDidDeactivate(_ session: WCSession) {
        Task { @MainActor [weak self] in self?.sending = false; self?.session?.activate() }
    }
    nonisolated func session(_ session: WCSession, didReceiveMessageData messageData: Data, replyHandler: @escaping (Data) -> Void) {
        let reply = WatchReplySender(replyHandler)
        Task { @MainActor [weak self] in
            guard let self else { reply.send(Data()); return }
            await self.receive(messageData, reply: reply)
        }
    }
}
