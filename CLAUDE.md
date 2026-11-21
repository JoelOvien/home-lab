# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

`home-lab` is a container for home-lab projects. Currently the only one is
`growatt-monitor/`: a Python asyncio worker that polls a Growatt SPF 6000 ES PLUS
inverter through the Growatt web dashboard API and talks to a Telegram bot
(scheduled alerts plus on-demand commands). It runs on Railway as a `worker`
process (`Procfile`). There is no HTTP server, so don't add one.

All commands below run from `growatt-monitor/`. Imports are top-level
(`from growatt import parsers`), so run things from that directory.

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
  `batPower` is stored raw because its sign convention is unverified.
- **`bot/notifications.py`**: `Notifier.send` plus message formatters.

## Growatt API notes

- The base URL is `https://openapi.growatt.com` (`client.py`). The README's
  mention of `server.growatt.com` is outdated.
- This inverter uses the **storage** panel endpoints, which need `plantId`:
  `POST /panel/storage/getStorageStatusData?plantId=…` (form `storageSn`) and
  `POST /panel/storage/getStorageEnergyDayChart` (form `plantId`, `storageSn`,
  `date`). `/panel/spf/*` returns 404.
- Login posts the MD5 of the password as `passwordCrc`, with `password` left empty.
- Real captured payloads are in `tests/fixtures/`. When you change a parser or
  field name, check it against those fixtures and run the tests.
- Treating an empty `obj` as "device offline" is an assumption that hasn't been
  observed live yet.
