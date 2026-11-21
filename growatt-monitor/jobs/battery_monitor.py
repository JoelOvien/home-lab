import logging

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_battery_low

log = logging.getLogger(__name__)

# SOC must climb this far above a level before that level can alert again,
# so a battery hovering around 30% doesn't send an alert every poll.
REARM_MARGIN = 5.0


def make_battery_monitor(client: GrowattClient, notifier: Notifier, levels: tuple[int, ...]):
    armed = set(levels)

    async def run() -> None:
        data = await client.acall("get_device_status")
        if data is None:
            log.info("battery_monitor: device offline, skipping")
            return
        soc = parsers.battery_soc(data)
        if soc is None:
            log.warning("battery_monitor: no SOC in payload")
            return

        for lvl in levels:
            if lvl not in armed and soc >= lvl + REARM_MARGIN:
                armed.add(lvl)

        crossed = [lvl for lvl in armed if soc <= lvl]
        if not crossed:
            return
        armed.difference_update(crossed)
        log.info("battery_monitor: SOC %.0f%% crossed %s", soc, crossed)
        await notifier.send(fmt_battery_low(
            soc,
            min(crossed),
            parsers.battery_voltage(data),
            parsers.load_watts(data),
            parsers.grid_present(data),
        ))

    return run
