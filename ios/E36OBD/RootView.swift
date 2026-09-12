import SwiftUI
import E36Core

struct RootView: View {
    @ObservedObject var model: AppModel
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var textSize
    @State private var showingInstruments = false
    @State private var expandedVehicle = false
    @State private var vehicleCamera = VehicleCameraPose()
    @State private var visitedSections: Set<AppSection> = []
    @State private var connectionPresented = false

    var body: some View {
        GeometryReader { geometry in
            let horizontal = geometry.size.width > geometry.size.height
            VStack(spacing: horizontal ? 4 : 12) {
                header(horizontal: horizontal).padding(.horizontal, horizontal ? 10 : 22)
                GeometryReader { bay in
                    ZStack {
                        garage(size: bay.size, horizontal: horizontal)
                            .opacity(showingInstruments ? 0 : 1)
                            .allowsHitTesting(!showingInstruments)
                            .accessibilityHidden(showingInstruments)
                        if showingInstruments {
                            VStack(spacing: horizontal ? 4 : 12) {
                                if !horizontal { AnnunciatorStrip(model: model).frame(height: 24) }
                                GeometryReader { instruments in cockpit(size: instruments.size) }
                            }
                            .padding(.horizontal, horizontal ? 10 : 22)
                            .frame(width: geometry.size.width)
                        }
                    }.frame(width: bay.size.width, height: bay.size.height)
                }
                // Only the scene bay extends through the horizontal safe areas.
                // Header, gauges and navigation keep their own readable insets.
                .ignoresSafeArea(.container, edges: .horizontal)
                VStack(spacing: 4) {
                    if horizontal {
                        HStack(spacing: 12) {
                            AnnunciatorStrip(model: model).frame(maxWidth: 330)
                            Spacer(minLength: 0)
                            connectionTiming
                        }.frame(height: 20)
                    }
                    tabs(horizontal: horizontal)
                }.padding(.horizontal, horizontal ? 10 : 22)
            }
            .padding(.top, horizontal ? 0 : 3).padding(.bottom, 8)
        }
        .background(ClusterTheme.background.ignoresSafeArea())
        .preferredColorScheme(.dark).tint(ClusterTheme.lcd)
        .sheet(isPresented: $connectionPresented) { ConnectionSheet(model: model) }
        .onOpenURL { url in
            guard url.scheme == "e36" else { return }
            if url.host == "dashboard" {
                connectionPresented = false
                showingInstruments = true
            } else if url.host == "vehicle" {
                connectionPresented = false
                select(.dashboard)
            }
        }
        .onChange(of: scenePhase, initial: true) { _, phase in model.setForeground(phase == .active); updateIdleTimer() }
        .onChange(of: model.wantsLive) { updateIdleTimer() }
        .onChange(of: connectionPresented) { updateIdleTimer() }
        .onDisappear { UIApplication.shared.isIdleTimerDisabled = false }
    }

    private func garage(size: CGSize, horizontal: Bool) -> some View {
        let layout = horizontal ? AnyLayout(HStackLayout(spacing: expandedVehicle ? 0 : 12)) : AnyLayout(VStackLayout(spacing: 0))
        let stageHeight = expandedVehicle ? size.height : min(size.height * (textSize.isAccessibilitySize ? 0.34 : 0.49), 370)
        let stageWidth = expandedVehicle ? size.width : size.width * 0.48
        return layout {
            // One UIView/Metal scene survives tabs, orientation and expansion.
            VehiclePresentation(camera: $vehicleCamera, expanded: $expandedVehicle,
                horizontal: horizontal, isVisible: !showingInstruments && !connectionPresented)
                .frame(width: horizontal ? stageWidth : size.width,
                       height: horizontal ? size.height : stageHeight)
            ZStack {
                VehicleOverview(model: model, horizontal: horizontal) { showingInstruments = true }
                    .zIndex(model.section == .dashboard ? 1 : 0)
                    .opacity(model.section == .dashboard ? 1 : 0)
                    .allowsHitTesting(model.section == .dashboard)
                    .accessibilityHidden(model.section != .dashboard)
                    .transaction { transaction in
                        if showingInstruments || model.section != .dashboard {
                            transaction.animation = nil
                            transaction.disablesAnimations = true
                        }
                    }
                ForEach([AppSection.faults, .sessions, .settings], id: \.self) { section in
                    if visitedSections.contains(section) {
                        DashboardPage(model: model, section: section, horizontal: horizontal)
                            .zIndex(model.section == section ? 1 : 0)
                            .opacity(model.section == section ? 1 : 0)
                            .allowsHitTesting(model.section == section)
                            .accessibilityHidden(model.section != section)
                    }
                }
            }
            .padding(.horizontal, horizontal ? 16 : 22)
            .padding(.trailing, horizontal ? 18 : 0)
            .frame(width: horizontal ? max(0, size.width - stageWidth - (expandedVehicle ? 0 : 12)) : size.width,
                   height: horizontal ? size.height : max(0, size.height - stageHeight))
            .opacity(expandedVehicle ? 0 : 1)
            .allowsHitTesting(!expandedVehicle)
            .accessibilityHidden(expandedVehicle)
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.18), value: model.section)
            .clipped()
        }
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
        UIApplication.shared.isIdleTimerDisabled = scenePhase == .active && !connectionPresented && model.wantsLive
    }

    private func header(horizontal: Bool) -> some View {
        HStack(spacing: horizontal ? 14 : 6) {
            if horizontal {
                Text("E36").font(.system(size: 21, weight: .medium).width(.expanded)).tracking(1)
                    .foregroundStyle(ClusterTheme.ink)
            }
            Button {
                if model.wantsLive { model.stop() } else { model.start() }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: model.wantsLive ? "stop.fill" : "play.fill")
                        .font(.system(size: 10, weight: .bold))
                    Text(model.wantsLive ? "Detener" : "En vivo").font(.system(size: 12, weight: .semibold))
                }
                .frame(width: 92, height: 44)
                .foregroundStyle(model.wantsLive ? ClusterTheme.ink : ClusterTheme.background)
                .background(model.wantsLive ? Color.white.opacity(0.08) : ClusterTheme.ink, in: Capsule())
                .opacity(!model.wantsLive && !model.canStart ? 0.35 : 1)
            }.buttonStyle(.plain).disabled(!model.wantsLive && !model.canStart).accessibilityIdentifier("liveButton")
            Button { showingInstruments.toggle() } label: {
                HStack(spacing: 7) {
                    Image(systemName: "gauge.with.dots.needle.50percent").font(.system(size: 15, weight: .light))
                    Text("Instrumentos").font(.system(size: 12, weight: showingInstruments ? .semibold : .regular))
                }
                .frame(minWidth: 116, minHeight: 44).contentShape(Rectangle())
                .foregroundStyle(showingInstruments ? ClusterTheme.ink : ClusterTheme.muted)
                .overlay(alignment: .bottom) {
                    Capsule().fill(showingInstruments ? ClusterTheme.accent : .clear).frame(width: 16, height: 2)
                }
            }.buttonStyle(.plain).accessibilityIdentifier("instrumentsTab")
                .accessibilityAddTraits(showingInstruments ? .isSelected : [])
            Spacer(minLength: 0)
            if model.isDemo {
                Menu {
                    Picker("Escenario", selection: $model.demoScenario) {
                        ForEach(DemoScenario.allCases) { Text($0.rawValue).tag($0) }
                    }
                } label: {
                    Image(systemName: "slider.horizontal.3").font(.system(size: 12, weight: .medium))
                        .foregroundStyle(ClusterTheme.accent).frame(width: 44, height: 44).contentShape(Rectangle())
                }.accessibilityIdentifier("demoScenario").accessibilityLabel("Escenario").accessibilityValue(model.demoScenario.rawValue)
            }
            Button { connectionPresented = true } label: {
                HStack(spacing: 6) {
                    Circle().fill(model.connected ? (model.stale ? ClusterTheme.accent : ClusterTheme.ready) : ClusterTheme.muted)
                        .frame(width: 4, height: 4)
                    Image(systemName: "antenna.radiowaves.left.and.right").font(.system(size: 16, weight: .light))
                }.foregroundStyle(ClusterTheme.ink).frame(width: 50, height: 44)
                    .background(Color.white.opacity(0.035), in: Capsule()).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("connectButton").accessibilityLabel("Conexión, \(model.status)")
        }.frame(height: 44)
    }
    private var connectionTiming: some View {
        HStack(spacing: 12) {
            if let data = model.telemetry { Text("ECU \(data.ecuMS) ms") }
            if let hz = model.hz { Text(String(format: "RX %.1f Hz", hz)) }
        }.font(.system(size: 9, weight: .medium, design: .monospaced)).foregroundStyle(ClusterTheme.muted)
    }
    private func tabs(horizontal: Bool) -> some View {
        HStack(spacing: horizontal ? 10 : 4) {
            if horizontal && showingInstruments {
                OBCDisplay(model: model, horizontal: true).frame(width: 215, height: 44)
                Rectangle().fill(ClusterTheme.line).frame(width: 0.5, height: 30)
            }
            dockButton(.dashboard, symbol: "car.side", title: "Auto", identifier: "vehicleTab")
            dockButton(.faults, symbol: "engine.combustion", title: "Fallas", identifier: "faultsTab")
            dockButton(.sessions, symbol: "clock.arrow.circlepath", title: "Sesiones", identifier: "sessionsTab")
            dockButton(.settings, symbol: "slider.horizontal.3", title: "Ajustes", identifier: "settingsTab")
        }
        .padding(6).modifier(CockpitSurface(radius: 19))
        .frame(maxWidth: horizontal ? 760 : .infinity).frame(height: 60)
    }
    private func dockButton(_ section: AppSection, symbol: String, title: String, identifier: String) -> some View {
        let selected = model.section == section && !showingInstruments
        return Button { select(section) } label: {
            VStack(spacing: 6) {
                Image(systemName: symbol).font(.system(size: 17, weight: .light))
                Text(title).font(.system(size: 9, weight: .medium))
            }.frame(maxWidth: .infinity).frame(height: 48).contentShape(Rectangle())
                .foregroundStyle(selected ? ClusterTheme.lcd : ClusterTheme.muted)
                .background(selected ? ClusterTheme.accent.opacity(0.07) : .clear, in: RoundedRectangle(cornerRadius: 12))
        }.buttonStyle(.plain).accessibilityIdentifier(identifier).accessibilityLabel(title)
            .accessibilityAddTraits(selected ? .isSelected : [])
    }
    private func select(_ section: AppSection) {
        let changed = model.section != section
        visitedSections.insert(section)
        showingInstruments = false
        if changed {
            expandedVehicle = false
            let order: [AppSection] = [.dashboard, .faults, .sessions, .settings]
            vehicleCamera = .tab(order.firstIndex(of: section) ?? 0,
                from: order.firstIndex(of: model.section) ?? 0)
        }
        model.section = section
        if section == .sessions { model.refreshSessions() }
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
