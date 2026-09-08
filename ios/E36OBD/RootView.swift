import SwiftUI
import E36Core

struct RootView: View {
    @ObservedObject var model: AppModel
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        GeometryReader { geometry in
            let horizontal = geometry.size.width > geometry.size.height
            VStack(spacing: horizontal ? 6 : 8) {
                header(horizontal: horizontal)
                if !horizontal { AnnunciatorStrip(model: model).frame(height: 28) }
                GeometryReader { bay in
                    ZStack(alignment: .trailing) {
                        cockpit(size: bay.size)
                            .opacity(model.section == .dashboard ? 1 : 0.35)
                            .accessibilityHidden(model.section != .dashboard)
                        if model.section != .dashboard {
                            Color.clear
                                .contentShape(Rectangle()).onTapGesture { model.section = .dashboard }
                                .accessibilityHidden(true)
                            InspectorPanel(model: model)
                                .frame(width: horizontal ? min(420, bay.size.width * 0.60) : bay.size.width)
                                .frame(maxHeight: .infinity)
                                .transition(.opacity)
                        }
                    }
                }
                controls(horizontal: horizontal)
            }
            .padding(.horizontal, horizontal ? 8 : 18)
            .padding(.top, 4).padding(.bottom, 8)
        }
        .background(ClusterTheme.background.ignoresSafeArea())
        .preferredColorScheme(.dark).tint(ClusterTheme.lcd)
        .onChange(of: scenePhase, initial: true) { _, phase in model.setForeground(phase == .active); updateIdleTimer() }
        .onChange(of: model.wantsLive) { updateIdleTimer() }
        .onChange(of: model.section) { updateIdleTimer() }
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
    private func header(horizontal: Bool) -> some View {
        HStack(spacing: 12) {
            Button { model.section = .dashboard } label: {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text("E36").font(.system(size: 22, weight: .semibold).width(.condensed)).tracking(1)
                    if !horizontal {
                        Text("M43").font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1).foregroundStyle(ClusterTheme.muted)
                    }
                }.frame(minHeight: 44).contentShape(Rectangle())
            }.buttonStyle(.plain).foregroundStyle(ClusterTheme.ink).accessibilityLabel("Tablero")
            if horizontal { AnnunciatorStrip(model: model) }
            Spacer(minLength: 0)
            if model.isDemo {
                Menu {
                    Picker("Escenario", selection: $model.demoScenario) {
                        ForEach(DemoScenario.allCases) { Text($0.rawValue).tag($0) }
                    }
                } label: {
                    Text("DEMO").font(.system(size: 9, weight: .semibold, design: .monospaced)).tracking(1)
                        .padding(.horizontal, 9).padding(.vertical, 6)
                        .overlay(Capsule().strokeBorder(ClusterTheme.lcd.opacity(0.35), lineWidth: 0.5))
                        .frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
                }.foregroundStyle(ClusterTheme.lcd)
                    .accessibilityIdentifier("demoScenario").accessibilityLabel("Demostración").accessibilityValue(model.demoScenario.rawValue)
            }
            Button { toggle(.connection) } label: {
                HStack(spacing: 7) {
                    Circle().fill(model.connected ? (model.stale ? ClusterTheme.lcd : Color(red: 0.5, green: 0.72, blue: 0.55)) : ClusterTheme.muted)
                        .frame(width: 5, height: 5)
                    Text("BLE").font(.system(size: 10, weight: .semibold, design: .monospaced)).tracking(1)
                    Image(systemName: "chevron.down").font(.system(size: 8, weight: .semibold))
                }
                .foregroundStyle(ClusterTheme.ink)
                .frame(width: 76, height: 44).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("connectButton").accessibilityLabel("Conexión, \(model.status)")
        }.frame(height: 44)
    }
    private func controls(horizontal: Bool) -> some View {
        HStack(spacing: horizontal ? 14 : 10) {
            if horizontal {
                OBCDisplay(model: model, horizontal: true).frame(width: 236, height: 44)
                Rectangle().fill(ClusterTheme.line).frame(width: 0.5, height: 32)
            }
            Button { model.wantsLive ? model.stop() : model.start() } label: {
                HStack(spacing: 9) {
                    Image(systemName: model.wantsLive ? "stop.fill" : "play.fill").font(.system(size: 11, weight: .bold))
                    Text(model.wantsLive ? "Detener" : "En vivo").font(.system(size: 14, weight: .semibold))
                }
                .frame(maxWidth: .infinity).frame(height: 48)
                .foregroundStyle(ClusterTheme.background)
                .background(ClusterTheme.ink, in: RoundedRectangle(cornerRadius: 12))
                .opacity(!model.wantsLive && !model.canStart ? 0.3 : 1)
            }.buttonStyle(.plain).disabled(!model.wantsLive && !model.canStart).accessibilityIdentifier("liveButton")
            dockButton(.faults, symbol: "engine.combustion", title: "Fallas", identifier: "faultsTab")
            dockButton(.sessions, symbol: "clock.arrow.circlepath", title: "Sesiones", identifier: "sessionsTab")
            dockButton(.settings, symbol: "slider.horizontal.3", title: "Ajustes", identifier: "settingsTab")
        }
        .padding(6).background(Color.black.opacity(0.16), in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(ClusterTheme.line, lineWidth: 0.5))
        .frame(maxWidth: horizontal ? 760 : .infinity).frame(height: 60)
    }
    private func dockButton(_ section: AppSection, symbol: String, title: String, identifier: String) -> some View {
        Button { toggle(section) } label: {
            VStack(spacing: 5) {
                Image(systemName: symbol).font(.system(size: 17, weight: .regular))
                Text(title).font(.system(size: 10, weight: .medium))
            }.frame(width: 54, height: 48).contentShape(Rectangle())
                .foregroundStyle(model.section == section ? ClusterTheme.lcd : ClusterTheme.muted)
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
