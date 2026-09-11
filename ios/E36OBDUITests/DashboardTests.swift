import XCTest

@MainActor final class DashboardTests: XCTestCase {
    private func launch() -> XCUIApplication {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        app.launchArguments = ["--demo", "--uitesting"]
        app.launch()
        let live = app.buttons["liveButton"]
        XCTAssertTrue(live.waitForExistence(timeout: 10))
        expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: live)
        waitForExpectations(timeout: 10)
        live.tap()
        XCTAssertTrue(app.staticTexts["recordingIndicator"].waitForExistence(timeout: 10))
        return app
    }
    private func element(_ id: String, in app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: id).firstMatch
    }
    private func scenario(_ name: String, in app: XCUIApplication) {
        app.buttons["demoScenario"].tap()
        app.buttons[name].tap()
    }
    private func waitLabel(_ text: String, on element: XCUIElement, timeout: Double = 8) {
        expectation(for: NSPredicate(format: "label CONTAINS %@", text), evaluatedWith: element)
        waitForExpectations(timeout: timeout)
    }
    private func closePanel(_ app: XCUIApplication) { app.buttons["closePanelButton"].tap() }
    private func orbitToRear(_ car: XCUIElement) {
        // swipeLeft's distance varies with the viewport and can stop at the
        // side. Use a measured drag to test the intended rear camera state.
        car.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5))
            .press(forDuration: 0.05, thenDragTo: car.coordinate(withNormalizedOffset: CGVector(dx: 0.1, dy: 0.5)))
    }
    private func frames(_ app: XCUIApplication) -> [String: CGRect] {
        let sensors = ["rpm", "load", "coolant"] + (app.otherElements["gauge-battery"].exists ? ["battery"] : [])
        return Dictionary(uniqueKeysWithValues: sensors.map { ($0, app.otherElements["gauge-\($0)"].frame) })
    }
    private func assertFrames(_ expected: [String: CGRect], _ app: XCUIApplication, file: StaticString = #filePath, line: UInt = #line) {
        for (sensor, frame) in expected {
            let actual = app.otherElements["gauge-\(sensor)"].frame
            XCTAssertEqual(actual.minX, frame.minX, accuracy: 0.5, file: file, line: line)
            XCTAssertEqual(actual.minY, frame.minY, accuracy: 0.5, file: file, line: line)
            XCTAssertEqual(actual.width, frame.width, accuracy: 0.5, file: file, line: line)
            XCTAssertEqual(actual.height, frame.height, accuracy: 0.5, file: file, line: line)
        }
    }

    func testFailedFaultReadDoesNotClaimZeroFaults() {
        let app = launch()
        app.buttons["liveButton"].tap()
        waitLabel("Conectado · detenido", on: app.buttons["connectButton"])
        scenario("DME sin respuesta", in: app)
        app.buttons["faultsTab"].tap()
        let read = app.buttons["readFaultsButton"]
        XCTAssertTrue(read.waitForExistence(timeout: 5))
        read.tap()
        let error = app.staticTexts["faultReadError"]
        XCTAssertTrue(error.waitForExistence(timeout: 5))
        waitLabel("sin respuesta de la ECU", on: error)
        expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: read)
        waitForExpectations(timeout: 5)
        XCTAssertFalse(app.staticTexts["faultsComplete"].exists)
        XCTAssertFalse(app.staticTexts["0 registros"].exists)
        capture("Fault read · ECU unavailable")
    }

    func testVehicleOverviewAndInstrumentsShareTheSameCapture() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        app.launchArguments = ["--demo", "--uitesting"]
        app.launch()
        XCTAssertTrue(element("vehicleOverview", in: app).waitForExistence(timeout: 10))
        let car = element("vehicle3D", in: app)
        XCTAssertTrue(car.waitForExistence(timeout: 10))
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 45)
        car.pinch(withScale: 1.2, velocity: 1)
        capture("Vehicle · native 3D zoom")
        car.doubleTap()
        orbitToRear(car)
        expectation(for: NSPredicate(format: "value == %@", "Vista trasera"), evaluatedWith: car)
        waitForExpectations(timeout: 5)
        capture("Vehicle · orbit")
        car.doubleTap()
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 5)
        capture("Vehicle · overview")
        let live = app.buttons["liveButton"]
        expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: live)
        waitForExpectations(timeout: 10)
        live.tap()
        XCTAssertTrue(app.otherElements["gauge-rpm"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["recordingIndicator"].waitForExistence(timeout: 5))
        app.buttons["vehicleTab"].tap()
        XCTAssertTrue(element("vehicleOverview", in: app).waitForExistence(timeout: 5))
        XCTAssertEqual(live.label, "Detener")
        capture("Vehicle · live overview")
        let liveCar = element("vehicle3D", in: app)
        orbitToRear(liveCar)
        expectation(for: NSPredicate(format: "value == %@", "Vista trasera"), evaluatedWith: liveCar)
        waitForExpectations(timeout: 5)
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(app.buttons["overviewInstrumentsButton"].waitForExistence(timeout: 5))
        let landscapeCar = element("vehicle3D", in: app)
        expectation(for: NSPredicate(format: "value == %@", "Vista trasera"), evaluatedWith: landscapeCar)
        waitForExpectations(timeout: 5)
        landscapeCar.doubleTap()
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: landscapeCar)
        waitForExpectations(timeout: 5)
        capture("Vehicle · landscape")
        app.buttons["overviewInstrumentsButton"].tap()
        XCTAssertTrue(app.otherElements["gauge-rpm"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["recordingIndicator"].exists)
        live.tap()
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["sessionRow"].firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["sessionCount"].label, "1 captura")
    }

    // Visual review artifacts come from the shipped Metal renderer and geometry,
    // using the same cameras as the reference photographs in the authoring scene.
    func testVehicleReferenceCameraScreenshots() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        for preset in ["nose", "rear", "side"] {
            app.launchArguments = ["--demo", "--uitesting", "--vehicle-review=\(preset)"]
            app.launch()
            let car = element("vehicle3D", in: app)
            XCTAssertTrue(car.waitForExistence(timeout: 10))
            expectation(for: NSPredicate(format: "value == %@", "Referencia \(preset)"), evaluatedWith: car)
            waitForExpectations(timeout: 45)
            let attachment = XCTAttachment(screenshot: car.screenshot())
            attachment.name = "Metal reference · \(preset)"
            attachment.lifetime = .keepAlways
            add(attachment)
            app.terminate()
        }
    }

    func testCaptureBothOrientationsFaultsAndHistory() {
        let app = launch()
        XCTAssertTrue(element("reading-battery", in: app).waitForExistence(timeout: 5))
        capture("Cockpit · portrait")
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(app.otherElements["gauge-battery"].waitForExistence(timeout: 5))
        let landscapeFrames = frames(app)
        let intake = element("reading-intake", in: app).frame
        let recording = app.staticTexts["recordingIndicator"].frame
        let control = app.buttons["liveButton"].frame
        XCTAssertGreaterThanOrEqual(intake.minY, control.minY)
        XCTAssertLessThanOrEqual(intake.maxY, control.maxY)
        XCTAssertGreaterThanOrEqual(recording.minY, control.minY)
        XCTAssertLessThanOrEqual(recording.maxY, control.maxY)
        XCTAssertLessThan(app.otherElements["gauge-rpm"].frame.maxY, control.minY)
        capture("Cockpit · landscape")
        app.buttons["faultsTab"].tap()
        let read = app.buttons["readFaultsButton"]
        XCTAssertTrue(read.waitForExistence(timeout: 5)); read.tap()
        XCTAssertTrue(app.staticTexts["faultsComplete"].waitForExistence(timeout: 10))
        XCTAssertTrue(element("fault-code-100", in: app).exists)
        capture("DME inspector")
        closePanel(app)
        assertFrames(landscapeFrames, app)
        XCTAssertTrue(app.staticTexts["recordingIndicator"].exists)
        app.buttons["liveButton"].tap()
        XCUIDevice.shared.orientation = .portrait
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["sessionRow"].firstMatch.waitForExistence(timeout: 10))
        XCTAssertEqual(app.staticTexts["sessionCount"].label, "1 captura")
        app.buttons["sessionRow"].firstMatch.tap()
        XCTAssertTrue(app.buttons["exportSessionButton"].waitForExistence(timeout: 10))
        capture("Session · aligned traces")
        app.buttons["exportSessionButton"].tap()
        XCTAssertTrue(app.otherElements["ActivityListView"].waitForExistence(timeout: 5))
        capture("CSV export")
    }

    func testInstrumentsStayAnchoredAcrossWarningsPanelsAndReconnection() {
        let app = launch()
        let reference = frames(app)
        scenario("Carga baja", in: app)
        let warning = element("activeAlert", in: app)
        XCTAssertTrue(warning.waitForExistence(timeout: 5))
        waitLabel("Carga baja", on: warning)
        assertFrames(reference, app)
        capture("Fixed warning strip")
        scenario("Temperatura", in: app)
        waitLabel("Refrigerante alto", on: warning)
        waitLabel("Admisión alta", on: warning)
        assertFrames(reference, app)
        capture("Two simultaneous warnings")
        scenario("Motor apagado", in: app)
        waitLabel("Motor apagado", on: app.buttons["connectButton"])
        XCTAssertFalse(warning.exists)
        assertFrames(reference, app)
        scenario("Saturación", in: app)
        XCTAssertTrue(element("saturationIndicator", in: app).waitForExistence(timeout: 5))
        assertFrames(reference, app)
        scenario("Desconexión", in: app)
        expectation(for: NSPredicate(format: "value == %@", "Ralentí"), evaluatedWith: app.buttons["demoScenario"])
        waitForExpectations(timeout: 5)
        waitLabel("Recibiendo sensores", on: app.buttons["connectButton"], timeout: 10)
        assertFrames(reference, app)
        for tab in ["settingsTab", "sessionsTab", "connectButton"] {
            app.buttons[tab].tap()
            XCTAssertTrue(app.buttons["closePanelButton"].waitForExistence(timeout: 5))
            if tab == "settingsTab" { capture("Settings · essentials") }
            closePanel(app)
            assertFrames(reference, app)
        }
        for id in ["liveButton", "faultsTab", "sessionsTab", "settingsTab", "connectButton", "demoScenario"] {
            XCTAssertGreaterThanOrEqual(app.buttons[id].frame.height, 44)
            XCTAssertGreaterThanOrEqual(app.buttons[id].frame.width, 44)
        }
        app.terminate()
        app.launchArguments = ["--demo", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        app.buttons["sessionsTab"].tap()
        let row = app.buttons["sessionRow"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        XCTAssertEqual(app.buttons.matching(identifier: "sessionRow").count, 1)
        XCTAssertEqual(app.staticTexts["sessionCount"].label, "1 captura")
        XCTAssertTrue(row.label.contains("Interrumpida"))
        capture("Recovery · accessibility text")
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
