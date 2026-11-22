import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot
from telegram.error import TelegramError

from growatt.parsers import status_name

log = logging.getLogger(__name__)

MUTE_KEY = "muted_until_ts"


class Notifier:
    def __init__(self, bot: Bot, chat_id: str, history=None, clock=time.time):
        self.bot = bot
        self.chat_id = chat_id
        self.history = history
        self.clock = clock
        self.muted_until = 0.0
        self._mute_loaded = history is None

    async def send(self, text: str) -> None:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
        except TelegramError:
            log.exception("Failed to send Telegram message: %s", text)

    async def _load_mute(self) -> None:
        # Retried on each alert until history answers, so a D1 outage at boot
        # doesn't silently drop a mute set before the restart.
        if self._mute_loaded:
            return
        try:
            raw = await self.history.get_state(MUTE_KEY)
        except Exception:
            log.exception("Could not read mute state from history")
            return
        self._mute_loaded = True
        if raw:
            try:
                self.muted_until = max(self.muted_until, float(raw))
            except ValueError:
                log.warning("Ignoring bad %s value %r", MUTE_KEY, raw)

    async def is_muted(self) -> bool:
        await self._load_mute()
        return self.clock() < self.muted_until

    async def set_mute(self, until_ts: float) -> None:
        """Mute alerts until until_ts (epoch seconds); a past time unmutes."""
        self.muted_until = until_ts
        self._mute_loaded = True
        if self.history is not None:
            await self.history.set_state(MUTE_KEY, int(until_ts))

    async def alert(self, kind: str, text: str) -> None:
        """Record an event and send it, unless alerts are muted. The event is
        written even while muted; mute only silences Telegram."""
        if self.history is not None:
            try:
                await self.history.add_event(kind, text)
            except Exception:
                log.exception("Could not record %s event in history", kind)
        if await self.is_muted():
            log.info("Muted, not sending %s alert: %s", kind, text)
            return
        await self.send(text)


def fmt_clock(ts: float, tz: ZoneInfo, now: float | None = None) -> str:
    """HH:MM for today, otherwise with the date, in the given time zone."""
    dt = datetime.fromtimestamp(ts, tz)
    if now is not None and dt.date() == datetime.fromtimestamp(now, tz).date():
        return dt.strftime("%H:%M")
    return dt.strftime("%a %d %b %H:%M")


def fmt_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def fmt_grid_change(now_on: bool, voltage: float | None, outage_seconds: float | None = None) -> str:
    v = f"{voltage:.1f}V" if voltage is not None else "n/a"
    if now_on:
        after = f" after {fmt_duration(outage_seconds)}" if outage_seconds is not None else ""
        return f"🔌 Grid RESTORED{after} ({v})"
    return f"⚠️ Grid LOST ({v})"


def fmt_battery_low(soc: float, level: int, voltage: float | None,
                    load_w: float | None, grid_on: bool | None) -> str:
    v = f"{voltage:.1f}V" if voltage is not None else "n/a"
    load = f"{load_w:.0f} W" if load_w is not None else "n/a"
    grid = {True: "ON", False: "OFF"}.get(grid_on, "unknown")
    return (
        f"🪫 Battery below {level}%: now {soc:.0f}% ({v})\n"
        f"Load {load} | Grid {grid}"
    )


def fmt_energy_report(kwh: float | None) -> str:
    if kwh is None:
        return "📊 Load energy today: no data yet"
    return f"📊 Load energy today so far: {kwh:.2f} kWh"


def fmt_outages(outages, now: float, tz: ZoneInfo | None = None) -> str:
    if not outages:
        return "🔌 No outages recorded yet."
    lines = ["🔌 Recent outages:"]
    for o in outages:
        ago = fmt_duration(now - o.start_ts) + " ago"
        if tz is not None:
            ago += f" ({fmt_clock(o.start_ts, tz, now)})"
        if o.end_ts is None:
            lines.append(f"• started {ago}, still ongoing")
        else:
            lines.append(f"• {ago}, lasted {fmt_duration(o.end_ts - o.start_ts)}")
    return "\n".join(lines)


def fmt_status_code(code: int | None) -> str:
    if code is None:
        return "n/a"
    name = status_name(code)
    return f"{name} (status {code})" if name else f"status {code} (unknown)"


def fmt_kwh(v: float | None) -> str:
    return f"{v:.2f} kWh" if v is not None else "n/a"


def fmt_energy_split(title: str, split, window_seconds: float) -> str:
    lines = [
        title,
        f"⚡ Used:       {fmt_kwh(split.load_kwh)}",
        f"☀️ Solar made: {fmt_kwh(split.pv_kwh)}",
        f"🔌 From grid:  {fmt_kwh(split.grid_kwh)}",
    ]
    if split.covered_seconds < window_seconds * 0.95:
        lines.append(f"(from {fmt_duration(split.covered_seconds)} of data)")
    lines.append("Grid draw includes any battery charging from the grid.")
    return "\n".join(lines)
