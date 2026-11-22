"""Overload, fault, battery-full and solar-stopped alerts, all checked from a
single status poll so these four alerts cost one Growatt call per run."""
import logging
import time
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from growatt import parsers
from bot.notifications import fmt_duration, fmt_status_code

log = logging.getLogger(__name__)

Alert = tuple[str, str]
Check = Callable[[dict, float], Optional[Alert]]

OVERLOAD_REARM_MARGIN = 10.0
BATTERY_FULL_SOC = 99.0
BATTERY_FULL_REARM_SOC = 95.0
SOLAR_LOW_WATTS = 50.0
SOLAR_LOW_SECONDS = 30 * 60
# Above this PV voltage the panels are live, so low PV power means the inverter
# isn't drawing from them (battery full, grid bypass), not a solar fault.
SOLAR_LIVE_VOLTAGE = 120.0


def make_overload_check(threshold_pct: float) -> Check:
    # Starts armed so an overload already in progress at boot still alerts.
    state = {"armed": True}

    def check(data: dict, _now: float) -> Optional[Alert]:
        pct = parsers.load_percent(data)
        if pct is None:
            return None
        if not state["armed"]:
            if pct < threshold_pct - OVERLOAD_REARM_MARGIN:
                state["armed"] = True
            return None
        if pct > threshold_pct:
            state["armed"] = False
            load = parsers.load_watts(data)
            watts = f" ({load:.0f} W)" if load is not None else ""
            return "overload", f"🔥 Overload: load at {pct:.0f}% of inverter rating{watts}"
        return None

    return check


def make_fault_check() -> Check:
    # The first reading after boot is only a baseline.
    state = {"dtc": None, "faulted": None}

    def check(data: dict, _now: float) -> Optional[Alert]:
        code = parsers.dtc(data)
        status = parsers.status_code(data)
        msgs = []
        if code is not None:
            if state["dtc"] is not None and code != state["dtc"]:
                msgs.append(f"fault code changed {state['dtc']} → {code}")
            state["dtc"] = code
        if status is not None:
            faulted = status == parsers.FAULT_STATUS
            if state["faulted"] is False and faulted:
                msgs.append(f"inverter reports {fmt_status_code(status)}")
            state["faulted"] = faulted
        if not msgs:
            return None
        return "fault", "🛠 Inverter fault: " + "; ".join(msgs)

    return check


def make_battery_full_check() -> Check:
    # None until the first reading, so a battery already full at boot doesn't alert.
    state = {"armed": None}

    def check(data: dict, _now: float) -> Optional[Alert]:
        soc = parsers.battery_soc(data)
        if soc is None:
            return None
        if state["armed"] is None:
            state["armed"] = soc < BATTERY_FULL_SOC
            return None
        if not state["armed"]:
            if soc < BATTERY_FULL_REARM_SOC:
                state["armed"] = True
            return None
        if soc >= BATTERY_FULL_SOC:
            state["armed"] = False
            return "battery_full", f"🔋 Battery full ({soc:.0f}%)"
        return None

    return check


def make_solar_check(hours: tuple[int, int], tz: ZoneInfo) -> Check:
    state = {"low_since": None, "alerted": False}

    def check(data: dict, now: float) -> Optional[Alert]:
        hour = datetime.fromtimestamp(now, tz).hour
        if not hours[0] <= hour < hours[1]:
            state["low_since"] = None
            state["alerted"] = False
            return None
        pv = parsers.pv_watts(data)
        if pv is None:
            return None
        pv_v = parsers.pv_voltage(data)
        panels_live = pv_v is not None and pv_v >= SOLAR_LIVE_VOLTAGE
        if pv >= SOLAR_LOW_WATTS or panels_live:
            state["low_since"] = None
            state["alerted"] = False
            return None
        if state["low_since"] is None:
            state["low_since"] = now
        if state["alerted"] or now - state["low_since"] < SOLAR_LOW_SECONDS:
            return None
        state["alerted"] = True
        volts = f", {pv_v:.0f} V" if pv_v is not None else ""
        return "solar_stopped", (
            f"🌥 Solar stopped: PV {pv:.0f} W{volts} for "
            f"{fmt_duration(now - state['low_since'])} in daylight. "
            "Check the panels and PV breaker."
        )

    return check


def make_status_alerts(client, notifier, load_alert_pct: float,
                       solar_hours: tuple[int, int], tz: ZoneInfo, clock=time.time):
    checks = [
        make_overload_check(load_alert_pct),
        make_fault_check(),
        make_battery_full_check(),
        make_solar_check(solar_hours, tz),
    ]

    async def run() -> None:
        data = await client.acall("get_device_status")
        if data is None:
            log.info("status_alerts: device offline, skipping")
            return
        now = clock()
        for check in checks:
            alert = check(data, now)
            if alert is not None:
                log.info("status_alerts: %s", alert[0])
                await notifier.alert(*alert)

    return run
