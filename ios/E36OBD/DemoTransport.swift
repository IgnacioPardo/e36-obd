import Foundation
import E36Core

enum DemoScenario: String, CaseIterable, Identifiable {
    case normal = "Ralentí", cut = "Carga baja", heat = "Temperatura", off = "Motor apagado", saturated = "Saturación", disconnect = "Desconexión", noECU = "DME sin respuesta"
    var id: String { rawValue }
}
@MainActor final class DemoTransport: ReaderTransport {
    var onEvent: (@MainActor (TransportEvent) -> Void)?
    var scenario: DemoScenario = .normal
    private var connected = false
    private var liveTask: Task<Void, Never>?
    private var connectTask: Task<Void, Never>?
    private var sampleCount = 0
    private var faultsOpen = false
    func connect(foreground: Bool, delay: Double) {
        connectTask?.cancel()
        connectTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(max(0.1, delay)))
            guard !Task.isCancelled, let self else { return }
            self.connected = true; self.onEvent?(.ready(restored: false))
        }
    }
    func select(_ id: UUID) {}
    func setForeground(_ value: Bool) {}
    func disconnect() { connected = false; liveTask?.cancel(); connectTask?.cancel(); liveTask = nil }
    func write(_ command: Command) {
        guard connected else { return }
        switch command {
        case .stop:
            if liveTask != nil { liveTask?.cancel(); liveTask = nil; send("detenido (\(sampleCount) muestras)") }
            send("detenido")
        case .live:
            liveTask?.cancel(); sampleCount = 0
            send("abriendo sesion...")
            if scenario == .noECU { send("error: sin respuesta de la ECU"); return }
            send("en vivo. cualquier tecla corta.")
            liveTask = Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(365))
                    guard !Task.isCancelled, let self, self.connected else { return }
                    if self.scenario == .noECU {
                        self.send("se corto: sin respuesta de la ECU")
                        self.send("detenido (\(self.sampleCount) muestras)")
                        return
                    }
                    if self.scenario == .disconnect {
                        self.scenario = .normal; self.connected = false
                        self.onEvent?(.disconnected("Desconexión simulada")); return
                    }
                    self.sampleCount += 1
                    let wobble = sin(Double(self.sampleCount) * 0.4)
                    let line: String
                    switch self.scenario {
                    case .off: line = "D 0 0.00 -32.5 0.00 341 -33.5"
                    case .cut: line = "D 930 0.70 90.9 13.48 341 28.5"
                    case .heat: line = "D 890 2.76 112.5 13.48 341 64.0"
                    case .saturated: line = "D 2550 4.25 90.9 13.48 341 28.5"
                    default: line = String(format: "D %d %.2f 90.9 13.48 341 28.5", 890 + Int(wobble * 30), 2.76 + wobble * 0.08)
                    }
                    self.send(line)
                }
            }
        case .faults:
            if liveTask != nil { liveTask?.cancel(); liveTask = nil; send("detenido (\(sampleCount) muestras)") }
            faultsOpen = true
            send("abriendo sesion...")
        case .help:
            if faultsOpen {
                if scenario == .noECU {
                    send("error: sin respuesta de la ECU")
                } else {
                    send("cod 100  ocurr 50"); send("  cond 0x68")
                    send("cod 36  ocurr 50"); send("  cond 0x72")
                }
                faultsOpen = false
            }
            for line in ["=== E36 M43B16 ===", "v  sensores en vivo", "f  memoria de fallas", "s  detener", "?  esta ayuda"] { send(line) }
        }
    }
    private func send(_ line: String) {
        let bytes = Array((line + "\r\n").utf8)
        for offset in stride(from: 0, to: bytes.count, by: 20) {
            onEvent?(.bytes(Data(bytes[offset..<min(offset + 20, bytes.count)]), Date(), ProcessInfo.processInfo.systemUptime))
        }
    }
}
