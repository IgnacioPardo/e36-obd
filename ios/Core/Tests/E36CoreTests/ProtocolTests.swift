import Foundation
import Testing
@testable import E36Core

struct ProtocolTests {
    let line = "D 930 0.70 63.1 13.48 341 23.7\r\n"
    @Test func everySplitAndSingleBytes() {
        let bytes = Array(line.utf8)
        for split in 0...bytes.count {
            var decoder = LineDecoder()
            let output = decoder.receive(Data(bytes[..<split])) + decoder.receive(Data(bytes[split...]))
            #expect(output == [.sample(Telemetry(rpm: 930, load: 0.7, coolant: 63.1, battery: 13.48, ecuMS: 341, intake: 23.7))])
        }
        var decoder = LineDecoder(); var output: [DecodedLine] = []
        for byte in bytes { output += decoder.receive(Data([byte])) }
        #expect(output.count == 1)
    }
    @Test func unicodeAndMultipleLines() {
        var decoder = LineDecoder(); var result: [DecodedLine] = []
        let bytes = Array(("temperatura y tensión\r\n" + line + "detenido\n").utf8)
        for offset in stride(from: 0, to: bytes.count, by: 20) {
            result += decoder.receive(Data(bytes[offset..<min(offset + 20, bytes.count)]))
        }
        #expect(result.count == 3); #expect(result.first == .text("temperatura y tensión"))
        #expect(result.last == .text("detenido"))
    }
    @Test func legacyAndInvalidNumbers() {
        if case .sample(let sample) = LineDecoder.parse("D 892 2.76 58.5 13.48 341") { #expect(sample.intake == nil) }
        else { Issue.record("Legacy message rejected") }
        for bad in ["D 890 nan 90 13 341", "D 890 2.7 inf 13 341", "D 890 2.7 90 13 0", "D 890 2.7 90 13 341 nan",
                    "D 890.5 2.7 90 13 341", "D -1 2.7 90 13 341", "D 2551 2.7 90 13 341", "D 890 2.7 90 13 341 20 extra"] {
            #expect(LineDecoder.parse(bad) == .invalid(bad))
        }
    }
    @Test func overflowAndConnectionReset() {
        var decoder = LineDecoder()
        let output = decoder.receive(Data((String(repeating: "x", count: 5000) + "\n" + line).utf8))
        #expect(output.count == 2)
        if case .invalid = output[0] {} else { Issue.record("Missing overflow event") }
        _ = decoder.receive(Data("D 100 ".utf8)); decoder.reset()
        #expect(decoder.receive(Data(line.utf8)).count == 1)
        decoder.reset(discardPartial: true)
        #expect(decoder.receive(Data(("broken remainder\n" + line).utf8)).count == 1)
    }
    @Test func zeroRAMIsNotTemperatureAndSaturation() {
        #expect(Telemetry(rpm: 0, load: 0, coolant: -32.5, battery: 0, ecuMS: 341, intake: -33.5).validity == .unpopulated)
        #expect(Telemetry(rpm: 0, load: 0, coolant: 0, battery: 0, ecuMS: 341).validity == .unpopulated)
        #expect(Telemetry(rpm: 0, load: 0, coolant: 90, battery: 13, ecuMS: 341).validity == .populated)
        #expect(Telemetry(rpm: 2550, load: 3, coolant: 90, battery: 13, ecuMS: 341).saturated)
    }
    @Test func effectiveRateUsesArrivalTimes() {
        var rate = ReceptionRate()
        for index in 0..<20 { rate.receive(at: Double(index) * 0.4) }
        #expect(abs((rate.hz ?? 0) - 2.5) < 0.001)
        rate.receive(at: 40); #expect(rate.hz == nil)
    }
    @Test func faultsPreserveOnlyRealDescriptions() {
        var report = FaultReport()
        for text in ["abriendo sesion...", "cod 100  ocurr 50", "  cond 0x68", "  Texto original", "cod 36  ocurr 50", "  cond 0x72",
                     "=== E36 M43B16 ===", "?  esta ayuda"] { report.receive(text) }
        #expect(report.records.count == 2); #expect(report.records[0].detail == "Texto original")
        #expect(report.records[1].condition == "0x72"); #expect(report.records[1].detail.isEmpty)
        #expect(!report.lines.contains("?  esta ayuda"))
    }
}
