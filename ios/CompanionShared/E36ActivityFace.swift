#if os(iOS)
import SwiftUI
import WidgetKit
import E36Core

struct E36ActivityFace: View {
    let snapshot: CompanionSnapshot
    let stale: Bool
    let small: Bool
    var island = false
    @Environment(\.isLuminanceReduced) private var dimmed
    private var active: Bool { snapshot.isFresh(at: .now) && !stale && !dimmed }
    private var stateLabel: String {
        if snapshot.observation.capture == .stopped { return "Finalizada" }
        if snapshot.observation.capture == .interrupted { return "Interrumpida" }
        if snapshot.observation.telemetry?.validity == .unpopulated { return "Motor apagado" }
        if snapshot.observation.capture == .paused { return snapshot.status(at: .now) }
        if active, let alert = snapshot.observation.alerts.first { return alert.title }
        // The system can defer rendering a stale-date transition. Describe the
        // dated observation rather than leaving an "En vivo" claim on a snapshot.
        if stale || !active { return "Última lectura" }
        return "\(snapshot.sampleCount.formatted()) muestras"
    }
    var body: some View {
        Group {
            if small { smallFace }
            else { fullFace }
        }
        .foregroundStyle(.white)
        .padding(small ? 10 : (island ? 4 : 16))
        .background(.black.opacity(dimmed ? 1 : 0.96))
    }
    private var identity: some View {
        HStack(spacing: 5) {
            Text("E36").font(.system(size: small ? 12 : 14, weight: .bold).width(.condensed)).tracking(1.5)
            Spacer(minLength: 0)
            Circle().fill(active ? CompanionAppearance.needle : .gray).frame(width: 4, height: 4)
            elapsed.font(.system(size: small ? 10 : 12, weight: .medium, design: .monospaced)).foregroundStyle(.secondary)
                .multilineTextAlignment(.trailing).lineLimit(1)
                .frame(width: small ? 44 : 68, alignment: .trailing)
        }
    }
    private var fullFace: some View {
        VStack(alignment: .leading, spacing: island ? 5 : 10) {
            identity
            HStack(alignment: .center, spacing: 18) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(snapshot.primarySensor.title.uppercased()).font(.system(size: 9, weight: .medium)).tracking(1).foregroundStyle(.secondary)
                    reading(snapshot.primarySensor, size: island ? 30 : 38)
                }.frame(maxWidth: .infinity, alignment: .leading)
                Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: island ? 4 : 8) {
                    let others = Sensor.allCases.filter { $0 != snapshot.primarySensor }
                    ForEach(0..<2) { row in
                        GridRow {
                            ForEach(Array(others[(row*2)..<(row*2+2)])) { sensor in
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(sensor.title).font(.system(size: 9)).foregroundStyle(.secondary).lineLimit(1)
                                    reading(sensor, size: island ? 15 : 18)
                                }
                            }
                        }
                    }
                }
            }
            HStack(spacing: 5) {
                if active && !snapshot.observation.alerts.isEmpty {
                    Image(systemName: "exclamationmark.circle.fill").foregroundStyle(CompanionAppearance.needle)
                }
                Text(stateLabel)
                Spacer(minLength: 2)
                if let received = snapshot.receivedAt {
                    Image(systemName: "clock")
                    Text(received, style: .timer).monospacedDigit()
                }
            }.font(.system(size: 10)).foregroundStyle(.secondary).lineLimit(1)
        }
    }
    private var smallFace: some View {
        VStack(alignment: .leading, spacing: 4) {
            identity
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                reading(snapshot.primarySensor, size: 27)
                Spacer(minLength: 0)
                Image(systemName: CompanionAppearance.symbol(snapshot.primarySensor)).font(.body).foregroundStyle(.secondary)
            }
            HStack {
                Text(stateLabel).lineLimit(1)
                Spacer(minLength: 1)
                if let date = snapshot.receivedAt { Text(date, style: .timer).monospacedDigit() }
            }.font(.system(size: 9)).foregroundStyle(.secondary)
        }
    }
    private func reading(_ sensor: Sensor, size: Double) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text(snapshot.formatted(sensor)).font(.system(size: size, weight: .semibold).width(.condensed)).monospacedDigit()
                .minimumScaleFactor(0.65).lineLimit(1)
            Text(sensor.unit).font(.system(size: small ? 10 : 11)).foregroundStyle(.secondary)
        }
        .foregroundStyle(active && snapshot.observation.hasWarning(for: sensor) && snapshot.value(for: sensor) != nil ? CompanionAppearance.needle : CompanionAppearance.amber)
        .opacity(active ? 1 : 0.6)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(sensor.title), \(snapshot.formatted(sensor)) \(sensor.unit)")
    }
    private var elapsed: Text {
        if let start = snapshot.startedAt {
            if snapshot.observation.capture == .stopped || snapshot.observation.capture == .interrupted {
                Text(Duration.seconds(max(0, snapshot.observation.updatedAt.timeIntervalSince(start))).formatted(.time(pattern: .minuteSecond)))
            } else { Text(timerInterval: start...Date.distantFuture, countsDown: false) }
        } else { Text("—") }
    }
}
#endif
