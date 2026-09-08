import AppIntents
import WidgetKit
import E36Core

struct RefreshE36WidgetIntent: AppIntent {
    static let title: LocalizedStringResource = "Actualizar lectura"
    static let description = IntentDescription("Muestra la última lectura compartida por E36. No inicia Bluetooth ni la captura.")
    static let openAppWhenRun = false
    static let isDiscoverable = false
    func perform() async throws -> some IntentResult {
        WidgetCenter.shared.reloadTimelines(ofKind: WidgetSnapshotStore.kind)
        return .result()
    }
}
