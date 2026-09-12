import XCTest
@testable import E36Core

final class CompanionTests: XCTestCase {
    let now = Date(timeIntervalSince1970: 1_800_000_000)
    func sample(sequence: UInt64 = 1, offset: Double = 0, source: WidgetSource = .reader) -> CompanionSnapshot {
        let date = now.addingTimeInterval(offset)
        return .init(streamID: "phone-A", sequence: sequence,
                     observation: .init(updatedAt: date, receivedAt: date,
                        telemetry: .init(rpm: 930, load: 0.7, coolant: 63.1, battery: 13.48, ecuMS: 341, intake: 23.7),
                        capture: .recording, alerts: [.lowLoad], source: source),
                     sessionID: "capture-A", startedAt: now, connected: true, phase: "live")
    }
    func testVersionedPayloadPreservesOriginalValuesAndRejectsMalformedData() throws {
        let original = sample()
        XCTAssertEqual(try CompanionSnapshot.decode(original.encoded()), original)
        var future = original; future.version = 2
        XCTAssertThrowsError(try CompanionSnapshot.decode(future.encoded()))
        XCTAssertThrowsError(try CompanionSnapshot.decode(Data(repeating: 32, count: 8193)))
        XCTAssertThrowsError(try CompanionSnapshot.decode(Data("{broken".utf8)))
        var bad = original; bad.observation.telemetry?.rpm = .nan
        XCTAssertThrowsError(try bad.encoded())
        bad = original; bad.sampleCount = -1
        XCTAssertThrowsError(try CompanionSnapshot.decode(bad.encoded()))
    }
    func testInteractiveUpdateWinsOverDelayedContextAndSourcesRemainSeparate() {
        var inbox = CompanionInbox()
        XCTAssertTrue(inbox.accept(sample(sequence: 5, offset: 5)))
        XCTAssertFalse(inbox.accept(sample(sequence: 4, offset: 4)))
        XCTAssertFalse(inbox.accept(sample(sequence: 5, offset: 5)))
        XCTAssertTrue(inbox.accept(sample(sequence: 1, source: .demo)))
        XCTAssertEqual(inbox.snapshot(for: .reader)?.sequence, 5)
        XCTAssertEqual(inbox.snapshot(for: .demo)?.sequence, 1)
        var restarted = sample(sequence: 1, offset: 6); restarted.streamID = "phone-B"
        XCTAssertTrue(inbox.accept(restarted))
        XCTAssertFalse(inbox.accept(sample(sequence: 6, offset: 5.5)))
    }
    func testStalePausedDisconnectedAndEmptyRAMNeverCarryActiveWarnings() {
        var snapshot = sample()
        XCTAssertTrue(snapshot.warning(for: .load, at: now))
        XCTAssertEqual(snapshot.status(at: now), "En vivo")
        XCTAssertFalse(snapshot.warning(for: .load, at: now.addingTimeInterval(2.1)))
        XCTAssertFalse(snapshot.isFresh(at: now.addingTimeInterval(-10)))
        XCTAssertEqual(snapshot.formatted(.load), "0.70")
        snapshot.observation.capture = .paused; snapshot.phase = "faultBarrier"
        XCTAssertFalse(snapshot.isFresh(at: now))
        XCTAssertEqual(snapshot.status(at: now), "Leyendo fallas")
        snapshot.connected = false
        XCTAssertEqual(snapshot.status(at: now), "Reconectando")
        snapshot = sample()
        snapshot.observation.telemetry = .init(rpm: 0, load: 0, coolant: -32.5, battery: 0, ecuMS: 340, intake: -33.5)
        XCTAssertEqual(snapshot.status(at: now), "Motor apagado")
        XCTAssertFalse(snapshot.warning(for: .load, at: now))
        XCTAssertEqual(snapshot.formatted(.rpm), "—")
    }
    func testMissingIntakeAndSaturatedRPMRemainExplicit() {
        var snapshot = sample(); snapshot.observation.telemetry?.intake = nil
        XCTAssertNil(snapshot.value(for: .intake))
        XCTAssertEqual(snapshot.formatted(.intake), "—")
        snapshot.observation.telemetry?.rpm = 2550
        XCTAssertEqual(snapshot.formatted(.rpm), "2550+")
        XCTAssertEqual(snapshot.value(for: .rpm), 2550)
    }
    func testNewCaptureDoesNotReuseThePreviousCapturesReading() {
        var snapshot = sample()
        snapshot.startedAt = now.addingTimeInterval(1)
        XCTAssertNil(snapshot.value(for: .rpm))
        XCTAssertEqual(snapshot.formatted(.battery), "—")
        XCTAssertFalse(snapshot.isFresh(at: now.addingTimeInterval(1)))
        XCTAssertFalse(snapshot.warning(for: .load, at: now.addingTimeInterval(1)))
        snapshot.observation.receivedAt = now.addingTimeInterval(1.2)
        XCTAssertEqual(snapshot.value(for: .rpm), 930)
        XCTAssertTrue(snapshot.isFresh(at: now.addingTimeInterval(1.3)))
        snapshot.observation.capture = .stopped
        XCTAssertEqual(snapshot.status(at: now.addingTimeInterval(2)), "Finalizada")
        XCTAssertFalse(snapshot.warning(for: .load, at: now.addingTimeInterval(2)))
    }
    func testPublicationCoalescesSamplesButDeliversPauseStopAndAlertsImmediately() {
        var policy = CompanionPublicationPolicy()
        XCTAssertTrue(policy.shouldPublish(sample(), at: now, interval: 15))
        XCTAssertFalse(policy.shouldPublish(sample(sequence: 2, offset: 1), at: now.addingTimeInterval(1), interval: 15))
        var pause = sample(sequence: 3, offset: 1.1); pause.observation.capture = .paused
        XCTAssertTrue(policy.shouldPublish(pause, at: now.addingTimeInterval(1.1), interval: 15))
        var stopped = pause; stopped.sessionID = nil; stopped.observation.capture = .stopped
        XCTAssertTrue(policy.shouldPublish(stopped, at: now.addingTimeInterval(1.2), interval: 15))
        var next = sample(sequence: 4, offset: 1.3); next.sessionID = "capture-B"
        XCTAssertTrue(policy.shouldPublish(next, at: now.addingTimeInterval(1.3), interval: 15))
        next.observation.alerts = [.coolant]
        XCTAssertTrue(policy.shouldPublish(next, at: now.addingTimeInterval(1.4), interval: 15))
        XCTAssertFalse(policy.shouldPublish(next, at: now.addingTimeInterval(30), interval: 15))
    }
    func testRequestsExpireInsteadOfStartingALaterCapture() {
        let request = CompanionRequest(action: .start, source: .reader, sentAt: now)
        XCTAssertTrue(request.isValid(at: now.addingTimeInterval(5)))
        XCTAssertFalse(request.isValid(at: now.addingTimeInterval(16)))
        XCTAssertFalse(request.isValid(at: now.addingTimeInterval(-6)))
    }
    func testCacheIsAtomicSourceSeparatedAndRejectsCrossSourceFiles() throws {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: folder) }
        let store = CompanionSnapshotStore(directory: folder)
        XCTAssertNil(try store.read(.reader))
        try store.write(sample()); try store.write(sample(source: .demo))
        XCTAssertEqual(try store.read(.reader), sample())
        XCTAssertEqual(try store.read(.demo), sample(source: .demo))
        try FileManager.default.removeItem(at: store.url(for: .reader))
        try FileManager.default.copyItem(at: store.url(for: .demo), to: store.url(for: .reader))
        XCTAssertThrowsError(try store.read(.reader))
    }
    func testDismissedActivitiesStayDismissedAcrossReconnectsAndNewCaptureCanStart() {
        var policy = CaptureActivityPolicy(); var snapshot = sample()
        XCTAssertFalse(policy.canStart(snapshot, foreground: false, enabled: true))
        XCTAssertFalse(policy.canStart(snapshot, foreground: true, enabled: false))
        XCTAssertTrue(policy.canStart(snapshot, foreground: true, enabled: true))
        policy.suppress("capture-A")
        snapshot.observation.capture = .paused; snapshot.connected = false
        XCTAssertFalse(policy.canStart(snapshot, foreground: true, enabled: true))
        snapshot.sessionID = "capture-B"
        XCTAssertTrue(policy.canStart(snapshot, foreground: true, enabled: true))
        snapshot.observation.capture = .interrupted
        XCTAssertFalse(policy.canStart(snapshot, foreground: true, enabled: true))
        snapshot.sessionID = nil
        XCTAssertFalse(policy.canStart(snapshot, foreground: true, enabled: true))
    }
}
