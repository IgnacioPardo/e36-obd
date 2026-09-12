import Foundation

public enum Sensor: String, CaseIterable, Codable, Sendable, Identifiable {
    case rpm, load, coolant, battery, intake
    public var id: String { rawValue }
    public var title: String {
        switch self {
        case .rpm: "Régimen"
        case .load: "Carga"
        case .coolant: "Refrigerante"
        case .battery: "Batería"
        case .intake: "Admisión"
        }
    }
    public var unit: String {
        switch self { case .rpm: "rpm"; case .load: "ms"; case .battery: "V"; default: "°C" }
    }
    public var decimals: Int { self == .rpm ? 0 : (self == .load || self == .battery ? 2 : 1) }
    public func formatted(_ value: Double?) -> String {
        guard let value, value.isFinite else { return "—" }
        return String(format: "%.*f", locale: Locale(identifier: "en_US_POSIX"), decimals, value)
    }
}

public struct Telemetry: Codable, Hashable, Sendable {
    public var rpm: Double
    public var load: Double
    public var coolant: Double
    public var battery: Double
    public var ecuMS: Int
    public var intake: Double?
    public init(rpm: Double, load: Double, coolant: Double, battery: Double, ecuMS: Int, intake: Double? = nil) {
        self.rpm = rpm; self.load = load; self.coolant = coolant
        self.battery = battery; self.ecuMS = ecuMS; self.intake = intake
    }
    public subscript(_ sensor: Sensor) -> Double? {
        switch sensor {
        case .rpm: rpm; case .load: load; case .coolant: coolant; case .battery: battery; case .intake: intake
        }
    }
    public var validity: SampleValidity {
        guard rpm == 0, load == 0, battery == 0 else { return .populated }
        let emptyCoolant = abs(coolant + 32.5) < 0.01 || coolant == 0
        let emptyIntake = intake == nil || intake == 0 || abs((intake ?? 0) + 33.5) < 0.01
        return emptyCoolant && emptyIntake ? .unpopulated : .populated
    }
    public var saturated: Bool { rpm >= 2550 }
}

public enum SampleValidity: String, Codable, Sendable { case populated, unpopulated }
public enum SessionStatus: String, Codable, Sendable { case recording, completed, interrupted }

public struct DriveSession: Identifiable, Codable, Equatable, Sendable {
    public var id: String
    public var startedAt: Date
    public var endedAt: Date?
    public var status: SessionStatus
    public var isDemo: Bool
    public var elapsed: Double
    public var sampleCount: Int
    public var eventCount: Int
    public var lastReceivedAt: Date?
    public init(id: String = UUID().uuidString, startedAt: Date = Date(), isDemo: Bool = false) {
        self.id = id; self.startedAt = startedAt; self.isDemo = isDemo
        status = .recording; elapsed = 0; sampleCount = 0; eventCount = 0
    }
}

public struct RecordedSample: Identifiable, Codable, Equatable, Sendable {
    public var id: Int64
    public var sessionID: String
    public var receivedAt: Date
    public var elapsed: Double
    public var telemetry: Telemetry
    public var segment: Int
    public init(id: Int64 = 0, sessionID: String, receivedAt: Date, elapsed: Double, telemetry: Telemetry, segment: Int) {
        self.id = id; self.sessionID = sessionID; self.receivedAt = receivedAt
        self.elapsed = elapsed; self.telemetry = telemetry; self.segment = segment
    }
}

public enum EventKind: String, Codable, Sendable {
    case message, invalidLine, connection, gap, alertStarted, alertEnded, configuration, engineState, recording
}
public struct SessionEvent: Identifiable, Codable, Equatable, Sendable {
    public var id: String
    public var sessionID: String?
    public var timestamp: Date
    public var kind: EventKind
    public var message: String
    public var sampleID: Int64?
    public var rule: AlertRule?
    public init(sessionID: String? = nil, timestamp: Date = Date(), kind: EventKind, message: String,
                sampleID: Int64? = nil, rule: AlertRule? = nil) {
        id = UUID().uuidString; self.sessionID = sessionID; self.timestamp = timestamp
        self.kind = kind; self.message = message; self.sampleID = sampleID; self.rule = rule
    }
}

public struct FaultRecord: Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var code: Int
    public var occurrences: Int
    public var condition: String?
    public var detail = ""
}
public struct FaultReport: Sendable {
    public private(set) var records: [FaultRecord] = []
    public private(set) var lines: [String] = []
    public private(set) var error: String?
    public private(set) var noFaults = false
    private var inHelp = false
    public init() {}
    public mutating func receive(_ line: String) {
        if line == "=== E36 M43B16 ===" { inHelp = true }
        guard !inHelp else { return }
        lines.append(line)
        let parts = line.split(whereSeparator: \.isWhitespace)
        if parts.count == 4, parts[0] == "cod", parts[2] == "ocurr",
           let code = Int(parts[1]), let occurrences = Int(parts[3]) {
            records.append(FaultRecord(code: code, occurrences: occurrences))
        } else if parts.count == 2, parts[0] == "cond", !records.isEmpty {
            records[records.count - 1].condition = String(parts[1])
        } else if line.hasPrefix("error:") { error = line }
        else if line == "sin fallas almacenadas" { noFaults = true }
        else if line.hasPrefix("  "), !records.isEmpty {
            records[records.count - 1].detail += (records.last!.detail.isEmpty ? "" : "\n") + line.trimmingCharacters(in: .whitespaces)
        }
    }
}
