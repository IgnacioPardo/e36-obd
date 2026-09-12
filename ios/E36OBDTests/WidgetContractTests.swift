import XCTest
import E36Core
@testable import E36OBD

final class WidgetContractTests: XCTestCase {
    func testWidgetExtensionIsEmbeddedInTheApp() throws {
        let app = Bundle(for: AppDelegate.self)
        let directory = try XCTUnwrap(app.builtInPlugInsURL).appendingPathComponent("E36OBDWidgets.appex")
        let widget = try XCTUnwrap(Bundle(url: directory))
        XCTAssertEqual(widget.bundleIdentifier, "com.ignaciopardo.e36obd.widgets")
        let extensionInfo = try XCTUnwrap(widget.object(forInfoDictionaryKey: "NSExtension") as? [String: Any])
        XCTAssertEqual(extensionInfo["NSExtensionPointIdentifier"] as? String, "com.apple.widgetkit-extension")
        XCTAssertEqual(widget.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String,
                       app.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String)
        let car = try XCTUnwrap(UIImage(named: "WidgetCar", in: widget, compatibleWith: nil))
        XCTAssertGreaterThan(try XCTUnwrap(car.cgImage).width, 500)
        XCTAssertNil(widget.url(forResource: "E36-316i", withExtension: "usdz", subdirectory: "VehicleScene"),
                     "Widgets ship the bounded render, not the vehicle geometry")
    }
    func testPublisherWritesTheSharedAppGroup() async throws {
        let group = try XCTUnwrap(FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: WidgetSnapshotStore.appGroup))
        let store = WidgetSnapshotStore(directory: group)
        let now = Date()
        let snapshot = WidgetSnapshot(updatedAt: now, receivedAt: now,
            telemetry: Telemetry(rpm: 930, load: 0.7, coolant: 63.1, battery: 13.48, ecuMS: 341, intake: 23.7),
            capture: .recording, alerts: [.lowLoad], source: .demo)
        let publisher = WidgetPublisher()
        try await publisher.publish(snapshot, foreground: true)
        let result = try XCTUnwrap(store.read(.demo))
        XCTAssertEqual(result.telemetry, snapshot.telemetry)
        XCTAssertEqual(result.capture, .recording)
        XCTAssertEqual(result.receivedAt!.timeIntervalSince1970, now.timeIntervalSince1970, accuracy: 0.001)
    }
}
