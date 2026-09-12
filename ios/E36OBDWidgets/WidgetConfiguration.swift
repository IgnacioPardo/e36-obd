import AppIntents
import E36Core

enum InstrumentChoice: String, AppEnum {
    case rpm, load, coolant, battery, intake
    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "Instrumento")
    static let caseDisplayRepresentations: [InstrumentChoice: DisplayRepresentation] = [
        .rpm: "Régimen", .load: "Carga", .coolant: "Refrigerante", .battery: "Batería", .intake: "Admisión"
    ]
    var sensor: Sensor { Sensor(rawValue: rawValue) ?? .coolant }
}
enum SourceChoice: String, AppEnum {
    case reader, demo
    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "Origen")
    static let caseDisplayRepresentations: [SourceChoice: DisplayRepresentation] = [.reader: "ESP32", .demo: "Simulación"]
    var source: WidgetSource { self == .reader ? .reader : .demo }
}
struct E36WidgetConfiguration: WidgetConfigurationIntent {
    static let title: LocalizedStringResource = "Instrumento E36"
    static let description = IntentDescription("Elegí un sensor para la pantalla de inicio, StandBy o CarPlay.")
    @Parameter(title: "Instrumento", default: .coolant) var instrument: InstrumentChoice
    @Parameter(title: "Origen", default: .reader) var source: SourceChoice
}
