import SwiftUI
import E36Core

struct DashboardPage: View {
    @ObservedObject var model: AppModel
    let section: AppSection
    let horizontal: Bool
    private var title: String {
        switch section {
        case .connection: "Conexión"
        case .faults: "Fallas"
        case .sessions: "Sesiones"
        case .settings: "Ajustes"
        case .dashboard: ""
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.title2.weight(.light)).tracking(-0.5)
                .foregroundStyle(ClusterTheme.ink).lineLimit(1).minimumScaleFactor(0.7)
                .accessibilityAddTraits(.isHeader)
            VStack(spacing: 12) {
                GarageRule()
                Group {
                    switch section {
                    case .faults: FaultsView(model: model)
                    case .sessions: SessionsView(model: model)
                    case .settings: SettingsView(model: model)
                    case .connection, .dashboard: EmptyView()
                    }
                }.frame(maxWidth: .infinity, maxHeight: .infinity)
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .padding(.top, horizontal ? 4 : 12)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("\(section.rawValue)Page")
    }
}

struct ConnectionSheet: View {
    @ObservedObject var model: AppModel
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ConnectionPanel(model: model)
                .padding(.horizontal, 22).padding(.top, 12)
                .frame(maxWidth: 680)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .navigationTitle("Conexión").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button { dismiss() } label: {
                            Image(systemName: "xmark").font(.system(size: 13, weight: .semibold))
                                .frame(width: 44, height: 44).contentShape(Rectangle())
                        }.accessibilityLabel("Cerrar conexión").accessibilityIdentifier("closeConnectionButton")
                    }
                }
        }
        .tint(ClusterTheme.ink)
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationCornerRadius(28)
        .presentationBackground(ClusterTheme.panel)
        .accessibilityIdentifier("connectionSheet")
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
    @Environment(\.verticalSizeClass) private var verticalSize
    private var compact: Bool { verticalSize == .compact }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: compact ? 10 : 18) {
                HStack(spacing: 12) {
                    Button(model.phase.readingFaults ? "Leyendo…" : "Leer DME") { model.readFaults() }
                        .buttonStyle(PhysicalButton()).disabled(!model.canReadFaults)
                        .accessibilityIdentifier("readFaultsButton")
                    if model.faultCompleted, model.faultReport.error == nil {
                        Label(model.faultReport.noFaults ? "Sin fallas" : "\(model.faultReport.records.count) registros", systemImage: "checkmark.circle")
                            .font(.caption).foregroundStyle(ClusterTheme.muted).accessibilityIdentifier("faultsComplete")
                    }
                }
                if let error = model.faultReport.error {
                    Text(error).font(.footnote).foregroundStyle(ClusterTheme.danger)
                        .accessibilityIdentifier("faultReadError")
                }
                if !model.faultCompleted && !model.phase.readingFaults && model.faultReport.error == nil {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            GarageCaption("BOSCH / DME")
                            Spacer()
                            Image(systemName: "engine.combustion").font(.system(size: 24, weight: .ultraLight)).foregroundStyle(ClusterTheme.muted)
                        }
                        Text("Motronic").font(.system(size: 30, weight: .light)).tracking(-0.8)
                        HStack {
                            Text("1.7.2").font(.system(.subheadline, design: .monospaced))
                            Spacer()
                            Text("Sin consultar").font(.footnote).foregroundStyle(ClusterTheme.muted)
                        }
                    }.foregroundStyle(ClusterTheme.ink).padding(.vertical, 20)
                }
                ForEach(model.faultReport.records) { fault in
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(String(format: "%03d", fault.code))
                                .font(.system(size: compact ? 28 : 38, weight: .light, design: .monospaced)).foregroundStyle(ClusterTheme.accent)
                                .accessibilityLabel("Código \(fault.code)").accessibilityIdentifier("fault-code-\(fault.code)")
                            if let condition = fault.condition {
                                Text("Condición \(condition)").font(.caption).foregroundStyle(ClusterTheme.muted)
                            }
                            if !fault.detail.isEmpty { Text(fault.detail).font(.footnote) }
                        }
                        Spacer()
                        Text("\(fault.occurrences) ocurr.").font(.caption).monospacedDigit().foregroundStyle(ClusterTheme.muted)
                    }.padding(.vertical, compact ? 10 : 18)
                        .padding(.leading, 16)
                        .overlay(alignment: .leading) { Rectangle().fill(ClusterTheme.accent.opacity(0.6)).frame(width: 1) }
                        .frame(maxWidth: .infinity, alignment: .leading)
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
