import asyncio
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from config import Config, ConfigError, _parse_levels  # noqa: E402
from jobs.battery_monitor import make_battery_monitor  # noqa: E402
from jobs.grid_monitor import make_grid_monitor  # noqa: E402


class FakeClient:
    def __init__(self):
        self.payload = None

    async def acall(self, _method, *args):
        return self.payload


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.kinds = []

    async def send(self, text):
        self.sent.append(text)

    async def alert(self, kind, text):
        self.kinds.append(kind)
        self.sent.append(text)


def status(soc=None, vac=None):
    obj = {"vBat": "51.0", "loadPower": "800"}
    if soc is not None:
        obj["capacity"] = str(soc)
    if vac is not None:
        obj["vAcInput"] = str(vac)
    return {"result": 1, "obj": obj}


def battery_run(levels=(30, 15)):
    client, notifier = FakeClient(), FakeNotifier()
    run = make_battery_monitor(client, notifier, levels)

    def step(soc):
        client.payload = status(soc=soc, vac=0)
        asyncio.run(run())
        return list(notifier.sent)

    return step, notifier


def test_battery_alerts_once_per_level():
    step, notifier = battery_run()
    step(50)
    step(29)
    step(28)
    assert len(notifier.sent) == 1
    assert "below 30%" in notifier.sent[0]
    assert notifier.kinds == ["battery_low"]
    step(14)
    assert len(notifier.sent) == 2
    assert "below 15%" in notifier.sent[1]


def test_battery_big_drop_sends_one_alert_for_lowest_level():
    step, notifier = battery_run()
    step(10)
    assert len(notifier.sent) == 1
    assert "below 15%" in notifier.sent[0]
    step(12)
    assert len(notifier.sent) == 1


def test_battery_rearms_only_after_margin():
    step, notifier = battery_run(levels=(30,))
    step(29)
    step(32)
    step(29)
    assert len(notifier.sent) == 1
    step(35)
    step(29)
    assert len(notifier.sent) == 2


def test_battery_skips_offline_and_missing_soc():
    client, notifier = FakeClient(), FakeNotifier()
    run = make_battery_monitor(client, notifier, (30,))
    asyncio.run(run())
    client.payload = status(soc=None)
    asyncio.run(run())
    assert notifier.sent == []


def test_grid_restore_reports_outage_duration():
    client, notifier = FakeClient(), FakeNotifier()
    now = [1000.0]
    run = make_grid_monitor(client, notifier, clock=lambda: now[0])

    for vac, t in [(220, 1000), (0, 1100), (0, 2000), (220, 1100 + 2 * 3600 + 14 * 60)]:
        now[0] = t
        client.payload = status(vac=vac)
        asyncio.run(run())

    assert notifier.sent[0].startswith("⚠️ Grid LOST")
    assert "RESTORED after 2h 14m" in notifier.sent[1]
    assert notifier.kinds == ["grid_down", "grid_up"]


def test_grid_restore_without_seen_loss_has_no_duration():
    client, notifier = FakeClient(), FakeNotifier()
    run = make_grid_monitor(client, notifier, clock=lambda: 0.0)
    for vac in (0, 220):
        client.payload = status(vac=vac)
        asyncio.run(run())
    assert notifier.sent == ["🔌 Grid RESTORED (220.0V)"]


def test_parse_levels():
    assert _parse_levels("15, 30,30") == (30, 15)
    with pytest.raises(ConfigError):
        _parse_levels("abc")
    with pytest.raises(ConfigError):
        _parse_levels("0")


def test_chat_id_must_be_numeric(monkeypatch):
    for k in ["GROWATT_USERNAME", "GROWATT_PASSWORD", "GROWATT_DEVICE_SN",
              "GROWATT_PLANT_ID", "TELEGRAM_TOKEN"]:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@me")
    with pytest.raises(ConfigError):
        Config.from_env()
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    assert Config.from_env().battery_alert_levels == (30, 15)
