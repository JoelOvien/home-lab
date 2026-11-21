import Foundation

/// The recorder writes every 5 minutes and skips writes while the inverter is
/// offline, so anything older than this means the numbers can't be trusted.
let staleAfter: TimeInterval = 15 * 60

struct InverterStatus: Codable, Equatable {
    var ts: Date
    var pvW: Double?
    var loadW: Double?
    var gridW: Double?
    var batteryW: Double?
    var soc: Double?
    var batteryV: Double?
    var gridV: Double?
    var gridPresent: Bool?
    var outageStart: Date?

    func isStale(at now: Date) -> Bool {
        now.timeIntervalSince(ts) > staleAfter
    }

    static let sample = InverterStatus(
        ts: .now, pvW: 1240, loadW: 820, gridW: 0, batteryW: nil,
        soc: 76, batteryV: 52.8, gridV: 231.4, gridPresent: true, outageStart: nil
    )
}

struct D1Config: Decodable {
    let accountId: String
    let databaseId: String
    let apiToken: String

    static func load() -> D1Config? {
        guard let url = Bundle.main.url(forResource: "Secrets", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(D1Config.self, from: data)
    }
}

enum StatusError: LocalizedError {
    case notConfigured
    case noData
    case http(Int)
    case api(String)

    var errorDescription: String? {
        switch self {
        case .notConfigured: "Add Shared/Secrets.json and rebuild"
        case .noData: "No snapshots recorded yet"
        case .http(let code): "D1 returned HTTP \(code)"
        case .api(let message): message
        }
    }
}

private struct D1Response<Row: Decodable>: Decodable {
    struct Message: Decodable { let message: String }
    struct Result: Decodable { let results: [Row]? }
    let success: Bool
    let errors: [Message]?
    let result: [Result]?
}

private struct SnapshotRow: Decodable {
    let ts: Int
    let pv_w, load_w, grid_w, battery_w, soc, battery_v, grid_v: Double?
    let grid_present: Int?
}

private struct OutageRow: Decodable {
    let start_ts: Int
}

struct StatusFetcher {
    let config: D1Config
    var session: URLSession = .shared

    init?(config: D1Config? = .load()) {
        guard let config else { return nil }
        self.config = config
    }

    func fetch() async throws -> InverterStatus {
        async let snapshots: [SnapshotRow] = query(
            "SELECT * FROM snapshots ORDER BY ts DESC LIMIT 1"
        )
        async let outages: [OutageRow] = query(
            "SELECT start_ts FROM outages WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
        )
        guard let s = try await snapshots.first else { throw StatusError.noData }
        let outage = try await outages.first

        return InverterStatus(
            ts: Date(timeIntervalSince1970: TimeInterval(s.ts)),
            pvW: s.pv_w, loadW: s.load_w, gridW: s.grid_w, batteryW: s.battery_w,
            soc: s.soc, batteryV: s.battery_v, gridV: s.grid_v,
            gridPresent: s.grid_present.map { $0 != 0 },
            outageStart: outage.map { Date(timeIntervalSince1970: TimeInterval($0.start_ts)) }
        )
    }

    private func query<Row: Decodable>(_ sql: String) async throws -> [Row] {
        let url = URL(string: "https://api.cloudflare.com/client/v4/accounts/\(config.accountId)/d1/database/\(config.databaseId)/query")!
        var request = URLRequest(url: url, timeoutInterval: 15)
        request.httpMethod = "POST"
        request.setValue("Bearer \(config.apiToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["sql": sql])

        let (data, response) = try await session.data(for: request)
        let body = try? JSONDecoder().decode(D1Response<Row>.self, from: data)
        guard let body, body.success else {
            if let message = body?.errors?.first?.message { throw StatusError.api(message) }
            throw StatusError.http((response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        return body.result?.first?.results ?? []
    }
}

/// Last good status, so a failed refresh still shows (stale) numbers.
enum StatusCache {
    private static let key = "lastStatus"

    static func load() -> InverterStatus? {
        guard let data = UserDefaults.standard.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(InverterStatus.self, from: data)
    }

    static func save(_ status: InverterStatus) {
        if let data = try? JSONEncoder().encode(status) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}
