# growatt-monitor to-do

Ideas for growing the bot, roughly in the order they pay off. Tick them off as
they ship.

## Fixes

- [ ] **Timezone.** Railway runs in UTC, so `energy_report`'s day-chart date is
  wrong around local midnight. Add a `TZ` setting and use it for dates and for
  showing clock times.
- [ ] **Daily report at a fixed time** (e.g. 21:00 local) instead of every 12h
  counted from whenever the worker started.

## New commands

- [ ] `/today`: today's kWh used, on demand.
- [ ] `/runtime`: estimated battery time left at the current load. Needs a new
  battery-capacity setting (kWh).
- [ ] `/flow`: one-line power snapshot, e.g. "PV 1.2 kW → load 0.8 kW, battery
  +0.4 kW charging, grid 0 W". Confirm `batPower`'s sign (charging vs
  discharging) against the live dashboard first.
- [ ] `/faults`: inverter mode and fault code (`invStatus`, `status`, `dtc`)
  in plain words.
- [ ] `/chart`: today's load and solar curve as an image (matplotlib).
- [ ] `/mute 2h`: pause alerts for a while.
- [ ] `/uptime`: worker uptime, last successful Growatt call, recent errors.

## Alerts

- [ ] **Overload**: warn when `loadPrecent` goes above ~85%, before the
  inverter trips.
- [ ] **Fault code**: alert when `dtc` changes.
- [ ] **Battery full**.
- [ ] **Solar stopped**: no PV during daylight (dirty panels, tripped breaker).

## History (D1)

- [ ] `/week` and `/month` energy totals.
- [ ] Solar vs grid split: how much of the energy used came from each.
- [ ] Battery health trend (voltage at a given SOC over weeks).

## Code health

- [ ] Shared wrapper for the command handlers' repeated try/except and
  offline handling, so each new command is a few lines.
- [ ] Capture a real `getStorageEnergyDayChart` payload into `tests/fixtures/`
  and test `total_load_energy_kwh` against it.
- [ ] Confirm that an offline inverter really returns an empty `obj` (the
  client assumes so; not yet observed live).

## Done

- [x] Commands only answer `TELEGRAM_CHAT_ID`.
- [x] Low-battery alerts (`BATTERY_ALERT_LEVELS`, default 30% and 15%).
- [x] Outage length in the grid-restored alert.
- [x] History in Cloudflare D1: 5-minute snapshots and an outage log.
- [x] `/outages` command.
- [x] Rolling 12h energy report from history.
- [x] One shared Growatt login across jobs.
- [x] Bot token no longer printed in logs.
