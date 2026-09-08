import Testing
@testable import E36Core

struct AlertTests {
    func sample(load: Double = 2.76, rpm: Double = 930, coolant: Double = 90, intake: Double? = 28) -> Telemetry {
        Telemetry(rpm: rpm, load: load, coolant: coolant, battery: 13.48, ecuMS: 341, intake: intake)
    }
    @Test func realSingleSampleCutAndHysteresis() {
        var engine = AlertEngine(); let settings = AlertSettings()
        let result = engine.evaluate(sample(load: 0.70), at: 0, settings: settings)
        #expect(result.count == 1); #expect(result.first?.rule == .lowLoad); #expect(result.first?.audible == true)
        #expect(engine.evaluate(sample(load: 0.70), at: 0.4, settings: settings).isEmpty)
        #expect(engine.evaluate(sample(), at: 1, settings: settings).isEmpty)
        _ = engine.evaluate(sample(), at: 2, settings: settings)
        #expect(engine.evaluate(sample(), at: 3, settings: settings).first?.started == false)
        let repeated = engine.evaluate(sample(load: 0.7), at: 3.4, settings: settings)
        #expect(repeated.first?.started == true); #expect(repeated.first?.audible == false)
    }
    @Test func temperaturesRequireContinuousEvidenceAndRearm() {
        var engine = AlertEngine(); let settings = AlertSettings()
        #expect(engine.evaluate(sample(coolant: 110, intake: 60), at: 0, settings: settings).isEmpty)
        #expect(engine.evaluate(sample(coolant: 110, intake: 60), at: 1, settings: settings).isEmpty)
        #expect(engine.evaluate(sample(coolant: 110, intake: 60), at: 2, settings: settings).count == 2)
        for time in 3...7 { #expect(engine.evaluate(sample(), at: Double(time), settings: settings).isEmpty) }
        #expect(engine.evaluate(sample(), at: 8, settings: settings).count == 2)
    }
    @Test func missingDataAndEngineOffSuppressAlerts() {
        var engine = AlertEngine(); let settings = AlertSettings()
        _ = engine.evaluate(sample(coolant: 112), at: 0, settings: settings)
        #expect(engine.evaluate(sample(coolant: 112), at: 4, settings: settings).isEmpty)
        engine.interrupt()
        #expect(engine.evaluate(sample(coolant: 112, intake: nil), at: 5, settings: settings).isEmpty)
        let off = Telemetry(rpm: 0, load: 0, coolant: -32.5, battery: 0, ecuMS: 341, intake: -33.5)
        #expect(engine.evaluate(off, at: 6, settings: settings).isEmpty); #expect(engine.active.isEmpty)
        #expect(engine.evaluate(sample(load: 0.7, rpm: 1600), at: 7, settings: settings).isEmpty)
    }
}
