# growatt-monitor

A Python worker that connects a Growatt SPF inverter (via `server.growatt.com`)
to a Telegram bot. Provides:

- **Scheduled jobs**: grid on/off alerts (every 60s), 12-hour energy reports.
- **On-demand commands**: `/pv`, `/load`, `/battery`, `/grid`, `/status`.

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
| `TELEGRAM_TOKEN`     | Bot token from @BotFather                           |
| `TELEGRAM_CHAT_ID`   | Chat ID to send alerts to (use @userinfobot to find)|

## Local run

```bash
pip install -r requirements.txt
export GROWATT_USERNAME=...
export GROWATT_PASSWORD=...
export GROWATT_DEVICE_SN=KHM9F990N7
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
4. Open the service → **Variables** → set the five environment variables above.
5. Deploy. You should see `🟢 Growatt Monitor is online` in your Telegram chat.

If the bot crashes, Railway will restart the worker; on shutdown it sends
`🔴 Growatt Monitor is shutting down`. Errors during runtime are logged to
stdout (visible in the Railway logs tab).

## Verifying API field names

The exact JSON keys returned by `server.growatt.com` for this account /
firmware have **not** been verified live — see the TODO comments in
`growatt/parsers.py`. After first deploy, temporarily add:

```python
log.info("status payload: %s", await client.acall("get_device_status"))
```

near the top of `main.py`, run once, then adjust any parser keys that don't
match. Remove the log line afterwards.

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
