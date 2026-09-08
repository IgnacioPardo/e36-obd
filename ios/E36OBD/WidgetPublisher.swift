import Foundation
import WidgetKit
import E36Core

actor WidgetPublisher {
    private let store: WidgetSnapshotStore?
    private var policy = WidgetPublicationPolicy()
    private var previous: WidgetSnapshot?
    private var loaded = false
    init() {
        store = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: WidgetSnapshotStore.appGroup)
            .map { WidgetSnapshotStore(directory: $0) }
    }
    func publish(_ incoming: WidgetSnapshot, foreground: Bool) throws {
        guard let store else { throw PublisherError.missingAppGroup }
        if !loaded {
            previous = try? store.read(incoming.source)
            loaded = true
        }
        var snapshot = incoming
        if snapshot.receivedAt == nil, let previous, previous.source == snapshot.source {
            snapshot.receivedAt = previous.receivedAt
            snapshot.telemetry = previous.telemetry
        }
        // Commit throttling state only after a successful atomic write.
        var next = policy
        let decision = next.decision(for: snapshot, foreground: foreground)
        guard decision.write else { return }
        try store.write(snapshot)
        policy = next
        previous = snapshot
        if decision.reload { WidgetCenter.shared.reloadTimelines(ofKind: WidgetSnapshotStore.kind) }
    }
    enum PublisherError: LocalizedError {
        case missingAppGroup
        var errorDescription: String? { "El widget requiere el App Group de E36 en la firma de la app." }
    }
}
