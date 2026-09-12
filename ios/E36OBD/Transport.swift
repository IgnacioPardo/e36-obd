import Foundation
import CoreBluetooth
import E36Core

struct ReaderDevice: Identifiable, Sendable {
    let id: UUID
    let name: String
    let rssi: Int
}
enum TransportEvent: Sendable {
    case status(String)
    case diagnostic(String)
    case devices([ReaderDevice])
    case ready(restored: Bool)
    case bytes(Data, Date, Double)
    case disconnected(String)
    case waitingForBluetooth(String)
}
@MainActor protocol ReaderTransport: AnyObject {
    var onEvent: (@MainActor (TransportEvent) -> Void)? { get set }
    func connect(foreground: Bool, delay: Double)
    func setForeground(_ value: Bool)
    func select(_ id: UUID)
    func disconnect()
    func write(_ command: Command)
}

@MainActor final class BluetoothTransport: NSObject, ReaderTransport, @preconcurrency CBCentralManagerDelegate,
    @preconcurrency CBPeripheralDelegate {
    static let service = CBUUID(string: "6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
    static let receive = CBUUID(string: "6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
    static let transmit = CBUUID(string: "6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
    var onEvent: (@MainActor (TransportEvent) -> Void)?
    private var manager: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var rx: CBCharacteristic?
    private var tx: CBCharacteristic?
    private var discovered: [UUID: (CBPeripheral, Int)] = [:]
    private var pendingWrite = false
    private var writes: [Command] = []
    private var scanTask: Task<Void, Never>?
    private var connectionTask: Task<Void, Never>?
    private var connectRequested = false
    private var foreground = true
    private var restoring = false
    private var readyDelivered = false
    private var fallbackScan = false
    private var delay: Double = 0
    private let defaults: UserDefaults

    static func connectionOptions(delay: Double) -> [String: Any]? {
        // The first connection uses CoreBluetooth's defaults. Only an actual
        // reconnect backoff needs this optional parameter.
        guard delay > 0, delay.isFinite else { return nil }
        // CoreBluetooth rejects a floating-point NSNumber on the physical
        // iPhone. Send whole seconds, matching our 1/2/5/10/30 s backoff.
        let seconds = Int(min(30, delay.rounded(.up)))
        return [CBConnectPeripheralOptionStartDelayKey: NSNumber(value: seconds)]
    }

    private func diagnostic(_ message: String) {
        onEvent?(.diagnostic(message))
    }

    private func failure(_ stage: String, error: Error?, fallback: String) -> String {
        guard let error = error as NSError? else { return fallback }
        diagnostic("\(stage): \(error.domain) (\(error.code)) · \(error.localizedDescription)")
        return "\(stage): \(error.localizedDescription)"
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        super.init()
        manager = CBCentralManager(delegate: self, queue: .main, options: [
            CBCentralManagerOptionRestoreIdentifierKey: "com.ignaciopardo.e36obd.reader",
            CBCentralManagerOptionShowPowerAlertKey: true
        ])
    }
    func connect(foreground: Bool, delay: Double = 0) {
        self.foreground = foreground; self.delay = delay; connectRequested = true
        if manager.state == .poweredOn { beginConnection() }
        else { centralManagerDidUpdateState(manager) }
    }
    func setForeground(_ value: Bool) {
        foreground = value
        if !value, manager.isScanning {
            scanTask?.cancel(); manager.stopScan()
            onEvent?(.status("Búsqueda pausada; abrí la app para continuar"))
        } else if value, connectRequested, manager.state == .poweredOn, !manager.isScanning {
            beginConnection()
        }
    }
    private func beginConnection() {
        guard peripheral?.state != .connected, peripheral?.state != .connecting else { return }
        if let raw = defaults.string(forKey: "readerID"), let id = UUID(uuidString: raw),
           let known = manager.retrievePeripherals(withIdentifiers: [id]).first {
            fallbackScan = foreground; open(known)
        } else if foreground { scan() }
        else { onEvent?(.disconnected("Abrí la app para buscar E36-OBD por primera vez")) }
    }
    private func scan() {
        scanTask?.cancel(); connectionTask?.cancel(); discovered = [:]
        onEvent?(.devices([])); onEvent?(.status("Buscando E36-OBD…"))
        // The firmware advertises its name, not the NUS UUID.
        manager.scanForPeripherals(withServices: nil, options: nil)
        diagnostic("Búsqueda BLE por nombre iniciada en primer plano")
        scanTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(10))
            guard !Task.isCancelled, let self else { return }
            self.manager.stopScan()
            self.diagnostic("Búsqueda terminada: \(self.discovered.count) lectores E36-OBD")
            if self.discovered.count == 1, let candidate = self.discovered.values.first { self.open(candidate.0) }
            else if self.discovered.isEmpty { self.onEvent?(.disconnected("No se encontró E36-OBD. Revisá alimentación y otro central conectado.")) }
            else { self.onEvent?(.status("Elegí tu lector")) }
        }
    }
    func select(_ id: UUID) {
        guard let candidate = discovered[id] else { return }
        open(candidate.0)
    }
    private func open(_ device: CBPeripheral) {
        scanTask?.cancel(); manager.stopScan(); onEvent?(.devices([]))
        peripheral = device; device.delegate = self; rx = nil; tx = nil; readyDelivered = false
        onEvent?(.status(delay > 0 ? "Reconectando en \(Int(delay)) s…" : "Conectando…"))
        // CoreBluetooth owns the delay, so reconnect does not require a background Swift timer.
        diagnostic("Conectando a E36-OBD · espera \(delay) s")
        manager.connect(device, options: Self.connectionOptions(delay: delay))
        if foreground {
            connectionTask?.cancel()
            connectionTask = Task { [weak self, weak device] in
                guard let self else { return }
                try? await Task.sleep(for: .seconds(15 + self.delay))
                guard !Task.isCancelled, let device, self.peripheral === device, !self.readyDelivered else { return }
                self.peripheral = nil; self.manager.cancelPeripheralConnection(device)
                if self.fallbackScan { self.fallbackScan = false; self.scan() }
                else { self.onEvent?(.disconnected("La conexión no respondió")) }
            }
        }
    }
    func disconnect() {
        connectRequested = false; scanTask?.cancel(); connectionTask?.cancel(); manager.stopScan()
        if let peripheral { manager.cancelPeripheralConnection(peripheral) }
        peripheral = nil; rx = nil; tx = nil; writes = []; pendingWrite = false; readyDelivered = false; restoring = false
    }
    func write(_ command: Command) {
        guard readyDelivered, let peripheral, peripheral.state == .connected, rx != nil else {
            onEvent?(.disconnected("No se pudo enviar el comando: lector no disponible")); return
        }
        writes.append(command); drainWrites()
    }
    private func drainWrites() {
        guard !pendingWrite, !writes.isEmpty, let peripheral, let rx else { return }
        pendingWrite = true
        let command = writes.removeFirst()
        peripheral.writeValue(Data(command.rawValue.utf8), for: rx, type: .withResponse)
    }
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        diagnostic("Estado CoreBluetooth: \(central.state.rawValue) · autorización \(CBManager.authorization.rawValue)")
        switch central.state {
        case .poweredOn: if connectRequested { beginConnection() }
        case .unauthorized: waitForBluetooth("Bluetooth sin permiso. Habilitalo en Ajustes.")
        case .poweredOff: waitForBluetooth("Bluetooth apagado")
        case .unsupported: waitForBluetooth("Bluetooth no disponible. Usá la simulación.")
        case .resetting: waitForBluetooth("Bluetooth se está reiniciando")
        case .unknown: onEvent?(.status("Preparando Bluetooth…"))
        @unknown default: waitForBluetooth("Estado Bluetooth desconocido")
        }
    }
    func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        guard let saved = (dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral])?.first else { return }
        restoring = true; connectRequested = true; peripheral = saved; saved.delegate = self
        if saved.state == .connected { discover(saved) }
    }
    func centralManager(_ central: CBCentralManager, didDiscover device: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? device.name
        guard name == "E36-OBD" else { return }
        if discovered[device.identifier] == nil { diagnostic("E36-OBD descubierto · \(RSSI.intValue) dBm") }
        discovered[device.identifier] = (device, RSSI.intValue)
        let devices = discovered.values.map { ReaderDevice(id: $0.0.identifier, name: $0.0.name ?? "E36-OBD", rssi: $0.1) }
        onEvent?(.devices(devices.sorted { $0.rssi > $1.rssi }))
        if device.identifier.uuidString == defaults.string(forKey: "readerID") { open(device) }
    }
    func centralManager(_ central: CBCentralManager, didConnect device: CBPeripheral) {
        guard peripheral === device else { return }
        diagnostic("Enlace BLE conectado")
        device.delegate = self; discover(device)
    }
    private func discover(_ device: CBPeripheral) {
        diagnostic("Buscando servicio NUS")
        onEvent?(.status("Verificando servicio NUS…"))
        device.discoverServices([Self.service])
    }
    func peripheral(_ device: CBPeripheral, didDiscoverServices error: Error?) {
        guard peripheral === device else { return }
        guard error == nil, let service = device.services?.first(where: { $0.uuid == Self.service }) else { fail("El lector no ofrece el servicio NUS"); return }
        device.discoverCharacteristics([Self.receive, Self.transmit], for: service)
    }
    func peripheral(_ device: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard peripheral === device else { return }
        rx = service.characteristics?.first { $0.uuid == Self.receive }
        tx = service.characteristics?.first { $0.uuid == Self.transmit }
        guard error == nil, let rx, rx.properties.contains(.write), let tx, tx.properties.contains(.notify) else {
            fail("Características BLE incompatibles"); return
        }
        if tx.isNotifying { deliverReady() } else { device.setNotifyValue(true, for: tx) }
    }
    func peripheral(_ device: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        guard peripheral === device, characteristic.uuid == Self.transmit else { return }
        guard error == nil, characteristic.isNotifying else { fail("No se pudieron activar las notificaciones"); return }
        deliverReady()
    }
    private func deliverReady() {
        guard !readyDelivered else { return }
        readyDelivered = true; connectionTask?.cancel()
        diagnostic("Servicio NUS verificado · notificaciones TX activas")
        if let peripheral { defaults.set(peripheral.identifier.uuidString, forKey: "readerID") }
        onEvent?(.ready(restored: restoring)); restoring = false
    }
    func peripheral(_ device: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard peripheral === device, characteristic.uuid == Self.transmit else { return }
        guard error == nil, let data = characteristic.value else { fail("Error de recepción BLE"); return }
        onEvent?(.bytes(data, Date(), ProcessInfo.processInfo.systemUptime))
    }
    func peripheral(_ device: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        guard peripheral === device, characteristic.uuid == Self.receive else { return }
        guard error == nil else { fail("El lector rechazó la escritura BLE"); return }
        pendingWrite = false; drainWrites()
    }
    func centralManager(_ central: CBCentralManager, didFailToConnect device: CBPeripheral, error: Error?) {
        guard peripheral === device else { return }
        let message = failure("Conexión BLE", error: error, fallback: "No se pudo conectar")
        if let error = error as NSError?, error.domain == CBErrorDomain,
           error.code == CBError.invalidParameters.rawValue {
            // Invalid options are rejected immediately, before the requested
            // delay. Never feed that error into automatic reconnect repeatedly.
            disconnect()
            onEvent?(.waitingForBluetooth("\(message) Detené y volvé a conectar."))
        } else { fail(message) }
    }
    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral device: CBPeripheral, error: Error?) {
        guard peripheral === device else { return }
        fail(failure("Desconexión BLE", error: error, fallback: "Se perdió la conexión con E36-OBD"))
    }
    private func fail(_ message: String) {
        let wasRequested = connectRequested
        disconnect()
        if wasRequested { onEvent?(.disconnected(message)) } else { onEvent?(.status(message)) }
    }
    private func waitForBluetooth(_ message: String) {
        // Only a central state change resumes this request. Retrying connect immediately
        // while powered off would form an unbounded event/reconnect loop.
        let requested = connectRequested
        disconnect(); connectRequested = requested
        onEvent?(.waitingForBluetooth(message))
    }
}
