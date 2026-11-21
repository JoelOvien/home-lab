import logging
import time

from growatt.client import GrowattClient
from growatt import parsers
from bot.notifications import Notifier, fmt_grid_change

log = logging.getLogger(__name__)


def make_grid_monitor(client: GrowattClient, notifier: Notifier, history=None, clock=time.time):
    # lost_at is only set for outages whose start we know (seen live, or an
    # open row in history), so the restore message never guesses a duration.
    state = {"last_present": None, "lost_at": None}

    async def resume_from_history(present: bool) -> None:
        open_ = await history.open_outage()
        if open_ is None:
            return
        if present:
            await history.end_outage()
            log.info("grid_monitor: closed outage from %s that ended while offline", open_.start_ts)
        else:
            state["lost_at"] = open_.start_ts

    async def record(present: bool) -> None:
        try:
            if present:
                await history.end_outage()
            else:
                await history.start_outage()
        except Exception:
            log.exception("grid_monitor: could not record outage in history")

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
            if history is not None:
                try:
                    await resume_from_history(present)
                except Exception:
                    log.exception("grid_monitor: could not read open outage from history")
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
            state["last_present"] = present
            await notifier.send(fmt_grid_change(present, voltage, outage))
            if history is not None:
                await record(present)

    return run
