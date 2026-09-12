import XCTest
import ActivityKit
import E36Core
@testable import E36OBD

final class CompanionContractTests: XCTestCase {
    func testWatchComplicationAndActivityConfigurationAreInBuiltProduct() throws {
        let app = Bundle(for: AppDelegate.self)
        XCTAssertEqual(app.object(forInfoDictionaryKey: "NSSupportsLiveActivities") as? Bool, true)
        let watch = try XCTUnwrap(Bundle(url: app.bundleURL.appendingPathComponent("Watch/E36Watch.app")))
        XCTAssertEqual(watch.object(forInfoDictionaryKey: "WKApplication") as? Bool, true)
        XCTAssertEqual(watch.object(forInfoDictionaryKey: "WKCompanionAppBundleIdentifier") as? String, app.bundleIdentifier)
        let extensionBundle = try XCTUnwrap(Bundle(url: watch.bundleURL.appendingPathComponent("PlugIns/E36WatchWidgets.appex")))
        let info = try XCTUnwrap(extensionBundle.object(forInfoDictionaryKey: "NSExtension") as? [String: Any])
        XCTAssertEqual(info["NSExtensionPointIdentifier"] as? String, "com.apple.widgetkit-extension")
        XCTAssertEqual(watch.object(forInfoDictionaryKey: "MinimumOSVersion") as? String, "11.0")
        #if targetEnvironment(simulator)
        XCTAssertEqual(watch.object(forInfoDictionaryKey: "CFBundleSupportedPlatforms") as? [String], ["WatchSimulator"])
        #else
        XCTAssertEqual(watch.object(forInfoDictionaryKey: "CFBundleSupportedPlatforms") as? [String], ["WatchOS"])
        #endif
    }

    @MainActor func testActivitySurvivesPauseThenEndsWithoutMixingCaptures() async throws {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { throw XCTSkip("Live Activities disabled by this simulator") }
        let suite = "ActivityTest-\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let coordinator = CaptureActivityCoordinator(defaults: defaults)
        let now = Date()
        let id = UUID().uuidString
        var snapshot = CompanionSnapshot(streamID: "test", sequence: 1,
            observation: .init(updatedAt: now, receivedAt: now,
                telemetry: .init(rpm: 930, load: 0.7, coolant: 90, battery: 13.48, ecuMS: 341, intake: 28),
                capture: .recording, source: .demo), sessionID: id, startedAt: now, connected: true, phase: "live")
        await coordinator.update(snapshot, foreground: true, enabled: true)
        let original = try XCTUnwrap(Activity<E36ActivityAttributes>.activities.first { $0.attributes.sessionID == id })
        snapshot.sequence += 1; snapshot.observation.capture = .paused; snapshot.phase = "faultBarrier"
        await coordinator.update(snapshot, foreground: false, enabled: true)
        let pauseDelivered = await eventually { original.content.state.snapshot.phase == "faultBarrier" }
        XCTAssertTrue(pauseDelivered)
        XCTAssertEqual(original.content.state.snapshot.phase, "faultBarrier")
        XCTAssertEqual(Activity<E36ActivityAttributes>.activities.filter { $0.attributes.sessionID == id }.count, 1)
        snapshot.sequence += 1; snapshot.connected = false; snapshot.phase = "disconnected"
        await coordinator.update(snapshot, foreground: false, enabled: true)
        let reconnectDelivered = await eventually { !original.content.state.snapshot.connected }
        XCTAssertTrue(reconnectDelivered)
        XCTAssertEqual(original.content.state.snapshot.status(at: .now), "Reconectando")
        // A second capture has a different primary value. The old activity must
        // end with its own value, even when the newest observation replaces it.
        snapshot.sessionID = UUID().uuidString; snapshot.observation.capture = .recording
        snapshot.observation.telemetry?.rpm = 1700; snapshot.connected = true; snapshot.phase = "live"
        await coordinator.update(snapshot, foreground: true, enabled: true)
        let endDelivered = await eventually { original.content.state.snapshot.observation.capture == .stopped }
        XCTAssertTrue(endDelivered)
        XCTAssertEqual(original.content.state.snapshot.value(for: .rpm), 930)
        XCTAssertEqual(original.content.state.snapshot.observation.capture, .stopped)
        let next = try XCTUnwrap(Activity<E36ActivityAttributes>.activities.first { $0.attributes.sessionID == snapshot.sessionID })
        XCTAssertNotEqual(original.id, next.id)
        snapshot.observation.capture = .interrupted
        await coordinator.update(snapshot, foreground: false, enabled: true)
        let failureDelivered = await eventually { next.content.state.snapshot.observation.capture == .interrupted }
        XCTAssertTrue(failureDelivered)
        XCTAssertEqual(next.content.state.snapshot.observation.capture, .interrupted)
        XCTAssertTrue(next.activityState == .ended || next.activityState == .dismissed)
    }

    @MainActor private func eventually(_ condition: () -> Bool) async -> Bool {
        // ActivityKit returns after submission; observer state arrives later.
        for _ in 0..<100 {
            if condition() { return true }
            try? await Task.sleep(for: .milliseconds(20))
        }
        return condition()
    }
}
