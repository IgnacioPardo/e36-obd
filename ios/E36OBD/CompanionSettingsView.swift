import SwiftUI
import E36Core

struct CompanionSettingsView: View {
    @ObservedObject var coordinator: CompanionCoordinator
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            GarageCaption("03 / A SIMPLE VISTA")
            Toggle("Actividad en pantalla bloqueada", isOn: $coordinator.activitiesEnabled)
                .accessibilityIdentifier("liveActivitiesToggle")
            Picker("Instrumento principal", selection: $coordinator.primarySensor) {
                ForEach(Sensor.allCases) { Text($0.title).tag($0) }
            }.accessibilityIdentifier("liveActivitySensor")
            Text(coordinator.activityStatus).font(.caption).foregroundStyle(ClusterTheme.muted)
                .accessibilityIdentifier("liveActivityStatus")
            DisclosureGroup("Apple Watch") {
                VStack(alignment: .leading, spacing: 10) {
                    Text(coordinator.watchStatus)
                    Text("Instalá E36 desde Watch en el iPhone. Girá la corona para cambiar de instrumento.")
                    Text("Agregá Instrumento E36 a una complicación y elegí el sensor. La esfera muestra la última lectura con su antigüedad; abrí E36 en el reloj para ver los indicadores en vivo.")
                }.font(.footnote).foregroundStyle(ClusterTheme.muted).padding(.top, 10)
            }
        }.font(.subheadline)
    }
}
