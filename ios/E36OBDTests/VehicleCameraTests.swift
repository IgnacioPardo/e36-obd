import XCTest
import simd
@testable import E36OBD

final class VehicleCameraTests: XCTestCase {
    func testExpandedCameraCanInspectDetailsAndPullFarBackWithoutAutoFit() {
        var pose = VehicleCameraPose(distance: 8)
        for _ in 0..<5 { pose.distance = VehicleFreeNavigation.zoom(distance: pose.distance!, scale: 2) }
        XCTAssertEqual(pose.distance!, 0.25, accuracy: 0.0001)
        // Orbiting, repositioning and changing viewport orientation must not
        // silently push a detail camera back out to the car's bounding box.
        pose.azimuth = .pi
        pose.focus = [0.6, 0.7, 2]
        XCTAssertEqual(pose.distance, 0.25)
        for _ in 0..<10 { pose.distance = VehicleFreeNavigation.zoom(distance: pose.distance!, scale: 0.5) }
        XCTAssertEqual(pose.distance, 256)
        XCTAssertEqual(VehicleFreeNavigation.zoom(distance: 8, scale: .nan), 8)
        XCTAssertEqual(VehicleFreeNavigation.zoom(distance: 8, scale: 0), 8)
    }

    func testPanFollowsScreenPlaneAtEveryAzimuthAndScalesWithDistance() {
        for angle: Float in [0, .pi / 2, .pi, 7 * .pi] {
            let pose = VehicleCameraPose(azimuth: angle, elevation: 0.8, distance: 4)
            let offset = VehicleFreeNavigation.pan(pose: pose, translation: [90, -60], width: 400)
            XCTAssertEqual(simd_dot(offset, VehicleCameraFraming.direction(pose)), 0, accuracy: 0.00001)
            var distant = pose; distant.distance = 8
            XCTAssertEqual(simd_length(VehicleFreeNavigation.pan(pose: distant, translation: [90, -60], width: 400)),
                           2 * simd_length(offset), accuracy: 0.00001)
            let back = VehicleFreeNavigation.pan(pose: pose, translation: [-90, 60], width: 400)
            XCTAssertLessThan(simd_length(offset + back), 0.00001)
        }
    }

    func testFreeCameraResetInterpolatesFocusAndDistanceAndCollapseRestoresSafeFraming() {
        let start = VehicleCameraPose(azimuth: 2, elevation: -0.8, focus: [10, -3, 20], distance: 0.05)
        let end = VehicleCameraPose(distance: 8)
        let flight = VehicleCameraFlight(from: start, to: end, started: 0, duration: 1)
        XCTAssertEqual(flight.pose(at: 0.5).distance!, 4.025, accuracy: 0.0001)
        XCTAssertLessThan(simd_length(flight.pose(at: 0.5).focus - (start.focus + end.focus) / 2), 0.0001)
        XCTAssertEqual(flight.pose(at: 1), end)
        XCTAssertNil(start.dashboardPose.distance)
        XCTAssertEqual(start.dashboardPose.focus, VehicleCameraFraming.target)
        XCTAssertEqual(start.dashboardPose.azimuth, start.azimuth)
        XCTAssertEqual(start.dashboardPose.elevation, 0.035)
        for value: Float in [-100, -1.4, 1.4, 100] {
            let elevation = VehicleFreeNavigation.elevation(value)
            XCTAssertLessThan(abs(elevation), .pi / 2)
            XCTAssertEqual(VehicleCameraFraming.direction(VehicleCameraPose(elevation: elevation)).x.isFinite, true)
        }
    }

    func testWholeCarFitsAcrossOrbitElevationAspectAndZoom() {
        let minimum = SIMD3<Float>(-1.0, 0, -2.3), maximum = SIMD3<Float>(1.0, 1.45, 2.3)
        for aspect: Float in [0.55, 1, 1.8, 3.2] {
            for step in 0..<36 {
                for elevation: Float in [0.035, 0.145, 0.7] {
                    for zoom: Float in [0.8, 1, 1.65] {
                        let pose = VehicleCameraPose(azimuth: Float(step) * .pi / 18, elevation: elevation, zoom: zoom)
                        let distance = VehicleCameraFraming.distance(pose: pose, aspect: aspect, minimum: minimum, maximum: maximum)
                        let forward = VehicleCameraFraming.direction(pose)
                        let right = simd_normalize(simd_cross(SIMD3<Float>(0, 1, 0), forward))
                        let up = simd_cross(forward, right)
                        for x in [minimum.x, maximum.x] {
                            for y in [minimum.y, maximum.y] {
                                for z in [minimum.z, maximum.z] {
                                    let p = SIMD3<Float>(x, y, z) - VehicleCameraFraming.target
                                    let depth = distance - simd_dot(p, forward)
                                    XCTAssertGreaterThan(depth, 0.3)
                                    let halfWidth = depth * tan(Float(17) * .pi / 180)
                                    XCTAssertLessThanOrEqual(abs(simd_dot(p, right)) / halfWidth, 0.881)
                                    XCTAssertLessThanOrEqual(abs(simd_dot(p, up)) / halfWidth * aspect, 0.881)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    func testOrbitCrossesSeamOnShortArcAndFinishesExactly() {
        let start = VehicleCameraPose(azimuth: .pi - 0.1, elevation: 0.1, zoom: 1)
        let end = VehicleCameraPose(azimuth: -.pi + 0.1, elevation: 0.3, zoom: 1.2)
        let flight = VehicleCameraFlight(from: start, to: end, started: 10, duration: 1)
        XCTAssertEqual(flight.pose(at: 9), start)
        XCTAssertEqual(flight.pose(at: 10.5).azimuth, .pi, accuracy: 0.0001)
        XCTAssertEqual(flight.pose(at: 10.5).elevation, 0.2, accuracy: 0.0001)
        XCTAssertEqual(flight.pose(at: 11), end)
        XCTAssertEqual(flight.pose(at: 100), end)
    }
    func testDragCoastNeverOvershoots() {
        let start = VehicleCameraPose(azimuth: 0.5)
        let end = VehicleCameraPose(azimuth: 0.82)
        let flight = VehicleCameraFlight(from: start, to: end, started: 0, duration: 0.4, coast: true)
        let angles = (0...50).map { flight.pose(at: Double($0) / 100).azimuth }
        XCTAssertTrue(zip(angles, angles.dropFirst()).allSatisfy { $0 <= $1 })
        XCTAssertTrue(angles.allSatisfy { $0 >= start.azimuth && $0 <= end.azimuth })
    }

    func testTabOrbitFollowsBarOrderEvenWhenSkippingThreeTabs() {
        let first = VehicleCameraPose.tab(0, from: 0)
        let last = VehicleCameraPose.tab(3, from: 0)
        let forward = VehicleCameraFlight(from: first, to: last, started: 0, duration: 1)
        let angles = (0...100).map { forward.pose(at: Double($0) / 100).azimuth }
        XCTAssertTrue(zip(angles, angles.dropFirst()).allSatisfy { $0 >= $1 })
        XCTAssertEqual(angles.last! - angles.first!, -3 * .pi / 2, accuracy: 0.0001)
        XCTAssertEqual(forward.pose(at: 0.5).azimuth, (first.azimuth + last.azimuth) / 2, accuracy: 0.0001)
        let back = VehicleCameraFlight(from: last, to: .tab(0, from: 3), started: 0, duration: 1)
        let reverse = (0...100).map { back.pose(at: Double($0) / 100).azimuth }
        XCTAssertTrue(zip(reverse, reverse.dropFirst()).allSatisfy { $0 <= $1 })
        XCTAssertEqual(reverse.last! - reverse.first!, 3 * .pi / 2, accuracy: 0.0001)
        // A second tap starts from the frame currently on screen, never from
        // the previous tab's unrealized destination.
        let interrupted = forward.pose(at: 0.3)
        let retargeted = VehicleCameraFlight(from: interrupted, to: .tab(1, from: 3), started: 0.3, duration: 1)
        XCTAssertEqual(retargeted.pose(at: 0.3).azimuth, interrupted.azimuth, accuracy: 0.0001)
    }
}
