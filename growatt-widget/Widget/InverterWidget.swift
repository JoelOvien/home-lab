import SwiftUI
import WidgetKit

struct StatusEntry: TimelineEntry {
    let date: Date
    let status: InverterStatus?
    let error: String?
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> StatusEntry {
        StatusEntry(date: .now, status: .sample, error: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (StatusEntry) -> Void) {
        if context.isPreview {
            completion(placeholder(in: context))
            return
        }
        Task { completion(await load().entry) }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<StatusEntry>) -> Void) {
        Task {
            let (entry, status) = await load()
            var entries = [entry]
            // A second entry flips the view to "stale" if no refresh lands before then.
            if let status {
                let staleAt = status.ts.addingTimeInterval(staleAfter + 1)
                if staleAt > entry.date {
                    entries.append(StatusEntry(date: staleAt, status: status, error: entry.error))
                }
            }
            completion(Timeline(entries: entries, policy: .after(.now.addingTimeInterval(10 * 60))))
        }
    }

    private func load() async -> (entry: StatusEntry, status: InverterStatus?) {
        guard let fetcher = StatusFetcher() else {
            return (StatusEntry(date: .now, status: nil, error: StatusError.notConfigured.errorDescription), nil)
        }
        do {
            let status = try await fetcher.fetch()
            StatusCache.save(status)
            return (StatusEntry(date: .now, status: status, error: nil), status)
        } catch {
            let cached = StatusCache.load()
            return (StatusEntry(date: .now, status: cached, error: error.localizedDescription), cached)
        }
    }
}

struct InverterWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: StatusEntry

    var body: some View {
        StatusView(
            status: entry.status,
            error: entry.error,
            now: entry.date,
            layout: family == .systemSmall ? .small : .medium
        )
        .containerBackground(.fill.tertiary, for: .widget)
    }
}

@main
struct InverterWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "InverterStatus", provider: Provider()) { entry in
            InverterWidgetView(entry: entry)
        }
        .configurationDisplayName("Inverter")
        .description("Battery, grid and load from the Growatt monitor.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
