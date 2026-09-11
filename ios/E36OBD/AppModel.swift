import SwiftUI
import E36Core

enum AppSection: String, CaseIterable { case dashboard, connection, faults, sessions, settings }
private enum AppAction: Sendable {
    case boot(Bool), transport(TransportEvent), connect, disconnect, start, stop, faults
    case tick, foreground(Bool), settings(AlertSettings), refreshSessions, permission, expired
}

@MainActor final class AppModel: ObservableObject {
    @Published var section: AppSection = .dashboard
    @Published private(set) var status = "Sin conectar"
    @Published private(set) var connected = false
    @Published private(set) var phase: AcquisitionPhase = .disconnected
    @Published private(set) var telemetry: Telemetry?
    @Published private(set) var lastReceivedAt: Date?
    @Published private(set) var stale = true
    @Published private(set) var hz: Double?
    @Published private(set) var recording: DriveSession?
    @Published private(set) var wantsLive = false
    @Published private(set) var storageError: String?
    @Published private(set) var activeAlerts: [AlertRule] = []
    @Published private(set) var lastAlert: String?
    @Published private(set) var log: [SessionEvent] = []
    @Published private(set) var faultReport = FaultReport()
    @Published private(set) var faultCompleted = false
    @Published private(set) var sessions: [DriveSession] = []
    @Published private(set) var devices: [ReaderDevice] = []
    @Published private(set) var settings = AlertSettings()
    @Published private(set) var notificationStatus = "Permiso de notificaciones pendiente"
    @Published private(set) var widgetError: String?
    @Published private(set) var isForeground = true
    @Published var demoScenario: DemoScenario = .normal { didSet { (transport as? DemoTransport)?.scenario = demoScenario } }
    let isDemo: Bool
    private(set) var store: SessionStore?
    private var transport: (any ReaderTransport)?
    private var decoder = LineDecoder()
    private var machine = AcquisitionMachine()
    private var alerts = AlertEngine()
    private var rate = ReceptionRate()
    private let presenter = AlertPresenter()
    private let widgetPublisher = WidgetPublisher()
    private var continuation: AsyncStream<AppAction>.Continuation!
    private var consumer: Task<Void, Never>?
    private var ticker: Task<Void, Never>?
    private var lastSampleUptime: Double?
    private var elapsedOrigin: Double = 0
    private var elapsedOffset: Double = 0
    private var segment = 0
    private var gapOpen = false
    private var reconnectAttempt = 0
    private var previousValidity: SampleValidity?
    private var operationTask: UIBackgroundTaskIdentifier = .invalid
    private var booted = false
    private let defaults: UserDefaults
    private var now: Double { ProcessInfo.processInfo.systemUptime }

    init() {
        isDemo = ProcessInfo.processInfo.arguments.contains("--demo")
        defaults = .standard
        if let data = defaults.data(forKey: "alertSettings"), let saved = try? JSONDecoder().decode(AlertSettings.self, from: data), saved.isValid { settings = saved }
        let stream = AsyncStream<AppAction> { self.continuation = $0 }
        consumer = Task { [weak self] in
            for await action in stream {
                guard let self else { return }
                await self.handle(action)
            }
        }
    }
    func boot(restoration: Bool) { continuation.yield(.boot(restoration)) }
    func connect() { continuation.yield(.connect) }
    func disconnect() { continuation.yield(.disconnect) }
    func start() { continuation.yield(.start) }
    func stop() { continuation.yield(.stop) }
    func readFaults() { continuation.yield(.faults) }
    func selectDevice(_ id: UUID) { transport?.select(id) }
    func setForeground(_ value: Bool) { continuation.yield(.foreground(value)) }
    func saveSettings(_ value: AlertSettings) { continuation.yield(.settings(value)) }
    func refreshSessions() { continuation.yield(.refreshSessions) }
    func requestNotifications() { continuation.yield(.permission) }
    var canStart: Bool { connected && phase == .idle && storageError == nil }
    var canReadFaults: Bool { connected && (phase == .idle || phase == .live || phase == .recoveringDME) }
    var displayTelemetry: Telemetry? { telemetry?.validity == .populated ? telemetry : nil }
    var recordingElapsed: Double { recording == nil ? 0 : elapsedOffset + max(0, now - elapsedOrigin) }

    private func handle(_ action: AppAction) async {
        switch action {
        case .boot(let restoration): await initialize(restoration: restoration)
        case .transport(let event): await received(event)
        case .connect: transport?.connect(foreground: isForeground, delay: 0)
        case .disconnect:
            _ = machine.setLiveIntent(false, now: now); machine.disconnected(); transport?.disconnect()
            connected = false; devices = []; decoder.reset(); status = "Desconectado"
            await markGap("Desconexión manual"); await finishRecording(message: "Grabación finalizada al desconectar")
        case .start:
            guard canStart, let store else { break }
            do {
                recording = try await store.start(at: Date(), isDemo: isDemo)
                defaults.set(recording?.id, forKey: isDemo ? "demoSessionID" : "activeSessionID")
                elapsedOrigin = now; elapsedOffset = 0; segment = 0; gapOpen = false; previousValidity = nil
                alerts = AlertEngine(); activeAlerts = []; lastAlert = nil; rate.reset()
                apply(machine.setLiveIntent(true, now: now))
                if !ProcessInfo.processInfo.arguments.contains("--uitesting") {
                    Task { self.notificationStatus = await self.presenter.requestPermission() }
                }
            } catch { await failedStorage(error) }
        case .stop:
            apply(machine.setLiveIntent(false, now: now))
            if !connected { transport?.disconnect() }
            if phase == .idle || !connected { await finishRecording(message: "Grabación detenida") }
        case .faults:
            guard canReadFaults else { break }
            faultReport = FaultReport(); faultCompleted = false
            await markGap("Pausa para leer fallas del DME")
            apply(machine.requestFaults(now: now))
        case .tick:
            apply(machine.tick(now: now))
            if phase == .live, let lastSampleUptime, now - lastSampleUptime > 2 {
                await markGap("Sin muestras nuevas durante más de dos segundos")
            }
        case .foreground(let value):
            isForeground = value
            transport?.setForeground(value)
            if value { apply(machine.tick(now: now)) }
        case .settings(let value):
            guard value.isValid else { break }
            settings = value; alerts.interrupt(); activeAlerts = []
            defaults.set(try? JSONEncoder().encode(value), forKey: "alertSettings")
            let json = (try? JSONEncoder().encode(value)).flatMap { String(data: $0, encoding: .utf8) } ?? ""
            await record(.configuration, "Configuración de avisos: " + json)
        case .refreshSessions:
            do { sessions = try await store?.sessions() ?? [] } catch { await failedStorage(error) }
        case .permission: notificationStatus = await presenter.requestPermission()
        case .expired:
            if phase.pending { resetLink(reason: "Se agotó el tiempo disponible para la operación BLE") }
        }
        phase = machine.phase; wantsLive = machine.wantsLive
        if phase == .idle, recording != nil, !wantsLive { await finishRecording(message: "Grabación detenida") }
        updateStatus()
        updateBackgroundTask()
        let capture: WidgetCaptureState = storageError != nil ? .interrupted
            : (recording == nil ? .stopped : (phase == .live && connected && !stale ? .recording : .paused))
        let snapshot = WidgetSnapshot(updatedAt: Date(), receivedAt: lastReceivedAt, telemetry: telemetry,
            capture: capture, alerts: activeAlerts, source: isDemo ? .demo : .reader)
        do {
            try await widgetPublisher.publish(snapshot, foreground: isForeground)
            widgetError = nil
        } catch { widgetError = error.localizedDescription }
    }

    private func initialize(restoration: Bool) async {
        guard !booted else { return }; booted = true
        do {
            let root = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            let folder = root.appendingPathComponent(isDemo ? "E36Demo" : "E36", isDirectory: true)
            if ProcessInfo.processInfo.arguments.contains("--uitesting") { try? FileManager.default.removeItem(at: folder) }
            store = try SessionStore(url: folder.appendingPathComponent("sessions.sqlite"))
            let id = restoration && !isDemo ? defaults.string(forKey: "activeSessionID") : nil
            recording = try await store?.recover(restoring: id)
            if let recording {
                elapsedOffset = recording.elapsed + max(0, Date().timeIntervalSince(recording.lastReceivedAt ?? recording.startedAt))
                elapsedOrigin = now
                let savedSamples = try await store?.samples(sessionID: recording.id) ?? []
                segment = (savedSamples.last?.segment ?? 0) + 1
                _ = machine.setLiveIntent(true, now: now)
                await record(.gap, "Captura restaurada por iOS; intervalo de continuidad desconocida")
            }
            log = try await store?.events(limit: 250) ?? []
            sessions = try await store?.sessions() ?? []
        } catch { await failedStorage(error) }
        transport = isDemo ? DemoTransport() : BluetoothTransport()
        transport?.onEvent = { [weak self] event in self?.continuation.yield(.transport(event)) }
        ticker = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(500))
                guard !Task.isCancelled else { return }
                self?.continuation.yield(.tick)
            }
        }
        if isDemo { transport?.connect(foreground: true, delay: 0) }
        #if DEBUG
        // Physical-device smoke test: exercise a delayed BLE connection without
        // enabling capture or replacing any saved sessions (unlike --uitesting).
        if !isDemo, ProcessInfo.processInfo.arguments.contains("--ble-smoke-test") {
            transport?.connect(foreground: true, delay: 1)
        }
        #endif
    }

    private func received(_ event: TransportEvent) async {
        switch event {
        case .status(let message): status = message
        case .diagnostic(let message): await record(.connection, message)
        case .devices(let list): devices = list
        case .ready(let restored):
            connected = true; decoder.reset(discardPartial: restored)
            rate.reset(); lastSampleUptime = nil; stale = true
            await record(.connection, restored ? "Conexión restaurada" : "Conectado a E36-OBD")
            apply(machine.connected(restored: restored, now: now))
        case .disconnected(let message):
            if isDemo, demoScenario == .disconnect { demoScenario = .normal }
            connected = false; decoder.reset(); machine.disconnected(); status = message
            await markGap(message)
            await record(.connection, message)
            if machine.wantsLive { reconnect() }
        case .waitingForBluetooth(let message):
            connected = false; decoder.reset(); machine.disconnected(); status = message
            await markGap(message)
            await record(.connection, message)
        case .bytes(let data, let receivedAt, let uptime):
            guard connected else { return }
            for line in decoder.receive(data) {
                switch line {
                case .sample(let value): await sample(value, at: receivedAt, uptime: uptime)
                case .invalid(let raw):
                    alerts.interrupt(); activeAlerts = []
                    await record(.invalidLine, raw, at: receivedAt)
                case .text(let text):
                    let reading = machine.phase.readingFaults
                    if reading { faultReport.receive(text) }
                    await record(.message, text, at: receivedAt)
                    apply(machine.text(text, now: uptime))
                    if machine.phase == .recoveringDME { await markGap("Recuperando conexión con el DME") }
                }
            }
        }
    }

    private func sample(_ value: Telemetry, at receivedAt: Date, uptime: Double) async {
        if let lastSampleUptime, uptime - lastSampleUptime > 2 { await markGap("Interrupción entre muestras") }
        let oldPhase = machine.phase
        apply(machine.sample(now: uptime))
        telemetry = value; lastReceivedAt = receivedAt; lastSampleUptime = uptime; stale = now - uptime > 2
        reconnectAttempt = 0
        rate.receive(at: uptime); hz = rate.hz; gapOpen = false
        if previousValidity != value.validity {
            segment += 1; previousValidity = value.validity
            await record(.engineState, value.validity == .unpopulated ? "Motor apagado / DME sin datos" : "RAM del DME poblada", at: receivedAt)
        }
        // A late sample while stopping or reading faults is retained, but cannot raise a new alarm.
        if stale { alerts.interrupt() }
        let changes = machine.phase == .live && machine.wantsLive && !stale
            ? alerts.evaluate(value, at: uptime, settings: settings) : []
        activeAlerts = alerts.active
        var events = changes.map { change in
            SessionEvent(sessionID: recording?.id, timestamp: receivedAt,
                kind: change.started ? .alertStarted : .alertEnded, message: change.message, rule: change.rule)
        }
        if oldPhase == .restoring { events.append(SessionEvent(sessionID: recording?.id, timestamp: receivedAt, kind: .connection, message: "Flujo existente recuperado sin enviar v")) }
        if let recording, let store, storageError == nil {
            let row = RecordedSample(sessionID: recording.id, receivedAt: receivedAt,
                elapsed: elapsedOffset + max(0, uptime - elapsedOrigin), telemetry: value, segment: segment)
            do {
                _ = try await store.append(row, events: events)
                self.recording?.sampleCount += 1; self.recording?.elapsed = row.elapsed
                self.recording?.eventCount += events.count
                events.forEach(addLog)
            } catch { await failedStorage(error) }
        }
        for change in changes where change.started {
            lastAlert = change.message
            presenter.present(change, settings: settings, foreground: isForeground, demo: isDemo)
        }
    }
    private func apply(_ effects: [AcquisitionEffect]) {
        for effect in effects {
            switch effect {
            case .write(let command): transport?.write(command)
            case .faultsCompleted: faultCompleted = true
            case .resetLink: resetLink(reason: "Operación interrumpida; restableciendo enlace")
            }
        }
        phase = machine.phase; wantsLive = machine.wantsLive
    }
    private func resetLink(reason: String) {
        transport?.disconnect(); connected = false; decoder.reset(); machine.disconnected(); stale = true
        alerts.interrupt(); activeAlerts = []; rate.reset(); hz = nil; status = reason
        continuation.yield(.transport(.disconnected(reason)))
    }
    private func reconnect() {
        let delays: [Double] = [1, 2, 5, 10, 30]
        let delay = delays[min(reconnectAttempt, delays.count - 1)]; reconnectAttempt += 1
        transport?.connect(foreground: isForeground, delay: delay)
    }
    private func markGap(_ message: String) async {
        stale = true; alerts.interrupt(); activeAlerts = []; rate.reset(); hz = nil
        guard !gapOpen else { return }
        gapOpen = true; segment += 1
        await record(.gap, message)
    }
    private func finishRecording(message: String) async {
        guard let recording else { return }
        do { try await store?.finish(recording.id, at: Date(), elapsed: recordingElapsed, message: message) }
        catch { await failedStorage(error) }
        self.recording = nil; alerts.interrupt(); activeAlerts = []
        defaults.removeObject(forKey: isDemo ? "demoSessionID" : "activeSessionID")
        sessions = (try? await store?.sessions()) ?? []
    }
    private func failedStorage(_ error: Error) async {
        storageError = "Grabación interrumpida: \(error.localizedDescription)"
        if let recording {
            try? await store?.finish(recording.id, status: .interrupted, at: Date(), elapsed: recordingElapsed, message: storageError!)
        }
        recording = nil
        defaults.removeObject(forKey: isDemo ? "demoSessionID" : "activeSessionID")
        addLog(SessionEvent(kind: .recording, message: storageError!))
        let change = AlertTransition(rule: .lowLoad, started: true, audible: true, message: storageError!)
        // Reuse delivery with a dedicated visible error; the REC indicator is removed immediately.
        presenter.present(change, settings: settings, foreground: isForeground, demo: isDemo, title: "Grabación interrumpida")
    }
    private func record(_ kind: EventKind, _ message: String, at date: Date = Date()) async {
        let event = SessionEvent(sessionID: recording?.id, timestamp: date, kind: kind, message: message)
        addLog(event)
        guard storageError == nil else { return }
        do { try await store?.appendEvent(event) } catch { await failedStorage(error) }
    }
    private func addLog(_ event: SessionEvent) {
        log.append(event); if log.count > 500 { log.removeFirst(log.count - 500) }
    }
    private func updateStatus() {
        guard connected else { return }
        switch machine.phase {
        case .idle: status = "Conectado · detenido"
        case .restoring: status = "Restaurando flujo…"
        case .synchronizing: status = "Sincronizando lector…"
        case .starting: status = "Abriendo sesión del DME…"
        case .recoveringDME: status = "Reconectando DME…"
        case .stopping: status = "Deteniendo…"
        case .faultOpening, .faultBarrier: status = "Leyendo fallas del DME…"
        case .live:
            if stale { status = "Datos desactualizados" }
            else if telemetry?.validity == .unpopulated { status = "Motor apagado / DME sin datos" }
            else { status = "Recibiendo sensores" }
        case .disconnected: break
        }
    }
    private func updateBackgroundTask() {
        if machine.phase.pending, operationTask == .invalid {
            operationTask = UIApplication.shared.beginBackgroundTask(withName: "Operación BLE") { [weak self] in
                Task { @MainActor in self?.continuation.yield(.expired) }
            }
        } else if !machine.phase.pending, operationTask != .invalid {
            UIApplication.shared.endBackgroundTask(operationTask); operationTask = .invalid
        }
    }
}
