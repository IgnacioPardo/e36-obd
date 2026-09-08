import XCTest
import E36Core
import CoreBluetooth
@testable import E36OBD

final class AppContractTests: XCTestCase {
    @MainActor func testInitialBLEConnectionUsesDefaultOptions() {
        XCTAssertNil(BluetoothTransport.connectionOptions(delay: 0))
    }

    @MainActor func testReconnectBackoffUsesCoreBluetoothNumber() throws {
        for delay in [1.0, 2, 5, 10, 30] {
            let options = try XCTUnwrap(BluetoothTransport.connectionOptions(delay: delay))
            let number = try XCTUnwrap(options[CBConnectPeripheralOptionStartDelayKey] as? NSNumber)
            XCTAssertEqual(number.doubleValue, delay)
            XCTAssertFalse(["d", "f"].contains(String(cString: number.objCType)),
                           "CoreBluetooth requires integer seconds on the physical iPhone")
            XCTAssertEqual(options.count, 1)
        }
        for delay in [-1.0, .nan, .infinity] {
            XCTAssertNil(BluetoothTransport.connectionOptions(delay: delay))
        }
    }

    func testBluetoothPermissionInBuiltApp() {
        let bundle = Bundle(for: AppDelegate.self)
        XCTAssertFalse((bundle.object(forInfoDictionaryKey: "NSBluetoothAlwaysUsageDescription") as? String ?? "").isEmpty)
        XCTAssertTrue((bundle.object(forInfoDictionaryKey: "UIBackgroundModes") as? [String] ?? []).contains("bluetooth-central"))
    }
    func testProtocolFromFirmware() {
        var decoder = LineDecoder()
        XCTAssertEqual(decoder.receive(Data("D 930 0.70 63.1 13.48 341 23.7\r\n".utf8)).count, 1)
    }
    @MainActor func testDemoFaultsUseHelpBarrier() async {
        let transport = DemoTransport()
        let finished = expectation(description: "Fault response followed by help sentinel")
        var decoder = LineDecoder()
        var lines: [String] = []
        transport.onEvent = { event in
            switch event {
            case .ready: transport.write(.faults)
            case .bytes(let data, _, _):
                for line in decoder.receive(data) {
                    if case .text(let text) = line {
                        lines.append(text)
                        if text == "abriendo sesion..." { transport.write(.help) }
                        if text == "?  esta ayuda" { finished.fulfill() }
                    }
                }
            default: break
            }
        }
        transport.connect(foreground: true, delay: 0)
        await fulfillment(of: [finished], timeout: 3)
        XCTAssertTrue(lines.contains("cod 100  ocurr 50"))
        XCTAssertTrue(lines.contains("  cond 0x72"))
        XCTAssertEqual(lines.last, "?  esta ayuda")
        transport.disconnect()
    }
}
