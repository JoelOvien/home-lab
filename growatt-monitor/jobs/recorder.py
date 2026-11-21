import logging

from growatt.client import GrowattClient
from growatt import parsers
from history import History

log = logging.getLogger(__name__)


def make_recorder(client: GrowattClient, history: History):
    async def run() -> None:
        data = await client.acall("get_device_status")
        if data is None:
            log.info("recorder: device offline, skipping")
            return
        history.add_snapshot(
            pv_w=parsers.pv_watts(data),
            load_w=parsers.load_watts(data),
            grid_w=parsers.grid_watts(data),
            battery_w=parsers.battery_watts(data),
            soc=parsers.battery_soc(data),
            battery_v=parsers.battery_voltage(data),
            grid_v=parsers.grid_voltage(data),
            grid_present=parsers.grid_present(data),
        )

    return run
