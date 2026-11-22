import json

import pytest

from bot.notifications import Notifier
from bot.push import FcmPusher, build_message
from config import Config, ConfigError
from tests.test_features import FakeBot
from tests.test_history import Clock, a, base_env


class FakePusher:
    def __init__(self):
        self.pushed = []

    async def push(self, kind, text):
        self.pushed.append((kind, text))


def test_alert_is_pushed_after_telegram():
    bot, pusher = FakeBot(), FakePusher()
    n = Notifier(bot, "1", clock=Clock(), pusher=pusher)
    a(n.alert("grid_down", "lost"))
    assert bot.sent == ["lost"]
    assert pusher.pushed == [("grid_down", "lost")]


def test_plain_send_and_muted_alerts_are_not_pushed():
    clock, pusher = Clock(), FakePusher()
    n = Notifier(FakeBot(), "1", clock=clock, pusher=pusher)
    a(n.send("online"))
    a(n.set_mute(clock.t + 60))
    a(n.alert("grid_down", "lost"))
    assert pusher.pushed == []


def test_push_failure_is_logged_not_raised(caplog):
    pusher = object.__new__(FcmPusher)

    def boom(kind, text):
        raise RuntimeError("FCM returned HTTP 403")
    pusher._send_sync = boom
    a(pusher.push("fault", "fault"))
    assert "Failed to send fault push" in caplog.text


def test_message_targets_alerts_topic_on_high_priority_channel():
    msg = build_message("battery_low", "Battery at 15%")["message"]
    assert msg["topic"] == "alerts"
    assert msg["notification"] == {"title": "Battery low", "body": "Battery at 15%"}
    assert msg["android"] == {"priority": "HIGH", "notification": {"channel_id": "alerts"}}


def test_push_is_off_without_config(monkeypatch):
    base_env(monkeypatch)
    assert Config.from_env().fcm_service_account_json is None


def test_service_account_json_accepted(monkeypatch):
    base_env(monkeypatch)
    raw = json.dumps({"project_id": "p", "client_email": "e", "private_key": "k"})
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", raw)
    assert Config.from_env().fcm_service_account_json == raw


@pytest.mark.parametrize("raw", ["not json", '{"project_id": "p"}', "[]"])
def test_bad_service_account_json_rejected(monkeypatch, raw):
    base_env(monkeypatch)
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", raw)
    with pytest.raises(ConfigError, match="FCM_SERVICE_ACCOUNT_JSON"):
        Config.from_env()
