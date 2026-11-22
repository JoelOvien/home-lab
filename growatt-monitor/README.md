# growatt-monitor

A Python worker that connects a Growatt SPF inverter (via `openapi.growatt.com`)
to a Telegram bot. Provides:

- **Scheduled jobs**: grid on/off alerts with outage duration (every 120s),
  low-battery alerts (every 5 min), overload / fault / battery-full /
  solar-stopped alerts (every 5 min), a daily energy report at
  `DAILY_REPORT_TIME`, and a history recorder that saves a reading every 5 min
  to Cloudflare D1 (or a local SQLite file when D1 isn't configured).
- **On-demand commands** (below). The bot only answers `TELEGRAM_CHAT_ID`;
  messages from any other chat are ignored.

Designed to run on Railway as a `worker` process (no HTTP server).

---

## Configuration

All config is via environment variables. The service fails fast at startup if
any are missing.

| Variable             | Description                                         |
|----------------------|-----------------------------------------------------|
| `GROWATT_USERNAME`   | Growatt portal account                              |
| `GROWATT_PASSWORD`   | Growatt portal password (sent MD5-hashed)           |
| `GROWATT_DEVICE_SN`  | Device serial number (e.g. `KHM9F990N7`)            |
| `GROWATT_PLANT_ID`   | Plant ID (`plantId` in dashboard requests, e.g. `10808840`) |
| `TELEGRAM_TOKEN`     | Bot token from @BotFather                           |
| `TELEGRAM_CHAT_ID`   | Numeric chat ID for alerts, and the only chat allowed to run commands (use @userinfobot to find)|
| `CLOUDFLARE_ACCOUNT_ID` | Optional. Set all three Cloudflare variables to store history in D1 (see below). |
| `CLOUDFLARE_D1_DATABASE_ID` | Optional. The D1 database ID. |
| `CLOUDFLARE_API_TOKEN` | Optional. API token with D1 Edit permission. |
| `HISTORY_DB_PATH` | Optional. Local SQLite file used when D1 isn't configured, default `data/history.db`. |
| `BATTERY_ALERT_LEVELS` | Optional. SOC % levels that trigger a low-battery alert, default `30,15`. A level re-arms once SOC is 5% above it. |
| `TZ` | Optional. IANA time zone (e.g. `Africa/Lagos`) for dates, the daily report and clock times shown. Default `UTC`. |
| `DAILY_REPORT_TIME` | Optional. Local `HH:MM` for the daily energy report, default `21:00`. |
| `BATTERY_CAPACITY_KWH` | Optional. Usable battery size in kWh, needed by `/runtime`. |
| `LOAD_ALERT_PCT` | Optional. Overload alert threshold as % of inverter rating (`loadPrecent`), default `85`. Re-arms 10 points below. |
| `SOLAR_CHECK_HOURS` | Optional. Local hour range for the solar-stopped alert, default `10-15` (10:00 to 14:59). |
| `BATTERY_SIGN` | Optional. `charge_positive` or `charge_negative`: whether `batPower` is positive while charging. While unset, battery direction isn't shown. |

For this installation (SPF 6000 ES PLUS, confirmed against the Growatt
dashboard) set `TZ=Africa/Lagos`, `BATTERY_CAPACITY_KWH=5` and
`BATTERY_SIGN=charge_positive` in Railway. The code defaults stay `UTC`,
unset and unset.

## Commands

| Command | What it does | Data source |
|---|---|---|
| `/status`, `/pv`, `/load`, `/battery`, `/grid` | Live readings | Growatt |
| `/flow` | One-line power flow: PV → load, battery, grid | Growatt |
| `/runtime` | Battery time left at the current load (SOC × capacity ÷ load) | Growatt |
| `/faults` | Inverter mode (`status`), `invStatus`, fault code (`dtc`) | Growatt |
| `/today` | Energy used today, plus solar made and grid drawn | History (day chart fallback) |
| `/week`, `/month` | Same totals for the last 7 / 30 days | History |
| `/chart` | PNG of today's load, PV and SOC | History |
| `/health` | Weekly mean battery voltage at 45–55% SOC | History |
| `/outages` | Last 10 grid outages | History |
| `/mute 2h`, `/unmute` | Pause / resume alerts (`30m`, `1d`, `1h30m`; up to 30 days). Survives restarts. | — |
| `/uptime` | Worker uptime, last good Growatt call, recent errors | — |

Muting only silences Telegram: every alert is still written to the `events`
table. "From grid" in the energy totals includes any battery charging from the
grid, so solar + grid doesn't have to equal what was used.

## Alerts

| Alert | Fires when | Re-arms |
|---|---|---|
| Grid lost / restored | `vAcInput` crosses 180 V | on each change |
| Battery low | SOC at or below each `BATTERY_ALERT_LEVELS` value | SOC 5% above the level |
| Overload | `loadPrecent` above `LOAD_ALERT_PCT` (alerts even at boot) | 10 points below the threshold |
| Fault | `dtc` changes, or `status` turns 3 (fault); the first reading after boot is a baseline | on each change |
| Battery full | SOC ≥ 99% (not if already full at boot) | SOC below 95% |
| Solar stopped | PV < 50 W for 30 min within `SOLAR_CHECK_HOURS`, and PV voltage below 120 V (live panels with low power just mean the inverter isn't drawing them) | PV recovers, or the next day |
| Growatt unreachable | 10 consecutive failed calls | next success |

## Local run

```bash
pip install -r requirements.txt
export GROWATT_USERNAME=...
export GROWATT_PASSWORD=...
export GROWATT_DEVICE_SN=KHM9F990N7
export GROWATT_PLANT_ID=10808840
export TELEGRAM_TOKEN=...
export TELEGRAM_CHAT_ID=...
python main.py
```

## Deploy to Railway

1. Push this directory to a GitHub repo.
2. In Railway, **New Project → Deploy from GitHub** and select the repo.
3. Railway auto-detects Python via `requirements.txt`. The `Procfile` declares
   a single `worker:` process — Railway will run `python main.py`. There is no
   web service, so **do not** add a public domain.
4. Open the service → **Variables** → set the six required environment variables above (plus any optional ones).
5. Deploy. You should see `🟢 Growatt Monitor is online` in your Telegram chat.

### Storing history in Cloudflare D1

Railway's filesystem is wiped on every deploy, so on Railway the history
(snapshots and outage log) should live in Cloudflare D1:

1. In the Cloudflare dashboard, go to **Storage & Databases → D1** and create a
   database (any name, e.g. `growatt-history`). Copy its **Database ID**.
2. Copy your **Account ID** (shown on the account home page or in the D1 page's
   sidebar).
3. Go to **My Profile → API Tokens → Create Token → Custom token**. Give it one
   permission, **Account → D1 → Edit**, limited to your account. Copy the token.
4. In Railway, set `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_D1_DATABASE_ID` and
   `CLOUDFLARE_API_TOKEN`.

The tables are created automatically on the first successful call. If D1 is
unreachable, that reading or outage row is dropped and logged; alerts still
go out. Without the Cloudflare variables the bot uses a local SQLite file,
which is handy for local runs.

The daily energy report (and `/today`) integrates history since local
midnight once it covers at least half of that time, and falls back to today's
day-chart total until then.

Besides `snapshots` and `outages`, the worker keeps two tables for the mobile
app (`growatt-app/`) to read:

- `worker_state(key, value, updated_ts)`: `started_ts`, `tz`,
  `battery_capacity_kwh`, `battery_sign` (written at startup; the last two are
  deleted when unset), `last_ok_ts` (at most every 5 min), `last_error`,
  `last_error_ts`, `muted_until_ts`.
- `events(id, ts, kind, detail)`: one row per alert, with `kind` one of
  `grid_down`, `grid_up`, `battery_low`, `battery_full`, `overload`, `fault`,
  `solar_stopped`, `unreachable`, and `detail` the alert text.

New `snapshots` columns (`load_pct`, `inv_status`, `status`, `dtc`) are added
to an existing database automatically; older rows have NULL there.

If the bot crashes, Railway will restart the worker; on shutdown it sends
`🔴 Growatt Monitor is shutting down`. Errors during runtime are logged to
stdout (visible in the Railway logs tab).

## Growatt endpoints and field names

Verified 2026-11-21 against the live web dashboard. The SPF 6000 ES PLUS is
served by the **storage** panel endpoints, which need `plantId`:

| Purpose | Endpoint | Params |
|---|---|---|
| Live status | `POST /panel/storage/getStorageStatusData?plantId=…` | form: `storageSn` |
| Day chart (5-min samples) | `POST /panel/storage/getStorageEnergyDayChart` | form: `plantId`, `storageSn`, `date` |

`/panel/spf/*` returns 404. Real payloads live in `tests/fixtures/`; run
`python -m pytest` after changing any parser.

## Architecture

Two registries make extension trivial:

### Adding a new scheduled job

1. Create `jobs/my_job.py`:
   ```python
   def make_my_job(client, notifier):
       async def run():
           data = await client.acall("get_device_status")
           # … do something …
       return run
   ```
2. Register it in `main.py`:
   ```python
   from jobs.my_job import make_my_job
   scheduler.register("my_job", interval_seconds=300, fn=make_my_job(client, notifier))
   ```

For a job at a fixed local time, use
`scheduler.register_daily("name", "21:00", cfg.tz, fn)`.

That's it. The scheduler runs all jobs concurrently via `asyncio`, and a crash
in one job does not affect the others — the loop catches exceptions and resumes
on the next interval.

### Adding a new Telegram command

1. Add a handler to `bot/commands.py`. The decorators handle errors, the
   offline case and the reply:
   ```python
   @status_command          # gets the live payload; replies "offline" on None
   def cmd_hello(data):
       return f"PV is {parsers.pv_watts(data)} W"
   ```
   Use `@history_command` for history-backed replies and `@command` for
   anything else (both take `async def fn(update, ctx)` returning the text).
2. Append to the `COMMANDS` list:
   ```python
   Command("hello", "Say hi", cmd_hello),
   ```

`main.py` iterates `COMMANDS` to register handlers, so no other wiring is
needed. Unknown commands automatically reply with the help listing.

## Reliability

- **Session expiry**: any API call that returns a login redirect or login-page
  HTML triggers an automatic re-login + one retry.
- **Network errors**: exponential backoff, 5s → 5min cap, with jitter.
- **Unreachable alert**: after 10 consecutive failures, sends
  `⚠️ Cannot reach Growatt API. Will keep retrying.` to Telegram (once per
  outage; resets on the next success).
- **Health in history**: each Growatt call updates `last_ok_ts` or
  `last_error` in `worker_state`, without changing the retry or login logic.
- **Job isolation**: each scheduled job is wrapped; a crash logs and continues.
- **Command errors**: each handler replies with a friendly message on failure.
- **Logging**: all errors logged with timestamps via the `logging` module.
