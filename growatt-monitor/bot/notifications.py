import logging
from telegram import Bot
from telegram.error import TelegramError

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot: Bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id

    async def send(self, text: str) -> None:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
        except TelegramError:
            log.exception("Failed to send Telegram message: %s", text)


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
