# growatt-app

A read-only phone dashboard (Android and iOS) for the Growatt inverter. It
shows what the Telegram bot shows, without typing commands.

The app reads only the Cloudflare D1 database that the `growatt-monitor`
worker writes to: 5-minute `snapshots`, `outages`, and, once the worker is
updated, `worker_state` and `events`. It sends `SELECT`s only, through D1's
HTTP `/query` endpoint. It never calls Growatt, because a second login risks
the captcha lockout. Data is up to about 5 minutes old.

## Tabs

- **Now**: solar, load (and % of rated), battery SOC and voltage, grid state
  and voltage or "outage for Xh Ym", a flow line, runtime at the current
  load, the inverter status (in words, using the SPF code table the worker
  uses, plus the raw code) with the raw `invStatus` and `dtc`, data age (flagged after 15 min),
  and a banner while alerts are muted. Pull to refresh. It also refreshes
  every 60 s while open and when the app comes back to the foreground. The
  last good result is cached, so a failed refresh still shows saved data.
- **Charts**: load vs solar and battery SOC, for today or the last 24 h. Energy
  for today, 7 days and 30 days (load, solar, grid), integrated the same way
  as the worker's `History.load_energy`: trapezoids, skipping gaps over 15
  min. The 7- and 30-day windows are rolling, not calendar weeks or months.
  Battery health is the weekly mean voltage at 45–55 % SOC.
- **Activity**: the `events` feed and the outage list.
- **System**: worker uptime, last good Growatt call, last error, data age,
  time zone, and battery settings.

Times use `worker_state.tz`, or the phone's time zone if that isn't set.
Missing values show "n/a", never 0. Battery direction (charging or
discharging) shows only when the worker sets `battery_sign`, because the sign
of `batPower` hasn't been confirmed.

The app also works with the old schema, before the worker is redeployed. If D1
answers "no such table" or "no such column", that counts as no data. Cards
that depend on missing data are hidden or show "n/a".

## Setup

Flutter is at `~/DevSDKs/flutter/bin/flutter` on the dev Mac. Run these from
`growatt-app/`.

```bash
cp secrets.example.json secrets.json
```

Fill in `accountId`, `databaseId` and `apiToken`. Use a Cloudflare API token
with only **D1 Read** permission, such as the one the macOS widget uses.
`secrets.json` is gitignored. The values are compiled in with
`--dart-define-from-file`. A build without them opens a "Not configured"
screen.

```bash
flutter pub get
flutter run --dart-define-from-file=secrets.json
```

To try the UI without credentials, use generated sample data. The second
command also simulates the old schema, with no `worker_state` or `events`
and an outage in progress.

```bash
flutter run --dart-define=FAKE_DATA=true
```

```bash
flutter run --dart-define=FAKE_DATA=old_schema
```

Checks:

```bash
flutter analyze
```

```bash
flutter test
```

## Install on Android

```bash
flutter build apk --release --dart-define-from-file=secrets.json
```

The APK is written to `build/app/outputs/flutter-apk/app-release.apk`. Copy it
to the phone and open it (allow installs from unknown sources), or, with USB
debugging on:

```bash
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

The release build is signed with the debug key, which is fine for sideloading.

## Install on iOS

With a free Apple ID (no paid developer account):

1. Open `ios/Runner.xcworkspace` in Xcode.
2. Under Runner → Signing & Capabilities, choose your personal team, and
   change the bundle identifier (`com.homelab.growattApp`) if Xcode says it
   is taken.
3. Plug in the iPhone, select it as the run destination, and build once from
   the terminal so the secrets are compiled in:

   ```bash
   flutter run --release --dart-define-from-file=secrets.json
   ```

4. On the phone, trust the developer profile under Settings → General → VPN &
   Device Management, and turn on Developer Mode if asked.

With free signing the app stops opening after 7 days. Run step 3 again to
reinstall it.

For the Simulator:

```bash
flutter run -d "iPhone 17" --dart-define-from-file=secrets.json
```

## Security caveat

The D1 token is compiled into the app, and anyone with the APK or IPA can
extract it. Use a token with only the **D1 Read** permission. Cloudflare
scopes D1 permissions to the account, so the token can read every D1 database
in that account, but it can't write to any of them or reach Growatt or
Telegram. If a phone is lost, revoke the token in the Cloudflare
dashboard and rebuild with a new one.

## Layout

```
lib/
  main.dart                     ProviderScope, time zone data, prefs
  app/                          MaterialApp, GoRouter bottom-nav shell, not-configured screen
  core/
    config/d1_config.dart       credentials from --dart-define, FAKE_DATA switch
    d1/                         D1Source interface, Dio D1Client, FakeD1Source
    inverter/                   models, energy integration, time zone clock, repository
    providers.dart              Riverpod providers (override d1SourceProvider in tests)
  features/{now,charts,activity,system}/presentation/
  shared/                       theme tokens, formatters, cards
```
