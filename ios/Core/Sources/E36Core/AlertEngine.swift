import Foundation

public enum AlertRule: String, CaseIterable, Codable, Sendable, Identifiable {
    case lowLoad, coolant, intake
    public var id: String { rawValue }
    public var title: String {
        switch self { case .lowLoad: "Carga baja en ralentí"; case .coolant: "Refrigerante alto"; case .intake: "Admisión alta" }
    }
}
public struct AlertSettings: Codable, Equatable, Sendable {
    public var lowLoad = 1.5
    public var idleMinimum = 600.0
    public var idleMaximum = 1200.0
    public var coolantHigh = 110.0
    public var intakeHigh = 60.0
    public var sound = true
    public var haptics = true
    public init() {}
    public var isValid: Bool {
        [lowLoad, idleMinimum, idleMaximum, coolantHigh, intakeHigh].allSatisfy(\.isFinite)
        && lowLoad > 0 && lowLoad <= 12 && idleMinimum > 0 && idleMinimum < idleMaximum
        && idleMaximum < 2550 && (50...130).contains(coolantHigh) && (0...130).contains(intakeHigh)
    }
}
public struct AlertTransition: Equatable, Sendable {
    public var rule: AlertRule
    public var started: Bool
    public var audible: Bool
    public var message: String
    public init(rule: AlertRule, started: Bool, audible: Bool, message: String) {
        self.rule = rule; self.started = started; self.audible = audible; self.message = message
    }
}
public struct AlertEngine: Sendable {
    private struct State: Sendable {
        var active = false
        var highSince: Double?
        var clearSince: Double?
        var lastAttention: Double?
    }
    private var states: [AlertRule: State] = [:]
    private var previous: Double?
    public init() {}
    public var active: [AlertRule] { AlertRule.allCases.filter { states[$0]?.active == true } }
    /// A gap interrupts evidence; it does not establish that a hot engine has cooled.
    public mutating func interrupt() {
        previous = nil
        for rule in AlertRule.allCases {
            let attention = states[rule]?.lastAttention
            states[rule] = State(lastAttention: attention)
        }
    }
    public mutating func evaluate(_ sample: Telemetry, at now: Double, settings: AlertSettings) -> [AlertTransition] {
        guard settings.isValid, sample.validity == .populated else { interrupt(); return [] }
        if let previous, now - previous > 2 || now < previous { interrupt() }
        previous = now
        var changes: [AlertTransition] = []
        for rule in AlertRule.allCases {
            var state = states[rule] ?? State()
            let high: Bool, clear: Bool, triggerDelay: Double, clearDelay: Double
            let detail: String
            switch rule {
            case .lowLoad:
                let idle = (settings.idleMinimum...settings.idleMaximum).contains(sample.rpm)
                high = idle && sample.load < settings.lowLoad
                clear = !idle || sample.load >= settings.lowLoad + 0.3
                triggerDelay = 0; clearDelay = 2
                detail = "\(Sensor.load.formatted(sample.load)) ms · \(Sensor.rpm.formatted(sample.rpm)) rpm"
            case .coolant:
                high = sample.coolant >= settings.coolantHigh; clear = sample.coolant < settings.coolantHigh - 3
                triggerDelay = 2; clearDelay = 5
                detail = "\(Sensor.coolant.formatted(sample.coolant)) °C · umbral \(Sensor.coolant.formatted(settings.coolantHigh)) °C"
            case .intake:
                guard let intake = sample.intake else {
                    state.active = false; state.highSince = nil; state.clearSince = nil; states[rule] = state; continue
                }
                high = intake >= settings.intakeHigh; clear = intake < settings.intakeHigh - 3
                triggerDelay = 2; clearDelay = 5
                detail = "\(Sensor.intake.formatted(intake)) °C · umbral \(Sensor.intake.formatted(settings.intakeHigh)) °C"
            }
            if !state.active {
                state.clearSince = nil
                if high {
                    if state.highSince == nil { state.highSince = now }
                    if now - state.highSince! >= triggerDelay {
                        state.active = true
                        let attention = state.lastAttention == nil || now - state.lastAttention! >= 30
                        if attention { state.lastAttention = now }
                        changes.append(AlertTransition(rule: rule, started: true, audible: attention,
                                                       message: "\(rule.title): \(detail)"))
                    }
                } else { state.highSince = nil }
            } else {
                if clear {
                    if state.clearSince == nil { state.clearSince = now }
                    if now - state.clearSince! >= clearDelay {
                        state.active = false; state.highSince = nil; state.clearSince = nil
                        changes.append(AlertTransition(rule: rule, started: false, audible: false,
                                                       message: "\(rule.title): condición finalizada"))
                    }
                } else { state.clearSince = nil }
            }
            states[rule] = state
        }
        return changes
    }
}
