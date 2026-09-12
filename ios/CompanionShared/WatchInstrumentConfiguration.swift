import AppIntents
import E36Core

enum WatchInstrumentChoice: String, AppEnum {
    case rpm, load, coolant, battery, intake
    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "Instrumento")
    static let caseDisplayRepresentations: [Self: DisplayRepresentation] = [
        .rpm: "Régimen", .load: "Carga", .coolant: "Refrigerante", .battery: "Batería", .intake: "Admisión"
    ]
    var sensor: Sensor { Sensor(rawValue: rawValue) ?? .coolant }
}
enum WatchSourceChoice: String, AppEnum {
    case reader, demo
    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "Origen")
    static let caseDisplayRepresentations: [Self: DisplayRepresentation] = [.reader: "ESP32 / iPhone", .demo: "Simulación"]
    var source: WidgetSource { self == .reader ? .reader : .demo }
}
struct E36WatchConfiguration: WidgetConfigurationIntent {
    static let title: LocalizedStringResource = "Instrumento E36"
    static let description = IntentDescription("Elegí la última lectura que querés ver en la esfera.")
    @Parameter(title: "Instrumento", default: .coolant) var instrument: WatchInstrumentChoice
    @Parameter(title: "Origen", default: .reader) var source: WatchSourceChoice
}
