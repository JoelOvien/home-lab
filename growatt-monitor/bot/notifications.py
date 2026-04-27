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


def fmt_grid_change(now_on: bool, voltage: float | None) -> str:
    v = f"{voltage:.1f}V" if voltage is not None else "n/a"
    if now_on:
        return f"🔌 Grid RESTORED ({v})"
    return f"⚠️ Grid LOST ({v})"


def fmt_energy_report(kwh: float | None, hours: int) -> str:
    if kwh is None:
        return f"📊 Energy report ({hours}h): no data"
    return f"📊 Load energy in last {hours}h: {kwh:.2f} kWh"
