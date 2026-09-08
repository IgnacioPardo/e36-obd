import SwiftUI
import E36Core

struct InspectorPanel: View {
    @ObservedObject var model: AppModel
    private var title: String {
        switch model.section {
        case .connection: "Conexión"
        case .faults: "Fallas"
        case .sessions: "Sesiones"
        case .settings: "Ajustes"
        case .dashboard: ""
        }
    }
    var body: some View {
        VStack(spacing: 14) {
            HStack {
                Text(title).font(.system(.title3, weight: .semibold)).foregroundStyle(ClusterTheme.ink)
                Spacer()
                Button { model.section = .dashboard } label: {
                    Image(systemName: "xmark").font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(ClusterTheme.muted).frame(width: 44, height: 44)
                        .background(Color.white.opacity(0.04), in: Circle())
                }.buttonStyle(.plain).accessibilityLabel("Cerrar panel").accessibilityIdentifier("closePanelButton")
            }
            Rectangle().fill(ClusterTheme.line).frame(height: 0.5)
            Group {
                switch model.section {
                case .connection: ConnectionPanel(model: model)
                case .faults: FaultsView(model: model)
                case .sessions: SessionsView(model: model)
                case .settings: SettingsView(model: model)
                case .dashboard: EmptyView()
                }
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .padding(18)
        .background(ClusterTheme.panel, in: RoundedRectangle(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).strokeBorder(Color.white.opacity(0.12), lineWidth: 0.5))
        .shadow(color: .black.opacity(0.4), radius: 18, x: -8, y: 0)
        .accessibilityAction(.escape) { model.section = .dashboard }
    }
}

struct ConnectionPanel: View {
    @ObservedObject var model: AppModel
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(spacing: 12) {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                        .font(.system(size: 24, weight: .light)).foregroundStyle(ClusterTheme.lcd)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(model.isDemo ? "Lector simulado" : "E36-OBD").font(.headline)
                        Text(model.status).font(.footnote).foregroundStyle(ClusterTheme.muted).accessibilityIdentifier("connectionStatus")
                    }
                }
                ForEach(model.devices) { device in
                    Button { model.selectDevice(device.id) } label: {
                        HStack { Text(device.name); Spacer(); Text("\(device.rssi) dBm").foregroundStyle(ClusterTheme.muted) }
                    }.buttonStyle(PhysicalButton())
                }
                Button(model.connected || model.wantsLive ? "Desconectar" : "Buscar lector") {
                    if model.connected || model.wantsLive { model.disconnect() } else { model.connect() }
                }.buttonStyle(PhysicalButton(selected: true)).accessibilityIdentifier("readerActionButton")
                if let error = model.storageError {
                    Text(error).font(.footnote).foregroundStyle(ClusterTheme.danger)
                }
                VStack(spacing: 14) {
                    DetailRow(title: "Consulta ECU", value: model.telemetry.map { "\($0.ecuMS) ms" } ?? "—")
                    DetailRow(title: "Recepción", value: model.hz.map { String(format: "%.2f Hz", $0) } ?? "—")
                    if let date = model.lastReceivedAt {
                        HStack {
                            Text("Última muestra").foregroundStyle(ClusterTheme.muted)
                            Spacer(); Text(date, style: .time).monospacedDigit()
                        }.font(.subheadline)
                    }
                }
                DisclosureGroup("Acerca del enlace") {
                    Text("El lector admite una conexión a la vez. La búsqueda inicial requiere la app abierta.")
                        .font(.footnote).foregroundStyle(ClusterTheme.muted).padding(.top, 8)
                }.font(.subheadline)
            }.padding(.vertical, 4)
        }.foregroundStyle(ClusterTheme.ink)
    }
}

struct DetailRow: View {
    let title: String
    let value: String
    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title).foregroundStyle(ClusterTheme.muted)
            Spacer(minLength: 12)
            Text(value).monospacedDigit()
        }.font(.subheadline).foregroundStyle(ClusterTheme.ink)
    }
}

struct FaultsView: View {
    @ObservedObject var model: AppModel
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 12) {
                    Button(model.phase.readingFaults ? "Leyendo…" : "Leer DME") { model.readFaults() }
                        .buttonStyle(PhysicalButton()).disabled(!model.canReadFaults)
                        .accessibilityIdentifier("readFaultsButton")
                    if model.faultCompleted {
                        Label(model.faultReport.noFaults ? "Sin fallas" : "\(model.faultReport.records.count) registros", systemImage: "checkmark.circle")
                            .font(.caption).foregroundStyle(ClusterTheme.muted).accessibilityIdentifier("faultsComplete")
                    }
                }
                if let error = model.faultReport.error { Text(error).font(.footnote).foregroundStyle(ClusterTheme.danger) }
                ForEach(model.faultReport.records) { fault in
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(String(format: "%03d", fault.code))
                                .font(.system(size: 30, weight: .light, design: .monospaced))
                                .accessibilityLabel("Código \(fault.code)").accessibilityIdentifier("fault-code-\(fault.code)")
                            if let condition = fault.condition {
                                Text("Condición \(condition)").font(.caption).foregroundStyle(ClusterTheme.muted)
                            }
                            if !fault.detail.isEmpty { Text(fault.detail).font(.footnote) }
                        }
                        Spacer()
                        Text("\(fault.occurrences) ocurr.").font(.caption).monospacedDigit().foregroundStyle(ClusterTheme.muted)
                    }.padding(.vertical, 4)
                    Divider().overlay(ClusterTheme.line)
                }
                DisclosureGroup("Registro") {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(model.log.suffix(150).reversed()) { event in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(event.timestamp, format: .dateTime.hour().minute().second()).font(.caption2).foregroundStyle(ClusterTheme.muted)
                                Text(event.message).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                            }
                        }
                    }.padding(.top, 12)
                }.font(.subheadline).accessibilityIdentifier("firmwareLogDisclosure")
            }.padding(.vertical, 4)
        }.foregroundStyle(ClusterTheme.ink)
    }
}
