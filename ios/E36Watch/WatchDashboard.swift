import SwiftUI
import E36Core

struct WatchDashboard: View {
    @ObservedObject var model: WatchModel
    @Environment(\.isLuminanceReduced) private var dimmed
    @State private var settings = false
    var body: some View {
        NavigationStack {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            TabView(selection: $model.selected) {
                ForEach(Array(Sensor.allCases.enumerated()), id: \.element) { index, sensor in
                    WatchInstrument(snapshot: model.snapshot, sensor: sensor, date: context.date, dimmed: dimmed)
                        .tag(index)
                }
                overview(date: context.date).tag(5)
            }
            .tabViewStyle(.verticalPage)
            .ignoresSafeArea(edges: .bottom)
            .onChange(of: model.selected) { _, value in UserDefaults.standard.set(value, forKey: "watchGauge") }
        }
        .containerBackground(.black, for: .navigation)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Button { settings = true } label: { Image(systemName: "ellipsis").font(.caption) }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Opciones de E36")
            }
        }
        .sheet(isPresented: $settings) {
            NavigationStack {
                Form {
                    Picker("Origen", selection: $model.source) {
                        Text("ESP32 / iPhone").tag(WidgetSource.reader)
                        Text("Simulación").tag(WidgetSource.demo)
                    }
                    Text(model.reachable ? "iPhone conectado" : "Abrí E36 en el iPhone para recibir datos.")
                        .font(.footnote)
                    Text("En vivo en el iPhone inicia la captura. El reloj muestra sus mismos cinco sensores.")
                        .font(.footnote).foregroundStyle(.secondary)
                    if model.source == .demo { Text("Iniciá una simulación en el iPhone.").font(.footnote) }
                    Button("Solicitar lectura") { model.request(.snapshot) }.disabled(model.commandPending)
                }.navigationTitle("E36")
                    .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Listo") { settings = false } } }
            }
        }
    }
    }
    private func overview(date: Date) -> some View {
        ScrollView {
            VStack(spacing: 8) {
                WatchIdentity(snapshot: model.snapshot, date: date, dimmed: dimmed)
                ForEach(Sensor.allCases) { sensor in
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Image(systemName: CompanionAppearance.symbol(sensor))
                            .font(.system(size: 13, weight: .medium))
                            .frame(width: 17)
                            .accessibilityHidden(true)
                        Text(sensor.title).font(.system(size: 12)).foregroundStyle(.secondary)
                            .lineLimit(1).minimumScaleFactor(0.8)
                        Spacer(minLength: 4)
                        Text(model.snapshot.formatted(sensor)).font(.system(size: 18, weight: .semibold, design: .rounded)).monospacedDigit()
                        Text(sensor.unit).font(.system(size: 10)).foregroundStyle(.secondary)
                    }
                    .foregroundStyle(model.snapshot.warning(for: sensor, at: date) && !dimmed ? CompanionAppearance.needle : CompanionAppearance.amber)
                    .opacity(model.snapshot.isFresh(at: date) && !dimmed ? 1 : 0.55)
                    .accessibilityElement(children: .combine)
                }
                Divider().padding(.vertical, 2)
                Text(model.snapshot.status(at: date)).font(.caption2).foregroundStyle(.secondary)
                if let received = model.snapshot.receivedAt, !model.snapshot.isFresh(at: date) {
                    Text(received, style: .relative).font(.caption2).monospacedDigit().foregroundStyle(.secondary)
                }
                if let message = model.message { Text(message).font(.caption2).multilineTextAlignment(.center) }
                Group {
                    Button {
                        model.request(model.snapshot.sessionID == nil ? .start : .stop)
                    } label: {
                        Label(model.snapshot.sessionID == nil ? "En vivo" : "Detener",
                              systemImage: model.snapshot.sessionID == nil ? "record.circle" : "stop.fill")
                            .frame(minHeight: 30)
                    }
                    .tint(CompanionAppearance.amber)
                    .disabled(model.commandPending || !model.reachable || (model.snapshot.sessionID == nil && !model.snapshot.canStart))
                }
            }.padding(.horizontal, 6).padding(.bottom, 16)
        }.accessibilityIdentifier("watchOverview")
    }
}

private struct WatchIdentity: View {
    let snapshot: CompanionSnapshot
    let date: Date
    let dimmed: Bool
    var body: some View {
        HStack(spacing: 5) {
            Text("E36").font(.system(size: 12, weight: .bold).width(.condensed)).tracking(2)
            Spacer(minLength: 2)
            if snapshot.sessionID != nil {
                Circle().fill(snapshot.isFresh(at: date) && !dimmed ? CompanionAppearance.needle : .gray)
                    .frame(width: 4, height: 4)
                Text(snapshot.observation.capture == .recording ? "REC" : "PAUSA")
                    .font(.system(size: 8, weight: .medium)).tracking(1)
            }
        }.foregroundStyle(.secondary)
    }
}

private struct WatchInstrument: View {
    let snapshot: CompanionSnapshot
    let sensor: Sensor
    let date: Date
    let dimmed: Bool
    private var fresh: Bool { snapshot.isFresh(at: date) }
    var body: some View {
        GeometryReader { geometry in
            // Use the display width. Identity and captions belong inside the
            // instrument, leaving the face for the scale, needle and reading.
            let diameter = geometry.size.width - 4
            VStack(spacing: 0) {
                ZStack {
                    WatchDial(sensor: sensor, value: snapshot.value(for: sensor), faded: !fresh || dimmed)
                    HStack(spacing: 5) {
                        Image(systemName: CompanionAppearance.symbol(sensor))
                            .font(.system(size: diameter * 0.11, weight: .regular))
                            .symbolRenderingMode(.monochrome)
                            .accessibilityHidden(true)
                    }
                    .foregroundStyle(snapshot.warning(for: sensor, at: date) && !dimmed ? CompanionAppearance.needle : CompanionAppearance.amber)
                    .opacity(dimmed ? 0.65 : (!fresh ? 0.5 : 1))
                    .offset(y: -diameter * 0.14)
                    Text(sensor.title.uppercased()).font(.system(size: 8, weight: .medium)).tracking(1)
                        .foregroundStyle(.secondary).offset(y: diameter * 0.10)
                    VStack(spacing: 1) {
                        Text(snapshot.formatted(sensor))
                            .font(.system(size: diameter * 0.20, weight: .medium).width(.condensed))
                            .monospacedDigit().minimumScaleFactor(0.6).lineLimit(1)
                        Text(sensor.unit).font(.system(size: 10, weight: .medium)).tracking(1)
                    }
                    .foregroundStyle(snapshot.warning(for: sensor, at: date) && !dimmed ? CompanionAppearance.needle : CompanionAppearance.amber)
                    .opacity(dimmed ? 0.65 : (!fresh ? 0.5 : 1))
                    .offset(y: diameter * 0.27)
                }
                .frame(width: diameter, height: diameter)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(sensor.title), \(snapshot.formatted(sensor)) \(sensor.unit)")
                .accessibilityValue(snapshot.status(at: date))
                HStack(spacing: 3) {
                    if snapshot.sessionID != nil {
                        Circle().fill(fresh && !dimmed ? CompanionAppearance.needle : .gray).frame(width: 3, height: 3)
                    }
                    if !fresh, let received = snapshot.receivedAt {
                        Image(systemName: "clock")
                        Text(received, style: .relative).monospacedDigit()
                    } else if sensor == .rpm && snapshot.value(for: .rpm) == 2550 {
                        Text("LECTURA SATURADA")
                    } else { Text(snapshot.status(at: date)) }
                }.font(.system(size: 9)).foregroundStyle(.secondary).lineLimit(1)
            }
            .fixedSize(horizontal: false, vertical: true)
            .frame(width: geometry.size.width, height: geometry.size.height)
            .offset(y: -6)
        }
        .accessibilityIdentifier("watchGauge-\(sensor.rawValue)")
    }
}

private struct WatchDial: View {
    let sensor: Sensor
    let value: Double?
    let faded: Bool
    var body: some View {
        Canvas { context, size in
            let c = CGPoint(x: size.width / 2, y: size.height / 2)
            let r = size.width * 0.47
            let range = CompanionAppearance.range(sensor)
            let major = sensor == .rpm ? 7 : 8
            func point(_ f: Double, _ radius: Double) -> CGPoint {
                let a = (-110 + f * 220) * .pi / 180
                return .init(x: c.x + sin(a) * radius, y: c.y - cos(a) * radius)
            }
            context.stroke(Path(ellipseIn: CGRect(x: c.x-r, y: c.y-r, width: r*2, height: r*2)),
                           with: .color(.white.opacity(0.09)), lineWidth: 1)
            for tick in 0...(major * 5) {
                let f = Double(tick) / Double(major * 5)
                let unavailable = sensor == .rpm && f * 7000 > 2550
                let main = tick.isMultiple(of: 5)
                let color = Color.white.opacity(unavailable ? 0.16 : (faded ? 0.36 : 0.86))
                var line = Path(); line.move(to: point(f, r*0.95)); line.addLine(to: point(f, r*(main ? 0.80 : 0.89)))
                context.stroke(line, with: .color(color), lineWidth: main ? 1.5 : 0.6)
                if main {
                    let raw = range.lowerBound + f*(range.upperBound-range.lowerBound)
                    let label = sensor == .rpm ? String(tick/5) : String(format: "%.0f", raw)
                    context.draw(Text(label).font(.system(size: size.width*0.077, weight: .medium).width(.condensed)).foregroundStyle(color), at: point(f, r*0.66))
                }
            }
            if let value {
                let f = CompanionAppearance.fraction(sensor, value: value)
                let a = (-110 + f*220) * .pi / 180
                let dx = cos(a) * 1.5, dy = sin(a) * 1.5
                let end = point(f, r*0.89)
                var needle = Path(); needle.move(to: CGPoint(x: c.x-dx, y: c.y-dy)); needle.addLine(to: end)
                needle.addLine(to: CGPoint(x: c.x+dx, y: c.y+dy)); needle.closeSubpath()
                context.fill(needle, with: .color(CompanionAppearance.needle.opacity(faded ? 0.4 : 1)))
            }
            let hub = CGRect(x: c.x-7, y: c.y-7, width: 14, height: 14)
            if sensor == .rpm {
                context.draw(Text("SIN DATO").font(.system(size: size.width * 0.035, weight: .medium))
                    .foregroundStyle(.white.opacity(0.27)), at: CGPoint(x: c.x + r * 0.58, y: c.y + r * 0.12))
            }
            context.fill(Path(ellipseIn: hub), with: .color(Color(white: 0.055)))
            context.stroke(Path(ellipseIn: hub), with: .color(.white.opacity(0.13)), lineWidth: 0.5)
        }.accessibilityHidden(true)
    }
}
