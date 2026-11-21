import logging
import time

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_grid_change

log = logging.getLogger(__name__)


def make_grid_monitor(client: GrowattClient, notifier: Notifier, clock=time.monotonic):
    # lost_at is only set for outages we saw start, so the restore message
    # never reports a duration that began before the worker did.
    state = {"last_present": None, "lost_at": None}

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
            outage = None
            if present:
                if state["lost_at"] is not None:
                    outage = clock() - state["lost_at"]
                state["lost_at"] = None
            else:
                state["lost_at"] = clock()
            await notifier.send(fmt_grid_change(present, voltage, outage))
            state["last_present"] = present

    return run
