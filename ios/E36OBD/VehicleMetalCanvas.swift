import MetalKit
import RealityKit

/// RealityKit's PBR renderer inside an explicitly scheduled Metal view. The GPU
/// renders camera changes and a bounded initial warm-up, then rests while idle.
@MainActor
final class VehicleMetalCanvas: MTKView, MTKViewDelegate {
    private(set) var engine: RealityRenderer?
    private var presentationQueue: (any MTLCommandQueue)?
    private var completionEvent: (any MTLSharedEvent)?
    private var eventValue: UInt64 = 0
    private var inFlight = false
    private var requested = false
    private var warmupUntil: TimeInterval = 0
    var active = true
    var onFailure: ((Error) -> Void)?
    var onNextPresentation: (() -> Void)?

    init() {
        let gpu = MTLCreateSystemDefaultDevice()
        super.init(frame: .zero, device: gpu)
        framebufferOnly = false
        colorPixelFormat = .bgra8Unorm_srgb
        isOpaque = false
        backgroundColor = .clear
        clearColor = MTLClearColorMake(0, 0, 0, 0)
        isPaused = true
        enableSetNeedsDisplay = true
        delegate = self
        presentationQueue = gpu?.makeCommandQueue()
        completionEvent = gpu?.makeSharedEvent()
        do {
            engine = try RealityRenderer()
            engine?.cameraSettings.colorBackground = .color(UIColor.clear.cgColor)
            engine?.cameraSettings.isToneMappingEnabled = true
            engine?.cameraSettings.antialiasing = .multisample4X
        } catch { engine = nil }
    }
    required init(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func refresh(warmup: Bool = false) {
        requested = true
        if warmup { warmupUntil = CACurrentMediaTime() + 3 }
        if active, !inFlight { setNeedsDisplay() }
    }

    func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) { refresh() }

    func draw(in view: MTKView) {
        guard active, !inFlight, requested, let engine,
              let event = completionEvent, let queue = presentationQueue,
              let drawable = currentDrawable, let present = queue.makeCommandBuffer() else { return }
        requested = false
        inFlight = true
        eventValue += 1
        do {
            let output = try RealityRenderer.CameraOutput(.singleProjection(colorTexture: drawable.texture))
            try engine.updateAndRender(deltaTime: 0, cameraOutput: output,
                                       actionsAfterRender: [.signal(event, value: eventValue)])
            // RealityRenderer owns its command queue. This GPU fence prevents
            // presentation from racing its render, without blocking the UI.
            present.encodeWaitForEvent(event, value: eventValue)
            present.present(drawable)
            present.addCompletedHandler { [weak self] _ in
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.inFlight = false
                    let presented = self.onNextPresentation
                    self.onNextPresentation = nil
                    presented?()
                    if CACurrentMediaTime() < self.warmupUntil { self.requested = true }
                    if self.requested, self.active { self.setNeedsDisplay() }
                }
            }
            present.commit()
        } catch {
            inFlight = false
            onFailure?(error)
        }
    }

    func stop() {
        active = false
        requested = false
        onNextPresentation = nil
        engine?.entities.removeAll()
        engine = nil
        delegate = nil
    }
}
