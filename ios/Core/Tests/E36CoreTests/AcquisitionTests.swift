import Testing
@testable import E36Core

struct AcquisitionTests {
    func connectedMachine() -> AcquisitionMachine {
        var machine = AcquisitionMachine()
        #expect(machine.connected(restored: false, now: 0) == [.write(.stop)])
        #expect(machine.text("detenido", now: 0.1).isEmpty)
        return machine
    }
    @Test func liveFaultBarrierAndResume() {
        var machine = connectedMachine()
        #expect(machine.setLiveIntent(true, now: 1) == [.write(.live)])
        #expect(machine.text("abriendo sesion...", now: 2).isEmpty)
        #expect(machine.text("en vivo. cualquier tecla corta.", now: 6).isEmpty)
        #expect(machine.sample(now: 6.4).isEmpty)
        #expect(machine.requestFaults(now: 7) == [.write(.faults)])
        #expect(machine.text("detenido (4 muestras)", now: 7.3).isEmpty)
        #expect(machine.text("abriendo sesion...", now: 7.4) == [.write(.help)])
        #expect(machine.text("abriendo sesion...", now: 7.5).isEmpty)
        #expect(machine.text("cod 100  ocurr 50", now: 13).isEmpty)
        #expect(machine.text("?  esta ayuda", now: 14) == [.faultsCompleted, .write(.live)])
    }
    @Test func stopDoesNotAdvanceOnLiveStopCount() {
        var machine = connectedMachine()
        _ = machine.setLiveIntent(true, now: 1); _ = machine.sample(now: 2)
        #expect(machine.setLiveIntent(false, now: 3) == [.write(.stop)])
        #expect(machine.text("detenido (3 muestras)", now: 3.1).isEmpty)
        #expect(machine.phase == .stopping)
        #expect(machine.text("detenido", now: 3.2).isEmpty)
        #expect(machine.phase == .idle)
    }
    @Test func stopWhileStartingOrReadingDoesNotOverwriteMailbox() {
        var machine = connectedMachine()
        _ = machine.setLiveIntent(true, now: 1)
        #expect(machine.setLiveIntent(false, now: 2).isEmpty)
        #expect(machine.text("en vivo. cualquier tecla corta.", now: 6) == [.write(.stop)])
        _ = machine.text("detenido", now: 6.5)
        _ = machine.requestFaults(now: 7)
        #expect(machine.setLiveIntent(false, now: 8).isEmpty)
        _ = machine.text("abriendo sesion...", now: 9)
        #expect(machine.text("error: sin respuesta", now: 10).isEmpty)
        #expect(machine.text("?  esta ayuda", now: 11) == [.faultsCompleted])
    }
    @Test func restorationNeverSendsLiveIntoExistingFlow() {
        var machine = AcquisitionMachine()
        _ = machine.setLiveIntent(true, now: 0)
        #expect(machine.connected(restored: true, now: 0).isEmpty)
        #expect(machine.sample(now: 0.4).isEmpty)
        #expect(machine.tick(now: 2.1).isEmpty)
        #expect(machine.phase == .live)
        machine.disconnected()
        _ = machine.connected(restored: true, now: 4)
        #expect(machine.tick(now: 6) == [.write(.stop)])
        #expect(machine.text("detenido", now: 7) == [.write(.live)])
    }
    @Test func errorsAndTimeoutsResetBeforeMoreWrites() {
        var machine = connectedMachine()
        _ = machine.setLiveIntent(true, now: 1)
        #expect(machine.tick(now: 31) == [.resetLink])
        #expect(machine.phase == .disconnected); #expect(machine.wantsLive)
        _ = machine.connected(restored: false, now: 40); _ = machine.text("detenido", now: 41)
        #expect(machine.text("error: sin respuesta", now: 42) == [.resetLink])
    }

    @Test func ecuRecoveryKeepsBLEAndResumesWithoutCommands() {
        var machine = connectedMachine()
        _ = machine.setLiveIntent(true, now: 1)
        _ = machine.sample(now: 2)
        #expect(machine.text("recuperando DME (1/5): sin respuesta de la ECU", now: 18).isEmpty)
        #expect(machine.phase == .recoveringDME)
        #expect(machine.wantsLive)
        // The old sample is over 30 s old, but a new ECU attempt is in progress.
        #expect(machine.text("recuperando DME (2/5): sin respuesta de la ECU", now: 27).isEmpty)
        #expect(machine.tick(now: 33).isEmpty)
        #expect(machine.text("en vivo. cualquier tecla corta.", now: 34).isEmpty)
        #expect(machine.sample(now: 34.5).isEmpty)
        #expect(machine.phase == .live)
        #expect(machine.wantsLive)
    }

    @Test func ecuRecoveryCanBeStoppedOrInterruptedForFaults() {
        var machine = connectedMachine()
        _ = machine.setLiveIntent(true, now: 1)
        _ = machine.text("recuperando DME (1/5): sin respuesta", now: 8)
        #expect(machine.setLiveIntent(false, now: 9) == [.write(.stop)])
        #expect(machine.text("recuperando DME (2/5): sin respuesta", now: 9.1).isEmpty)
        #expect(machine.text("en vivo. cualquier tecla corta.", now: 9.2).isEmpty)
        #expect(machine.phase == .stopping)
        _ = machine.text("detenido (0 muestras)", now: 9.3)
        _ = machine.text("detenido", now: 9.4)
        #expect(machine.phase == .idle)
        _ = machine.setLiveIntent(true, now: 10)
        _ = machine.text("recuperando DME (1/5): sin respuesta", now: 16)
        #expect(machine.requestFaults(now: 17) == [.write(.faults)])
        #expect(machine.text("abriendo sesion...", now: 18) == [.write(.help)])
        #expect(machine.text("?  esta ayuda", now: 24) == [.faultsCompleted, .write(.live)])
    }

    @Test func ecuRecoveryRestorationDoesNotToggleTheWorker() {
        var machine = AcquisitionMachine()
        _ = machine.setLiveIntent(true, now: 0)
        _ = machine.connected(restored: true, now: 1)
        #expect(machine.text("recuperando DME (2/5): sin respuesta", now: 1.5).isEmpty)
        #expect(machine.tick(now: 3).isEmpty)
        #expect(machine.sample(now: 9).isEmpty)
        #expect(machine.phase == .live)
        #expect(machine.text("recuperando DME (1/5): sin respuesta", now: 20).isEmpty)
        #expect(machine.tick(now: 50) == [.resetLink])
        _ = machine.connected(restored: true, now: 51)
        _ = machine.text("recuperando DME (5/5): sin respuesta", now: 52)
        #expect(machine.text("se corto: sin respuesta", now: 53) == [.resetLink])
    }
}
