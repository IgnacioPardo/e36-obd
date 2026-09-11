import Foundation

public enum Command: String, Sendable { case live = "v", stop = "s", faults = "f", help = "?" }
public enum AcquisitionPhase: String, Sendable {
    case disconnected, restoring, synchronizing, idle, starting, live, recoveringDME, stopping, faultOpening, faultBarrier
    public var pending: Bool { ![.disconnected, .idle, .live, .recoveringDME].contains(self) }
    public var readingFaults: Bool { self == .faultOpening || self == .faultBarrier }
}
public enum AcquisitionEffect: Equatable, Sendable {
    case write(Command), resetLink, faultsCompleted
}

/// Firmware acknowledgements, rather than GATT write acknowledgements, advance this machine.
public struct AcquisitionMachine: Sendable {
    public private(set) var phase: AcquisitionPhase = .disconnected
    public private(set) var wantsLive = false
    private var deadline: Double?
    private var lastSample: Double?
    public init() {}
    public mutating func setLiveIntent(_ value: Bool, now: Double) -> [AcquisitionEffect] {
        wantsLive = value
        if value, phase == .idle { return start(now) }
        if !value, phase == .live || phase == .recoveringDME {
            phase = .stopping; deadline = now + 30; return [.write(.stop)]
        }
        return []
    }
    public mutating func connected(restored: Bool, now: Double) -> [AcquisitionEffect] {
        lastSample = nil
        phase = restored ? .restoring : .synchronizing
        deadline = now + (restored ? 2 : 30)
        return restored ? [] : [.write(.stop)]
    }
    public mutating func disconnected() {
        phase = .disconnected; deadline = nil; lastSample = nil
    }
    public mutating func requestFaults(now: Double) -> [AcquisitionEffect] {
        guard phase == .idle || phase == .live || phase == .recoveringDME else { return [] }
        phase = .faultOpening; deadline = now + 30
        return [.write(.faults)]
    }
    public mutating func sample(now: Double) -> [AcquisitionEffect] {
        lastSample = now
        if phase == .restoring || phase == .starting || phase == .recoveringDME {
            phase = .live; deadline = nil
            if !wantsLive { return setLiveIntent(false, now: now) }
        }
        return []
    }
    public mutating func text(_ text: String, now: Double) -> [AcquisitionEffect] {
        // The ESP owns ECU recovery. Its progress proves BLE is still alive;
        // retain the recording intent and never toggle v into that worker.
        if text.hasPrefix("recuperando DME ("),
           [.starting, .live, .recoveringDME, .restoring].contains(phase) {
            phase = .recoveringDME; deadline = now + 30
            return wantsLive ? [] : setLiveIntent(false, now: now)
        }
        if text == "abriendo sesion...", phase == .faultOpening {
            phase = .faultBarrier
            return [.write(.help)]
        }
        if text == "?  esta ayuda", phase == .faultBarrier {
            phase = .idle; deadline = nil
            return [.faultsCompleted] + (wantsLive ? start(now) : [])
        }
        if text == "detenido", phase == .synchronizing || phase == .stopping {
            phase = .idle; deadline = nil
            return wantsLive ? start(now) : []
        }
        if text == "en vivo. cualquier tecla corta.", phase == .starting || phase == .recoveringDME {
            phase = .live; deadline = nil; lastSample = now
            return wantsLive ? [] : setLiveIntent(false, now: now)
        }
        // Fault errors are followed by our queued help barrier. Do not send another command yet.
        if (text.hasPrefix("error:") || text.hasPrefix("se corto:") || text.hasPrefix("detenido (")),
           phase == .starting || phase == .live || phase == .recoveringDME {
            disconnected(); return [.resetLink]
        }
        return []
    }
    public mutating func tick(now: Double) -> [AcquisitionEffect] {
        if phase == .restoring, let deadline, now >= deadline {
            phase = .synchronizing; self.deadline = now + 30
            return [.write(.stop)]
        }
        if let deadline, now >= deadline {
            disconnected(); return [.resetLink]
        }
        if phase == .live, let lastSample, now - lastSample >= 30 {
            disconnected(); return [.resetLink]
        }
        return []
    }
    private mutating func start(_ now: Double) -> [AcquisitionEffect] {
        phase = .starting; deadline = now + 30; lastSample = nil
        return [.write(.live)]
    }
}
