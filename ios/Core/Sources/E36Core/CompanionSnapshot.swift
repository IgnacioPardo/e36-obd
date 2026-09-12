import Foundation

/// A view of the phone's capture. The companion never owns a BLE connection.
public struct CompanionSnapshot: Codable, Hashable, Sendable {
    public var version = 1
    public var streamID: String
    public var sequence: UInt64
    public var observation: WidgetSnapshot
    public var sessionID: String?
    public var startedAt: Date?
    public var sampleCount: Int
    public var connected: Bool
    public var canStart: Bool
    public var phase: String
    public var primarySensor: Sensor

    public init(streamID: String, sequence: UInt64, observation: WidgetSnapshot,
                sessionID: String? = nil, startedAt: Date? = nil, sampleCount: Int = 0,
                connected: Bool = false, canStart: Bool = false, phase: String = "disconnected",
                primarySensor: Sensor = .coolant) {
        self.streamID = streamID; self.sequence = sequence; self.observation = observation
        self.sessionID = sessionID; self.startedAt = startedAt; self.sampleCount = sampleCount
        self.connected = connected; self.canStart = canStart; self.phase = phase; self.primarySensor = primarySensor
    }
    public static func empty(source: WidgetSource = .reader, at date: Date = .now) -> Self {
        .init(streamID: "empty", sequence: 0, observation: .init(updatedAt: date, source: source))
    }
    public var source: WidgetSource { observation.source }
    public var receivedAt: Date? { observation.receivedAt }
    public func isFresh(at date: Date) -> Bool {
        guard connected, observation.capture == .recording, let receivedAt else { return false }
        if let startedAt, receivedAt < startedAt { return false }
        let age = date.timeIntervalSince(receivedAt)
        return age >= -1 && age <= 2
    }
    public func value(for sensor: Sensor) -> Double? {
        if let startedAt, let receivedAt, receivedAt < startedAt { return nil }
        return observation.value(for: sensor)
    }
    public func formatted(_ sensor: Sensor) -> String {
        if sensor == .rpm, let value = value(for: sensor), value >= 2550 { return "2550+" }
        return sensor.formatted(value(for: sensor))
    }
    public func warning(for sensor: Sensor, at date: Date) -> Bool {
        isFresh(at: date) && value(for: sensor) != nil && observation.hasWarning(for: sensor)
    }
    public func status(at date: Date) -> String {
        if observation.capture == .interrupted { return "Interrumpida" }
        if sessionID != nil && observation.capture == .stopped { return "Finalizada" }
        if sessionID == nil { return connected ? "Listo" : "Sin conexión" }
        if !connected { return "Reconectando" }
        if phase == "faultOpening" || phase == "faultBarrier" { return "Leyendo fallas" }
        if phase == "starting" || phase == "restoring" || phase == "synchronizing" { return "Iniciando" }
        if phase == "stopping" { return "Deteniendo" }
        if phase == "recoveringDME" { return "Recuperando DME" }
        if observation.capture == .paused { return "En pausa" }
        if !isFresh(at: date) { return "Sin actualización" }
        if observation.telemetry?.validity == .unpopulated { return "Motor apagado" }
        return "En vivo"
    }
    public var stateKey: String {
        [source.rawValue, sessionID ?? "", observation.capture.rawValue, phase,
         String(connected), String(canStart), observation.telemetry?.validity.rawValue ?? "",
         observation.alerts.map(\.rawValue).sorted().joined(separator: ","), primarySensor.rawValue].joined(separator: "|")
    }
    public func encoded() throws -> Data {
        let data = try JSONEncoder().encode(self)
        guard data.count <= 8192 else { throw CompanionError.invalidPayload }
        return data
    }
    public static func decode(_ data: Data) throws -> Self {
        guard data.count <= 8192 else { throw CompanionError.invalidPayload }
        let value = try JSONDecoder().decode(Self.self, from: data)
        guard value.version == 1, value.observation.version == 1,
              !value.streamID.isEmpty, value.streamID.count <= 80,
              (value.sessionID?.count ?? 0) <= 80, value.phase.count <= 40,
              value.sampleCount >= 0, value.observation.alerts.count <= 3,
              value.observation.updatedAt.timeIntervalSince1970.isFinite,
              value.receivedAt?.timeIntervalSince1970.isFinite != false,
              value.startedAt?.timeIntervalSince1970.isFinite != false,
              Sensor.allCases.allSatisfy({ value.observation.telemetry?[$0]?.isFinite != false })
        else { throw CompanionError.invalidPayload }
        return value
    }
    public enum CompanionError: Error { case invalidPayload }
}

/// Applies independently per source. A delayed background delivery cannot
/// overwrite an interactive update; a restarted sender uses a new stream ID.
public struct CompanionInbox: Sendable {
    private var latest: [WidgetSource: CompanionSnapshot] = [:]
    public init() {}
    public func snapshot(for source: WidgetSource) -> CompanionSnapshot? { latest[source] }
    @discardableResult public mutating func accept(_ incoming: CompanionSnapshot) -> Bool {
        if let previous = latest[incoming.source] {
            if previous.streamID == incoming.streamID {
                guard incoming.sequence > previous.sequence else { return false }
            } else {
                guard incoming.observation.updatedAt >= previous.observation.updatedAt else { return false }
            }
        }
        latest[incoming.source] = incoming
        return true
    }
}

public struct CompanionPublicationPolicy: Sendable {
    private var state: String?
    private var lastSample: Date?
    private var lastSent: Date?
    public init() {}
    public mutating func shouldPublish(_ snapshot: CompanionSnapshot, at now: Date, interval: TimeInterval) -> Bool {
        let changedState = state != snapshot.stateKey
        let changedReading = lastSample != snapshot.receivedAt
        guard changedState || (changedReading && now.timeIntervalSince(lastSent ?? .distantPast) >= interval) else { return false }
        state = snapshot.stateKey; lastSample = snapshot.receivedAt; lastSent = now
        return true
    }
}

/// Versioned command envelope. Explicit start/stop actions are never queued for
/// later delivery to an unreachable phone or automatically retried by the watch.
public struct CompanionRequest: Codable, Sendable {
    public enum Action: String, Codable, Sendable { case snapshot, start, stop }
    public var version = 1
    public var id: UUID
    public var action: Action
    public var source: WidgetSource
    public var sentAt: Date
    public init(action: Action, source: WidgetSource, id: UUID = UUID(), sentAt: Date = .now) {
        self.action = action; self.source = source; self.id = id; self.sentAt = sentAt
    }
    public func isValid(at date: Date) -> Bool {
        let age = date.timeIntervalSince(sentAt)
        return version == 1 && age >= -5 && age <= 15
    }
}

public struct CompanionReply: Codable, Sendable {
    public var snapshot: CompanionSnapshot
    public var message: String?
    public var accepted: Bool
    public init(snapshot: CompanionSnapshot, message: String? = nil, accepted: Bool = true) {
        self.snapshot = snapshot; self.message = message; self.accepted = accepted
    }
}

public struct CompanionSnapshotStore: Sendable {
    public static let appGroup = WidgetSnapshotStore.appGroup
    public static let kind = "E36WatchInstrument"
    public let directory: URL
    public init(directory: URL) { self.directory = directory }
    public func url(for source: WidgetSource) -> URL { directory.appendingPathComponent("companion-\(source.rawValue).json") }
    public func write(_ snapshot: CompanionSnapshot) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        #if os(iOS) || os(watchOS)
        try snapshot.encoded().write(to: url(for: snapshot.source), options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        #else
        try snapshot.encoded().write(to: url(for: snapshot.source), options: .atomic)
        #endif
    }
    public func read(_ source: WidgetSource) throws -> CompanionSnapshot? {
        let path = url(for: source)
        guard FileManager.default.fileExists(atPath: path.path) else { return nil }
        let result = try CompanionSnapshot.decode(Data(contentsOf: path))
        guard result.source == source else { throw CompanionSnapshot.CompanionError.invalidPayload }
        return result
    }
}

/// Records dismissals by capture identity, so ticks/reconnects cannot restart
/// an activity the user dismissed. A different recording gets a new identity.
public struct CaptureActivityPolicy: Sendable {
    private var suppressed: Set<String> = []
    public init() {}
    public mutating func suppress(_ id: String) {
        if suppressed.count >= 32 { suppressed.removeAll() }
        suppressed.insert(id)
    }
    public func canStart(_ snapshot: CompanionSnapshot, foreground: Bool, enabled: Bool) -> Bool {
        guard enabled, foreground, let id = snapshot.sessionID,
              snapshot.observation.capture != .interrupted, snapshot.observation.capture != .stopped else { return false }
        return !suppressed.contains(id)
    }
}
