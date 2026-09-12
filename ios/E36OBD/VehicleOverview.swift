import SwiftUI
import E36Core

/// Presentation only: scene navigation observes the same capture as the cluster.
struct VehicleOverview: View {
    @ObservedObject var model: AppModel
    let horizontal: Bool
    let instruments: () -> Void
    @ScaledMetric(relativeTo: .title) private var metricSize = 30.0
    @ScaledMetric(relativeTo: .caption2) private var unitSize = 9.0

    private var receiving: Bool { model.phase == .live && model.connected && !model.stale }
    private var stateTitle: String {
        if model.storageError != nil { return "Captura interrumpida" }
        if model.phase.readingFaults { return "Leyendo DME" }
        if model.wantsLive && !receiving { return "Captura en pausa" }
        if model.telemetry?.validity == .unpopulated && !model.stale { return "Motor apagado" }
        if receiving { return "En vivo" }
        return model.connected ? "Conectado" : "Sin conectar"
    }
    private var stateColor: Color {
        if model.storageError != nil { return ClusterTheme.danger }
        if receiving { return ClusterTheme.ready }
        return model.wantsLive || model.phase.readingFaults ? ClusterTheme.accent : ClusterTheme.muted
    }
    private var hasNotice: Bool {
        model.storageError != nil || !model.activeAlerts.isEmpty || model.wantsLive && model.stale || model.telemetry?.saturated == true
    }

    var body: some View {
        ScrollView(showsIndicators: false) {
            telemetry.padding(.top, 12).padding(.bottom, 8)
        }
        .onAppear { model.refreshSessions() }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("vehicleOverview")
    }

    private var telemetry: some View {
        VStack(spacing: 0) {
            GarageRule()
            Button(action: instruments) {
                VStack(alignment: .leading, spacing: 20) {
                    HStack(spacing: 8) {
                        GarageCaption("INSTRUMENTOS", color: ClusterTheme.ink)
                        Spacer(minLength: 0)
                        Image(systemName: "arrow.up.right").font(.system(size: 12, weight: .medium))
                            .foregroundStyle(ClusterTheme.accent)
                    }
                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .top, spacing: 0) {
                            metric(.rpm); metric(.coolant); metric(.battery)
                        }
                        VStack(alignment: .leading, spacing: 16) {
                            metric(.rpm); metric(.coolant); metric(.battery)
                        }
                    }
                }.padding(.vertical, 16).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("overviewInstrumentsButton")
                .accessibilityLabel("Abrir instrumentos")
                .accessibilityValue([Sensor.rpm, .coolant, .battery].map { sensor in
                    "\(sensor.title), \(sensor.formatted(model.displayTelemetry?[sensor])) \(sensor.unit)"
                }.joined(separator: ", ") + (receiving ? ", en vivo" : ", última lectura"))
            captureStatus
            // Reserve this slot, so warnings never resize the car or telemetry.
            if !horizontal {
                AnnunciatorStrip(model: model).frame(height: 24)
                    .opacity(hasNotice ? 1 : 0).accessibilityHidden(!hasNotice)
            }
        }
    }

    private func metric(_ sensor: Sensor) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(sensor.title).font(.caption2).foregroundStyle(ClusterTheme.muted)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(sensor.formatted(model.displayTelemetry?[sensor]))
                    .font(.system(size: metricSize, weight: .light).width(.condensed)).monospacedDigit()
                    .contentTransition(.numericText()).lineLimit(1).fixedSize(horizontal: true, vertical: false)
                Text(sensor.unit).font(.system(size: unitSize, weight: .medium, design: .monospaced))
                    .foregroundStyle(ClusterTheme.muted)
            }.foregroundStyle(model.stale ? ClusterTheme.muted : ClusterTheme.ink)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private var captureStatus: some View {
        ViewThatFits(in: .horizontal) {
            HStack { status; Spacer(minLength: 8); captureTime }
            VStack(alignment: .leading, spacing: 5) { status; captureTime }.frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 10).padding(.vertical, 9)
        .background(Color.white.opacity(0.025), in: RoundedRectangle(cornerRadius: 5))
    }
    private var status: some View {
        HStack(spacing: 7) {
            Circle().fill(stateColor).frame(width: 4, height: 4)
            Text(stateTitle).font(.caption2).foregroundStyle(stateColor)
        }.accessibilityElement(children: .combine).accessibilityIdentifier("vehicleStatus")
    }
    private var captureTime: some View {
        Group {
            if model.wantsLive {
                Text("\(receiving && model.storageError == nil ? "REC" : "PAUSA") \(duration(model.recordingElapsed))")
                    .foregroundStyle(model.storageError != nil ? ClusterTheme.danger : ClusterTheme.muted)
            } else {
                Text(model.displayTelemetry == nil ? "SIN MUESTRAS" : "ÚLTIMA LECTURA").foregroundStyle(ClusterTheme.muted)
            }
        }.font(.system(size: unitSize, weight: .medium, design: .monospaced)).monospacedDigit()
    }

}

/// A single live scene across all four destinations. Only content beside or
/// below it changes; no tab constructs another renderer or owns capture state.
struct VehiclePresentation: View {
    @Binding var camera: VehicleCameraPose
    @Binding var expanded: Bool
    let horizontal: Bool
    let isVisible: Bool
    @AppStorage("vehicleStage") private var stage = VehicleStage.graphite.rawValue
    @State private var expandedCamera = VehicleCameraPose()
    private var sceneCamera: Binding<VehicleCameraPose> { expanded ? $expandedCamera : $camera }

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text("316i").font(.system(size: horizontal ? 28 : 38, weight: .light).width(.expanded))
                    .tracking(-1.5).foregroundStyle(ClusterTheme.ink).accessibilityLabel("BMW 316i")
                GarageCaption("BMW / E36")
                Spacer()
                GarageCaption("1994")
            }.padding(.horizontal, horizontal ? 28 : 22).frame(height: horizontal ? 38 : 58)
            VehicleSceneView(camera: sceneCamera, isVisible: isVisible, allowsFreeNavigation: expanded)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            HStack(spacing: 4) {
                if expanded {
                    cameraButton("Frente", azimuth: 0.58, identifier: "vehicleFrontButton")
                    cameraButton("Perfil", azimuth: .pi / 2, identifier: "vehicleSideButton")
                    cameraButton("Atrás", azimuth: .pi - 0.58, identifier: "vehicleRearButton")
                    Button { expandedCamera = VehicleCameraPose() } label: {
                        Image(systemName: "arrow.counterclockwise").font(.system(size: 14, weight: .light))
                            .foregroundStyle(ClusterTheme.ink).frame(width: 44, height: 44).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityLabel("Restablecer cámara")
                        .accessibilityIdentifier("resetVehicleCameraButton")
                } else {
                    Circle()
                        .fill(LinearGradient(colors: [Color(red: 0.38, green: 0.46, blue: 0.53), Color(red: 0.15, green: 0.21, blue: 0.27)], startPoint: .topLeading, endPoint: .bottomTrailing))
                        .overlay(Circle().strokeBorder(Color.white.opacity(0.25), lineWidth: 0.5))
                        .frame(width: 10, height: 10).padding(.trailing, 4).accessibilityHidden(true)
                    Text("295 · Samoablau Metallic").font(.system(size: 10)).foregroundStyle(ClusterTheme.muted)
                    Spacer(minLength: 0)
                }
                stageMenu
                Button {
                    if expanded { camera = expandedCamera.dashboardPose }
                    else { expandedCamera = camera.dashboardPose }
                    expanded.toggle()
                } label: {
                    Image(systemName: expanded ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right")
                        .font(.system(size: 13, weight: .light)).foregroundStyle(ClusterTheme.ink)
                        .frame(width: 44, height: 44).contentShape(Rectangle())
                }.buttonStyle(.plain)
                    .accessibilityLabel(expanded ? "Cerrar vista ampliada" : "Ampliar vista del auto")
                    .accessibilityIdentifier(expanded ? "closeVehicleButton" : "expandVehicleButton")
            }.padding(.horizontal, 22).frame(height: 44)
        }
        .accessibilityElement(children: .contain).accessibilityIdentifier("vehiclePresentation")
    }
    private var stageMenu: some View {
        Menu {
            Picker("Ambiente", selection: $stage) {
                ForEach(VehicleStage.allCases) { Text($0.title).tag($0.rawValue) }
            }
        } label: {
            Image(systemName: "sun.max").font(.system(size: 15, weight: .light)).foregroundStyle(ClusterTheme.muted)
                .frame(width: 44, height: 44).contentShape(Rectangle())
        }.accessibilityLabel("Ambiente del auto").accessibilityIdentifier("vehicleStageMenu")
    }
    private func cameraButton(_ title: String, azimuth: Float, identifier: String) -> some View {
        let selected = abs(atan2(sin(sceneCamera.wrappedValue.azimuth - azimuth), cos(sceneCamera.wrappedValue.azimuth - azimuth))) < 0.12
        return Button { sceneCamera.wrappedValue = VehicleCameraPose(azimuth: azimuth) } label: {
            Text(title).font(.system(size: 11, weight: selected ? .semibold : .regular))
                .foregroundStyle(selected ? ClusterTheme.ink : ClusterTheme.muted)
                .frame(maxWidth: .infinity).frame(height: 44).contentShape(Rectangle())
                .background(selected ? Color.white.opacity(0.06) : .clear, in: Capsule())
        }.buttonStyle(.plain).accessibilityIdentifier(identifier).accessibilityAddTraits(selected ? .isSelected : [])
    }
}

/// Fine rules and engraved labels belong to the app's surrounding UI, not the gauges.
struct GarageRule: View {
    var body: some View {
        Rectangle().fill(LinearGradient(colors: [Color.white.opacity(0.22), Color.white.opacity(0.06)], startPoint: .leading, endPoint: .trailing))
            .frame(height: 0.5).accessibilityHidden(true)
    }
}
struct GarageCaption: View {
    let title: String
    var color: Color = ClusterTheme.muted
    init(_ title: String, color: Color = ClusterTheme.muted) { self.title = title; self.color = color }
    var body: some View {
        Text(title).font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1.8).foregroundStyle(color)
    }
}
