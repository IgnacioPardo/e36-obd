import Foundation
import Testing
@testable import E36Core

struct StoreTests {
    func temporary() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true); return url
    }
    @Test func persistenceRecoveryAndExports() async throws {
        let directory = try temporary(); defer { try? FileManager.default.removeItem(at: directory) }
        let url = directory.appendingPathComponent("test.sqlite")
        let store = try SessionStore(url: url)
        let date = Date(timeIntervalSince1970: 1000)
        let session = try await store.start(at: date, isDemo: false)
        let sample = RecordedSample(sessionID: session.id, receivedAt: date, elapsed: 0,
            telemetry: Telemetry(rpm: 930, load: 0.7, coolant: 63, battery: 13.48, ecuMS: 341), segment: 0)
        let event = SessionEvent(timestamp: date, kind: .alertStarted, message: "Texto, con \"comillas\"\ny acento: tensión", rule: .lowLoad)
        let id = try await store.append(sample, events: [event])
        let reopened = try SessionStore(url: url)
        let restored = try await reopened.recover(restoring: session.id)
        #expect(restored?.sampleCount == 1); #expect(restored?.eventCount == 2)
        #expect(try await reopened.events(sessionID: session.id).last?.sampleID == id)
        let files = try await reopened.export(sessionID: session.id, to: directory.appendingPathComponent("export"))
        let csv = try String(contentsOf: files[0], encoding: .utf8)
        #expect(csv.contains("timestamp,elapsed_s,battery,intake_air_temp,coolant_temp,rpm,load,ecu_ms,validity"))
        #expect(csv.contains(",13.48,,63.0,930.0,0.7,341,populated"))
        #expect(try String(contentsOf: files[1], encoding: .utf8).contains("\"Texto, con \"\"comillas\"\"\ny acento: tensión\""))
        #expect(try await reopened.recover(restoring: nil) == nil)
        #expect(try await reopened.sessions().first?.status == .interrupted)
    }
    @Test func sampleAndEventAreAtomicOnFailure() async throws {
        let directory = try temporary(); defer { try? FileManager.default.removeItem(at: directory) }
        let store = try SessionStore(url: directory.appendingPathComponent("test.sqlite"))
        let session = try await store.start(at: Date(), isDemo: true)
        let event = SessionEvent(sessionID: session.id, kind: .alertStarted, message: "duplicate ID")
        try await store.appendEvent(event)
        let sample = RecordedSample(sessionID: session.id, receivedAt: Date(), elapsed: 1,
            telemetry: Telemetry(rpm: 930, load: 0.7, coolant: 90, battery: 13, ecuMS: 341), segment: 0)
        do { _ = try await store.append(sample, events: [event]); Issue.record("Transaction should fail") }
        catch { #expect(try await store.samples(sessionID: session.id).isEmpty) }
        try await store.finish(session.id, at: Date(), elapsed: 30, message: "Stop during a gap")
        #expect(try await store.sessions().first?.elapsed == 30)
        await #expect(throws: StoreError.self) { try await store.append(sample, events: []) }
    }
    @Test func filesystemFailureIsReported() throws {
        let directory = try temporary(); defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("file")
        try Data("not a directory".utf8).write(to: file)
        #expect(throws: (any Error).self) { try SessionStore(url: file.appendingPathComponent("test.sqlite")) }
    }
    @Test func graphReductionRetainsDipAndBreaks() {
        var samples: [RecordedSample] = []
        for index in 0..<2000 {
            samples.append(RecordedSample(id: Int64(index + 1), sessionID: "test", receivedAt: Date(),
                elapsed: Double(index) * 0.4 + (index >= 1000 ? 20 : 0),
                telemetry: Telemetry(rpm: 930, load: index == 503 ? 0.7 : 2.76, coolant: 90, battery: 13, ecuMS: 341),
                segment: index >= 1000 ? 1 : 0))
        }
        let points = GraphSeries.points(samples, sensor: .load, budget: 80, preserving: [700])
        #expect(points.contains { $0.value == 0.7 }); #expect(points.contains { $0.id == 700 })
        #expect(points.contains { $0.id == 1000 }); #expect(points.contains { $0.id == 1001 })
        #expect(points.first?.segment != points.last?.segment)
        #expect(GraphSeries.nearest(samples, elapsed: 201.2)?.id == 504)
    }
}
