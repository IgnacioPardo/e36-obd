import SwiftUI
import Charts
import E36Core

struct SessionsView: View {
    @ObservedObject var model: AppModel
    @Environment(\.dynamicTypeSize) private var textSize
    @State private var selected: DriveSession?
    var body: some View {
        Group {
            if let selected {
                SessionDetailView(session: selected, store: model.store) { self.selected = nil }
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            Text(model.sessions.isEmpty ? "Sin sesiones" : "\(model.sessions.count) \(model.sessions.count == 1 ? "captura" : "capturas")")
                                .font(.footnote).foregroundStyle(ClusterTheme.muted).accessibilityIdentifier("sessionCount")
                            Spacer()
                            Button { model.refreshSessions() } label: {
                                Image(systemName: "arrow.clockwise").font(.system(size: 18)).frame(width: 44, height: 44)
                            }.accessibilityLabel("Actualizar sesiones")
                        }
                        if model.sessions.isEmpty {
                            Text("Iniciá En vivo para grabar.").font(.footnote).foregroundStyle(ClusterTheme.muted)
                        }
                        ForEach(model.sessions) { session in
                            Button { selected = session } label: {
                                VStack(alignment: .leading, spacing: 6) {
                                    rowLayout {
                                        Text(session.startedAt, format: .dateTime.day().month().hour().minute())
                                        if !textSize.isAccessibilitySize { Spacer() }
                                        if session.isDemo { Text("DEMO").font(.system(size: 9, weight: .semibold, design: .monospaced)).foregroundStyle(ClusterTheme.lcd) }
                                    }.font(.headline)
                                    Text("\(duration(session.elapsed)) · \(session.sampleCount) muestras · \(session.eventCount) eventos")
                                        .font(.system(.caption, design: .monospaced))
                                    Text(status(session)).font(.caption).foregroundStyle(session.status == .interrupted ? ClusterTheme.danger : ClusterTheme.muted)
                                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8).contentShape(Rectangle())
                            }.buttonStyle(.plain).accessibilityIdentifier("sessionRow")
                            Divider()
                        }
                    }.padding(.vertical, 4)
                }
            }
        }.foregroundStyle(ClusterTheme.ink).onAppear { model.refreshSessions() }
    }
    private var rowLayout: AnyLayout {
        textSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 8)) : AnyLayout(HStackLayout())
    }
    private func status(_ session: DriveSession) -> String {
        switch session.status { case .recording: "Grabando"; case .completed: "Finalizada"; case .interrupted: "Interrumpida" }
    }
}

private struct ShareFiles: Identifiable { let id = UUID(); let urls: [URL] }
struct SessionDetailView: View {
    let session: DriveSession
    let store: SessionStore?
    let back: () -> Void
    @State private var samples: [RecordedSample] = []
    @State private var events: [SessionEvent] = []
    @State private var series: [Sensor: [GraphPoint]] = [:]
    @State private var cursor: Double?
    @State private var error: String?
    @State private var loading = true
    @State private var exporting = false
    @State private var share: ShareFiles?
    private var end: Double { max(samples.last?.elapsed ?? 0, session.elapsed, 1) }
    private var alertIDs: Set<Int64> { Set(events.filter { $0.kind == .alertStarted }.compactMap(\.sampleID)) }
    private var focused: RecordedSample? {
        guard let cursor, let nearest = GraphSeries.nearest(samples, elapsed: cursor), abs(nearest.elapsed - cursor) <= 1 else { return nil }
        return nearest
    }
    var body: some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 8) {
                    Button(action: back) {
                        Image(systemName: "chevron.left").frame(width: 44, height: 44)
                    }.accessibilityLabel("Volver a sesiones")
                    Text(session.startedAt, format: .dateTime.day().month().hour().minute())
                        .font(.subheadline).foregroundStyle(ClusterTheme.ink).lineLimit(2)
                    Spacer(minLength: 0)
                    Button { Task { await export() } } label: {
                        Image(systemName: "square.and.arrow.up").frame(width: 44, height: 44)
                    }.disabled(exporting || loading).accessibilityIdentifier("exportSessionButton").accessibilityLabel("Exportar CSV")
                }.id("charts")
                HStack {
                    if session.isDemo { Text("DEMO").foregroundStyle(ClusterTheme.lcd) }
                    Text(cursor.map(duration) ?? duration(session.elapsed)).monospacedDigit()
                    Spacer()
                    Menu {
                        ForEach(events.filter { $0.kind == .alertStarted }) { event in
                            Button {
                                if let id = event.sampleID, let row = samples.first(where: { $0.id == id }) { cursor = row.elapsed }
                                withAnimation { proxy.scrollTo("charts", anchor: .top) }
                            } label: { Text(event.message) }
                        }
                    } label: { Label("Avisos", systemImage: "waveform.path") }
                    .disabled(!events.contains { $0.kind == .alertStarted })
                }.font(.caption).foregroundStyle(ClusterTheme.muted).frame(height: 24)
                if loading { ProgressView() }
                if let error { Text(error).font(.footnote).foregroundStyle(ClusterTheme.danger) }
                ForEach(Sensor.allCases) { sensor in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(sensor.title).font(.subheadline).foregroundStyle(ClusterTheme.ink)
                            Spacer()
                            if let value = focused?.telemetry[sensor], focused?.telemetry.validity == .populated {
                                Text("\(sensor.formatted(value)) \(sensor.unit)").monospacedDigit()
                            }
                        }
                        chart(sensor)
                    }
                }
                Text("Eventos").font(.headline).padding(.top, 12)
                ForEach(events.filter { [.alertStarted, .alertEnded, .gap, .configuration, .recording, .engineState].contains($0.kind) }) { event in
                    Button {
                        if let id = event.sampleID, let row = samples.first(where: { $0.id == id }) { cursor = row.elapsed }
                        else { cursor = max(0, event.timestamp.timeIntervalSince(session.startedAt)) }
                        withAnimation { proxy.scrollTo("charts", anchor: .top) }
                    } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(event.timestamp, format: .dateTime.hour().minute().second()).font(.caption2).foregroundStyle(ClusterTheme.muted)
                            Text(event.message).font(.footnote).foregroundStyle(event.kind == .alertStarted ? ClusterTheme.lcd : ClusterTheme.ink)
                        }.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading).padding(.vertical, 5).contentShape(Rectangle())
                    }.buttonStyle(.plain)
                }
            }.padding(.vertical, 4)
        }
        .task(id: session.id) { await load() }
        .sheet(item: $share) { ShareSheet(urls: $0.urls) }
        }
    }
    private func chart(_ sensor: Sensor) -> some View {
        let points = series[sensor] ?? []
        return Chart {
            ForEach(points) { point in
                LineMark(x: .value("Tiempo", point.elapsed), y: .value(sensor.unit, point.value), series: .value("Tramo", point.segment))
                    .foregroundStyle(ClusterTheme.ink).lineStyle(StrokeStyle(lineWidth: 1.4))
                if alertIDs.contains(point.id) {
                    PointMark(x: .value("Tiempo", point.elapsed), y: .value(sensor.unit, point.value))
                        .foregroundStyle(ClusterTheme.lcd).symbolSize(28)
                }
            }
            if let cursor {
                RuleMark(x: .value("Cursor", cursor)).foregroundStyle(ClusterTheme.muted).lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
            }
        }
        .chartXScale(domain: 0...end).chartYScale(domain: yDomain(sensor, points: points))
        .chartYAxisLabel(sensor.unit)
        .chartXSelection(value: $cursor)
        .chartXAxis { AxisMarks(values: .automatic(desiredCount: 4)) }
        .chartYAxis {
            AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine(); AxisTick()
                AxisValueLabel {
                    if let number = value.as(Double.self) {
                        Text(number, format: .number.precision(.fractionLength(0...1)))
                            .font(.caption2).monospacedDigit().lineLimit(1).minimumScaleFactor(0.5).frame(width: 44, alignment: .trailing)
                    }
                }
            }
        }
        .frame(height: 120)
        .padding(.trailing, 12)
        .overlay { if points.isEmpty { Text("Sin datos").font(.caption).foregroundStyle(ClusterTheme.muted) } }
        .accessibilityLabel("Gráfico de \(sensor.title)")
        .accessibilityIdentifier("chart-\(sensor.rawValue)")
    }
    private func yDomain(_ sensor: Sensor, points: [GraphPoint]) -> ClosedRange<Double> {
        let values = points.map(\.value)
        let minimumSpan: Double = switch sensor { case .rpm: 300; case .load, .battery: 2; default: 10 }
        let low = values.min() ?? 0, high = values.max() ?? minimumSpan
        let span = max(high - low, minimumSpan), middle = (low + high) / 2
        return (middle - span * 0.6)...(middle + span * 0.6)
    }
    private func load() async {
        loading = true
        do {
            samples = try await store?.samples(sessionID: session.id) ?? []
            events = try await store?.events(sessionID: session.id) ?? []
            let rows = samples, preserve = Set(events.compactMap(\.sampleID))
            series = await Task.detached {
                Dictionary(uniqueKeysWithValues: Sensor.allCases.map { ($0, GraphSeries.points(rows, sensor: $0, preserving: preserve)) })
            }.value
        } catch { self.error = error.localizedDescription }
        loading = false
    }
    private func export() async {
        exporting = true; defer { exporting = false }
        do {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent("E36Exports/\(UUID().uuidString)")
            if let urls = try await store?.export(sessionID: session.id, to: directory) { share = ShareFiles(urls: urls) }
        } catch { self.error = error.localizedDescription }
    }
}
struct ShareSheet: UIViewControllerRepresentable {
    let urls: [URL]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: urls, applicationActivities: nil) }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
