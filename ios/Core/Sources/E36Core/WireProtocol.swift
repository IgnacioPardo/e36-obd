import Foundation

public enum DecodedLine: Equatable, Sendable {
    case sample(Telemetry)
    case text(String)
    case invalid(String)
}

/// Frames bytes before UTF-8 decoding. A lost boundary cannot leak into another connection.
public struct LineDecoder: Sendable {
    public static let maximumBytes = 4096
    private var buffer: [UInt8] = []
    private var discarding = false
    public init() {}
    public mutating func reset(discardPartial: Bool = false) {
        buffer.removeAll(keepingCapacity: true); discarding = discardPartial
    }
    public mutating func receive(_ data: Data) -> [DecodedLine] {
        var output: [DecodedLine] = []
        for byte in data {
            if discarding {
                if byte == 10 { discarding = false }
                continue
            }
            if byte == 10 {
                if buffer.last == 13 { buffer.removeLast() }
                if let line = String(bytes: buffer, encoding: .utf8) {
                    if !line.isEmpty { output.append(Self.parse(line)) }
                } else {
                    output.append(.invalid("UTF-8 inválido: " + buffer.map { String(format: "%02x", $0) }.joined()))
                }
                buffer.removeAll(keepingCapacity: true)
            } else if buffer.count == Self.maximumBytes {
                let prefix = String(decoding: buffer, as: UTF8.self)
                output.append(.invalid("Línea excede 4096 bytes; resincronizando: " + prefix))
                buffer.removeAll(keepingCapacity: true); discarding = true
            } else { buffer.append(byte) }
        }
        return output
    }
    public static func parse(_ line: String) -> DecodedLine {
        let parts = line.split(whereSeparator: \.isWhitespace)
        guard parts.first == "D" else { return .text(line) }
        guard parts.count == 6 || parts.count == 7,
              let rpm = Int(parts[1]), rpm >= 0, rpm <= 2550,
              let load = Double(parts[2]), load.isFinite, load >= 0,
              let coolant = Double(parts[3]), coolant.isFinite,
              let battery = Double(parts[4]), battery.isFinite, battery >= 0,
              let milliseconds = Int(parts[5]), milliseconds > 0 else { return .invalid(line) }
        var intake: Double?
        if parts.count == 7 {
            guard let value = Double(parts[6]), value.isFinite else { return .invalid(line) }
            intake = value
        }
        return .sample(Telemetry(rpm: Double(rpm), load: load, coolant: coolant, battery: battery,
                                 ecuMS: milliseconds, intake: intake))
    }
}

public struct ReceptionRate: Sendable {
    private var previous: Double?
    private var intervals: [Double] = []
    public init() {}
    public var hz: Double? {
        guard !intervals.isEmpty else { return nil }
        return Double(intervals.count) / intervals.reduce(0, +)
    }
    public mutating func reset() { previous = nil; intervals = [] }
    public mutating func receive(at now: Double) {
        if let previous {
            let interval = now - previous
            if interval > 0, interval <= 2 {
                intervals.append(interval)
                if intervals.count > 8 { intervals.removeFirst() }
            } else { intervals = [] }
        }
        previous = now
    }
}
