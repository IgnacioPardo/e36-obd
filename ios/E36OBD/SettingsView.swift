import SwiftUI
import E36Core

struct SettingsView: View {
    @ObservedObject var model: AppModel
    @Environment(\.dynamicTypeSize) private var textSize
    @State private var draft = AlertSettings()
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 18) {
                    GarageCaption("01 / UMBRALES")
                    threshold("Refrigerante", value: $draft.coolantHigh, range: 80...130, unit: "°C", step: 1)
                    threshold("Admisión", value: $draft.intakeHigh, range: 30...100, unit: "°C", step: 1)
                    threshold("Carga baja", value: $draft.lowLoad, range: 0.2...3, unit: "ms", step: 0.05)
                    DisclosureGroup("Banda de ralentí") {
                        VStack(spacing: 16) {
                            threshold("Mínimo", value: $draft.idleMinimum, range: 400...1000, unit: "rpm", step: 50)
                            threshold("Máximo", value: $draft.idleMaximum, range: 1050...1800, unit: "rpm", step: 50)
                        }.padding(.top, 12)
                    }.font(.subheadline)
                    Text("Valores personales, no límites de BMW.").font(.caption).foregroundStyle(ClusterTheme.muted)
                }
                GarageRule()
                VStack(alignment: .leading, spacing: 14) {
                    GarageCaption("02 / AVISOS")
                    Toggle("Sonido", isOn: $draft.sound)
                    Toggle("Hápticos en la app", isOn: $draft.haptics)
                }.font(.subheadline)
                Button(draft == model.settings ? "Guardado" : "Guardar cambios") { model.saveSettings(draft) }
                    .buttonStyle(PhysicalButton(selected: true)).disabled(!draft.isValid || draft == model.settings)
                    .opacity(draft == model.settings ? 0.45 : 1).accessibilityIdentifier("saveSettingsButton")
                DisclosureGroup("Notificaciones") {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(model.notificationStatus).font(.footnote).foregroundStyle(ClusterTheme.muted)
                        Button("Habilitar") { model.requestNotifications() }.buttonStyle(PhysicalButton())
                        Button("Ajustes del iPhone") {
                            if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                        }.buttonStyle(PhysicalButton())
                        Text("Con la pantalla bloqueada, el iPhone controla el sonido y la vibración.").font(.caption).foregroundStyle(ClusterTheme.muted)
                    }.padding(.top, 12)
                }.font(.subheadline)
                DisclosureGroup("Ayuda") {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("En vivo graba automáticamente. Detener finaliza la sesión.")
                        Text("Bloquear el teléfono permite seguir capturando. Cerrar la app desde el selector interrumpe la grabación.")
                        Text("Carga: aviso inmediato; rearme a +0,3 ms durante 2 s. Temperaturas: aviso tras 2 s; rearme a −3 °C durante 5 s.")
                    }.font(.footnote).foregroundStyle(ClusterTheme.muted).padding(.top, 12)
                }.font(.subheadline)
                GarageRule()
                CompanionSettingsView(coordinator: model.companion)
                DisclosureGroup("Widget y CarPlay") {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Agregá Instrumento E36 y elegí el sensor. CarPlay requiere iOS 26 o posterior.")
                        Text("Ajustes del iPhone → General → CarPlay → tu auto → Widgets.")
                        Text("Muestra la última lectura con su antigüedad. El iPhone decide cuándo actualizar; la flecha solicita una lectura más reciente de la app.")
                        if let error = model.widgetError { Text(error).foregroundStyle(ClusterTheme.danger) }
                    }.font(.footnote).foregroundStyle(ClusterTheme.muted).padding(.top, 12)
                }.font(.subheadline)
            }.foregroundStyle(ClusterTheme.ink).padding(.vertical, 4)
        }.onAppear { draft = model.settings }
    }
    private func threshold(_ title: String, value: Binding<Double>, range: ClosedRange<Double>, unit: String, step: Double) -> some View {
        let labels = textSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4)) : AnyLayout(HStackLayout())
        return VStack(alignment: .leading, spacing: 6) {
            labels {
                Text(title).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                if !textSize.isAccessibilitySize { Spacer() }
                Text("\(value.wrappedValue, specifier: unit == "ms" ? "%.2f" : "%.0f") \(unit)")
                    .font(.system(.subheadline, design: .monospaced)).foregroundStyle(ClusterTheme.lcd)
                    .fixedSize(horizontal: true, vertical: false)
            }.frame(maxWidth: .infinity, alignment: .leading)
            Slider(value: value, in: range, step: step).accessibilityLabel(title)
        }
    }
}
