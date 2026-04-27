import logging
from datetime import datetime

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_energy_report

log = logging.getLogger(__name__)


def make_energy_report(client: GrowattClient, notifier: Notifier, hours: int = 12):
    async def run() -> None:
        date = datetime.now().strftime("%Y-%m-%d")
        data = await client.acall("get_energy_day_chart", date)
        # NOTE: the day-chart endpoint reports today's totals. For a true rolling
        # 12h window we'd need to subtract a snapshot from 12h ago — left as a
        # follow-up. For now we report today's accumulated load energy.
        kwh = parsers.total_load_energy_kwh(data)
        await notifier.send(fmt_energy_report(kwh, hours))

    return run
