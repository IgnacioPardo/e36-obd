import Foundation

public enum WidgetSource: String, Codable, Sendable, CaseIterable { case reader, demo }
public enum WidgetCaptureState: String, Codable, Sendable { case stopped, recording, paused, interrupted }

/// A dated observation, never a second BLE owner or a claim of continuous widget updates.
public struct WidgetSnapshot: Codable, Hashable, Sendable {
    public var version = 1
    public var updatedAt: Date
    public var receivedAt: Date?
    public var telemetry: Telemetry?
    public var capture: WidgetCaptureState
    public var alerts: [AlertRule]
    public var source: WidgetSource
    public init(updatedAt: Date, receivedAt: Date? = nil, telemetry: Telemetry? = nil,
                capture: WidgetCaptureState = .stopped, alerts: [AlertRule] = [], source: WidgetSource = .reader) {
        self.updatedAt = updatedAt; self.receivedAt = receivedAt; self.telemetry = telemetry
        self.capture = capture; self.alerts = alerts; self.source = source
    }
    public func value(for sensor: Sensor) -> Double? {
        guard receivedAt != nil, telemetry?.validity == .populated,
              let value = telemetry?[sensor], value.isFinite else { return nil }
        return value
    }
    public func isOld(at date: Date) -> Bool {
        guard let receivedAt else { return true }
        let age = date.timeIntervalSince(receivedAt)
        return age < -5 || age >= 300
    }
    public func observationLabel(at date: Date) -> String {
        if receivedAt == nil { return "Sin lecturas" }
        if isOld(at: date) { return "Anterior" }
        if telemetry?.validity == .unpopulated { return "Motor apagado" }
        switch capture {
        case .recording: return "Muestra"
        case .paused: return "Pausa"
        case .interrupted: return "Interrumpida"
        case .stopped: return "Detenido"
        }
    }
    public func hasWarning(for sensor: Sensor) -> Bool {
        switch sensor {
        case .coolant: alerts.contains(.coolant)
        case .intake: alerts.contains(.intake)
        case .load: alerts.contains(.lowLoad)
        default: false
        }
    }
}

/// The app writes atomically off the Bluetooth callback. The extension only reads.
public struct WidgetSnapshotStore: Sendable {
    public static let appGroup = "group.com.ignaciopardo.e36obd"
    public static let kind = "E36Instrument"
    public let directory: URL
    public init(directory: URL) { self.directory = directory }
    public func url(for source: WidgetSource) -> URL {
        directory.appendingPathComponent("widget-\(source.rawValue).json")
    }
    public func write(_ snapshot: WidgetSnapshot) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let encoder = JSONEncoder(); encoder.dateEncodingStrategy = .millisecondsSince1970
        let data = try encoder.encode(snapshot)
        #if os(iOS)
        try data.write(to: url(for: snapshot.source), options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        #else
        try data.write(to: url(for: snapshot.source), options: .atomic)
        #endif
    }
    public func read(_ source: WidgetSource) throws -> WidgetSnapshot? {
        let url = url(for: source)
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .millisecondsSince1970
        let snapshot = try decoder.decode(WidgetSnapshot.self, from: Data(contentsOf: url))
        guard snapshot.version == 1, snapshot.source == source else { throw SnapshotError.incompatible }
        return snapshot
    }
    public enum SnapshotError: Error { case incompatible }
}

public struct WidgetPublicationPolicy: Sendable {
    private var lastStored: WidgetSnapshot?
    private var lastReload: Date?
    public init() {}
    public mutating func decision(for snapshot: WidgetSnapshot, foreground: Bool) -> (write: Bool, reload: Bool) {
        let stateChanged = lastStored.map {
            $0.capture != snapshot.capture || $0.alerts != snapshot.alerts || $0.source != snapshot.source
                || $0.telemetry?.validity != snapshot.telemetry?.validity
                || snapshot.updatedAt < $0.updatedAt
        } ?? true
        let changed = stateChanged || lastStored?.receivedAt != snapshot.receivedAt
        let write = stateChanged || (changed && snapshot.updatedAt.timeIntervalSince(lastStored?.updatedAt ?? .distantPast) >= 1)
        guard write else { return (false, false) }
        let reload = stateChanged || snapshot.updatedAt.timeIntervalSince(lastReload ?? .distantPast) >= (foreground ? 15 : 300)
        lastStored = snapshot
        if reload { lastReload = snapshot.updatedAt }
        return (true, reload)
    }
}
