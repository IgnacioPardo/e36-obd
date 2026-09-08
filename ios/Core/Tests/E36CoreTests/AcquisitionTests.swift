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
}
