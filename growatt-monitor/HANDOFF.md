# Handoff: growatt-monitor (Telegram outage + diagnosis bot)

Context for picking this project up in Claude Code. Start Claude Code from the
repo root and say: "Read growatt-monitor/HANDOFF.md and continue from it."

Last updated: 2026-11-21.

---

Use the workflow-orchestrator skill. You're picking up work on `growatt-monitor/` in this repo: a Python worker on Railway (python-telegram-bot v20, polling) that reads my Growatt SPF 6000 ES PLUS via the unofficial web API and sends Telegram alerts and command replies.

## State right now

- Branch `fix/storage-endpoints` (commit `110b064`) is pushed and NOT merged. It fixes the bot always replying "Inverter is offline":
  - Root cause: `/panel/spf/getSPFStatusData` returns 404 for this account and the client mapped 404 to "offline".
  - Correct endpoints (verified live against the web dashboard on 2026-11-21):
    - `POST /panel/storage/getStorageStatusData?plantId=10808840`, form `storageSn=KHM9F990N7`
    - `POST /panel/storage/getStorageEnergyDayChart`, form `plantId`, `storageSn`, `date=YYYY-MM-DD`
    - Base URL `https://openapi.growatt.com`
  - Real status fields: `vAcInput` (grid V), `ppv1`/`ppv2` (PV W), `vPv1` (PV V), `loadPower`, `capacity` (SOC %), `vBat`, `gridPower`, `status`, `invStatus`. Fixture: `growatt-monitor/tests/fixtures/storage_status.json`.
  - Day chart: `obj.charts.{userLoad, ppv, pacToUser, pacToGrid, sysOut}`, 288 samples of watts at 5-minute intervals (so the datalogger uploads every 5 min; polling faster than that returns duplicates).
  - New required env var `GROWATT_PLANT_ID=10808840`.
- Still to do before it's live: add `GROWATT_PLANT_ID` in Railway, merge to `main`, confirm `/status` returns real data and the logs show `Growatt login successful`.

## Known remaining issues

1. `GrowattClient.acall` retries forever. A command run while Growatt is down never replies and multiplies requests, which risks the captcha lockout.
2. One `requests.Session` is shared across executor threads with no login lock, so concurrent re-logins are possible.
3. No staleness detection. If the router or datalogger loses power with the grid, no outage alert is sent.
4. No debounce on grid state, and state is lost on restart.
5. The energy report is "today so far" because a rolling 12h needs history.

## Target architecture (agreed direction, plan before building)

One collector is the only Growatt caller. It normalizes each reading into a `Snapshot` and saves it. Everything else reads snapshots.

| Layer | Job |
|---|---|
| Collector | Polls once per datalogger interval, bounded retries, login lock, dedupes by reading timestamp, writes the store |
| Snapshot store | Latest in memory plus history in SQLite on a Railway volume (default choice; confirm with me) |
| Event detector | Grid on/off with 2-read debounce, fault raised/cleared, data stale (>10 min), state persisted |
| Diagnosis engine | Plugin rules `(snapshot, history) -> Finding(severity, why, action)`, run each poll for critical alerts and on demand via `/diagnose` |
| Command handlers | Existing registry, read from the store, show "as of HH:MM" |
| Notifier | Dedup plus cooldown per finding |

Proposed order: (1) Snapshot + mapper, (2) collector job with bounded retries + lock, (3) store, (4) event detector replacing `jobs/grid_monitor.py`, (5) commands read store, (6) diagnosis engine + `/diagnose` + notifier cooldowns, (7) energy report from history at fixed times (07:00 and 19:00 WAT).

Starter diagnosis rules:
- PV voltage < 120V in daylight: MPPT not activating (panels must be 9S×1P; ~292V is normal)
- PV voltage OK but ~0W at midday: PV breaker or MPPT issue
- Error 09 followed by 5109 within minutes: battery can't start the DC bus
- Error 09 that clears within N minutes of grid return: info only
- Load near 6kW or 5004 derating: overload
- Grid off: runtime estimate from remaining kWh / load
- No fresh data > 10 min: datalogger/router/internet offline, distinct from grid off

System context: Growatt SPF 6000 ES PLUS (6kW, single MPPT, 120 to 450V window), 9× 300W panels in series, Deye LiFePO4 battery just installed with RS485 to the inverter. Inverter battery type (program 05) is still on AGM until the installer sets Li and the protocol (program 36), so treat SOC as low-confidence for now.

Open decisions to confirm with me before implementing: storage (SQLite on volume vs Postgres vs memory only), diagnosis style (rules only for v1, LLM explain layer later), whether Solvue should later read from this service.

Verification: pytest for the mapper (real fixture), each rule (synthetic histories), detector debounce and staleness; then a local run against the live API before deploying.
