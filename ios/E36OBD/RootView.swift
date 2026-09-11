import SwiftUI
import E36Core

private enum DashboardSurface: String, CaseIterable { case vehicle = "Auto", instruments = "Instrumentos" }

struct RootView: View {
    @ObservedObject var model: AppModel
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var surface: DashboardSurface = .vehicle
    var body: some View {
        GeometryReader { geometry in
            let horizontal = geometry.size.width > geometry.size.height
            VStack(spacing: horizontal ? 4 : 12) {
                header(horizontal: horizontal)
                if !horizontal && surface == .instruments {
                    AnnunciatorStrip(model: model).frame(height: 24)
                }
                GeometryReader { bay in
                    ZStack(alignment: .trailing) {
                        Group {
                            if surface == .vehicle {
                                VehicleOverview(model: model, horizontal: horizontal) { showInstruments() }
                            } else {
                                cockpit(size: bay.size)
                            }
                        }
                        .opacity(model.section == .dashboard ? 1 : 0.18)
                        .allowsHitTesting(model.section == .dashboard)
                        .accessibilityHidden(model.section != .dashboard)
                        if model.section != .dashboard {
                            Color.clear.contentShape(Rectangle()).onTapGesture { model.section = .dashboard }
                                .accessibilityHidden(true)
                            InspectorPanel(model: model)
                                .frame(width: horizontal ? min(440, bay.size.width * 0.62) : bay.size.width)
                                .frame(maxHeight: .infinity)
                                .transition(.opacity)
                        }
                    }
                }
                VStack(spacing: 4) {
                    if horizontal {
                        HStack(spacing: 12) {
                            AnnunciatorStrip(model: model).frame(maxWidth: 330)
                            Spacer(minLength: 0)
                            connectionTiming
                        }.frame(height: 20)
                    }
                    controls(horizontal: horizontal)
                }
            }
            .padding(.horizontal, horizontal ? 10 : 22)
            .padding(.top, horizontal ? 0 : 3).padding(.bottom, 8)
        }
        .background(ClusterTheme.background.ignoresSafeArea())
        .preferredColorScheme(.dark).tint(ClusterTheme.lcd)
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: model.section)
        .onChange(of: scenePhase, initial: true) { _, phase in model.setForeground(phase == .active); updateIdleTimer() }
        .onChange(of: model.wantsLive) { updateIdleTimer() }
        .onChange(of: model.section) { updateIdleTimer() }
        .onChange(of: surface) { updateIdleTimer() }
        .onDisappear { UIApplication.shared.isIdleTimerDisabled = false }
    }
    private func cockpit(size: CGSize) -> some View {
        let layout = CockpitLayout(size: size)
        return ZStack {
            ForEach(layout.placements) { placement in
                InstrumentDial(sensor: placement.sensor, value: model.displayTelemetry?[placement.sensor],
                    stale: model.stale, compact: placement.compact, warning: warning(placement.sensor))
                    .frame(width: placement.frame.width, height: placement.frame.height)
                    .position(x: placement.frame.midX, y: placement.frame.midY)
            }
            if let display = layout.display {
                OBCDisplay(model: model)
                    .frame(width: display.width, height: display.height)
                    .position(x: display.midX, y: display.midY)
            }
        }.frame(width: size.width, height: size.height)
    }
    private func warning(_ sensor: Sensor) -> Bool {
        switch sensor {
        case .load: model.activeAlerts.contains(.lowLoad)
        case .coolant: model.activeAlerts.contains(.coolant)
        case .intake: model.activeAlerts.contains(.intake)
        default: false
        }
    }
    private func updateIdleTimer() {
        UIApplication.shared.isIdleTimerDisabled = scenePhase == .active && model.section == .dashboard && model.wantsLive
    }
    private func showInstruments() {
        surface = .instruments
        model.section = .dashboard
    }
    private func header(horizontal: Bool) -> some View {
        HStack(spacing: horizontal ? 18 : 8) {
            if horizontal {
                Text("E36").font(.system(size: 21, weight: .medium).width(.expanded)).tracking(1)
                    .foregroundStyle(ClusterTheme.ink)
            }
            HStack(spacing: 0) {
                ForEach(DashboardSurface.allCases, id: \.self) { item in
                    Button {
                        surface = item
                        model.section = .dashboard
                    } label: {
                        VStack(spacing: 8) {
                            Text(item.rawValue).font(.system(size: 12, weight: surface == item ? .semibold : .regular))
                                .foregroundStyle(surface == item ? ClusterTheme.ink : ClusterTheme.muted)
                            Capsule().fill(surface == item ? ClusterTheme.accent : .clear).frame(width: 16, height: 2)
                        }.frame(width: item == .vehicle ? 58 : 104, height: 44).contentShape(Rectangle())
                    }.buttonStyle(.plain)
                        .accessibilityIdentifier(item == .vehicle ? "vehicleTab" : "instrumentsTab")
                        .accessibilityAddTraits(surface == item ? .isSelected : [])
                }
            }
            Spacer(minLength: 0)
            if model.isDemo {
                Menu {
                    Picker("Escenario", selection: $model.demoScenario) {
                        ForEach(DemoScenario.allCases) { Text($0.rawValue).tag($0) }
                    }
                } label: {
                    Text("DEMO").font(.system(size: 8, weight: .semibold, design: .monospaced)).tracking(1)
                        .padding(.horizontal, 7).padding(.vertical, 6)
                        .background(ClusterTheme.accent.opacity(0.07), in: Capsule())
                        .overlay(Capsule().strokeBorder(ClusterTheme.accent.opacity(0.25), lineWidth: 0.5))
                        .frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
                }.foregroundStyle(ClusterTheme.accent)
                    .accessibilityIdentifier("demoScenario").accessibilityLabel("Demostración").accessibilityValue(model.demoScenario.rawValue)
            }
            Button { toggle(.connection) } label: {
                HStack(spacing: 6) {
                    Circle().fill(model.connected ? (model.stale ? ClusterTheme.accent : ClusterTheme.ready) : ClusterTheme.muted)
                        .frame(width: 4, height: 4)
                    Image(systemName: "antenna.radiowaves.left.and.right").font(.system(size: 16, weight: .light))
                }.foregroundStyle(ClusterTheme.ink).frame(width: 48, height: 44)
                    .background(Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 14))
                    .contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("connectButton").accessibilityLabel("Conexión, \(model.status)")
        }.frame(height: 44)
    }
    private var connectionTiming: some View {
        HStack(spacing: 12) {
            if let data = model.telemetry {
                Text("ECU \(data.ecuMS) ms")
            }
            if let hz = model.hz { Text(String(format: "RX %.1f Hz", hz)) }
        }.font(.system(size: 9, weight: .medium, design: .monospaced)).foregroundStyle(ClusterTheme.muted)
    }
    private func controls(horizontal: Bool) -> some View {
        HStack(spacing: horizontal ? 10 : 5) {
            if horizontal {
                OBCDisplay(model: model, horizontal: true).frame(width: 215, height: 44)
                Rectangle().fill(ClusterTheme.line).frame(width: 0.5, height: 30)
            }
            Button {
                if model.wantsLive { model.stop() }
                else { showInstruments(); model.start() }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: model.wantsLive ? "stop.fill" : "play.fill").font(.system(size: 10, weight: .bold))
                    Text(model.wantsLive ? "Detener" : "En vivo").font(.system(size: 13, weight: .semibold))
                }
                .frame(maxWidth: .infinity).frame(height: 48)
                .foregroundStyle(model.wantsLive ? ClusterTheme.ink : ClusterTheme.background)
                .background(model.wantsLive ? Color.white.opacity(0.08) : ClusterTheme.ink, in: RoundedRectangle(cornerRadius: 13))
                .overlay(RoundedRectangle(cornerRadius: 13).strokeBorder(model.wantsLive ? ClusterTheme.line : .clear, lineWidth: 0.5))
                .opacity(!model.wantsLive && !model.canStart ? 0.35 : 1)
            }.buttonStyle(.plain).disabled(!model.wantsLive && !model.canStart).accessibilityIdentifier("liveButton")
            dockButton(.faults, symbol: "engine.combustion", title: "Fallas", identifier: "faultsTab")
            dockButton(.sessions, symbol: "clock.arrow.circlepath", title: "Sesiones", identifier: "sessionsTab")
            dockButton(.settings, symbol: "slider.horizontal.3", title: "Ajustes", identifier: "settingsTab")
        }
        .padding(6).modifier(CockpitSurface(radius: 19))
        .frame(maxWidth: horizontal ? 760 : .infinity).frame(height: 60)
    }
    private func dockButton(_ section: AppSection, symbol: String, title: String, identifier: String) -> some View {
        Button { toggle(section) } label: {
            VStack(spacing: 6) {
                Image(systemName: symbol).font(.system(size: 17, weight: .light))
                Text(title).font(.system(size: 9, weight: .medium))
            }.frame(width: 52, height: 48).contentShape(Rectangle())
                .foregroundStyle(model.section == section ? ClusterTheme.lcd : ClusterTheme.muted)
                .background(model.section == section ? ClusterTheme.accent.opacity(0.07) : .clear, in: RoundedRectangle(cornerRadius: 12))
        }.buttonStyle(.plain).accessibilityIdentifier(identifier).accessibilityLabel(title)
            .accessibilityAddTraits(model.section == section ? .isSelected : [])
    }
    private func toggle(_ section: AppSection) {
        model.section = model.section == section ? .dashboard : section
        if model.section == .sessions { model.refreshSessions() }
    }
}
struct AnnunciatorStrip: View {
    @ObservedObject var model: AppModel
    var body: some View {
        ZStack {
            if let error = model.storageError {
                Label("Grabación interrumpida", systemImage: "record.circle")
                    .foregroundStyle(ClusterTheme.danger).accessibilityIdentifier("storageError").accessibilityLabel(error)
            } else if !model.activeAlerts.isEmpty {
                HStack(spacing: 14) {
                    ForEach(model.activeAlerts) { rule in
                        Label(shortTitle(rule), systemImage: symbol(rule))
                    }
                }.foregroundStyle(ClusterTheme.danger)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(model.activeAlerts.map(\.title).joined(separator: " · "))
                    .accessibilityIdentifier("activeAlert")
            } else if model.telemetry?.saturated == true {
                Label("Lectura saturada", systemImage: "gauge.with.dots.needle.100percent")
                    .foregroundStyle(ClusterTheme.lcd).accessibilityIdentifier("saturationIndicator")
            } else if model.telemetry?.validity == .unpopulated && !model.stale {
                Label("DME sin datos", systemImage: "engine.combustion").foregroundStyle(ClusterTheme.muted)
            } else if model.wantsLive && model.stale {
                Label(model.phase.readingFaults ? "Leyendo fallas" : "Captura en pausa", systemImage: "pause.circle")
                    .foregroundStyle(ClusterTheme.lcd)
            } else {
                HStack(spacing: 28) {
                    ForEach(AlertRule.allCases) { Image(systemName: symbol($0)) }
                }.foregroundStyle(ClusterTheme.muted.opacity(0.27)).accessibilityHidden(true)
            }
        }
        .font(.system(size: 11, weight: .medium)).lineLimit(1).minimumScaleFactor(0.8)
        .frame(maxWidth: .infinity).frame(height: 28)
    }
    private func shortTitle(_ rule: AlertRule) -> String {
        switch rule { case .lowLoad: "Carga baja"; case .coolant: "Refrigerante"; case .intake: "Admisión" }
    }
    private func symbol(_ rule: AlertRule) -> String {
        switch rule { case .lowLoad: "waveform.path"; case .coolant: "thermometer.high"; case .intake: "wind" }
    }
}
