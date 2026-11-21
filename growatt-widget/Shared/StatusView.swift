import SwiftUI

enum StatusLayout {
    case small, medium
}

struct StatusView: View {
    let status: InverterStatus?
    let error: String?
    let now: Date
    let layout: StatusLayout

    var body: some View {
        if let status {
            switch layout {
            case .small: SmallStatus(status: status, now: now)
            case .medium: MediumStatus(status: status, now: now)
            }
        } else {
            VStack(alignment: .leading, spacing: 6) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                Text("Inverter")
                    .font(.headline)
                Text(error ?? "Loading…")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct SmallStatus: View {
    let status: InverterStatus
    let now: Date

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                GridBadge(present: status.gridPresent)
                Spacer()
                Image(systemName: Fmt.batteryIcon(status.soc))
                    .foregroundStyle(Fmt.socColor(status.soc))
            }
            BatteryHeadline(soc: status.soc)
            Spacer(minLength: 0)
            Label(Fmt.watts(status.loadW), systemImage: "house.fill")
            Label(Fmt.watts(status.pvW), systemImage: "sun.max.fill")
            UpdatedFooter(status: status, now: now)
        }
        .font(.caption)
        .labelStyle(CompactLabel())
    }
}

private struct MediumStatus: View {
    let status: InverterStatus
    let now: Date

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Battery")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                BatteryHeadline(soc: status.soc)
                Text(Fmt.volts(status.batteryV))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
                UpdatedFooter(status: status, now: now)
                    .font(.caption)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            VStack(alignment: .leading, spacing: 8) {
                Row(icon: "bolt.fill", title: "Grid") { GridDetail(status: status) }
                Row(icon: "house.fill", title: "Load") { Text(Fmt.watts(status.loadW)) }
                Row(icon: "sun.max.fill", title: "Solar") { Text(Fmt.watts(status.pvW)) }
                Spacer(minLength: 0)
            }
            .font(.caption)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct BatteryHeadline: View {
    let soc: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(soc.map { "\(Int($0.rounded()))%" } ?? "n/a")
                .font(.system(size: 34, weight: .semibold, design: .rounded))
                .monospacedDigit()
                .minimumScaleFactor(0.6)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(.quaternary)
                    Capsule()
                        .fill(Fmt.socColor(soc))
                        .frame(width: geo.size.width * min(max((soc ?? 0) / 100, 0), 1))
                }
            }
            .frame(height: 6)
        }
    }
}

private struct GridBadge: View {
    let present: Bool?

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(present == true ? .green : present == false ? .red : .gray)
                .frame(width: 7, height: 7)
            Text(present == true ? "Grid on" : present == false ? "Grid off" : "Grid n/a")
                .fontWeight(.medium)
        }
    }
}

private struct GridDetail: View {
    let status: InverterStatus

    var body: some View {
        switch status.gridPresent {
        case true?:
            Text("On · \(Fmt.volts(status.gridV))")
        case false?:
            if let start = status.outageStart {
                (Text("Off · ") + Text(start, style: .relative))
                    .foregroundStyle(.red)
            } else {
                Text("Off").foregroundStyle(.red)
            }
        case nil:
            Text("n/a")
        }
    }
}

private struct Row<Content: View>: View {
    let icon: String
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundStyle(.secondary)
                .frame(width: 14)
            Text(title).foregroundStyle(.secondary)
            Spacer(minLength: 4)
            content
                .fontWeight(.medium)
                .monospacedDigit()
                .lineLimit(1)
        }
    }
}

private struct UpdatedFooter: View {
    let status: InverterStatus
    let now: Date

    var body: some View {
        let stale = status.isStale(at: now)
        HStack(spacing: 3) {
            if stale { Image(systemName: "clock.badge.exclamationmark") }
            Text(status.ts, style: .relative) + Text(" ago")
        }
        .foregroundStyle(stale ? AnyShapeStyle(.orange) : AnyShapeStyle(.secondary))
        .lineLimit(1)
    }
}

private struct CompactLabel: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 4) {
            configuration.icon
                .foregroundStyle(.secondary)
                .frame(width: 14)
            configuration.title
                .monospacedDigit()
        }
    }
}

enum Fmt {
    static func watts(_ w: Double?) -> String {
        guard let w else { return "n/a" }
        if abs(w) >= 1000 { return String(format: "%.2f kW", w / 1000) }
        return "\(Int(w.rounded())) W"
    }

    static func volts(_ v: Double?) -> String {
        v.map { String(format: "%.1f V", $0) } ?? "n/a"
    }

    // Thresholds mirror the bot's default BATTERY_ALERT_LEVELS (30, 15).
    static func socColor(_ soc: Double?) -> Color {
        guard let soc else { return .gray }
        if soc > 30 { return .green }
        if soc > 15 { return .orange }
        return .red
    }

    static func batteryIcon(_ soc: Double?) -> String {
        guard let soc else { return "battery.0percent" }
        switch soc {
        case 88...: return "battery.100percent"
        case 63..<88: return "battery.75percent"
        case 38..<63: return "battery.50percent"
        case 13..<38: return "battery.25percent"
        default: return "battery.0percent"
        }
    }
}
