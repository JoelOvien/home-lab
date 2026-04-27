import logging

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_grid_change

log = logging.getLogger(__name__)


def make_grid_monitor(client: GrowattClient, notifier: Notifier):
    state = {"last_present": None}  # None | True | False

    async def run() -> None:
        data = await client.acall("get_device_status")
        if data is None:
            log.info("grid_monitor: device offline, skipping")
            return
        present = parsers.grid_present(data)
        if present is None:
            log.warning("grid_monitor: could not determine grid state from payload")
            return
        last = state["last_present"]
        if last is None:
            state["last_present"] = present
            log.info("grid_monitor: initial state present=%s", present)
            return
        if present != last:
            voltage = parsers.grid_voltage(data)
            log.info("grid_monitor: state change %s -> %s (%sV)", last, present, voltage)
            await notifier.send(fmt_grid_change(present, voltage))
            state["last_present"] = present

    return run
