import SwiftUI
import E36Core

enum CompanionAppearance {
    static let amber = Color(red: 1, green: 0.66, blue: 0.30)
    static let needle = Color(red: 1, green: 0.26, blue: 0.14)
    static func symbol(_ sensor: Sensor) -> String {
        switch sensor {
        case .rpm: "tachometer"
        case .load: "waveform.path"
        case .coolant: "thermometer.and.liquid.waves"
        case .battery: "battery.100percent"
        case .intake: "wind"
        }
    }
    static func range(_ sensor: Sensor) -> ClosedRange<Double> {
        switch sensor {
        case .rpm: 0...7000
        case .load: 0...16
        case .coolant: 40...120
        case .battery: 8...16
        case .intake: 0...100
        }
    }
    static func fraction(_ sensor: Sensor, value: Double?) -> Double {
        let range = range(sensor)
        let value = min(max(value ?? range.lowerBound, range.lowerBound), sensor == .rpm ? 2550 : range.upperBound)
        return (value - range.lowerBound) / (range.upperBound - range.lowerBound)
    }
}
