# growatt-monitor

A Python worker that connects a Growatt SPF inverter (via `server.growatt.com`)
to a Telegram bot. Provides:

- **Scheduled jobs**: grid on/off alerts with outage duration (every 120s),
  low-battery alerts (every 5 min), 12-hour energy reports, and a
  history recorder that saves a reading every 5 min to Cloudflare D1
  (or a local SQLite file when D1 isn't configured).
- **On-demand commands**: `/pv`, `/load`, `/battery`, `/grid`, `/status`, `/outages`.
  The bot only answers `TELEGRAM_CHAT_ID`; messages from any other chat are ignored.

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
4. Open the service → **Variables** → set the six environment variables above.
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

The 12-hour energy report uses the history once it covers at least half the
window, and falls back to today's day-chart total until then.

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

That's it. The scheduler runs all jobs concurrently via `asyncio`, and a crash
in one job does not affect the others — the loop catches exceptions and resumes
on the next interval.

### Adding a new Telegram command

1. Add a handler to `bot/commands.py`:
   ```python
   async def cmd_hello(update, _ctx):
       await _safe_reply(update, "hi")
   ```
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
- **Job isolation**: each scheduled job is wrapped; a crash logs and continues.
- **Command errors**: each handler replies with a friendly message on failure.
- **Logging**: all errors logged with timestamps via the `logging` module.
