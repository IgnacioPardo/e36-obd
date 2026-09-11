import SwiftUI
import E36Core

/// Vehicle identity and observed state. Opening this view never sends an ECU command.
struct VehicleOverview: View {
    @ObservedObject var model: AppModel
    let horizontal: Bool
    let instruments: () -> Void
    @Environment(\.dynamicTypeSize) private var textSize
    @State private var vehicleCamera = VehicleCameraPose()

    private var receiving: Bool { model.phase == .live && model.connected && !model.stale }
    private var stateTitle: String {
        if model.storageError != nil { return "Captura interrumpida" }
        if model.phase.readingFaults { return "Leyendo DME" }
        if model.wantsLive && !receiving { return "Captura en pausa" }
        if model.telemetry?.validity == .unpopulated && !model.stale { return "Motor apagado" }
        if receiving { return "En vivo" }
        return model.connected ? "Conectado" : "Sin conectar"
    }
    var body: some View {
        GeometryReader { geometry in
            if horizontal && !textSize.isAccessibilitySize {
                HStack(spacing: 28) {
                    VStack(alignment: .leading, spacing: 0) {
                        identity(compact: true)
                        car.frame(maxHeight: .infinity)
                    }.frame(maxWidth: .infinity)
                    ScrollView {
                        VStack(spacing: 14) { readings; destinations }
                    }.frame(width: min(330, geometry.size.width * 0.43))
                }
            } else {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 0) {
                        identity(compact: false)
                        car.frame(height: min(235, max(170, geometry.size.height * 0.34)))
                            .overlay(alignment: .bottom) {
                                if model.storageError != nil || !model.activeAlerts.isEmpty || model.wantsLive && model.stale || model.telemetry?.saturated == true {
                                    AnnunciatorStrip(model: model).frame(height: 24)
                                }
                            }
                        readings.padding(.bottom, 18)
                        destinations
                    }.padding(.bottom, 8)
                }
            }
        }
        .onAppear { model.refreshSessions() }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("vehicleOverview")
    }
    private func identity(compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: compact ? 5 : 8) {
            if !compact { Eyebrow(title: "BMW · Serie 3") }
            HStack(alignment: .firstTextBaseline) {
                Text("E36").font(.system(size: compact ? 44 : 64, weight: .light).width(.expanded))
                    .tracking(-3).foregroundStyle(ClusterTheme.ink)
                Spacer()
                VStack(alignment: .trailing, spacing: 5) {
                    Text("1994").font(.system(size: 16, weight: .light, design: .monospaced))
                    Text("M43B16").font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1.6)
                        .foregroundStyle(ClusterTheme.muted)
                }.foregroundStyle(ClusterTheme.ink)
            }
            HStack(spacing: 7) {
                Circle().fill(receiving ? ClusterTheme.ready : ClusterTheme.accent).frame(width: 4, height: 4)
                Text(stateTitle).font(.system(size: 12, weight: .medium)).foregroundStyle(ClusterTheme.muted)
            }.accessibilityIdentifier("vehicleStatus")
        }
    }
    private var car: some View {
        VehicleSceneView(camera: $vehicleCamera)
    }
    private var readings: some View {
        Button(action: instruments) {
            VStack(alignment: .leading, spacing: horizontal ? 10 : 16) {
                HStack {
                    Eyebrow(title: receiving ? "Telemetría en vivo" : "Última lectura")
                    Spacer()
                    Image(systemName: "arrow.up.right").font(.system(size: 12)).foregroundStyle(ClusterTheme.accent)
                }
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 0) { metric(.rpm); separator; metric(.coolant); separator; metric(.battery) }
                    VStack(spacing: 16) { metric(.rpm); metric(.coolant); metric(.battery) }
                }
            }.padding(horizontal ? 14 : 18).modifier(CockpitSurface())
        }.buttonStyle(.plain).accessibilityIdentifier("overviewInstrumentsButton")
            .accessibilityLabel("Abrir instrumentos")
            .accessibilityValue([Sensor.rpm, .coolant, .battery].map { sensor in
                "\(sensor.title), \(sensor.formatted(model.displayTelemetry?[sensor])) \(sensor.unit)"
            }.joined(separator: ", ") + (receiving ? ", en vivo" : ", última lectura"))
    }
    private var separator: some View { Rectangle().fill(ClusterTheme.line).frame(width: 0.5, height: 36).padding(.horizontal, 10) }
    private func metric(_ sensor: Sensor) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(sensor.formatted(model.displayTelemetry?[sensor]))
                    .font(.system(size: 25, weight: .light).width(.condensed)).monospacedDigit()
                    .contentTransition(.numericText()).lineLimit(1)
                Text(sensor.unit).font(.system(size: 9, weight: .medium)).foregroundStyle(ClusterTheme.muted)
            }.foregroundStyle(model.stale ? ClusterTheme.muted : ClusterTheme.ink)
            Text(sensor.title).font(.system(size: 10)).foregroundStyle(ClusterTheme.muted)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
    private var destinations: some View {
        VStack(spacing: 0) {
            destination("Diagnóstico", subtitle: faultSubtitle, icon: "engine.combustion", section: .faults)
            Rectangle().fill(ClusterTheme.line).frame(height: 0.5).padding(.leading, 57)
            destination("Tus recorridos", subtitle: sessionSubtitle, icon: "point.topleft.down.curvedto.point.bottomright.up", section: .sessions)
        }
    }
    private func destination(_ title: String, subtitle: String, icon: String, section: AppSection) -> some View {
        Button {
            model.section = section
            if section == .sessions { model.refreshSessions() }
        } label: {
            HStack(spacing: 15) {
                Image(systemName: icon).font(.system(size: 19, weight: .light)).foregroundStyle(ClusterTheme.ink)
                    .frame(width: horizontal ? 32 : 42, height: horizontal ? 32 : 42)
                    .background(Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 12))
                VStack(alignment: .leading, spacing: 5) {
                    Text(title).font(.system(size: 15, weight: .medium)).foregroundStyle(ClusterTheme.ink)
                    if !horizontal || textSize.isAccessibilitySize {
                        Text(subtitle).font(.system(size: 11)).foregroundStyle(ClusterTheme.muted)
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 10, weight: .medium)).foregroundStyle(ClusterTheme.muted)
            }.padding(.vertical, horizontal ? 8 : 14).frame(minHeight: 44).contentShape(Rectangle())
        }.buttonStyle(.plain)
    }
    private var faultSubtitle: String {
        if model.phase.readingFaults { return "Lectura en curso" }
        if model.faultReport.error != nil { return "Lectura no disponible" }
        guard model.faultCompleted else { return "Memoria del DME · sin consultar" }
        return model.faultReport.noFaults ? "Sin fallas en la última lectura" : "\(model.faultReport.records.count) registros en la última lectura"
    }
    private var sessionSubtitle: String {
        guard let last = model.sessions.first else { return "El historial de tu E36" }
        return "\(last.startedAt.formatted(.dateTime.day().month())) · \(duration(last.elapsed))"
    }
}
