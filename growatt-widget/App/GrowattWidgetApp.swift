import SwiftUI
import WidgetKit

@main
struct GrowattWidgetApp: App {
    var body: some Scene {
        WindowGroup("Growatt") {
            ContentView()
        }
        .windowResizability(.contentSize)
    }
}

struct ContentView: View {
    @State private var status: InverterStatus?
    @State private var error: String?
    @State private var loading = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            StatusView(status: status, error: error, now: .now, layout: .medium)
                .padding(16)
                .frame(width: 340, height: 160)
                .background(.fill.tertiary, in: RoundedRectangle(cornerRadius: 20))

            if let error, status != nil {
                Text(error).font(.caption).foregroundStyle(.orange)
            }

            HStack {
                Button(loading ? "Refreshing…" : "Refresh") { Task { await refresh() } }
                    .disabled(loading)
                Button("Reload widgets") { WidgetCenter.shared.reloadAllTimelines() }
            }

            Text("To add the widget, right-click the desktop, choose Edit Widgets, and search for Growatt.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(20)
        .frame(width: 380)
        .task { await refresh() }
    }

    private func refresh() async {
        guard let fetcher = StatusFetcher() else {
            error = StatusError.notConfigured.errorDescription
            return
        }
        loading = true
        defer { loading = false }
        do {
            status = try await fetcher.fetch()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
