import Foundation
import CSQLite

public struct StoreError: Error, LocalizedError, Sendable {
    public let message: String
    public var errorDescription: String? { message }
}
private final class DatabaseConnection: @unchecked Sendable {
    let raw: OpaquePointer
    init(path: String) throws {
        var pointer: OpaquePointer?
        let result = sqlite3_open_v2(path, &pointer, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nil)
        guard result == SQLITE_OK, let pointer else {
            let message = pointer.map { String(cString: sqlite3_errmsg($0)) } ?? "No se pudo abrir SQLite"
            if let pointer { sqlite3_close(pointer) }
            throw StoreError(message: message)
        }
        raw = pointer
    }
    deinit { sqlite3_close(raw) }
}

/// Its actor is the sole owner of the SQLite connection. UI and BLE never do synchronous disk I/O.
public actor SessionStore {
    private let connection: DatabaseConnection
    public let url: URL
    private let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    public init(url: URL) throws {
        self.url = url
        let directory = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication], ofItemAtPath: directory.path)
        #endif
        connection = try DatabaseConnection(path: url.path)
        let schema = """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        PRAGMA foreign_keys=ON;
        PRAGMA busy_timeout=3000;
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, started REAL NOT NULL, ended REAL, status TEXT NOT NULL,
          demo INTEGER NOT NULL, elapsed REAL NOT NULL DEFAULT 0
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_recording ON sessions(status) WHERE status='recording';
        CREATE TABLE IF NOT EXISTS samples (
          id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          received REAL NOT NULL, elapsed REAL NOT NULL, rpm REAL NOT NULL, load REAL NOT NULL,
          coolant REAL NOT NULL, battery REAL NOT NULL, ecu_ms INTEGER NOT NULL, intake REAL,
          segment INTEGER NOT NULL, validity TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS samples_session ON samples(session_id, id);
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id), timestamp REAL NOT NULL,
          kind TEXT NOT NULL, message TEXT NOT NULL, sample_id INTEGER REFERENCES samples(id), rule TEXT
        );
        CREATE INDEX IF NOT EXISTS events_session ON events(session_id, timestamp);
        PRAGMA user_version=1;
        """
        guard sqlite3_exec(connection.raw, schema, nil, nil, nil) == SQLITE_OK else {
            throw StoreError(message: String(cString: sqlite3_errmsg(connection.raw)))
        }
        #if os(iOS)
        for file in [url.path, url.path + "-wal", url.path + "-shm"] where FileManager.default.fileExists(atPath: file) {
            try FileManager.default.setAttributes([.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication], ofItemAtPath: file)
        }
        #endif
    }

    private func execute(_ sql: String) throws {
        guard sqlite3_exec(connection.raw, sql, nil, nil, nil) == SQLITE_OK else { throw failure() }
    }
    private func failure() -> StoreError { StoreError(message: String(cString: sqlite3_errmsg(connection.raw))) }
    private func statement<T>(_ sql: String, _ body: (OpaquePointer) throws -> T) throws -> T {
        var pointer: OpaquePointer?
        guard sqlite3_prepare_v2(connection.raw, sql, -1, &pointer, nil) == SQLITE_OK, let pointer else { throw failure() }
        defer { sqlite3_finalize(pointer) }
        return try body(pointer)
    }
    private func bind(_ value: String?, _ index: Int32, _ statement: OpaquePointer) {
        if let value { sqlite3_bind_text(statement, index, value, -1, transient) }
        else { sqlite3_bind_null(statement, index) }
    }
    private func done(_ statement: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else { throw failure() }
    }
    private func string(_ statement: OpaquePointer, _ column: Int32) -> String {
        sqlite3_column_text(statement, column).map { String(cString: $0) } ?? ""
    }
    private func transaction<T>(_ body: () throws -> T) throws -> T {
        try execute("BEGIN IMMEDIATE")
        do { let value = try body(); try execute("COMMIT"); return value }
        catch { try? execute("ROLLBACK"); throw error }
    }

    public func start(at date: Date, isDemo: Bool) throws -> DriveSession {
        let session = DriveSession(startedAt: date, isDemo: isDemo)
        try transaction {
            try statement("INSERT INTO sessions(id,started,status,demo) VALUES(?,?,'recording',?)") { s in
                bind(session.id, 1, s); sqlite3_bind_double(s, 2, date.timeIntervalSince1970)
                sqlite3_bind_int(s, 3, isDemo ? 1 : 0); try done(s)
            }
            try insertEvent(SessionEvent(sessionID: session.id, timestamp: date, kind: .recording, message: "Grabación iniciada"))
        }
        return session
    }

    /// Only a launch explicitly requested by CoreBluetooth may retain an active recording.
    public func recover(restoring sessionID: String?, now: Date = Date()) throws -> DriveSession? {
        let active = try sessions().filter { $0.status == .recording }
        for session in active where session.id != sessionID {
            try finish(session.id, status: .interrupted, at: now, message: "Captura interrumpida por cierre de la app")
        }
        return active.first { $0.id == sessionID }
    }

    public func finish(_ sessionID: String, status: SessionStatus = .completed, at date: Date, elapsed: Double? = nil, message: String) throws {
        try transaction {
            try statement("UPDATE sessions SET status=?,ended=?,elapsed=MAX(elapsed,COALESCE(?,elapsed)) WHERE id=? AND status='recording'") { s in
                bind(status.rawValue, 1, s); sqlite3_bind_double(s, 2, date.timeIntervalSince1970)
                if let elapsed { sqlite3_bind_double(s, 3, elapsed) } else { sqlite3_bind_null(s, 3) }
                bind(sessionID, 4, s)
                try done(s)
            }
            if sqlite3_changes(connection.raw) > 0 {
                try insertEvent(SessionEvent(sessionID: sessionID, timestamp: date, kind: .recording, message: message))
            }
        }
    }

    @discardableResult
    public func append(_ sample: RecordedSample, events: [SessionEvent]) throws -> Int64 {
        try transaction {
            try statement("SELECT status FROM sessions WHERE id=?") { s in
                bind(sample.sessionID, 1, s)
                guard sqlite3_step(s) == SQLITE_ROW, string(s, 0) == SessionStatus.recording.rawValue else {
                    throw StoreError(message: "La sesión ya no está grabando")
                }
            }
            try statement("""
                INSERT INTO samples(session_id,received,elapsed,rpm,load,coolant,battery,ecu_ms,intake,segment,validity)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """) { s in
                bind(sample.sessionID, 1, s); sqlite3_bind_double(s, 2, sample.receivedAt.timeIntervalSince1970)
                sqlite3_bind_double(s, 3, sample.elapsed); sqlite3_bind_double(s, 4, sample.telemetry.rpm)
                sqlite3_bind_double(s, 5, sample.telemetry.load); sqlite3_bind_double(s, 6, sample.telemetry.coolant)
                sqlite3_bind_double(s, 7, sample.telemetry.battery); sqlite3_bind_int64(s, 8, Int64(sample.telemetry.ecuMS))
                if let intake = sample.telemetry.intake { sqlite3_bind_double(s, 9, intake) } else { sqlite3_bind_null(s, 9) }
                sqlite3_bind_int(s, 10, Int32(sample.segment)); bind(sample.telemetry.validity.rawValue, 11, s)
                try done(s)
            }
            let id = sqlite3_last_insert_rowid(connection.raw)
            for var event in events { event.sessionID = sample.sessionID; event.sampleID = id; try insertEvent(event) }
            try statement("UPDATE sessions SET elapsed=MAX(elapsed,?) WHERE id=?") { s in
                sqlite3_bind_double(s, 1, sample.elapsed); bind(sample.sessionID, 2, s); try done(s)
            }
            return id
        }
    }
    public func appendEvent(_ event: SessionEvent) throws { try insertEvent(event) }
    private func insertEvent(_ event: SessionEvent) throws {
        try statement("INSERT INTO events(id,session_id,timestamp,kind,message,sample_id,rule) VALUES(?,?,?,?,?,?,?)") { s in
            bind(event.id, 1, s); bind(event.sessionID, 2, s); sqlite3_bind_double(s, 3, event.timestamp.timeIntervalSince1970)
            bind(event.kind.rawValue, 4, s); bind(event.message, 5, s)
            if let id = event.sampleID { sqlite3_bind_int64(s, 6, id) } else { sqlite3_bind_null(s, 6) }
            bind(event.rule?.rawValue, 7, s); try done(s)
        }
    }
    public func sessions() throws -> [DriveSession] {
        try statement("""
          SELECT id,started,ended,status,demo,elapsed,
          (SELECT COUNT(*) FROM samples WHERE session_id=sessions.id),
          (SELECT COUNT(*) FROM events WHERE session_id=sessions.id),
          (SELECT MAX(received) FROM samples WHERE session_id=sessions.id)
          FROM sessions ORDER BY started DESC
          """) { s in
            var result: [DriveSession] = []
            while true {
                let step = sqlite3_step(s)
                if step == SQLITE_DONE { break }
                guard step == SQLITE_ROW else { throw failure() }
                var session = DriveSession(id: string(s, 0), startedAt: Date(timeIntervalSince1970: sqlite3_column_double(s, 1)),
                                           isDemo: sqlite3_column_int(s, 4) != 0)
                session.endedAt = sqlite3_column_type(s, 2) == SQLITE_NULL ? nil : Date(timeIntervalSince1970: sqlite3_column_double(s, 2))
                session.status = SessionStatus(rawValue: string(s, 3)) ?? .interrupted
                session.elapsed = sqlite3_column_double(s, 5); session.sampleCount = Int(sqlite3_column_int64(s, 6))
                session.eventCount = Int(sqlite3_column_int64(s, 7))
                session.lastReceivedAt = sqlite3_column_type(s, 8) == SQLITE_NULL ? nil : Date(timeIntervalSince1970: sqlite3_column_double(s, 8))
                result.append(session)
            }
            return result
        }
    }
    private func readSample(_ s: OpaquePointer) -> RecordedSample {
        let intake: Double? = sqlite3_column_type(s, 9) == SQLITE_NULL ? nil : sqlite3_column_double(s, 9)
        return RecordedSample(id: sqlite3_column_int64(s, 0), sessionID: string(s, 1),
            receivedAt: Date(timeIntervalSince1970: sqlite3_column_double(s, 2)), elapsed: sqlite3_column_double(s, 3),
            telemetry: Telemetry(rpm: sqlite3_column_double(s, 4), load: sqlite3_column_double(s, 5),
                                 coolant: sqlite3_column_double(s, 6), battery: sqlite3_column_double(s, 7),
                                 ecuMS: Int(sqlite3_column_int64(s, 8)), intake: intake), segment: Int(sqlite3_column_int(s, 10)))
    }
    public func samples(sessionID: String) throws -> [RecordedSample] {
        try statement("SELECT id,session_id,received,elapsed,rpm,load,coolant,battery,ecu_ms,intake,segment FROM samples WHERE session_id=? ORDER BY id") { s in
            bind(sessionID, 1, s); var result: [RecordedSample] = []
            while true {
                let step = sqlite3_step(s)
                if step == SQLITE_DONE { break }
                guard step == SQLITE_ROW else { throw failure() }
                result.append(readSample(s))
            }
            return result
        }
    }
    public func events(sessionID: String? = nil, limit: Int = 100_000) throws -> [SessionEvent] {
        let filter = sessionID == nil ? "" : "WHERE session_id=?"
        return try statement("SELECT id,session_id,timestamp,kind,message,sample_id,rule FROM events \(filter) ORDER BY timestamp DESC,rowid DESC LIMIT ?") { s in
            if let sessionID { bind(sessionID, 1, s) }
            sqlite3_bind_int64(s, sessionID == nil ? 1 : 2, Int64(limit))
            var result: [SessionEvent] = []
            while true {
                let step = sqlite3_step(s)
                if step == SQLITE_DONE { break }
                guard step == SQLITE_ROW else { throw failure() }
                var event = SessionEvent(sessionID: sqlite3_column_type(s, 1) == SQLITE_NULL ? nil : string(s, 1),
                    timestamp: Date(timeIntervalSince1970: sqlite3_column_double(s, 2)),
                    kind: EventKind(rawValue: string(s, 3)) ?? .message, message: string(s, 4),
                    sampleID: sqlite3_column_type(s, 5) == SQLITE_NULL ? nil : sqlite3_column_int64(s, 5),
                    rule: AlertRule(rawValue: string(s, 6)))
                event.id = string(s, 0); result.append(event)
            }
            return result.reversed()
        }
    }

    /// Streams every stored row to disk; chart reduction is never involved in an export.
    public func export(sessionID: String, to directory: URL) throws -> [URL] {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        guard try sessions().contains(where: { $0.id == sessionID }) else { throw StoreError(message: "Sesión no encontrada") }
        let prefix = "e36-" + sessionID
        let sensors = directory.appendingPathComponent(prefix + "-sensores.csv")
        let eventsURL = directory.appendingPathComponent(prefix + "-eventos.csv")
        FileManager.default.createFile(atPath: sensors.path, contents: nil)
        FileManager.default.createFile(atPath: eventsURL.path, contents: nil)
        let samplesHandle = try FileHandle(forWritingTo: sensors)
        let eventsHandle = try FileHandle(forWritingTo: eventsURL)
        defer { try? samplesHandle.close(); try? eventsHandle.close() }
        func write(_ cells: [String], _ handle: FileHandle) throws {
            try handle.write(contentsOf: Data((cells.map(CSV.escape).joined(separator: ",") + "\r\n").utf8))
        }
        try write(["timestamp","elapsed_s","battery","intake_air_temp","coolant_temp","rpm","load","ecu_ms","validity"], samplesHandle)
        let formatter = Date.ISO8601FormatStyle(includingFractionalSeconds: true)
        try statement("SELECT id,session_id,received,elapsed,rpm,load,coolant,battery,ecu_ms,intake,segment FROM samples WHERE session_id=? ORDER BY id") { s in
            bind(sessionID, 1, s)
            while true {
                let step = sqlite3_step(s)
                if step == SQLITE_DONE { break }
                guard step == SQLITE_ROW else { throw failure() }
                let row = readSample(s), t = row.telemetry
                try write([formatter.format(row.receivedAt), String(format: "%.3f", locale: Locale(identifier: "en_US_POSIX"), row.elapsed),
                    String(t.battery), t.intake.map { String($0) } ?? "", String(t.coolant), String(t.rpm), String(t.load),
                    String(t.ecuMS), t.validity.rawValue], samplesHandle)
            }
        }
        try write(["timestamp","kind","message","sample_id","rule"], eventsHandle)
        for event in try events(sessionID: sessionID, limit: Int.max) {
            try write([formatter.format(event.timestamp), event.kind.rawValue, event.message,
                       event.sampleID.map { String($0) } ?? "", event.rule?.rawValue ?? ""], eventsHandle)
        }
        return [sensors, eventsURL]
    }
}

public enum CSV {
    public static func escape(_ text: String) -> String {
        if text.contains(where: { $0 == "," || $0 == "\"" || $0 == "\n" || $0 == "\r" }) {
            return "\"" + text.replacingOccurrences(of: "\"", with: "\"\"") + "\""
        }
        return text
    }
}
