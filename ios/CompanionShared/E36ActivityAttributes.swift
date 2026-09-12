#if os(iOS)
import ActivityKit
import E36Core

struct E36ActivityAttributes: ActivityAttributes, Sendable {
    struct ContentState: Codable, Hashable, Sendable {
        var snapshot: CompanionSnapshot
    }
    var sessionID: String
    var source: WidgetSource
}
#endif
