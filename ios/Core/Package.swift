// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "E36Core",
    platforms: [.iOS(.v18), .macOS(.v14)],
    products: [.library(name: "E36Core", targets: ["E36Core"])],
    targets: [
        .systemLibrary(name: "CSQLite"),
        .target(name: "E36Core", dependencies: ["CSQLite"]),
        .testTarget(name: "E36CoreTests", dependencies: ["E36Core"])
    ]
)
