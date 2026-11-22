# growatt-monitor to-do

Ideas for growing the bot, roughly in the order they pay off. Tick them off as
they ship.

## Fixes

- [x] **Timezone.** Railway runs in UTC, so `energy_report`'s day-chart date is
  wrong around local midnight. Add a `TZ` setting and use it for dates and for
  showing clock times.
- [x] **Daily report at a fixed time** (e.g. 21:00 local) instead of every 12h
  counted from whenever the worker started.

## New commands

- [x] `/today`: today's kWh used, on demand.
- [x] `/runtime`: estimated battery time left at the current load. Needs a new
  battery-capacity setting (kWh).
- [x] `/flow`: one-line power snapshot, e.g. "PV 1.2 kW → load 0.8 kW, battery
  +0.4 kW charging, grid 0 W". Battery direction shows only once
  `BATTERY_SIGN` is set.
- [x] Confirm `batPower`'s sign: positive while charging, so
  `BATTERY_SIGN=charge_positive`.
- [x] `/faults`: inverter mode and fault code (`invStatus`, `status`, `dtc`)
  in plain words.
- [x] `/chart`: today's load and solar curve as an image (matplotlib).
- [x] `/mute 2h`: pause alerts for a while.
- [x] `/uptime`: worker uptime, last successful Growatt call, recent errors.

## Alerts

- [x] **Overload**: warn when `loadPrecent` goes above ~85%, before the
  inverter trips.
- [x] **Fault code**: alert when `dtc` changes, or `status` turns 3 (fault).
- [ ] Check whether `dtc` (20006 on a healthy inverter) is a fault code or a
  device-type code, and confirm the `status` names `/faults` shows.
- [x] **Battery full**.
- [x] **Solar stopped**: no PV during daylight (dirty panels, tripped breaker).

## History (D1)

- [x] `/week` and `/month` energy totals.
- [x] Solar vs grid split: how much of the energy used came from each.
- [x] Battery health trend (voltage at a given SOC over weeks).

## Code health

- [x] Shared wrapper for the command handlers' repeated try/except and
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
