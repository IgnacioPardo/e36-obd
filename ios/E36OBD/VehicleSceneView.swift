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
            .aspectRatio(Self.preset == "widget" ? 1.65 : 0.75, contentMode: .fit)
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
    /// An unwrapped origin makes the tab bar a continuous, ordered orbit.
    /// Manual gestures and exterior presets still use the shortest arc.
    var orderedFrom: Float?
    var focus = SIMD3<Float>(0, 0.64, 0)
    /// A world-space distance detaches expanded navigation from the auto-fit.
    /// Nil retains the protected framing used by the dashboard and presets.
    var distance: Float?

    var dashboardPose: Self {
        Self(azimuth: azimuth, elevation: min(0.70, max(0.035, elevation)))
    }

    static func tab(_ index: Int, from previousIndex: Int) -> Self {
        Self(azimuth: 0.58 - Float(index) * .pi / 2,
             orderedFrom: 0.58 - Float(previousIndex) * .pi / 2)
    }
}

enum VehicleStage: String, CaseIterable, Identifiable {
    case graphite, limestone
    var id: String { rawValue }
    var title: String { self == .graphite ? "Grafito" : "Luz natural" }
    var floorColor: SIMD3<Float> {
        self == .graphite ? [0.12, 0.13, 0.15] : [0.27, 0.255, 0.23]
    }
    var backdrop: SIMD3<Float> {
        self == .graphite ? [0.018, 0.020, 0.024] : [0.082, 0.080, 0.074]
    }
}

/// Perspective-fit all eight corners, including the near end of an oblique
/// car. The visible mesh, rather than a guessed distance, defines the frame.
enum VehicleCameraFraming {
    static let target = SIMD3<Float>(0, 0.64, 0)
    static func direction(_ pose: VehicleCameraPose) -> SIMD3<Float> {
        [sin(pose.azimuth) * cos(pose.elevation), sin(pose.elevation), cos(pose.azimuth) * cos(pose.elevation)]
    }
    static func distance(pose: VehicleCameraPose, aspect: Float, minimum: SIMD3<Float>, maximum: SIMD3<Float>) -> Float {
        let forward = direction(pose)
        let right = simd_normalize(simd_cross(SIMD3<Float>(0, 1, 0), forward))
        let up = simd_cross(forward, right)
        let horizontal = tan(Float(17) * .pi / 180) * 0.88
        let vertical = horizontal / max(aspect, 0.1)
        var fit: Float = 1
        for x in [minimum.x, maximum.x] {
            for y in [minimum.y, maximum.y] {
                for z in [minimum.z, maximum.z] {
                    let relative = SIMD3<Float>(x, y, z) - target
                    fit = max(fit, simd_dot(relative, forward) + max(abs(simd_dot(relative, right)) / horizontal, abs(simd_dot(relative, up)) / vertical))
                }
            }
        }
        // Pinch can tighten the composition, never crop the vehicle.
        return fit * max(1, 1.1 / max(pose.zoom, 0.1))
    }
}

enum VehicleFreeNavigation {
    static func zoom(distance: Float, scale: Float) -> Float {
        guard scale.isFinite, scale > 0 else { return distance }
        // Only numerical guards: 2 mm to 100 km, with no composition limit.
        return min(100_000, max(0.002, distance / scale))
    }

    static func pan(pose: VehicleCameraPose, translation: SIMD2<Float>, width: Float) -> SIMD3<Float> {
        let right = SIMD3<Float>(cos(pose.azimuth), 0, -sin(pose.azimuth))
        let up = simd_cross(VehicleCameraFraming.direction(pose), right)
        let metresPerPoint = 2 * (pose.distance ?? 1) * tan(Float(17) * .pi / 180) / max(width, 1)
        return (-right * translation.x + up * translation.y) * metresPerPoint
    }

    static func elevation(_ value: Float) -> Float {
        // Keep the horizon upright without a singular look-at at either pole.
        min(.pi / 2 - 0.001, max(-.pi / 2 + 0.001, value))
    }
}

/// The scene owns no telemetry, Bluetooth, storage, or recurring app timer.
struct VehicleSceneView: UIViewRepresentable {
    @Binding var camera: VehicleCameraPose
    var isVisible = true
    var allowsFreeNavigation = false
    @AppStorage("vehicleStage") private var stage = VehicleStage.graphite.rawValue
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeUIView(context: Context) -> VehicleSceneHost {
        let view = VehicleSceneHost(frame: .zero)
        view.reduceMotion = reduceMotion
        view.cameraChanged = { camera = $0 }
        view.setCamera(camera, freeNavigation: allowsFreeNavigation)
        view.setStage(VehicleStage(rawValue: stage) ?? .graphite)
        return view
    }

    func updateUIView(_ view: VehicleSceneHost, context: Context) {
        view.reduceMotion = reduceMotion
        view.cameraChanged = { camera = $0 }
        view.setActive(scenePhase == .active && isVisible)
        view.setCamera(camera, freeNavigation: allowsFreeNavigation)
        view.setStage(VehicleStage(rawValue: stage) ?? .graphite)
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
        let studioDiffuse: Bool?
    }
    static let logger = Logger(subsystem: "com.ignaciopardo.e36obd", category: "VehicleMetal")
    private static var pending: Task<VehicleSceneAssets, Error>?
    let vehicle: Entity
    let environment: EnvironmentResource
    let studioEnvironment: EnvironmentResource
    let library: any MTLLibrary
    let contactShadow: TextureResource
    let softboxShadow: TextureResource
    let parkingBackdrop: TextureResource
    let studioDiffuse: Bool

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
        studioDiffuse = manifest.studioDiffuse == true
        self.library = library
        let started = ContinuousClock.now
        vehicle = try await Entity(contentsOf: modelURL)
        Self.logger.info("Model decoded in \(String(describing: started.duration(to: .now)))")
        environment = try await EnvironmentResource(named: "VehicleScene/StudioEnvironment", in: .main)
        studioEnvironment = try await EnvironmentResource(named: "VehicleScene/SoftboxEnvironment", in: .main)
        guard let panoramaURL = Bundle.main.url(forResource: "ParkingBackdrop", withExtension: "exr", subdirectory: "VehicleScene") else { throw CocoaError(.fileNoSuchFile) }
        parkingBackdrop = try await TextureResource(contentsOf: panoramaURL, options: .init(semantic: .hdrColor))
        guard let shadowURL = Bundle.main.url(forResource: "ContactShadow", withExtension: "png", subdirectory: "VehicleScene") else {
            throw CocoaError(.fileNoSuchFile)
        }
        contactShadow = try await TextureResource(contentsOf: shadowURL)
        if let studioShadowURL = Bundle.main.url(forResource: "SoftboxShadow", withExtension: "png", subdirectory: "VehicleScene") {
            softboxShadow = try await TextureResource(contentsOf: studioShadowURL)
        } else {
            softboxShadow = contactShadow
        }
        let shader = CustomMaterial.SurfaceShader(named: "e36MetallicPaint", in: library)
        let glassShader = CustomMaterial.SurfaceShader(named: "e36OpticalGlass", in: library)
        let opticalGeometry = CustomMaterial.GeometryModifier(named: "e36OpticalGeometry", in: library)
        // Draw the refracting circular lenses before the transparent cover.
        // An automatic depth prepass can make the cover erase inner optics.
        let headlampOrder = ModelSortGroup(depthPass: .postPass)
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
                        // The front shell evaluates both air/glass interfaces.
                        // The rear shell stays hidden to avoid self-occlusion.
                        glass.faceCulling = .none
                        glass.custom.value.x = key == "wcwindow" ? 0.10 : 0.012
                        // Shared with the Metal shader: 1 = optical front,
                        // 2 = hidden rear shell, 3 = clear outer cover.
                        if key.contains("polished_outer") { glass.custom.value.z = 1 }
                        else if key.contains("pressed_halogen") { glass.custom.value.z = 2 }
                        else if key == "material__58" { glass.custom.value.z = 3 }
                        if glass.custom.value.z > 0.5 {
                            glass.writesDepth = false
                            glass.readsDepth = true
                        }
                        glass.custom.value.w = key == "wcwindow" ? 0.035 : 0.025
                        return glass
                    }
                    if key.contains("glass") || key == "material__58" || key == "_03___default" { return material }
                    guard let imported = material as? PhysicallyBasedMaterial else { return material }
                    if key == "pisca" {
                        // The silvered return behind the amber cover has its
                        // own prismatic response. The separate clear cover
                        // supplies the untinted dielectric reflection.
                        var signal = try CustomMaterial(surfaceShader: .init(named: "e36SignalReflector", in: library), geometryModifier: opticalGeometry, lightingModel: .unlit)
                        signal.blending = .opaque
                        return signal
                    }
                    guard key == "car_body" || key.contains("painted_fog_intake_duct") else {
                        var finish = try CustomMaterial(from: imported, surfaceShader: .init(named: "e36VehicleSurface", in: library))
                        if key == "interior_dash_plastic" {
                            finish.baseColor.tint = UIColor(red: 0.1718, green: 0.1897, blue: 0.2098, alpha: 1)
                        }
                        finish.blending = .opaque
                        finish.custom.value.z = -1
                        // USD Preview Surface drops Blender's zero specular
                        // control on the ink beneath this clear resin coat.
                        if key.contains("domed_body_badge_enamel") { finish.specular = .init(scale: 0) }
                        // Coloured lamp plastic has one dielectric interface,
                        // not automotive paint's extra clear lacquer layer.
                        // A second lobe bleaches the red/amber moulded lenses.
                        if key == "bmw_m3_e36_lights" {
                            finish.clearcoat = .init(scale: 0)
                            finish.roughness = .init(scale: 0.24)
                        }
                        return finish
                    }
                    var paint = try CustomMaterial(surfaceShader: shader, lightingModel: .clearcoat)
                    paint.baseColor = .init(tint: imported.baseColor.tint)
                    // Calibrate the mobile BRDF separately from the offline
                    // material. Preserve the sampled Samoablau pigment while
                    // separating metallic reflections from diffuse body colour.
                    paint.metallic = .init(scale: 0.50)
                    paint.roughness = .init(scale: 0.22)
                    paint.clearcoat = 1.0
                    paint.clearcoatRoughness = 0.055
                    paint.custom.value.z = -1
                    painted += 1
                    return paint
                }
                entity.components.set(component)
                let optics = component.materials.compactMap { $0 as? CustomMaterial }
                    .map { $0.custom.value.z }.filter { $0 > 0.5 }
                if !optics.isEmpty {
                    entity.components.set(ModelSortGroupComponent(group: headlampOrder,
                        order: optics.contains(3) ? 20 : 10))
                }
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
    private var requestedPose = VehicleCameraPose()
    private var allowsFreeNavigation = false
    private var flight: VehicleCameraFlight?
    private var displayLink: CADisplayLink?
    private lazy var frameTarget = VehicleCameraFrameTarget(host: self)
    var reduceMotion = false {
        didSet {
            if reduceMotion && !oldValue { finishFlight() }
        }
    }
    private var panStart = VehicleCameraPose()
    private var pinchStart: Float = 1
    private var previousSize = CGSize.zero
    private var vehicleBounds: (min: SIMD3<Float>, max: SIMD3<Float>) = ([-0.95, 0, -2.3], [0.95, 1.45, 2.3])
    private var stage = VehicleStage.graphite
    private var sceneAssets: VehicleSceneAssets?
    private var presentationGround: ModelEntity?
    private var outdoorBackdrop: Entity?
    private var shadowGround: ModelEntity?
    private var shadedVehicle: Entity?
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
        lens.camera.far = 80
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
        elevation.delegate = self
        addGestureRecognizer(elevation)
        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(zoom(_:)))
        pinch.delegate = self
        addGestureRecognizer(pinch)
        let reset = UITapGestureRecognizer(target: self, action: #selector(resetCamera))
        reset.numberOfTapsRequired = 2
        addGestureRecognizer(reset)
        let turn = UITapGestureRecognizer(target: self, action: #selector(tapView))
        turn.require(toFail: reset)
        addGestureRecognizer(turn)
        isAccessibilityElement = true
        accessibilityIdentifier = "vehicle3D"
        accessibilityLabel = "Tu BMW E36 azul, modelo 3D"
        accessibilityHint = "Toca para cambiar de ángulo. Desliza para girar. Pellizca para acercar. Usa dos dedos para cambiar la altura. Doble toque para restablecer."
        accessibilityTraits = [.image, .adjustable]
        accessibilityValue = "Cargando"
        accessibilityCustomActions = [
            UIAccessibilityCustomAction(name: "Siguiente ángulo", target: self, selector: #selector(nextView)),
            UIAccessibilityCustomAction(name: "Vista inicial", target: self, selector: #selector(resetCamera))
        ]
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
                self.shadedVehicle = vehicle
                self.anchor.addChild(vehicle)
                let bounds = vehicle.visualBounds(relativeTo: nil)
                self.vehicleBounds = (bounds.min, bounds.max)
                self.sceneAssets = assets
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
                            let refractingLens = glass.custom.value.z < 1.5
                            glass.custom.value.y = visible ? (refractingLens && resource != nil ? 1 : 0) : -1
                            if refractingLens, let resource { glass.custom.texture = .init(resource) }
                            return glass
                        }
                        entity.components.set(component)
                    }
                }
                engine.lighting.resource = assets.environment
                // Half a stop below the previous scene: retain bright reflected
                // highlights without washing the shaded panels into pale blue.
                engine.lighting.intensityExponent = 0.15

                // Precomputed contact and directional shadow from this exact car mesh.
                // The car, highlights, glass and camera still render live in Metal.
                var floor = UnlitMaterial(color: .white, applyPostProcessToneMap: false)
                floor.color.texture = .init(assets.contactShadow)
                floor.blending = .transparent(opacity: .init(scale: 1))
                let ground = ModelEntity(mesh: .generatePlane(width: 8, depth: 8), materials: [floor])
                ground.position.y = -0.003
                ground.name = "Ground contact and directional shadow"
                self.anchor.addChild(ground)
                self.shadowGround = ground
                var surface = try CustomMaterial(surfaceShader: .init(named: "e36PresentationGround", in: assets.library), lightingModel: .unlit)
                surface.blending = .transparent(opacity: .init(scale: 1))
                let presentation = ModelEntity(mesh: .generatePlane(width: 40, depth: 40), materials: [surface])
                presentation.position.y = -0.006
                presentation.name = "World-fixed matte ground"
                self.anchor.addChild(presentation)
                self.presentationGround = presentation
                var outdoorMaterial = try CustomMaterial(surfaceShader: .init(named: "e36OutdoorBackdrop", in: assets.library), lightingModel: .unlit)
                outdoorMaterial.custom.texture = .init(assets.parkingBackdrop)
                outdoorMaterial.faceCulling = .front
                outdoorMaterial.blending = .transparent(opacity: .init(scale: 1))
                let outdoor = Entity()
                let dome = ModelEntity(mesh: .generateSphere(radius: 30), materials: [outdoorMaterial])
                dome.position.y = 1.65
                outdoor.addChild(dome)
                outdoorMaterial.faceCulling = .back
                let paving = ModelEntity(mesh: .generatePlane(width: 60, depth: 60), materials: [outdoorMaterial])
                paving.position.y = -0.006
                outdoor.addChild(paving)
                self.anchor.addChild(outdoor)
                self.outdoorBackdrop = outdoor
                self.applyStage()
#if DEBUG
                // Matched-camera lighting studies; the production probe stays
                // world-fixed and uses its matching diffuse/shadow bake.
                if let argument = ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix("--studio-angle=") }),
                   let degrees = Float(argument.split(separator: "=").last ?? "") {
                    let probe = Entity()
                    var light = ImageBasedLightComponent(source: .single(assets.studioEnvironment))
                    light.inheritsRotation = true
                    if let exposure = ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix("--studio-exposure=") }),
                       let stops = Float(exposure.split(separator: "=").last ?? "") {
                        light.intensityExponent = stops
                    }
                    probe.components.set(light)
                    probe.orientation = simd_quatf(angle: degrees * .pi / 180, axis: [0, 1, 0])
                    self.anchor.addChild(probe)
                    func receive(_ entity: Entity) {
                        if entity.components[ModelComponent.self] != nil {
                            entity.components.set(ImageBasedLightReceiverComponent(imageBasedLight: probe))
                        }
                        entity.children.forEach(receive)
                    }
                    receive(vehicle)
                }
#endif
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

    func setCamera(_ camera: VehicleCameraPose, freeNavigation: Bool = false) {
        if allowsFreeNavigation != freeNavigation {
            cancelFlight()
            allowsFreeNavigation = freeNavigation
            accessibilityHint = freeNavigation
                ? "Arrastra con un dedo para girar en cualquier dirección. Pellizca para acercar o alejar. Arrastra con dos dedos para desplazar. Doble toque para restablecer."
                : "Toca para cambiar de ángulo. Desliza para girar. Pellizca para acercar. Usa dos dedos para cambiar la altura. Doble toque para restablecer."
            if freeNavigation {
                pose = camera
                requestedPose = camera
                updateCamera()
            } else {
                // A tab can close the expanded camera. Recover safe framing
                // first, then follow that tab's ordered orbit from this angle.
                pose = pose.dashboardPose
                move(to: camera)
            }
            return
        }
        guard requestedPose != camera else { return }
        move(to: camera)
    }

    func setStage(_ value: VehicleStage) {
        guard stage != value else { return }
        stage = value
        applyStage()
    }

    private func applyStage() {
        guard let assets = sceneAssets else { return }
        var selected = stage
        var baseline = false
        var export = false
#if DEBUG
        let option = ProcessInfo.processInfo.arguments.first { $0.hasPrefix("--scene-study=") }?.components(separatedBy: "=").last
        if let option, let override = VehicleStage(rawValue: option) { selected = override }
        baseline = option == "original"
        export = ProcessInfo.processInfo.arguments.contains("--widget-car-export")
#endif
        renderer.engine?.lighting.resource = selected == .graphite && !baseline ? assets.studioEnvironment : assets.environment
        renderer.engine?.lighting.intensityExponent = selected == .graphite && !baseline ? 0 : 0.15
        renderer.stageBackdrop = baseline || selected == .limestone ? .zero : selected.backdrop
        presentationGround?.isEnabled = !baseline && !export && selected == .graphite
        outdoorBackdrop?.isEnabled = !baseline && !export && selected == .limestone
#if DEBUG
        shadowGround?.isEnabled = !ProcessInfo.processInfo.arguments.contains("--widget-car-only")
#endif
        var bakedDiffuse = selected == .graphite && !baseline && assets.studioDiffuse
#if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--live-studio-lighting") { bakedDiffuse = false }
#endif
        func updateDiffuse(_ entity: Entity) {
            if var component = entity.components[ModelComponent.self] {
                component.materials = component.materials.map { material in
                    guard var surface = material as? CustomMaterial, surface.custom.value.z < -0.5 else { return material }
                    surface.custom.value.w = bakedDiffuse ? 1 : 0
                    return surface
                }
                entity.components.set(component)
            }
            for child in entity.children { updateDiffuse(child) }
        }
        if let shadedVehicle { updateDiffuse(shadedVehicle) }
        if var component = shadowGround?.model, var material = component.materials.first as? UnlitMaterial {
            material.color.texture = .init(selected == .graphite && !baseline ? assets.softboxShadow : assets.contactShadow)
            let extent: Float = selected == .graphite && !baseline ? 20 : 8
            component.mesh = .generatePlane(width: extent, depth: extent)
            component.materials = [material]
            shadowGround?.model = component
        }
        if var component = presentationGround?.model, var material = component.materials.first as? CustomMaterial {
            material.custom.value = SIMD4<Float>(selected.floorColor, 0)
            component.materials = [material]
            presentationGround?.model = component
        }
        renderer.refresh(warmup: true)
    }

    private func move(to camera: VehicleCameraPose, duration: Double = 0.85, coast: Bool = false) {
        cancelFlight()
        if let reference = camera.orderedFrom, pose.orderedFrom == nil {
            // A manual orbit may have crossed 2π several times. Put its
            // equivalent angle on the current tab's branch without a jump.
            pose.azimuth = reference + atan2(sin(pose.azimuth - reference), cos(pose.azimuth - reference))
        }
        requestedPose = camera
        var destination = camera
        if allowsFreeNavigation {
            freezeFreeDistance()
            destination.distance = camera.distance ?? fittedDistance(for: camera)
        }
        guard loaded, presented, active, !reduceMotion else {
            pose = destination
            updateCamera()
            return
        }
        let travel = camera.orderedFrom == nil ? duration : min(1.65, duration * max(1, sqrt(Double(abs(camera.azimuth - pose.azimuth) / (.pi / 2)))))
        flight = VehicleCameraFlight(from: pose, to: destination, started: CACurrentMediaTime(), duration: travel, coast: coast)
        let link = CADisplayLink(target: frameTarget, selector: #selector(VehicleCameraFrameTarget.tick(_:)))
        link.preferredFrameRateRange = CAFrameRateRange(minimum: 30, maximum: 60, preferred: 60)
        link.add(to: .main, forMode: .common)
        displayLink = link
    }

    fileprivate func animateCamera(at time: Double) {
        guard let flight else { return }
        pose = flight.pose(at: time)
        updateCamera()
        if time >= flight.started + flight.duration { cancelFlight() }
    }

    private func cancelFlight() {
        displayLink?.invalidate()
        displayLink = nil
        flight = nil
    }

    private func finishFlight() {
        guard let destination = flight?.to else { return }
        cancelFlight()
        pose = destination
        updateCamera()
    }

    private func publishGesture() {
        pose.orderedFrom = nil
        requestedPose = pose
        updateCamera()
        cameraChanged?(pose)
    }

    private func selectCamera(_ target: VehicleCameraPose, duration: Double = 0.85, coast: Bool = false) {
        var camera = target
        camera.orderedFrom = nil
        move(to: camera, duration: duration, coast: coast)
        cameraChanged?(camera)
    }

    func setActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        if !value { finishFlight() }
        isUserInteractionEnabled = value
        anchor.isEnabled = value
        renderer.active = value
        renderer.isHidden = !value
        if value { renderer.refresh() }
    }

    func stop() {
        cancelFlight()
        loading?.cancel()
        loading = nil
        renderer.stop()
        renderer.isHidden = true
    }

    private func updateCamera() {
#if DEBUG
        if let preset = VehicleReferenceReview.preset {
            if preset == "widget" {
                lens.look(at: [0, 0.62, 0], from: [4.9, 2.15, 7.2], relativeTo: nil)
                lens.camera.fieldOfViewInDegrees = 34
                renderer.refractionIsVisible = true
                if loaded {
                    if presented { accessibilityValue = "Referencia widget" }
                    renderer.refresh()
                }
                return
            }
            if preset == "apron" {
                lens.look(at: [0, 0.53, -2.16], from: [0, 0.66, -4.9], relativeTo: nil)
                lens.camera.fieldOfViewInDegrees = 42
                renderer.refractionIsVisible = false
                if loaded {
                    if presented { accessibilityValue = "Referencia \(preset)" }
                    renderer.refresh()
                }
                return
            }
            if preset == "cabin" {
                // Review the actual cabin from between the front seats. Vehicle
                // left is +X; this camera never reflects or hides any geometry.
                lens.look(at: [0, 0.83, 0.60], from: [0, 1.13, -0.40], relativeTo: nil)
                lens.camera.fieldOfViewInDegrees = 85
                renderer.refractionIsVisible = false
                if loaded {
                    if presented { accessibilityValue = "Referencia \(preset)" }
                    renderer.refresh()
                }
                return
            }
            if preset == "optics" {
                // Inspect the headlamp and indicator together at an oblique
                // angle, including the clear cover and recessed optics.
                lens.look(at: [0.53, 0.636, 2.01], from: [1.08, 0.80, 3.20], relativeTo: nil)
                lens.camera.fieldOfViewInDegrees = 31
                renderer.refractionIsVisible = true
                if loaded {
                    if presented { accessibilityValue = "Referencia \(preset)" }
                    renderer.refresh()
                }
                return
            }
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
        // Keep the car inside narrow landscape viewports without changing its
        // saved orbit or zoom when SwiftUI reconstructs the orientation layout.
        let radius = allowsFreeNavigation ? (pose.distance ?? fittedDistance(for: pose)) : fittedDistance(for: pose)
        let target = allowsFreeNavigation ? pose.focus : VehicleCameraFraming.target
        lens.camera.near = allowsFreeNavigation ? max(0.0005, min(0.03, radius * 0.002)) : 0.3
        lens.camera.far = allowsFreeNavigation ? max(80, radius + simd_length(target) + 100) : 80
        let position = target + VehicleCameraFraming.direction(pose) * radius
        lens.look(at: target, from: position, relativeTo: nil)
        // The headlamp faces sit at the front of this fixed vehicle, +Z.
        // Rear/side views need no hidden reflector capture pass.
        renderer.refractionIsVisible = lens.position.z > 1.9
        guard loaded else { return }
        renderer.refresh()
        guard presented else { return }
        let facing = cos(pose.azimuth)
        let view = facing > 0.4 ? "Vista delantera" : facing < -0.4 ? "Vista trasera" : "Vista lateral"
        accessibilityValue = allowsFreeNavigation
            ? String(format: "%@ · Distancia %.2f m · Elevación %.0f° · Centro %.2f, %.2f, %.2f m", view, radius, pose.elevation * 180 / .pi, target.x, target.y, target.z)
            : view
    }

    override func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        guard let pan = gestureRecognizer as? UIPanGestureRecognizer else { return true }
        if allowsFreeNavigation || pan.minimumNumberOfTouches == 2 { return true }
        let velocity = pan.velocity(in: self)
        return abs(velocity.x) > abs(velocity.y)
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
        guard allowsFreeNavigation else { return false }
        let pair = [gestureRecognizer, otherGestureRecognizer]
        return pair.contains { $0 is UIPinchGestureRecognizer }
            && pair.contains { ($0 as? UIPanGestureRecognizer)?.minimumNumberOfTouches == 2 }
    }

    private func fittedDistance(for camera: VehicleCameraPose) -> Float {
        VehicleCameraFraming.distance(pose: camera, aspect: Float(max(bounds.width, 1) / max(bounds.height, 1)),
                                      minimum: vehicleBounds.min, maximum: vehicleBounds.max)
    }

    private func freezeFreeDistance() {
        if allowsFreeNavigation && pose.distance == nil { pose.distance = fittedDistance(for: pose) }
    }

    @objc private func orbit(_ recognizer: UIPanGestureRecognizer) {
        if recognizer.state == .began { cancelFlight(); freezeFreeDistance(); panStart = pose }
        pose.azimuth = panStart.azimuth - Float(recognizer.translation(in: self).x / max(bounds.width, 1)) * .pi
        if allowsFreeNavigation {
            pose.elevation = VehicleFreeNavigation.elevation(panStart.elevation + Float(recognizer.translation(in: self).y / max(bounds.height, 1)) * .pi)
        }
        publishGesture()
        if recognizer.state == .ended, !reduceMotion {
            let velocity = Float(recognizer.velocity(in: self).x / max(bounds.width, 1))
            if abs(velocity) > 0.2 {
                var destination = pose
                destination.azimuth -= min(0.32, max(-0.32, velocity * 0.12))
                selectCamera(destination, duration: 0.4, coast: true)
            }
        }
    }
    @objc private func elevate(_ recognizer: UIPanGestureRecognizer) {
        if recognizer.state == .began { cancelFlight(); freezeFreeDistance(); panStart = pose }
        if allowsFreeNavigation {
            let delta = recognizer.translation(in: self)
            let focus = pose.focus + VehicleFreeNavigation.pan(pose: pose, translation: [Float(delta.x), Float(delta.y)], width: Float(bounds.width))
            if focus.x.isFinite && focus.y.isFinite && focus.z.isFinite { pose.focus = focus }
            recognizer.setTranslation(.zero, in: self)
            publishGesture()
            return
        }
        pose.elevation = min(0.70, max(0.035, panStart.elevation + Float(recognizer.translation(in: self).y) * 0.004))
        publishGesture()
    }
    @objc private func zoom(_ recognizer: UIPinchGestureRecognizer) {
        if recognizer.state == .began { cancelFlight(); freezeFreeDistance(); pinchStart = pose.zoom }
        if allowsFreeNavigation {
            pose.distance = VehicleFreeNavigation.zoom(distance: pose.distance ?? fittedDistance(for: pose), scale: Float(recognizer.scale))
            recognizer.scale = 1
            publishGesture()
            return
        }
        pose.zoom = min(1.1, max(0.8, pinchStart * Float(recognizer.scale)))
        publishGesture()
    }
    @objc @discardableResult private func resetCamera() -> Bool {
        selectCamera(VehicleCameraPose())
        return true
    }
    @objc private func tapView() { if !allowsFreeNavigation { nextView() } }
    @objc @discardableResult private func nextView() -> Bool {
        let angles: [Float] = [0.58, .pi / 2, .pi - 0.58]
        let nearest = angles.indices.min { a, b in
            abs(atan2(sin(requestedPose.azimuth - angles[a]), cos(requestedPose.azimuth - angles[a]))) <
            abs(atan2(sin(requestedPose.azimuth - angles[b]), cos(requestedPose.azimuth - angles[b])))
        } ?? 0
        var camera = requestedPose
        camera.azimuth = angles[(nearest + 1) % angles.count]
        selectCamera(camera)
        return true
    }
    override func accessibilityIncrement() { var camera = pose; camera.azimuth += .pi / 6; selectCamera(camera) }
    override func accessibilityDecrement() { var camera = pose; camera.azimuth -= .pi / 6; selectCamera(camera) }
}

/// A weak display-link target lets a removed scene release immediately.
@MainActor private final class VehicleCameraFrameTarget: NSObject {
    weak var host: VehicleSceneHost?
    init(host: VehicleSceneHost) { self.host = host }
    @objc func tick(_ link: CADisplayLink) { host?.animateCamera(at: link.timestamp) }
}

struct VehicleCameraFlight {
    let from: VehicleCameraPose
    let to: VehicleCameraPose
    let started: Double
    let duration: Double
    var coast = false

    func pose(at time: Double) -> VehicleCameraPose {
        let t = Float(min(1, max(0, (time - started) / max(duration, 0.001))))
        if t == 1 { return to }
        let eased = coast ? 1 - pow(1 - t, 3) : t * t * t * (t * (t * 6 - 15) + 10)
        // Tab position defines the signed travel, including skipped tabs.
        // Gestures and presets retain their shortest path across ±π.
        let difference = to.azimuth - from.azimuth
        let turn = to.orderedFrom == nil ? atan2(sin(difference), cos(difference)) : difference
        let distance: Float? = if let start = from.distance, let end = to.distance { start + (end - start) * eased } else { to.distance }
        return VehicleCameraPose(azimuth: from.azimuth + turn * eased,
            elevation: from.elevation + (to.elevation - from.elevation) * eased,
            zoom: from.zoom + (to.zoom - from.zoom) * eased, orderedFrom: to.orderedFrom,
            focus: from.focus + (to.focus - from.focus) * eased, distance: distance)
    }
}
