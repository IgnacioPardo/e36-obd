import MetalKit
import RealityKit

#if DEBUG
/// This buffer is owned by one command buffer, then read once by its completion
/// handler after the GPU finishes. No CPU or GPU writer retains it afterward.
private struct WidgetCarReadback: @unchecked Sendable {
    let buffer: any MTLBuffer
}
#endif

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
    private var hdrTexture: (any MTLTexture)?
    private var displayLUT: (any MTLTexture)?
    private var displayPipeline: (any MTLRenderPipelineState)?
    private var opticalBackground: LowLevelTexture?
    private var opticalResource: TextureResource?
    private var capturedCameraTransform: Transform?
    private var capturedCameraProjection: PerspectiveCameraComponent?
    private var capturedDrawable: (any CAMetalDrawable)?
    var configureOptics: ((TextureResource?, Bool) -> Void)?
    var refractionIsVisible = true
    var stageBackdrop = SIMD3<Float>.zero
    var active = true
    var onFailure: ((Error) -> Void)?
    var onNextPresentation: (() -> Void)?
#if DEBUG
    private var exportedWidgetCar = false
#endif

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
            guard let gpu, let library = gpu.makeDefaultLibrary(),
                  let url = Bundle.main.url(forResource: "AgXDisplay", withExtension: "rgba16f", subdirectory: "VehicleScene") else {
                throw CocoaError(.fileNoSuchFile)
            }
            let data = try Data(contentsOf: url)
            let size = 64
            guard data.count == size * size * size * 8 else { throw CocoaError(.fileReadCorruptFile) }
            let descriptor = MTLTextureDescriptor()
            descriptor.textureType = .type3D
            descriptor.pixelFormat = .rgba16Float
            descriptor.width = size
            descriptor.height = size
            descriptor.depth = size
            descriptor.usage = .shaderRead
            descriptor.storageMode = .shared
            guard let lut = gpu.makeTexture(descriptor: descriptor) else { throw CocoaError(.coderInvalidValue) }
            data.withUnsafeBytes { bytes in
                lut.replace(region: MTLRegionMake3D(0, 0, 0, size, size, size), mipmapLevel: 0,
                            slice: 0, withBytes: bytes.baseAddress!, bytesPerRow: size * 8, bytesPerImage: size * size * 8)
            }
            displayLUT = lut
            let pipeline = MTLRenderPipelineDescriptor()
            pipeline.vertexFunction = library.makeFunction(name: "e36DisplayVertex")
            pipeline.fragmentFunction = library.makeFunction(name: "e36PhotographicDisplay")
            pipeline.colorAttachments[0].pixelFormat = colorPixelFormat
            displayPipeline = try gpu.makeRenderPipelineState(descriptor: pipeline)
            engine = try RealityRenderer()
            engine?.cameraSettings.colorBackground = .color(UIColor.clear.cgColor)
            engine?.cameraSettings.isToneMappingEnabled = false
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
              let drawable = currentDrawable, let capture = queue.makeCommandBuffer(),
              let device else { return }
        requested = false
        inFlight = true
        eventValue += 1
        do {
            // 1.5x linear supersampling also filters shader highlights and
            // transparent optics, which coverage MSAA alone cannot resolve.
            // Cap the long edge to bound memory on large devices.
            let scale = min(1.5, 2560.0 / Double(max(drawable.texture.width, drawable.texture.height)))
            let width = max(1, Int(Double(drawable.texture.width) * scale))
            let height = max(1, Int(Double(drawable.texture.height) * scale))
            if hdrTexture?.width != width || hdrTexture?.height != height {
                let descriptor = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .rgba16Float, width: width, height: height, mipmapped: false)
                descriptor.usage = [.renderTarget, .shaderRead]
                descriptor.storageMode = .private
                hdrTexture = device.makeTexture(descriptor: descriptor)
                opticalBackground = nil
                opticalResource = nil
            }
            capturedCameraTransform = engine.activeCamera?.transform
            capturedCameraProjection = engine.activeCamera?.components[PerspectiveCameraComponent.self]
            if !refractionIsVisible {
                configureOptics?(nil, true)
                presentOpticalScene(drawable: drawable)
                return
            }
            if opticalBackground == nil {
                opticalBackground = try LowLevelTexture(descriptor: .init(pixelFormat: .rgba16Float, width: width, height: height, textureUsage: [.shaderRead, .renderTarget]))
                opticalResource = try TextureResource(from: opticalBackground!)
            }
            guard let hdrTexture, let opticalBackground else { throw CocoaError(.coderInvalidValue) }
            capturedDrawable = drawable
            configureOptics?(opticalResource, false)
            let output = try RealityRenderer.CameraOutput(.singleProjection(colorTexture: hdrTexture))
            try engine.updateAndRender(deltaTime: 0, cameraOutput: output,
                                       actionsAfterRender: [.signal(event, value: eventValue)])
            capture.encodeWaitForEvent(event, value: eventValue)
            let background = opticalBackground.replace(using: capture)
            guard let blit = capture.makeBlitCommandEncoder() else { throw CocoaError(.coderInvalidValue) }
            blit.copy(from: hdrTexture, to: background)
            blit.endEncoding()
            // Wait asynchronously before the optical pass: no stale camera
            // frame is ever sampled and the main thread remains available.
            capture.addCompletedHandler { [weak self] buffer in
                let completed = buffer.status == .completed
                let error = buffer.error
                DispatchQueue.main.async {
                    guard let self else { return }
                    guard completed, self.active, let drawable = self.capturedDrawable else {
                        self.inFlight = false
                        self.capturedDrawable = nil
                        if let error { self.onFailure?(error) }
                        return
                    }
                    self.capturedDrawable = nil
                    self.configureOptics?(self.opticalResource, true)
                    self.presentOpticalScene(drawable: drawable)
                }
            }
            capture.commit()
        } catch {
            inFlight = false
            capturedDrawable = nil
            onFailure?(error)
        }
    }

    private func presentOpticalScene(drawable: any CAMetalDrawable) {
        guard let engine, let event = completionEvent, let present = presentationQueue?.makeCommandBuffer(),
              let hdrTexture, let displayPipeline, let displayLUT else { inFlight = false; return }
        do {
            eventValue += 1
            let camera = engine.activeCamera
            let pendingTransform = camera?.transform
            let pendingProjection = camera?.components[PerspectiveCameraComponent.self]
            if let capturedCameraTransform { camera?.transform = capturedCameraTransform }
            if let capturedCameraProjection { camera?.components.set(capturedCameraProjection) }
            defer {
                if let pendingTransform { camera?.transform = pendingTransform }
                if let pendingProjection { camera?.components.set(pendingProjection) }
            }
            let output = try RealityRenderer.CameraOutput(.singleProjection(colorTexture: hdrTexture))
            try engine.updateAndRender(deltaTime: 0, cameraOutput: output,
                                       actionsAfterRender: [.signal(event, value: eventValue)])
            present.encodeWaitForEvent(event, value: eventValue)
            let pass = MTLRenderPassDescriptor()
            pass.colorAttachments[0].texture = drawable.texture
            pass.colorAttachments[0].loadAction = .dontCare
            pass.colorAttachments[0].storeAction = .store
            guard let encoder = present.makeRenderCommandEncoder(descriptor: pass) else { throw CocoaError(.coderInvalidValue) }
            encoder.setRenderPipelineState(displayPipeline)
            encoder.setFragmentTexture(hdrTexture, index: 0)
            encoder.setFragmentTexture(displayLUT, index: 1)
            var transparentExport: UInt32 = 0
#if DEBUG
            if ProcessInfo.processInfo.arguments.contains("--widget-car-export") { transparentExport = 1 }
#endif
            encoder.setFragmentBytes(&transparentExport, length: MemoryLayout<UInt32>.size, index: 0)
            var backdrop = SIMD4<Float>(stageBackdrop, 0)
            encoder.setFragmentBytes(&backdrop, length: MemoryLayout<SIMD4<Float>>.stride, index: 1)
            encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
            encoder.endEncoding()
#if DEBUG
            // Development export from the actual final Metal pass, including
            // its alpha and contact shadow. WidgetKit receives a small bitmap,
            // never the vehicle mesh, lighting maps, or a live GPU renderer.
            if !exportedWidgetCar, warmupUntil > 0, CACurrentMediaTime() >= warmupUntil,
               ProcessInfo.processInfo.arguments.contains("--widget-car-export") {
                let texture = drawable.texture
                let rowBytes = ((texture.width * 4 + 255) / 256) * 256
                if let pixels = device?.makeBuffer(length: rowBytes * texture.height, options: .storageModeShared),
                   let blit = present.makeBlitCommandEncoder() {
                    blit.copy(from: texture, sourceSlice: 0, sourceLevel: 0, sourceOrigin: .init(),
                        sourceSize: .init(width: texture.width, height: texture.height, depth: 1),
                        to: pixels, destinationOffset: 0, destinationBytesPerRow: rowBytes,
                        destinationBytesPerImage: rowBytes * texture.height)
                    blit.endEncoding()
                    exportedWidgetCar = true
                    let width = texture.width, height = texture.height
                    let readback = WidgetCarReadback(buffer: pixels)
                    present.addCompletedHandler { command in
                        guard command.status == .completed else { return }
                        var data = Data(bytes: readback.buffer.contents(), count: rowBytes * height)
                        // The sRGB drawable contains straight-alpha color. PNG
                        // encoding through CoreGraphics expects premultiplied BGRA.
                        data.withUnsafeMutableBytes { bytes in
                            let pixels = bytes.bindMemory(to: UInt8.self)
                            for y in 0..<height {
                                for x in 0..<width {
                                    let offset = y * rowBytes + x * 4
                                    let alpha = UInt32(pixels[offset + 3])
                                    for c in 0..<3 { pixels[offset + c] = UInt8((UInt32(pixels[offset + c]) * alpha + 127) / 255) }
                                }
                            }
                        }
                        guard let provider = CGDataProvider(data: data as CFData),
                              let image = CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
                                  bytesPerRow: rowBytes, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedFirst.rawValue).union(.byteOrder32Little),
                                  provider: provider, decode: nil, shouldInterpolate: true, intent: .defaultIntent),
                              let png = UIImage(cgImage: image).pngData() else { return }
                        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("widget-car.png")
                        try? png.write(to: url, options: .atomic)
                    }
                }
            }
#endif
            present.present(drawable)
            present.addCompletedHandler { [weak self] buffer in
                let completed = buffer.status == .completed
                let error = buffer.error
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.inFlight = false
                    guard completed else {
                        if let error { self.onFailure?(error) }
                        return
                    }
                    let presented = self.onNextPresentation
                    self.onNextPresentation = nil
                    presented?()
                    if CACurrentMediaTime() < self.warmupUntil { self.requested = true }
#if DEBUG
                    if !self.exportedWidgetCar, ProcessInfo.processInfo.arguments.contains("--widget-car-export") {
                        self.requested = true
                    }
#endif
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
        hdrTexture = nil
        displayLUT = nil
        displayPipeline = nil
        opticalBackground = nil
        opticalResource = nil
        configureOptics = nil
        capturedDrawable = nil
        delegate = nil
    }
}
