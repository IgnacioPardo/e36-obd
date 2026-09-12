import SwiftUI
import WidgetKit
import E36Core

enum E36WidgetKinds {
    static let garage = "E36Garage"
    static let obc = "E36OBC"
    static let all = [WidgetSnapshotStore.kind, garage, obc]
    static func reload() {
        for kind in all { WidgetCenter.shared.reloadTimelines(ofKind: kind) }
    }
}

/// Dated observations shared by all three designs. The widget never owns BLE.
struct E36CollectionFace: View {
    enum Style { case garage, obc }
    let style: Style
    let snapshot: WidgetSnapshot
    let sensor: Sensor
    let date: Date
    var previewFamily: WidgetFamily? = nil
    @Environment(\.widgetFamily) private var widgetFamily
    @Environment(\.widgetRenderingMode) private var renderingMode
    @Environment(\.showsWidgetContainerBackground) private var showsBackground
    private var family: WidgetFamily { previewFamily ?? widgetFamily }
    private var small: Bool { family == .systemSmall }
    private var large: Bool { family == .systemLarge }
    private var amber: Color { renderingMode == .fullColor ? CompanionAppearance.amber : .primary }
    private var ink: Color { renderingMode == .fullColor ? Color(white: 0.91) : .primary }
    private var secondary: Color { renderingMode == .fullColor ? Color(white: 0.57) : .secondary }
    private var otherSensors: [Sensor] { Sensor.allCases.filter { $0 != sensor } }

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text(style == .garage ? "BMW 316i" : "E36 / OBC")
                    .font(.system(size: large ? 15 : 12, weight: .medium).width(.expanded)).tracking(1)
                Spacer(minLength: 4)
                Image(systemName: style == .garage ? "car.side" : "waveform.path")
                    .font(.system(size: 11)).foregroundStyle(amber).accessibilityHidden(true)
            }.foregroundStyle(ink).lineLimit(1).minimumScaleFactor(0.8)
            if style == .garage { garage }
            else { obc }
            observation
        }
        .padding(large ? 18 : (showsBackground ? 14 : 10))
        .foregroundStyle(ink)
        .widgetURL(URL(string: style == .garage ? "e36://vehicle" : "e36://dashboard"))
    }

    private var garage: some View {
        Group {
            if large {
                largeGarage
            } else if small {
                VStack(spacing: 0) {
                    car.frame(maxHeight: .infinity)
                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        reading(sensor, size: 27)
                        Spacer(minLength: 0)
                        Image(systemName: CompanionAppearance.symbol(sensor)).font(.system(size: 15)).foregroundStyle(secondary)
                    }.padding(.bottom, 5)
                }
            } else {
                HStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 0) {
                        car.frame(maxHeight: .infinity)
                        Text("295 / SAMOABLAU METALLIC")
                            .font(.system(size: 7, weight: .medium, design: .monospaced)).tracking(1.4)
                            .foregroundStyle(secondary).padding(.bottom, 7)
                    }.frame(maxWidth: .infinity)
                    VStack(alignment: .leading, spacing: 8) {
                        Label(sensor.title, systemImage: CompanionAppearance.symbol(sensor))
                            .font(.system(size: 10)).foregroundStyle(secondary)
                        reading(sensor, size: 34)
                        Rectangle().fill(secondary.opacity(0.25)).frame(height: 0.5)
                        let secondarySensor: Sensor = sensor == .coolant ? .battery : .coolant
                        HStack(spacing: 5) {
                            Image(systemName: CompanionAppearance.symbol(secondarySensor)).font(.system(size: 11)).foregroundStyle(secondary)
                            reading(secondarySensor, size: 16)
                        }
                    }.frame(width: 105, alignment: .leading).padding(.leading, 2)
                }.frame(maxHeight: .infinity)
            }
        }
    }

    private var largeGarage: some View {
        VStack(spacing: 10) {
            car.frame(maxWidth: .infinity, maxHeight: .infinity)
            HStack {
                Text("295 / SAMOABLAU METALLIC")
                    .font(.system(size: 8, weight: .medium, design: .monospaced)).tracking(1.2)
                Spacer(minLength: 4)
                Text("1994").font(.system(size: 9, weight: .medium, design: .monospaced))
            }.foregroundStyle(secondary).lineLimit(1).minimumScaleFactor(0.8)
            Rectangle().fill(secondary.opacity(0.25)).frame(height: 0.5)
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 9) {
                    Label(sensor.title, systemImage: CompanionAppearance.symbol(sensor))
                        .font(.system(size: 10)).foregroundStyle(secondary)
                    reading(sensor, size: 42)
                }.frame(maxWidth: .infinity, alignment: .leading)
                Rectangle().fill(secondary.opacity(0.25)).frame(width: 0.5, height: 70)
                LazyVGrid(columns: [.init(.flexible(), alignment: .leading), .init(.flexible(), alignment: .leading)], alignment: .leading, spacing: 16) {
                    ForEach(otherSensors) { compactMetric($0, labelled: true) }
                }.frame(maxWidth: .infinity)
            }.frame(height: 94)
        }.padding(.vertical, 10)
    }

    private var car: some View {
        Image("WidgetCar")
            .resizable()
            .widgetAccentedRenderingMode(.fullColor)
            .scaledToFit()
            .accessibilityLabel("BMW E36 316i, 295 · Samoablau Metallic")
    }

    private var obc: some View {
        Group {
            if large {
                largeOBC
            } else if small {
                VStack(alignment: .leading, spacing: 7) {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Image(systemName: CompanionAppearance.symbol(sensor)).font(.system(size: 16)).foregroundStyle(amber)
                        reading(sensor, size: 30)
                    }
                    LazyVGrid(columns: [.init(.flexible(), alignment: .leading), .init(.flexible(), alignment: .leading)], alignment: .leading, spacing: 8) {
                        ForEach(otherSensors) { compactMetric($0) }
                    }
                }.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            } else {
                HStack(spacing: 18) {
                    VStack(alignment: .leading, spacing: 5) {
                        Image(systemName: CompanionAppearance.symbol(sensor)).font(.system(size: 22, weight: .light)).foregroundStyle(amber)
                        reading(sensor, size: 38)
                        Text(sensor.title).font(.system(size: 10)).foregroundStyle(secondary)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    Rectangle().fill(secondary.opacity(0.25)).frame(width: 0.5).padding(.vertical, 17)
                    LazyVGrid(columns: [.init(.flexible(), alignment: .leading), .init(.flexible(), alignment: .leading)], alignment: .leading, spacing: 16) {
                        ForEach(otherSensors) { compactMetric($0, labelled: true) }
                    }.frame(maxWidth: .infinity)
                }.frame(maxHeight: .infinity)
            }
        }
    }

    private var largeOBC: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 16) {
                Image(systemName: CompanionAppearance.symbol(sensor))
                    .font(.system(size: 32, weight: .light)).foregroundStyle(amber)
                VStack(alignment: .leading, spacing: 6) {
                    Text(sensor.title).font(.system(size: 12)).foregroundStyle(secondary)
                    reading(sensor, size: 66)
                }
            }.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            Rectangle().fill(secondary.opacity(0.25)).frame(height: 0.5)
            LazyVGrid(columns: [.init(.flexible(), alignment: .leading), .init(.flexible(), alignment: .leading)], alignment: .leading, spacing: 22) {
                ForEach(otherSensors) { sensor in
                    VStack(alignment: .leading, spacing: 8) {
                        Label(sensor.title, systemImage: CompanionAppearance.symbol(sensor))
                            .font(.system(size: 11)).foregroundStyle(secondary)
                        reading(sensor, size: 30)
                    }
                }
            }
        }.padding(.vertical, 18)
    }

    private func compactMetric(_ sensor: Sensor, labelled: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if labelled { Text(sensor.title).font(.system(size: 9)).foregroundStyle(secondary) }
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Image(systemName: CompanionAppearance.symbol(sensor)).font(.system(size: 10)).foregroundStyle(secondary)
                reading(sensor, size: small ? 14 : 17)
            }
        }
    }

    private func reading(_ sensor: Sensor, size: CGFloat) -> some View {
        let value = snapshot.value(for: sensor)
        let formatted = sensor == .rpm && (value ?? 0) >= 2550 ? "2550+" : sensor.formatted(value)
        return HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text(formatted).font(.system(size: size, weight: .medium).width(.condensed)).monospacedDigit()
            Text(sensor.unit).font(.system(size: size > 20 ? 10 : 8, weight: .medium))
        }
        .lineLimit(1).minimumScaleFactor(0.7)
        .foregroundStyle(snapshot.hasWarning(for: sensor) && !snapshot.isOld(at: date) ? CompanionAppearance.needle : amber)
        .opacity(snapshot.isOld(at: date) && value != nil ? 0.6 : 1)
        .widgetAccentable()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(sensor.title), última lectura: \(formatted) \(sensor.unit)")
    }

    private var observation: some View {
        HStack(spacing: 4) {
            Image(systemName: "clock").font(.system(size: 8))
            if let received = snapshot.receivedAt {
                Text(snapshot.observationLabel(at: date))
                Text(received, style: .relative).monospacedDigit()
            } else { Text("Sin lecturas") }
            Spacer(minLength: 0)
        }.font(.system(size: 9)).foregroundStyle(secondary)
            .lineLimit(1).minimumScaleFactor(0.8)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(snapshot.receivedAt.map { "Lectura recibida \($0.formatted(date: .abbreviated, time: .standard))" } ?? "Sin lecturas")
    }
}
