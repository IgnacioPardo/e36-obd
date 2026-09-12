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
        app.buttons["instrumentsTab"].tap()
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

    func testPersistentCarAcrossFourTabsAndEdgeToEdgeScene() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        app.launchArguments = ["--demo", "--uitesting"]
        app.launch()
        let car = element("vehicle3D", in: app)
        XCTAssertTrue(car.waitForExistence(timeout: 10))
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 45)
        let originalFrame = car.frame
        XCTAssertEqual(originalFrame.minX, 0, accuracy: 1)
        XCTAssertEqual(originalFrame.width, app.windows.firstMatch.frame.width, accuracy: 1)
        let live = app.buttons["liveButton"]
        expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: live)
        waitForExpectations(timeout: 10)
        live.tap()
        XCTAssertTrue(app.buttons["vehicleTab"].isSelected)
        XCTAssertFalse(app.buttons["instrumentsTab"].isSelected)
        for (tab, facing) in [("vehicleTab", "Vista delantera"), ("faultsTab", "Vista delantera"),
                              ("sessionsTab", "Vista trasera"), ("settingsTab", "Vista trasera")] {
            app.buttons[tab].tap()
            expectation(for: NSPredicate(format: "value == %@", facing), evaluatedWith: car)
            waitForExpectations(timeout: 8)
            XCTAssertEqual(app.descendants(matching: .any).matching(identifier: "vehicle3D").count, 1)
            XCTAssertTrue(car.isHittable)
            XCTAssertEqual(car.frame, originalFrame, "Tabs keep a single, stationary scene viewport")
            XCTAssertTrue(app.buttons[tab].isSelected)
            XCTAssertEqual(live.label, "Detener")
            XCTAssertLessThan(live.frame.maxY, car.frame.minY)
            XCTAssertLessThan(app.buttons["instrumentsTab"].frame.maxY, car.frame.minY)
            XCTAssertLessThan(app.buttons["connectButton"].frame.maxY, car.frame.minY)
            capture("Shared scene · \(tab) portrait")
        }
        XCUIDevice.shared.orientation = .landscapeLeft
        expectation(for: NSPredicate { object, _ in
            guard let window = object as? XCUIElement else { return false }
            return window.frame.width > window.frame.height
        }, evaluatedWith: app.windows.firstMatch)
        waitForExpectations(timeout: 10)
        let landscapeFrame = car.frame
        XCTAssertEqual(landscapeFrame.minX, 0, accuracy: 1, "Landscape scene reaches the screen edge")
        for (tab, facing) in [("vehicleTab", "Vista delantera"), ("faultsTab", "Vista delantera"),
                              ("sessionsTab", "Vista trasera"), ("settingsTab", "Vista trasera")] {
            app.buttons[tab].tap()
            expectation(for: NSPredicate(format: "value == %@", facing), evaluatedWith: car)
            waitForExpectations(timeout: 8)
            XCTAssertTrue(car.isHittable)
            XCTAssertEqual(car.frame, landscapeFrame)
            XCTAssertEqual(live.label, "Detener")
            capture("Shared scene · \(tab) landscape")
        }
        app.buttons["instrumentsTab"].tap()
        XCTAssertTrue(app.otherElements["gauge-rpm"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["recordingIndicator"].exists)
        app.buttons["instrumentsTab"].tap()
        XCTAssertTrue(app.buttons["settingsTab"].isSelected, "Closing instruments returns to the selected page")
        XCTAssertTrue(car.isHittable)
        XCTAssertEqual(car.value as? String, "Vista trasera")
        live.tap()
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["sessionRow"].firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["sessionCount"].label, "1 captura")
    }

    func testExpandedCameraHasFreeZoomOrbitAndRestoresDashboardFraming() throws {
        let app = launch()
        app.buttons["vehicleTab"].tap()
        let car = element("vehicle3D", in: app)
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 45)
        let dashboardFrame = car.frame
        app.buttons["expandVehicleButton"].tap()
        let reset = app.buttons["resetVehicleCameraButton"]
        XCTAssertTrue(reset.waitForExistence(timeout: 5))
        func settleCamera() {
            var previous = ""
            var changed = Date()
            expectation(for: NSPredicate { _, _ in
                let value = car.value as? String ?? ""
                if value != previous { previous = value; changed = Date(); return false }
                return Date().timeIntervalSince(changed) > 0.6
            }, evaluatedWith: car)
            waitForExpectations(timeout: 8)
        }
        func distance() throws -> Double {
            let description = try XCTUnwrap(car.value as? String)
            let tail = try XCTUnwrap(description.components(separatedBy: "Distancia ").last)
            return try XCTUnwrap(Double(tail.components(separatedBy: " m").first ?? ""))
        }
        let initial = try distance()
        car.pinch(withScale: 2.5, velocity: 2)
        let near = try distance()
        XCTAssertLessThan(near, initial * 0.65, "Expanded zoom is no longer constrained by the whole-car fit")
        capture("Free camera · detail zoom")
        let beforeVertical = car.value as? String
        car.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.35))
            .press(forDuration: 0.05, thenDragTo: car.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.60)), withVelocity: .slow, thenHoldForDuration: 0.2)
        XCTAssertNotEqual(car.value as? String, beforeVertical, "A vertical one-finger drag changes elevation")
        XCTAssertEqual(try distance(), near, accuracy: 0.02, "Orbit must not auto-fit away the close-up")
        XCUIDevice.shared.orientation = .landscapeLeft
        expectation(for: NSPredicate { _, _ in app.windows.firstMatch.frame.width > app.windows.firstMatch.frame.height }, evaluatedWith: car)
        waitForExpectations(timeout: 10)
        XCTAssertEqual(try distance(), near, accuracy: 0.02)
        capture("Free camera · landscape orbit")
        reset.tap()
        expectation(for: NSPredicate(format: "value BEGINSWITH %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 10)
        settleCamera()
        let fitted = try distance()
        car.pinch(withScale: 0.25, velocity: -2)
        XCTAssertGreaterThan(try distance(), fitted * 2, "Expanded zoom also allows moving well away from the car")
        reset.tap()
        settleCamera()
        capture("Free camera · reset")
        app.buttons["closeVehicleButton"].tap()
        XCUIDevice.shared.orientation = .portrait
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 10)
        XCTAssertEqual(car.frame, dashboardFrame)
        XCTAssertEqual(app.descendants(matching: .any).matching(identifier: "vehicle3D").count, 1)
        XCTAssertEqual(app.buttons["liveButton"].label, "Detener")
        capture("Free camera · dashboard restored")
        // Tab navigation can also close free mode; retain the ordered route
        // and a single renderer instead of leaking the free zoom/translation.
        app.buttons["expandVehicleButton"].tap()
        car.pinch(withScale: 2, velocity: 2)
        app.buttons["settingsTab"].tap()
        expectation(for: NSPredicate(format: "value == %@", "Vista trasera"), evaluatedWith: car)
        waitForExpectations(timeout: 10)
        XCTAssertTrue(app.buttons["expandVehicleButton"].exists)
        XCTAssertFalse(app.buttons["resetVehicleCameraButton"].exists)
        XCTAssertEqual(car.frame, dashboardFrame)
        app.buttons["liveButton"].tap()
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
        XCTAssertTrue(element("vehicleOverview", in: app).isHittable, "Starting capture does not leave the selected tab")
        app.buttons["instrumentsTab"].tap()
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

    func testExteriorKeepsCaptureAndCameraAcrossNavigation() {
        let app = launch()
        app.buttons["vehicleTab"].tap()
        let car = element("vehicle3D", in: app)
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 45)
        app.buttons["expandVehicleButton"].tap()
        XCTAssertTrue(app.buttons["closeVehicleButton"].waitForExistence(timeout: 5))
        app.buttons["vehicleSideButton"].tap()
        expectation(for: NSPredicate(format: "value BEGINSWITH %@", "Vista lateral"), evaluatedWith: car)
        waitForExpectations(timeout: 10)
        capture("Exterior · portrait")
        XCUIDevice.shared.orientation = .landscapeLeft
        expectation(for: NSPredicate { object, _ in
            guard let window = object as? XCUIElement else { return false }
            return window.frame.width > window.frame.height
        }, evaluatedWith: app.windows.firstMatch)
        waitForExpectations(timeout: 10)
        app.buttons["vehicleRearButton"].tap()
        expectation(for: NSPredicate(format: "value BEGINSWITH %@", "Vista trasera"), evaluatedWith: car)
        waitForExpectations(timeout: 10)
        capture("Exterior · landscape")
        XCTAssertEqual(app.buttons["liveButton"].label, "Detener")
        for id in ["closeVehicleButton", "vehicleFrontButton", "vehicleSideButton", "vehicleRearButton"] {
            XCTAssertGreaterThanOrEqual(app.buttons[id].frame.height, 44)
            XCTAssertGreaterThanOrEqual(app.buttons[id].frame.width, 44)
        }
        app.buttons["closeVehicleButton"].tap()
        app.buttons["instrumentsTab"].tap()
        XCTAssertTrue(app.staticTexts["recordingIndicator"].waitForExistence(timeout: 5))
        app.buttons["vehicleTab"].tap()
        expectation(for: NSPredicate(format: "value == %@", "Vista trasera"), evaluatedWith: car)
        waitForExpectations(timeout: 10)
        app.buttons["liveButton"].tap()
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["sessionRow"].firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["sessionCount"].label, "1 captura")
        capture("Sessions · landscape archive")
        XCUIDevice.shared.orientation = .portrait
        XCTAssertTrue(app.buttons["sessionRow"].firstMatch.waitForExistence(timeout: 5))
        capture("Sessions · portrait archive")
    }

    func testOverviewAtAccessibilityTextSize() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        app.launchArguments = ["--demo", "--uitesting", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        let live = app.buttons["liveButton"]
        expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: live)
        waitForExpectations(timeout: 10)
        live.tap()
        app.buttons["instrumentsTab"].tap()
        XCTAssertTrue(app.staticTexts["recordingIndicator"].waitForExistence(timeout: 10))
        app.buttons["vehicleTab"].tap()
        let car = element("vehicle3D", in: app)
        expectation(for: NSPredicate(format: "value == %@", "Vista delantera"), evaluatedWith: car)
        waitForExpectations(timeout: 45)
        capture("Overview · accessibility text")
        app.scrollViews.firstMatch.swipeUp()
        let instruments = app.buttons["overviewInstrumentsButton"]
        XCTAssertTrue(instruments.isHittable)
        XCTAssertTrue((instruments.value as? String)?.contains("13.48 V") == true)
        capture("Telemetry · accessibility text")
        instruments.tap()
        XCTAssertTrue(app.otherElements["gauge-rpm"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["recordingIndicator"].exists)
        live.tap()
        app.buttons["settingsTab"].tap()
        XCTAssertTrue(app.sliders["Refrigerante"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.sliders["Refrigerante"].isHittable)
        app.sliders["Refrigerante"].adjust(toNormalizedSliderPosition: 0.8)
        XCUIDevice.shared.orientation = .landscapeLeft
        let settingsScroll = element("settingsPage", in: app).scrollViews.firstMatch
        let save = app.buttons["saveSettingsButton"]
        // A fast flick can skip a 44 pt action in this short viewport.
        // Drag towards the actual target and hold before lifting to stop inertia.
        for _ in 0..<24 {
            if save.isHittable { break }
            let viewport = settingsScroll.frame
            let difference = save.frame.midY - viewport.midY
            let distance = min(max(abs(difference), 24), viewport.height * 0.55)
            let direction: CGFloat = difference > 0 ? -1 : 1
            let start = settingsScroll.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5 - direction * distance / viewport.height / 2))
            let end = start.withOffset(CGVector(dx: 0, dy: direction * distance))
            start.press(forDuration: 0.05, thenDragTo: end, withVelocity: .slow, thenHoldForDuration: 0.2)
        }
        XCTAssertTrue(save.isHittable, "Settings stay reachable beside the car at the largest text size")
        capture("Shared scene · accessibility settings landscape")
    }

    // Visual review artifacts come from the shipped Metal renderer and geometry,
    // using the same cameras as the reference photographs in the authoring scene.
    func testVehicleReferenceCameraScreenshots() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        for preset in ["nose", "rear", "side", "optics", "cabin", "apron"] {
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
        XCTAssertGreaterThan(intake.minY, control.maxY)
        XCTAssertGreaterThan(recording.minY, control.maxY)
        XCTAssertGreaterThan(app.otherElements["gauge-rpm"].frame.minY, control.maxY)
        XCTAssertLessThan(app.otherElements["gauge-rpm"].frame.maxY, intake.minY)
        capture("Cockpit · landscape")
        app.buttons["faultsTab"].tap()
        let read = app.buttons["readFaultsButton"]
        XCTAssertTrue(read.waitForExistence(timeout: 5)); read.tap()
        XCTAssertTrue(app.staticTexts["faultsComplete"].waitForExistence(timeout: 10))
        XCTAssertTrue(element("fault-code-100", in: app).exists)
        capture("Fallas · landscape page")
        app.buttons["instrumentsTab"].tap()
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

    func testInstrumentsStayAnchoredAcrossWarningsNavigationAndReconnection() {
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
            if tab == "connectButton" {
                XCTAssertTrue(app.buttons["closeConnectionButton"].waitForExistence(timeout: 5))
                app.buttons["closeConnectionButton"].tap()
            } else {
                let page = tab == "settingsTab" ? "settingsPage" : "sessionsPage"
                XCTAssertTrue(element(page, in: app).waitForExistence(timeout: 5))
                if tab == "settingsTab" { capture("Settings · essentials") }
                app.buttons["instrumentsTab"].tap()
            }
            XCTAssertTrue(app.otherElements["gauge-rpm"].waitForExistence(timeout: 5))
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
        app.buttons["settingsTab"].tap()
        XCTAssertTrue(app.sliders["Refrigerante"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.sliders["Refrigerante"].isHittable)
        capture("Settings · accessibility portrait")
        XCUIDevice.shared.orientation = .landscapeLeft
        let settingsScroll = element("settingsPage", in: app).scrollViews.firstMatch
        let save = app.buttons["saveSettingsButton"]
        for _ in 0..<8 {
            if save.isHittable { break }
            settingsScroll.swipeUp()
        }
        XCTAssertTrue(save.isHittable, "Settings stay reachable at the largest text size in landscape")
        capture("Settings · accessibility landscape")
    }

    func testPagesRetainStateAndConnectionDismissesToTheSelectedPage() {
        let app = launch()
        let portraitFrames = frames(app)
        let instrumentsButtonFrame = app.buttons["instrumentsTab"].frame
        for (tab, page) in [("faultsTab", "faultsPage"), ("settingsTab", "settingsPage"), ("sessionsTab", "sessionsPage")] {
            app.buttons[tab].tap()
            XCTAssertTrue(element(page, in: app).waitForExistence(timeout: 5))
            XCTAssertTrue(app.buttons[tab].isSelected)
            XCTAssertFalse(app.buttons["vehicleTab"].isSelected)
            XCTAssertFalse(app.buttons["instrumentsTab"].isSelected)
            // The mounted instrument container can remain in XCTest's hierarchy;
            // its zero opacity and disabled hit testing keep it off the page.
            XCTAssertFalse(app.otherElements["gauge-rpm"].isHittable)
            XCTAssertFalse(app.buttons["closePanelButton"].exists)
            XCTAssertEqual(app.buttons["liveButton"].label, "Detener")
            app.buttons[tab].tap()
            XCTAssertTrue(element(page, in: app).exists, "Reselecting a tab must keep its destination open")
            capture("Navigation · \(page) portrait")
        }
        let row = app.buttons["sessionRow"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.buttons["exportSessionButton"].waitForExistence(timeout: 5))
        app.buttons["settingsTab"].tap()
        let coolant = app.sliders["Refrigerante"]
        XCTAssertTrue(coolant.waitForExistence(timeout: 5))
        coolant.adjust(toNormalizedSliderPosition: 0.8)
        let draftValue = coolant.value as? String
        XCTAssertTrue(app.buttons["saveSettingsButton"].isEnabled)
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["exportSessionButton"].waitForExistence(timeout: 5), "A selected session survives tab changes")
        app.buttons["settingsTab"].tap()
        XCTAssertEqual(coolant.value as? String, draftValue, "An unsaved threshold survives tab changes")
        app.buttons["connectButton"].tap()
        let sheet = element("connectionSheet", in: app)
        XCTAssertTrue(app.buttons["closeConnectionButton"].waitForExistence(timeout: 5))
        capture("Connection · native sheet portrait")
        sheet.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.02))
            .press(forDuration: 0.05, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.98)))
        expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: app.buttons["closeConnectionButton"])
        waitForExpectations(timeout: 5)
        XCTAssertTrue(app.buttons["settingsTab"].isSelected)
        XCTAssertEqual(coolant.value as? String, draftValue)
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(coolant.waitForExistence(timeout: 5))
        XCTAssertEqual(coolant.value as? String, draftValue, "The destination retains its draft when the layout changes")
        capture("Navigation · settingsPage landscape")
        app.buttons["connectButton"].tap()
        XCTAssertTrue(app.buttons["closeConnectionButton"].waitForExistence(timeout: 5))
        capture("Connection · native sheet landscape")
        app.buttons["closeConnectionButton"].tap()
        XCTAssertTrue(app.buttons["settingsTab"].isSelected)
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["exportSessionButton"].waitForExistence(timeout: 5))
        app.buttons["Volver a sesiones"].tap()
        capture("Navigation · sessionsPage landscape")
        app.buttons["faultsTab"].tap()
        XCTAssertTrue(app.buttons["readFaultsButton"].waitForExistence(timeout: 5))
        capture("Navigation · faultsPage landscape")
        XCUIDevice.shared.orientation = .portrait
        expectation(for: NSPredicate { object, _ in
            (object as? XCUIElement)?.frame == instrumentsButtonFrame
        }, evaluatedWith: app.buttons["instrumentsTab"])
        waitForExpectations(timeout: 5)
        app.buttons["instrumentsTab"].tap()
        expectation(for: NSPredicate(format: "selected == true"), evaluatedWith: app.buttons["instrumentsTab"])
        waitForExpectations(timeout: 5)
        XCTAssertTrue(app.otherElements["gauge-rpm"].waitForExistence(timeout: 5))
        assertFrames(portraitFrames, app)
        XCTAssertTrue(app.staticTexts["recordingIndicator"].exists)
        XCTAssertTrue(app.buttons["instrumentsTab"].isSelected)
        app.buttons["liveButton"].tap()
        app.buttons["sessionsTab"].tap()
        XCTAssertTrue(app.buttons["sessionRow"].firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["sessionCount"].label, "1 captura")
    }

    func testLiveActivitySystemPresentations() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        app.launchArguments = ["--demo", "--uitesting", "--live-activity-review", "--companion-system-review"]
        app.launch()
        let live = app.buttons["liveButton"]
        XCTAssertTrue(live.waitForExistence(timeout: 10))
        waitLabel("Detener", on: live)
        waitLabel("Recibiendo sensores", on: app.buttons["connectButton"])
        XCUIDevice.shared.press(.home)
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        XCTAssertTrue(springboard.icons["E36 OBD"].waitForExistence(timeout: 10))
        capture("Live Activity · compact island")
        springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.035))
            .press(forDuration: 1.2)
        capture("Live Activity · expanded island")
        // Dismiss SpringBoard's expanded overlay before returning to the app.
        // activate() alone can leave that overlay intercepting the first tap.
        XCUIDevice.shared.press(.home)
        app.activate()
        XCTAssertTrue(live.waitForExistence(timeout: 5))
        app.buttons["instrumentsTab"].tap()
        live.tap()
        waitLabel("Conectado · detenido", on: app.buttons["connectButton"])
    }

    func testLiveActivityPresentationSizesAndStates() {
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        for variant in ["full", "small", "paused", "stale", "off"] {
            app.launchArguments = ["--demo", "--uitesting", "--activity-face-review=\(variant)"]
            app.launch()
            let face = element("activityReviewFace", in: app)
            XCTAssertTrue(face.waitForExistence(timeout: 8))
            XCTAssertEqual(face.frame.width, variant == "small" ? 184 : 365, accuracy: 1)
            XCTAssertGreaterThan(face.frame.height, variant == "small" ? 60 : 130)
            XCTAssertLessThanOrEqual(face.frame.width, app.frame.width)
            let attachment = XCTAttachment(screenshot: face.screenshot())
            attachment.name = "Activity view · \(variant)"
            attachment.lifetime = .keepAlways; add(attachment)
            app.terminate()
        }
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
