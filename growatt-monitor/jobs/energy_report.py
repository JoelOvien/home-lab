import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_energy_report, fmt_energy_split

log = logging.getLogger(__name__)

# Below this share of the window covered by snapshots, the history figure is
# too partial to trust, so fall back to today's day-chart total.
MIN_COVERAGE = 0.5


def local_midnight(now: float, tz: ZoneInfo) -> float:
    dt = datetime.fromtimestamp(now, tz)
    return datetime(dt.year, dt.month, dt.day, tzinfo=tz).timestamp()


async def today_energy_text(client: GrowattClient, tz: ZoneInfo, history=None,
                            clock=time.time) -> str:
    now = clock()
    window = now - local_midnight(now, tz)
    if history is not None:
        try:
            split = await history.energy_split(window)
        except Exception:
            log.exception("energy_report: history unavailable, using day chart")
            split = None
        if split is not None and window > 0 and split.covered_seconds >= window * MIN_COVERAGE:
            return fmt_energy_split("📊 Energy today", split, window)
    date = datetime.fromtimestamp(now, tz).strftime("%Y-%m-%d")
    data = await client.acall("get_energy_day_chart", date)
    return fmt_energy_report(parsers.total_load_energy_kwh(data))


def make_energy_report(client: GrowattClient, notifier: Notifier, tz: ZoneInfo,
                       history=None, clock=time.time):
    async def run() -> None:
        await notifier.send(await today_energy_text(client, tz, history, clock))

    return run
