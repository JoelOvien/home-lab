# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

`home-lab` is a container for home-lab projects:

- `growatt-monitor/`: a Python asyncio worker that polls a Growatt SPF 6000 ES
  PLUS inverter through the Growatt web dashboard API and talks to a Telegram
  bot (scheduled alerts plus on-demand commands). It runs on Railway as a
  `worker` process (`Procfile`). There is no HTTP server, so don't add one.
- `growatt-widget/`: a macOS WidgetKit widget that reads the worker's D1
  history. See [macOS widget](#macos-widget) below.
- `growatt-app/`: a Flutter phone dashboard (Android + iOS) that also reads
  D1 only. See [Flutter app](#flutter-app) below.

All commands below, up to the widget section, run from `growatt-monitor/`.
Imports are top-level (`from growatt import parsers`), so run things from that
directory.

## Commands

```bash
pip install -r requirements.txt          # pytest is not listed; install it separately
python main.py                           # needs the six env vars below
python -m pytest                         # all tests
python -m pytest tests/test_parsers.py::test_status_fields_from_real_payload   # single test
```

Required env vars (startup fails fast if any are missing, see `config.py`):
`GROWATT_USERNAME`, `GROWATT_PASSWORD`, `GROWATT_DEVICE_SN`, `GROWATT_PLANT_ID`,
`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`. Optional: `BATTERY_ALERT_LEVELS` (default `30,15`); `CLOUDFLARE_ACCOUNT_ID`,
`CLOUDFLARE_D1_DATABASE_ID`, `CLOUDFLARE_API_TOKEN` (all three or none) to store
history in D1; otherwise `HISTORY_DB_PATH` (default `data/history.db`).
Also optional: `TZ` (IANA, default `UTC`; production uses `Africa/Lagos`),
`DAILY_REPORT_TIME` (default `21:00`), `BATTERY_CAPACITY_KWH`,
`LOAD_ALERT_PCT` (default 85), `SOLAR_CHECK_HOURS` (default `10-15`),
`FCM_SERVICE_ACCOUNT_JSON` (enables push alerts, see `bot/push.py`).
Commands only respond to `TELEGRAM_CHAT_ID` (a `filters.Chat` in `main.py`).

No linter or formatter is configured.

## Architecture

`main.py` wires everything together: builds `GrowattClient`, the Telegram
`Application`, a `Notifier`, and a `Scheduler`, then runs Telegram polling and
the scheduler side by side until SIGINT/SIGTERM.

- **`growatt/client.py`**: a *synchronous* `requests` client. Async code must
  call it through `await client.acall("method_name", *args)`, which runs the
  method in an executor and handles retries. `acall` is where the reliability
  logic lives:
  - Transient errors (`requests` errors, `GrowattAPIError`, `GrowattAuthError`)
    retry forever with exponential backoff (5s to 5min, jitter). After 10
    consecutive failures it calls `unreachable_callback` once per outage.
  - `GrowattDeviceOffline` (empty `obj`) makes `acall` **return `None`**, so
    callers must handle `None`.
  - `GrowattAuthLocked` (login `result: -1`, captcha or rate limit) waits from
    10 minutes up to 1 hour.
  - `GrowattAuthFatal` (login `result: -2`, bad credentials) is latched. Every
    later call fails fast and `fatal_auth_callback` fires once. This is
    deliberate: repeated bad logins trigger a captcha lockout that blocks even
    the correct password, so never add retry loops around login.
  - Session expiry (redirect to login, or login-page HTML) triggers one
    re-login and retry inside `_request`.
  - Logins go through `_ensure_login`, which holds a lock so concurrent jobs
    share one login (and one re-login on expiry). A caller that waited while
    another logged in reuses that result, and after a lockout no call tries
    to log in for 10 minutes.
- **`growatt/parsers.py`**: pure functions mapping raw payloads to metrics.
  They return `None` (never `0`) for missing fields. Grid presence is based on
  `vAcInput` against `GRID_DOWN_VOLTAGE` (180 V). Energy is integrated from the
  5-minute `userLoad` samples (12 per hour).
- **`scheduler.py`** plus `jobs/`: each job is a factory
  `make_x(client, notifier)` that returns an async `run()`, registered in
  `main.py` with `scheduler.register(name, interval_seconds, fn, run_immediately)`.
  Each job loops in its own task, and exceptions are logged without stopping
  other jobs. Job state (for example the last grid state in `grid_monitor`)
  lives in the factory closure.
- **`bot/commands.py`**: the `COMMANDS` list is the registry. `main.py` registers
  each entry, and unknown commands get the help listing. The client is injected
  through the module-level `bind_client()`. Handlers reply with `_safe_reply`.
- **`history.py`**: async history store (`snapshots`, `outages`), all
  timestamps UTC epoch seconds. Two backends with the same SQL: `D1Backend`
  (Cloudflare D1 HTTP `/query` API, used on Railway) and `LocalBackend`
  (sqlite3 file). Queries run in a thread so D1's HTTP calls don't block the
  event loop, and the schema is created lazily on the first successful call.
  History failures are logged and never block alerts. The `recorder` job writes a snapshot every 5 min.
  `grid_monitor` opens and closes outage rows and resumes an open one after a
  restart. `energy_report` integrates snapshots for a rolling 12h, skipping
  gaps over 15 min, and falls back to the day chart below 50% coverage.
  `batPower` is unsigned, so battery direction comes from `status`
  (`parsers.battery_direction`: 2 discharging, 5 to 10 charging).
- **`bot/notifications.py`**: `Notifier.send` plus message formatters.
  Alerts go through `Notifier.alert(kind, text)`, which always writes an
  `events` row and skips Telegram and push while muted (`muted_until_ts`).
  Push goes to the FCM topic `alerts` (HTTP v1 API, `bot/push.py`); the topic
  and channel id `alerts` are shared with the Android app.
- **D1 contract shared with the widget and app**: `snapshots` (plus
  `load_pct`, `inv_status`, `status`, `dtc` and the dashboard kWh counters
  `{pv,charge,discharge,import,load}_{today,total}_kwh`, added by
  `ALTER TABLE` in the lazy schema step), `outages`, `worker_state` (key/value: `started_ts`,
  `last_ok_ts`, `last_error`, `last_error_ts`, `muted_until_ts`,
  `battery_capacity_kwh`, `tz`; a leftover `battery_sign` is deleted at startup) and `events` (`kind` in
  `EVENT_KINDS`). Renaming any of these breaks the app.
- **`jobs/status_alerts.py`**: overload, fault (`dtc` change or `status` 3),
  battery full and solar stopped, all from one status poll. `energy_report`
  runs daily at `DAILY_REPORT_TIME` via `Scheduler.register_daily`.

## Growatt API notes

- The base URL is `https://openapi.growatt.com` (`client.py`). The README's
  mention of `server.growatt.com` is outdated.
- This inverter uses the **storage** panel endpoints, which need `plantId`:
  `POST /panel/storage/getStorageStatusData?plantId=…` (form `storageSn`),
  `POST /panel/storage/getStorageTotalData?plantId=…` (form `storageSn`; the
  dashboard's today/total kWh, see `parsers.ENERGY_TOTAL_FIELDS`) and
  `POST /panel/storage/getStorageEnergyDayChart` (form `plantId`, `storageSn`,
  `date`). `/panel/spf/*` returns 404.
- Login posts the MD5 of the password as `passwordCrc`, with `password` left empty.
- Real captured payloads are in `tests/fixtures/`. When you change a parser or
  field name, check it against those fixtures and run the tests.
- Treating an empty `obj` as "device offline" is an assumption that hasn't been
  observed live yet.

## macOS widget

`growatt-widget/` is an Xcode project: a host app (`App/`), a WidgetKit
extension (`Widget/`), and `Shared/` code compiled into both. It uses
file-system synchronized groups, so new files in those folders are picked up
without editing `project.pbxproj`. xcodegen isn't installed; the project file
is hand-written.

- Data comes from D1 only (latest `snapshots` row plus any open `outages`
  row) through the same `/query` endpoint as `D1Backend`. It must never call
  Growatt, because a second login risks the captcha lockout described above.
  If the snapshot schema changes, update `SnapshotRow` in
  `Shared/InverterStatus.swift`.
- Credentials are in `Shared/Secrets.json` (gitignored, D1 Read token),
  bundled at build time. Both targets are sandboxed, and there's no app group
  because the project is ad-hoc signed with no team. Each target reads its own
  bundle and caches in its own `UserDefaults`.
- Data older than 15 minutes is shown as stale, and nulls render as "n/a".
  Battery direction isn't shown (`batPower` is unsigned; direction needs
  the `status` column).

```bash
cd growatt-widget
xcodebuild -project GrowattWidget.xcodeproj -scheme GrowattWidget -configuration Release -derivedDataPath build build
```

`xcodebuild` fails inside the Claude Code sandbox because it can't write its
build files, so it has to run outside it. There are no tests.

## Flutter app

`growatt-app/` is a Riverpod + GoRouter Flutter app with four tabs (Now,
Charts, Activity, System). It reads D1 with SELECTs only, through
`lib/core/inverter/inverter_repository.dart`, and must never call Growatt.
It tolerates the old schema: "no such table/column" errors become empty results.

- Credentials: `--dart-define-from-file=secrets.json` (`accountId`,
  `databaseId`, `apiToken`, a D1 Read token). `secrets.json` is gitignored.
  `--dart-define=FAKE_DATA=true` (or `old_schema`) runs on generated data.
- Push alerts are Android only (iOS push needs a paid Apple account).
  `lib/core/push/push_setup.dart` initialises Firebase from the optional
  `fcm*` keys in `secrets.json`, with no `google-services.json` or Gradle
  plugin, and subscribes to the `alerts` topic. `MainActivity.kt` creates the
  high-importance `alerts` channel.
- The root `.gitignore` ignores `lib/`, so `growatt-app/.gitignore` re-includes it.
- Flutter writes to its SDK cache, so `flutter` commands fail inside the
  Claude Code sandbox.

```bash
cd growatt-app
flutter analyze && flutter test
flutter run --dart-define-from-file=secrets.json
flutter build apk --release --dart-define-from-file=secrets.json
```
