"""Telegram command handlers.

To add a command, write a function that returns the reply text and decorate it
with @command (no Growatt call), @status_command (gets the live status payload)
or @history_command (needs history), then append it to COMMANDS at the bottom.
main.py wires them into the Application.
"""
import asyncio
import functools
import io
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, List, Optional
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import (
    fmt_clock, fmt_duration, fmt_energy_split, fmt_outages, fmt_status_code,
)
from jobs.energy_report import local_midnight, today_energy_text

log = logging.getLogger(__name__)

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


@dataclass
class Command:
    name: str            # without leading slash
    description: str
    handler: Handler


@dataclass
class Settings:
    tz: ZoneInfo = ZoneInfo("UTC")
    battery_capacity_kwh: Optional[float] = None
    battery_sign: Optional[str] = None


# Injected by main.py at startup.
_client: GrowattClient | None = None
_history = None
_notifier = None
_health = None
_settings = Settings()
_clock: Callable[[], float] = time.time


def bind_client(client: GrowattClient) -> None:
    global _client
    _client = client


def bind_history(history) -> None:
    global _history
    _history = history


def bind(notifier=None, health=None, settings: Optional[Settings] = None, clock=None) -> None:
    global _notifier, _health, _settings, _clock
    if notifier is not None:
        _notifier = notifier
    if health is not None:
        _health = health
    if settings is not None:
        _settings = settings
    if clock is not None:
        _clock = clock


def _require_client() -> GrowattClient:
    if _client is None:
        raise RuntimeError("Growatt client not bound — call bind_client() at startup")
    return _client


async def _safe_reply(update: Update, text: str) -> None:
    if update.message is not None:
        await update.message.reply_text(text)


async def _safe_reply_photo(update: Update, png: bytes, caption: str) -> None:
    if update.message is not None:
        await update.message.reply_photo(photo=png, caption=caption)


async def _fetch_status() -> dict | None:
    client = _require_client()
    return await client.acall("get_device_status")


OFFLINE_MSG = "📴 Inverter is offline — no live data right now."
GROWATT_ERROR_MSG = "⚠️ Could not reach Growatt API. Try again shortly."
HISTORY_ERROR_MSG = "⚠️ Could not read history. Try again shortly."
NO_HISTORY_MSG = "History is not enabled."

ReplyFn = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Optional[str]]]


def command(fn: ReplyFn = None, *, error_msg: str = GROWATT_ERROR_MSG):
    """Turn a function returning reply text into a handler that logs errors
    and replies with error_msg instead. Returning None sends nothing."""
    if fn is None:
        return functools.partial(command, error_msg=error_msg)
    name = fn.__name__.removeprefix("cmd_")

    @functools.wraps(fn)
    async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            text = await fn(update, ctx)
        except Exception:
            log.exception("/%s failed", name)
            text = error_msg
        if text:
            await _safe_reply(update, text)

    return handler


def status_command(render: Callable[[dict], str]):
    """Fetch the live status, reply OFFLINE_MSG when there is none, else render it."""
    async def fn(_update, _ctx):
        data = await _fetch_status()
        return OFFLINE_MSG if data is None else render(data)

    fn.__name__ = render.__name__
    return command(fn)


def history_command(fn: ReplyFn):
    @functools.wraps(fn)
    async def guarded(update, ctx):
        if _history is None:
            return NO_HISTORY_MSG
        return await fn(update, ctx)

    return command(guarded, error_msg=HISTORY_ERROR_MSG)


def _fmt_w(v: float | None) -> str:
    return f"{v:.0f} W" if v is not None else "n/a"


def _fmt_power(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v / 1000:.1f} kW" if abs(v) >= 1000 else f"{v:.0f} W"


def _fmt_v(v: float | None) -> str:
    return f"{v:.1f} V" if v is not None else "n/a"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.0f}%" if v is not None else "n/a"


def _grid_state(present: bool | None) -> str:
    return "ON" if present else ("OFF" if present is False else "unknown")


# ---------- pure renderers (tested directly) ----------

def battery_direction(bat_w: float | None, sign: str | None) -> str:
    if bat_w is None:
        return "n/a"
    if bat_w == 0:
        return "idle"
    if sign is None:
        return f"{_fmt_power(abs(bat_w))} (direction unknown)"
    charging = (bat_w > 0) == (sign == "charge_positive")
    return f"{_fmt_power(abs(bat_w))} {'charging' if charging else 'discharging'}"


def render_flow(data: dict, sign: str | None) -> str:
    return (
        f"☀️ PV {_fmt_power(parsers.pv_watts(data))} → "
        f"⚡ load {_fmt_power(parsers.load_watts(data))} | "
        f"🔋 battery {battery_direction(parsers.battery_watts(data), sign)} | "
        f"🔌 grid {_fmt_power(parsers.grid_watts(data))}"
    )


def render_runtime(data: dict, capacity_kwh: float | None) -> str:
    if capacity_kwh is None:
        return ("Set BATTERY_CAPACITY_KWH (usable battery size in kWh) "
                "to get a runtime estimate.")
    soc = parsers.battery_soc(data)
    load = parsers.load_watts(data)
    if soc is None or load is None:
        return "⏳ Runtime: n/a (no SOC or load reading)"
    stored_kwh = soc / 100 * capacity_kwh
    if load <= 0:
        return f"⏳ Load is {_fmt_w(load)}; {stored_kwh:.1f} kWh stored."
    hours = stored_kwh * 1000 / load
    msg = (f"⏳ About {fmt_duration(hours * 3600)} left at {_fmt_w(load)} "
           f"({soc:.0f}% of {capacity_kwh:g} kWh, down to 0%)")
    if parsers.grid_present(data):
        msg += "\nGrid is ON, so the battery isn't carrying the load right now."
    return msg


def render_faults(data: dict) -> str:
    inv = parsers.inv_status(data)
    code = parsers.dtc(data)
    return (
        "🛠 Inverter state\n"
        f"Mode: {fmt_status_code(parsers.status_code(data))}\n"
        f"invStatus: {inv if inv is not None else 'n/a'}\n"
        f"Fault code (dtc): {code if code is not None else 'n/a'}\n"
        f"Load: {_fmt_pct(parsers.load_percent(data))} of rating\n"
        "Mode names come from Growatt's SPF protocol and aren't confirmed on this inverter yet."
    )


MAX_MUTE_SECONDS = 30 * 86400
_DURATION_UNITS = {"d": 86400, "h": 3600, "m": 60}


def parse_duration(raw: str) -> Optional[int]:
    """'2h', '30m', '1d', '1h30m' or bare minutes ('45') to seconds."""
    raw = raw.strip().lower()
    if raw.isdigit():
        seconds = int(raw) * 60
    else:
        parts = re.findall(r"(\d+)\s*([dhm])", raw)
        if not parts or re.sub(r"(\d+)\s*([dhm])", "", raw).strip():
            return None
        seconds = sum(int(n) * _DURATION_UNITS[u] for n, u in parts)
    return seconds if 0 < seconds <= MAX_MUTE_SECONDS else None


def render_uptime(health, now: float, tz: ZoneInfo, muted_until: float = 0) -> str:
    lines = [f"⏱ Up {fmt_duration(now - health.started_ts)} "
             f"(since {fmt_clock(health.started_ts, tz, now)})"]
    if health.last_ok_ts is None:
        lines.append("Last good Growatt call: none yet")
    else:
        lines.append(f"Last good Growatt call: {fmt_duration(now - health.last_ok_ts)} ago")
    if health.recent_errors:
        lines.append("Recent errors:")
        for e in reversed(health.recent_errors):
            lines.append(f"• {fmt_clock(e.ts, tz, now)} {e.text}")
    else:
        lines.append("No Growatt errors since start.")
    if muted_until > now:
        lines.append(f"🔕 Alerts muted until {fmt_clock(muted_until, tz, now)}")
    return "\n".join(lines)


def render_health(weeks, tz: ZoneInfo) -> str:
    if not weeks:
        return "🔋 Not enough data yet: needs snapshots taken at 45–55% SOC."
    lines = ["🔋 Battery voltage at 45–55% SOC, by week:"]
    for w in weeks:
        label = datetime.fromtimestamp(w.week_start_ts, tz).strftime("%d %b")
        lines.append(f"• week of {label}: {w.mean_v:.2f} V ({w.samples} readings)")
    if len(weeks) >= 2:
        lines.append(f"Change: {weeks[-1].mean_v - weeks[0].mean_v:+.2f} V since the first week")
    return "\n".join(lines)


def render_chart(rows, tz: ZoneInfo) -> bytes:
    # Imported here so the bot starts quickly and matplotlib loads only for /chart.
    from matplotlib.dates import DateFormatter
    from matplotlib.figure import Figure

    times = [datetime.fromtimestamp(r["ts"], tz) for r in rows]

    def col(name):
        return [float("nan") if r[name] is None else r[name] for r in rows]

    fig = Figure(figsize=(8, 4), dpi=100)
    ax = fig.add_subplot()
    ax.plot(times, col("load_w"), label="Load (W)", color="tab:red")
    ax.plot(times, col("pv_w"), label="PV (W)", color="tab:orange")
    ax.set_ylabel("Watts")
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M", tz=tz))
    soc_ax = ax.twinx()
    soc_ax.plot(times, col("soc"), label="SOC (%)", color="tab:green", linestyle="--")
    soc_ax.set_ylabel("SOC %")
    soc_ax.set_ylim(0, 100)
    handles = ax.get_legend_handles_labels()[0] + soc_ax.get_legend_handles_labels()[0]
    ax.legend(handles=handles, loc="upper left", fontsize="small")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


# ---------- handlers ----------

@status_command
def cmd_pv(data: dict) -> str:
    return f"☀️ PV output: {_fmt_w(parsers.pv_watts(data))}"


@status_command
def cmd_load(data: dict) -> str:
    return f"⚡ Load: {_fmt_w(parsers.load_watts(data))}"


@status_command
def cmd_battery(data: dict) -> str:
    return (f"🔋 Battery: SOC {_fmt_pct(parsers.battery_soc(data))} | "
            f"{_fmt_v(parsers.battery_voltage(data))}")


@status_command
def cmd_grid(data: dict) -> str:
    return (f"🔌 Grid: {_grid_state(parsers.grid_present(data))} "
            f"({_fmt_v(parsers.grid_voltage(data))})")


@status_command
def cmd_status(data: dict) -> str:
    return (
        "📟 Growatt status\n"
        f"☀️ PV:      {_fmt_w(parsers.pv_watts(data))}\n"
        f"⚡ Load:    {_fmt_w(parsers.load_watts(data))}\n"
        f"🔋 Battery: {_fmt_pct(parsers.battery_soc(data))} ({_fmt_v(parsers.battery_voltage(data))})\n"
        f"🔌 Grid:    {_grid_state(parsers.grid_present(data))} ({_fmt_v(parsers.grid_voltage(data))})"
    )


@status_command
def cmd_flow(data: dict) -> str:
    return render_flow(data, _settings.battery_sign)


@status_command
def cmd_runtime(data: dict) -> str:
    return render_runtime(data, _settings.battery_capacity_kwh)


@status_command
def cmd_faults(data: dict) -> str:
    return render_faults(data)


@history_command
async def cmd_outages(_update, _ctx):
    return fmt_outages(await _history.recent_outages(10), _history.now(), _settings.tz)


@command
async def cmd_today(_update, _ctx):
    return await today_energy_text(_require_client(), _settings.tz, _history, _clock)


@history_command
async def cmd_week(_update, _ctx):
    window = 7 * 86400
    return fmt_energy_split("📊 Energy, last 7 days", await _history.energy_split(window), window)


@history_command
async def cmd_month(_update, _ctx):
    window = 30 * 86400
    return fmt_energy_split("📊 Energy, last 30 days", await _history.energy_split(window), window)


@history_command
async def cmd_health(_update, _ctx):
    return render_health(await _history.battery_health(8), _settings.tz)


@history_command
async def cmd_chart(update, _ctx):
    now = _clock()
    rows = await _history.series(local_midnight(now, _settings.tz))
    if len(rows) < 2:
        return "📈 Not enough data for a chart yet today."
    png = await asyncio.to_thread(render_chart, rows, _settings.tz)
    await _safe_reply_photo(update, png, "📈 Today: load, PV and battery SOC")
    return None


@command(error_msg="⚠️ Could not save the mute. Try again shortly.")
async def cmd_mute(_update, ctx):
    args = getattr(ctx, "args", None) or []
    seconds = parse_duration("".join(args)) if args else None
    if seconds is None:
        return "Usage: /mute 2h (or 30m, 1d, 1h30m; up to 30 days)"
    until = _clock() + seconds
    await _notifier.set_mute(until)
    return (f"🔕 Alerts muted until {fmt_clock(until, _settings.tz, _clock())}. "
            "Events are still recorded. /unmute to resume.")


@command(error_msg="⚠️ Could not save the unmute. Try again shortly.")
async def cmd_unmute(_update, _ctx):
    await _notifier.set_mute(_clock())
    return "🔔 Alerts are back on."


@command
async def cmd_uptime(_update, _ctx):
    muted = _notifier.muted_until if _notifier is not None else 0
    return render_uptime(_health, _clock(), _settings.tz, muted)


COMMANDS: List[Command] = [
    Command("pv",      "Current PV (solar) output in watts",        cmd_pv),
    Command("load",    "Current load consumption in watts",         cmd_load),
    Command("battery", "Battery SOC % and voltage",                 cmd_battery),
    Command("grid",    "Grid voltage and on/off state",             cmd_grid),
    Command("status",  "Full summary",                              cmd_status),
    Command("flow",    "One-line power flow: PV, load, battery, grid", cmd_flow),
    Command("runtime", "Estimated battery time left at current load", cmd_runtime),
    Command("faults",  "Inverter mode and fault codes",             cmd_faults),
    Command("today",   "Energy used today, with solar and grid",    cmd_today),
    Command("week",    "Energy totals for the last 7 days",         cmd_week),
    Command("month",   "Energy totals for the last 30 days",        cmd_month),
    Command("chart",   "Today's load, PV and SOC as a chart",       cmd_chart),
    Command("health",  "Battery voltage trend at ~50% SOC",         cmd_health),
    Command("outages", "Last 10 grid outages and how long they lasted", cmd_outages),
    Command("mute",    "Pause alerts, e.g. /mute 2h",               cmd_mute),
    Command("unmute",  "Resume alerts",                             cmd_unmute),
    Command("uptime",  "Worker uptime, last Growatt call, recent errors", cmd_uptime),
]


async def cmd_unknown(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["Unknown command. Available:"]
    for c in COMMANDS:
        lines.append(f"  /{c.name} — {c.description}")
    await _safe_reply(update, "\n".join(lines))
