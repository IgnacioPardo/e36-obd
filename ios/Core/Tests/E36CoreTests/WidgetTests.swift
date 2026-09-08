import XCTest
@testable import E36Core

final class WidgetTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)
    private func sample(source: WidgetSource = .reader, offset: Double = 0) -> WidgetSnapshot {
        WidgetSnapshot(updatedAt: now.addingTimeInterval(offset), receivedAt: now.addingTimeInterval(offset),
            telemetry: Telemetry(rpm: 930, load: 0.7, coolant: 63.1, battery: 13.48, ecuMS: 341, intake: 23.7),
            capture: .recording, alerts: [.lowLoad], source: source)
    }
    func testAtomicSnapshotPreservesChannelsAndSeparatesDemo() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = WidgetSnapshotStore(directory: directory)
        XCTAssertNil(try store.read(.reader))
        try store.write(sample())
        var demo = sample(source: .demo); demo.telemetry?.coolant = 112
        try store.write(demo)
        XCTAssertEqual(try store.read(.reader), sample())
        XCTAssertEqual(try store.read(.demo), demo)
        var next = sample(offset: 1); next.capture = .interrupted
        try store.write(next)
        XCTAssertEqual(try store.read(.reader)?.capture, .interrupted)
        XCTAssertEqual(try store.read(.reader)?.value(for: .intake), 23.7)
    }
    func testCorruptIncompatibleAndCrossSourceSnapshotsAreRejected() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = WidgetSnapshotStore(directory: directory)
        var future = sample(); future.version = 99
        try store.write(future)
        XCTAssertThrowsError(try store.read(.reader))
        try Data("{partial".utf8).write(to: store.url(for: .reader))
        XCTAssertThrowsError(try store.read(.reader))
        try store.write(sample(source: .demo))
        try FileManager.default.removeItem(at: store.url(for: .reader))
        try FileManager.default.copyItem(at: store.url(for: .demo), to: store.url(for: .reader))
        XCTAssertThrowsError(try store.read(.reader))
    }
    func testUnavailableChannelsAndEngineOffDoNotInventReadings() {
        var snapshot = sample(); snapshot.telemetry?.intake = nil
        XCTAssertNil(snapshot.value(for: .intake))
        snapshot.telemetry = Telemetry(rpm: 0, load: 0, coolant: -32.5, battery: 0, ecuMS: 341, intake: -33.5)
        for sensor in Sensor.allCases { XCTAssertNil(snapshot.value(for: sensor)) }
        XCTAssertEqual(snapshot.observationLabel(at: now), "Motor apagado")
        snapshot.telemetry?.rpm = .infinity
        XCTAssertNil(snapshot.value(for: .rpm))
    }
    func testObservationAgeNeverClaimsAContinuousLiveRecording() {
        let snapshot = sample()
        XCTAssertEqual(snapshot.observationLabel(at: now), "Muestra")
        XCTAssertFalse(snapshot.isOld(at: now.addingTimeInterval(299)))
        XCTAssertTrue(snapshot.isOld(at: now.addingTimeInterval(300)))
        XCTAssertEqual(snapshot.observationLabel(at: now.addingTimeInterval(3600)), "Anterior")
        XCTAssertTrue(snapshot.isOld(at: now.addingTimeInterval(-60)))
        XCTAssertEqual(snapshot.value(for: .rpm), 930)
    }
    func testPublicationCoalescesSamplesAndBudgetsBackgroundReloads() {
        var policy = WidgetPublicationPolicy()
        XCTAssertTrue(policy.decision(for: sample(), foreground: false).reload)
        XCTAssertFalse(policy.decision(for: sample(offset: 0.3), foreground: false).write)
        let second = policy.decision(for: sample(offset: 1), foreground: false)
        XCTAssertTrue(second.write); XCTAssertFalse(second.reload)
        XCTAssertFalse(policy.decision(for: sample(offset: 60), foreground: false).reload)
        XCTAssertTrue(policy.decision(for: sample(offset: 300), foreground: false).reload)
        var stopped = sample(offset: 300.1); stopped.capture = .stopped
        XCTAssertTrue(policy.decision(for: stopped, foreground: false).reload)
        XCTAssertTrue(policy.decision(for: sample(offset: -10), foreground: false).reload)
    }
    func testForegroundAndWarningChangesRequestNewSnapshots() {
        var policy = WidgetPublicationPolicy()
        _ = policy.decision(for: sample(), foreground: true)
        XCTAssertFalse(policy.decision(for: sample(offset: 10), foreground: true).reload)
        XCTAssertTrue(policy.decision(for: sample(offset: 15), foreground: true).reload)
        var warning = sample(offset: 15.1); warning.alerts = [.coolant]
        XCTAssertTrue(policy.decision(for: warning, foreground: true).reload)
        var off = sample(offset: 15.2); off.telemetry = Telemetry(rpm: 0, load: 0, coolant: 0, battery: 0, ecuMS: 2, intake: 0)
        XCTAssertTrue(policy.decision(for: off, foreground: true).reload)
    }
}
