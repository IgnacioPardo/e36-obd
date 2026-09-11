import SwiftUI
import RealityKit
import Metal
import OSLog

#if DEBUG
/// Developer-only matched-camera review; the product always opens the dashboard.
struct VehicleReferenceReview: View {
    static var preset: String? {
        ProcessInfo.processInfo.arguments.first { $0.hasPrefix("--vehicle-review=") }?
            .split(separator: "=").last.map(String.init)
    }
    static var requested: Bool { preset != nil }
    @State private var camera = VehicleCameraPose()
    var body: some View {
        VehicleSceneView(camera: $camera)
            .aspectRatio(0.75, contentMode: .fit)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(ClusterTheme.background)
            .ignoresSafeArea().statusBarHidden()
    }
}
#endif

struct VehicleCameraPose: Equatable {
    var azimuth: Float = 0.58
    var elevation: Float = 0.145
    var zoom: Float = 1
}

/// The scene owns no telemetry, Bluetooth, storage, or recurring app timer.
struct VehicleSceneView: UIViewRepresentable {
    @Binding var camera: VehicleCameraPose
    @Environment(\.scenePhase) private var scenePhase

    func makeUIView(context: Context) -> VehicleSceneHost {
        let view = VehicleSceneHost(frame: .zero)
        view.cameraChanged = { camera = $0 }
        view.setCamera(camera)
        return view
    }

    func updateUIView(_ view: VehicleSceneHost, context: Context) {
        view.setCamera(camera)
        view.setActive(scenePhase == .active)
    }

    static func dismantleUIView(_ view: VehicleSceneHost, coordinator: ()) {
        view.stop()
    }
}

@MainActor
private final class VehicleSceneAssets {
    private struct LightingManifest: Decodable {
        let type: String
        let diffuseEncoding: String
    }
    static let logger = Logger(subsystem: "com.ignaciopardo.e36obd", category: "VehicleMetal")
    private static var pending: Task<VehicleSceneAssets, Error>?
    let vehicle: Entity
    let environment: EnvironmentResource
    let library: any MTLLibrary
    let contactShadow: TextureResource

    private init() async throws {
        guard let device = MTLCreateSystemDefaultDevice(),
              let library = device.makeDefaultLibrary(),
              let modelURL = Bundle.main.url(forResource: "E36-316i", withExtension: "usdz", subdirectory: "VehicleScene") else {
            throw CocoaError(.fileNoSuchFile)
        }
        guard let manifestURL = Bundle.main.url(forResource: "bake-report", withExtension: "json", subdirectory: "VehicleScene") else {
            throw CocoaError(.fileNoSuchFile)
        }
        let manifest = try JSONDecoder().decode(LightingManifest.self, from: Data(contentsOf: manifestURL))
        guard manifest.type == "diffuse_radiance_RGB_ambient_visibility_A",
              manifest.diffuseEncoding == "sqrt(linear / 4)" else {
            throw CocoaError(.fileReadCorruptFile)
        }
        self.library = library
        let started = ContinuousClock.now
        vehicle = try await Entity(contentsOf: modelURL)
        Self.logger.info("Model decoded in \(String(describing: started.duration(to: .now)))")
        environment = try await EnvironmentResource(named: "VehicleScene/StudioEnvironment", in: .main)
        guard let shadowURL = Bundle.main.url(forResource: "ContactShadow", withExtension: "png", subdirectory: "VehicleScene") else {
            throw CocoaError(.fileNoSuchFile)
        }
        contactShadow = try await TextureResource(contentsOf: shadowURL)
        let shader = CustomMaterial.SurfaceShader(named: "e36MetallicPaint", in: library)
        let glassShader = CustomMaterial.SurfaceShader(named: "e36OpticalGlass", in: library)
        let opticalGeometry = CustomMaterial.GeometryModifier(named: "e36OpticalGeometry", in: library)
        var meshes = 0, painted = 0
        func finish(_ entity: Entity) throws {
            if var component = entity.components[ModelComponent.self] {
                meshes += 1
                component.materials = try component.materials.map { material in
                    let name = material.name ?? ""
                    let key = name.lowercased().replacingOccurrences(of: " ", with: "_")
                    if key == "wcwindow" || key == "material__58" || key == "_03___default" || key.contains("pressed_halogen") {
                        var glass = try CustomMaterial(surfaceShader: glassShader, geometryModifier: opticalGeometry, lightingModel: .unlit)
                        glass.blending = .transparent(opacity: .init(scale: 1))
                        // The fluted interface is the inward-facing back of the
                        // closed lens; culling it discards the moulded optics.
                        glass.faceCulling = .none
                        glass.custom.value.x = key == "wcwindow" ? 0.10 : 0.012
                        glass.custom.value.z = key.contains("fluted_inner") ? 1 : (key.contains("pressed_halogen") ? 2 : 0)
                        glass.custom.value.w = key == "wcwindow" ? 0.035 : 0.025
                        if let imported = material as? PhysicallyBasedMaterial,
                           let normalTexture = imported.normal.texture {
                            glass.normal = .init(texture: .init(normalTexture.resource))
                        }
                        return glass
                    }
                    if key.contains("glass") || key == "material__58" || key == "_03___default" { return material }
                    guard let imported = material as? PhysicallyBasedMaterial else { return material }
                    guard key == "car_body" || key.contains("painted_fog_intake_duct") else {
                        var finish = try CustomMaterial(from: imported, surfaceShader: .init(named: "e36VehicleSurface", in: library))
                        if key == "interior_dash_plastic" {
                            finish.baseColor.tint = UIColor(red: 0.1718, green: 0.1897, blue: 0.2098, alpha: 1)
                        }
                        finish.blending = .opaque
                        // USD Preview Surface drops Blender's zero specular
                        // control on the ink beneath this clear resin coat.
                        if key.contains("domed_body_badge_enamel") { finish.specular = .init(scale: 0) }
                        // Coloured lamp plastic has one dielectric interface,
                        // not automotive paint's extra clear lacquer layer.
                        // A second lobe bleaches the red/amber moulded lenses.
                        if key == "bmw_m3_e36_lights" || key == "pisca" {
                            finish.clearcoat = .init(scale: 0)
                            finish.roughness = .init(scale: 0.24)
                        }
                        return finish
                    }
                    var paint = try CustomMaterial(surfaceShader: shader, lightingModel: .clearcoat)
                    paint.baseColor = .init(tint: imported.baseColor.tint)
                    paint.metallic = .init(scale: imported.metallic.scale)
                    paint.roughness = .init(scale: imported.roughness.scale)
                    paint.clearcoat = 1.0
                    paint.clearcoatRoughness = 0.075
                    painted += 1
                    return paint
                }
                entity.components.set(component)
            }
            for child in entity.children { try finish(child) }
        }
        try finish(vehicle)
        guard meshes > 5, painted > 0 else { throw CocoaError(.fileReadCorruptFile) }
        Self.logger.info("Loaded native USDZ: \(meshes) mesh entities, \(painted) Metal paint materials, precompiled HDR, \(String(describing: started.duration(to: .now)))")
    }

    static func shared() async throws -> VehicleSceneAssets {
        if let pending { return try await pending.value }
        let task = Task { try await VehicleSceneAssets() }
        pending = task
        do { return try await task.value }
        catch { pending = nil; throw error }
    }
}

@MainActor
final class VehicleSceneHost: UIView, UIGestureRecognizerDelegate {
    private let renderer = VehicleMetalCanvas()
    private let anchor = Entity()
    private let lens = PerspectiveCamera()
    private let spinner = UIActivityIndicatorView(style: .medium)
    private let retry = UIButton(type: .system)
    private var loading: Task<Void, Never>?
    private var loaded = false
    private var presented = false
    private var active = true
    private var pose = VehicleCameraPose()
    private var panStart = VehicleCameraPose()
    private var pinchStart: Float = 1
    private var previousSize = CGSize.zero
    var cameraChanged: ((VehicleCameraPose) -> Void)?

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        isOpaque = false
        renderer.engine?.cameraSettings.colorBackground = .color(UIColor.clear.cgColor)
        addSubview(renderer)
        spinner.color = .lightGray
        spinner.hidesWhenStopped = true
        addSubview(spinner)
        retry.setTitle("Vista 3D no disponible · Reintentar", for: .normal)
        retry.titleLabel?.font = .preferredFont(forTextStyle: .caption1)
        retry.tintColor = .lightGray
        retry.isHidden = true
        retry.addTarget(self, action: #selector(loadScene), for: .touchUpInside)
        addSubview(retry)

        lens.camera.near = 0.3
        lens.camera.far = 30
        lens.camera.fieldOfViewInDegrees = 34
        lens.camera.fieldOfViewOrientation = .horizontal
        anchor.addChild(lens)
        renderer.engine?.entities.append(anchor)
        renderer.engine?.activeCamera = lens
        renderer.onFailure = { [weak self] error in
            VehicleSceneAssets.logger.error("Metal frame failed: \(error.localizedDescription, privacy: .public)")
            self?.retry.isHidden = false
        }

        let orbit = UIPanGestureRecognizer(target: self, action: #selector(orbit(_:)))
        orbit.maximumNumberOfTouches = 1
        orbit.delegate = self
        addGestureRecognizer(orbit)
        let elevation = UIPanGestureRecognizer(target: self, action: #selector(elevate(_:)))
        elevation.minimumNumberOfTouches = 2
        elevation.maximumNumberOfTouches = 2
        addGestureRecognizer(elevation)
        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(zoom(_:)))
        addGestureRecognizer(pinch)
        let reset = UITapGestureRecognizer(target: self, action: #selector(resetCamera))
        reset.numberOfTapsRequired = 2
        addGestureRecognizer(reset)
        isAccessibilityElement = true
        accessibilityIdentifier = "vehicle3D"
        accessibilityLabel = "Tu BMW E36 azul, modelo 3D"
        accessibilityHint = "Desliza para girar. Pellizca para acercar. Usa dos dedos para cambiar la altura. Doble toque para restablecer."
        accessibilityTraits = [.image, .adjustable]
        accessibilityValue = "Cargando"
        accessibilityCustomActions = [UIAccessibilityCustomAction(name: "Vista inicial", target: self, selector: #selector(resetCamera))]
        loadScene()
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override var intrinsicContentSize: CGSize { CGSize(width: UIView.noIntrinsicMetric, height: UIView.noIntrinsicMetric) }

    override func layoutSubviews() {
        super.layoutSubviews()
        renderer.frame = bounds
        spinner.center = CGPoint(x: bounds.midX, y: bounds.midY)
        retry.frame = bounds.insetBy(dx: 8, dy: max(0, (bounds.height - 44) / 2))
        if previousSize != bounds.size {
            previousSize = bounds.size
            updateCamera()
        }
    }

    @objc private func loadScene() {
        guard !loaded else { return }
        loading?.cancel()
        retry.isHidden = true
        isAccessibilityElement = true
        accessibilityValue = "Cargando"
        spinner.startAnimating()
        loading = Task { [weak self] in
            do {
                let assets = try await VehicleSceneAssets.shared()
                guard !Task.isCancelled, let self else { return }
                guard let engine = self.renderer.engine else { throw CocoaError(.fileReadUnknown) }
                let vehicle = assets.vehicle.clone(recursive: true)
                self.anchor.addChild(vehicle)
                var opticalEntities: [Entity] = []
                @MainActor func collectOptics(_ entity: Entity) {
                    if let model = entity.components[ModelComponent.self],
                       model.materials.contains(where: { (($0 as? CustomMaterial)?.custom.value.z ?? 0) > 0.5 }) {
                        opticalEntities.append(entity)
                    }
                    entity.children.forEach(collectOptics)
                }
                collectOptics(vehicle)
                self.renderer.configureOptics = { resource, visible in
                    for entity in opticalEntities {
                        guard var component = entity.components[ModelComponent.self] else { continue }
                        component.materials = component.materials.map { material in
                            guard var glass = material as? CustomMaterial,
                                  glass.custom.value.z > 0.5 else { return material }
                            let inner = glass.custom.value.z < 1.5
                            glass.custom.value.y = visible ? (inner && resource != nil ? 1 : 0) : -1
                            if inner, let resource { glass.custom.texture = .init(resource) }
                            return glass
                        }
                        entity.components.set(component)
                    }
                }
                engine.lighting.resource = assets.environment
                engine.lighting.intensityExponent = 0.65

                // Precomputed contact and directional shadow from this exact car mesh.
                // The car, highlights, glass and camera still render live in Metal.
                var floor = UnlitMaterial(color: .white, applyPostProcessToneMap: false)
                floor.color.texture = .init(assets.contactShadow)
                floor.blending = .transparent(opacity: .init(scale: 1))
                let ground = ModelEntity(mesh: .generatePlane(width: 8, depth: 8), materials: [floor])
                ground.position.y = -0.003
                ground.name = "Ground contact and directional shadow"
                self.anchor.addChild(ground)
                self.loaded = true
                self.renderer.onNextPresentation = { [weak self] in
                    guard let self else { return }
                    self.presented = true
                    self.spinner.stopAnimating()
                    self.updateCamera()
                }
                self.updateCamera()
                self.renderer.refresh(warmup: true)
            } catch {
                guard !Task.isCancelled, let self else { return }
                VehicleSceneAssets.logger.error("3D scene failed: \(error.localizedDescription, privacy: .public)")
                self.spinner.stopAnimating()
                self.retry.isHidden = false
                self.accessibilityValue = "No disponible"
                self.isAccessibilityElement = false
            }
        }
    }

    func setCamera(_ camera: VehicleCameraPose) {
        guard pose != camera else { return }
        pose = camera
        updateCamera()
    }

    func setActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        isUserInteractionEnabled = value
        anchor.isEnabled = value
        renderer.active = value
        renderer.isHidden = !value
        if value { renderer.refresh() }
    }

    func stop() {
        loading?.cancel()
        loading = nil
        renderer.stop()
        renderer.isHidden = true
    }

    private func updateCamera() {
#if DEBUG
        if let preset = VehicleReferenceReview.preset {
            // These are the authoring scene's photo-matched cameras, converted
            // from Blender Z-up to the runtime's Y-up coordinate system.
            let position: SIMD3<Float>
            let rotation: SIMD3<Float>
            let focalLength: Float
            switch preset {
            case "rear":
                position = [-2.2308207, 5.9172955, 1.8037224]
                rotation = [1.3539621, -0.10091642, -2.8214743]
                focalLength = 105.419
            case "side":
                position = [16.38, -0.052, 0.85]
                rotation = [.pi / 2, 0, .pi / 2]
                focalLength = 100
            default:
                position = [1.5981098, -3.6229513, 1.4964381]
                rotation = [1.1484588, 0.07979319, 0.75059724]
                focalLength = 61.06119
            }
            lens.position = [position.x, position.z, -position.y]
            lens.orientation = simd_quatf(angle: -.pi / 2, axis: [1, 0, 0])
                * simd_quatf(angle: rotation.z, axis: [0, 0, 1])
                * simd_quatf(angle: rotation.y, axis: [0, 1, 0])
                * simd_quatf(angle: rotation.x, axis: [1, 0, 0])
            lens.camera.fieldOfViewInDegrees = 2 * atan(18 / focalLength) * 180 / .pi
            renderer.refractionIsVisible = lens.position.z > 1.9
            if loaded {
                if presented { accessibilityValue = "Referencia \(preset)" }
                renderer.refresh()
            }
            return
        }
#endif
        let aspect = Float(max(bounds.width, 1) / max(bounds.height, 1))
        // Keep the car inside narrow landscape viewports without changing its
        // saved orbit or zoom when SwiftUI reconstructs the orientation layout.
        let radius = max(8.1, aspect * 3.65) / pose.zoom
        let target = SIMD3<Float>(0, 0.64, 0)
        let position = target + SIMD3<Float>(sin(pose.azimuth) * cos(pose.elevation), sin(pose.elevation), cos(pose.azimuth) * cos(pose.elevation)) * radius
        lens.look(at: target, from: position, relativeTo: nil)
        // The headlamp faces sit at the front of this fixed vehicle, +Z.
        // Rear/side views need no hidden reflector capture pass.
        renderer.refractionIsVisible = lens.position.z > 1.9
        guard loaded else { return }
        renderer.refresh()
        guard presented else { return }
        let facing = cos(pose.azimuth)
        accessibilityValue = facing > 0.4 ? "Vista delantera" : facing < -0.4 ? "Vista trasera" : "Vista lateral"
    }

    override func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        guard let pan = gestureRecognizer as? UIPanGestureRecognizer else { return true }
        let velocity = pan.velocity(in: self)
        return abs(velocity.x) > abs(velocity.y)
    }

    @objc private func orbit(_ recognizer: UIPanGestureRecognizer) {
        if recognizer.state == .began { panStart = pose }
        pose.azimuth = panStart.azimuth - Float(recognizer.translation(in: self).x / max(bounds.width, 1)) * .pi
        updateCamera()
        cameraChanged?(pose)
    }
    @objc private func elevate(_ recognizer: UIPanGestureRecognizer) {
        if recognizer.state == .began { panStart = pose }
        pose.elevation = min(0.70, max(0.035, panStart.elevation + Float(recognizer.translation(in: self).y) * 0.004))
        updateCamera()
        cameraChanged?(pose)
    }
    @objc private func zoom(_ recognizer: UIPinchGestureRecognizer) {
        if recognizer.state == .began { pinchStart = pose.zoom }
        pose.zoom = min(1.65, max(0.8, pinchStart * Float(recognizer.scale)))
        updateCamera()
        cameraChanged?(pose)
    }
    @objc @discardableResult private func resetCamera() -> Bool {
        pose = VehicleCameraPose()
        updateCamera()
        cameraChanged?(pose)
        return true
    }
    override func accessibilityIncrement() { pose.azimuth += .pi / 6; updateCamera(); cameraChanged?(pose) }
    override func accessibilityDecrement() { pose.azimuth -= .pi / 6; updateCamera(); cameraChanged?(pose) }
}
