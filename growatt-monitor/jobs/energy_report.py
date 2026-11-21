import logging
from datetime import datetime

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_energy_report, fmt_rolling_energy

log = logging.getLogger(__name__)

# Below this share of the window covered by snapshots, the rolling figure is
# too partial to trust, so fall back to today's day-chart total.
MIN_COVERAGE = 0.5


def make_energy_report(client: GrowattClient, notifier: Notifier, hours: int = 12, history=None):
    window = hours * 3600

    async def run() -> None:
        if history is not None:
            try:
                energy = await history.load_energy(window)
            except Exception:
                log.exception("energy_report: history unavailable, using day chart")
                energy = None
            if energy is not None and energy.covered_seconds >= window * MIN_COVERAGE:
                await notifier.send(fmt_rolling_energy(energy.kwh, hours, energy.covered_seconds))
                return
        date = datetime.now().strftime("%Y-%m-%d")
        data = await client.acall("get_energy_day_chart", date)
        kwh = parsers.total_load_energy_kwh(data)
        await notifier.send(fmt_energy_report(kwh))

    return run
