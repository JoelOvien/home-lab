"""Tests for the TODO.md features: schema migration, worker state, events,
mute, daily scheduling, status alerts and the new commands."""
import asyncio
import json
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from bot import commands  # noqa: E402
from bot.notifications import Notifier  # noqa: E402
from config import Config, ConfigError  # noqa: E402
from growatt.client import GrowattAPIError, GrowattClient  # noqa: E402
from health import OK_WRITE_INTERVAL, WorkerHealth  # noqa: E402
from history import History, LocalBackend  # noqa: E402
from jobs.recorder import make_recorder  # noqa: E402
from jobs.status_alerts import (  # noqa: E402
    make_battery_full_check, make_fault_check, make_overload_check,
    make_solar_check, make_status_alerts,
)
from scheduler import next_daily_run, seconds_until_daily  # noqa: E402
from tests.test_history import BrokenBackend, Clock, a, base_env, make_store  # noqa: E402,F401
from tests.test_jobs import FakeClient, FakeNotifier  # noqa: E402

UTC = ZoneInfo("UTC")
FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixtures" / "storage_status.json").read_text())


def payload(**fields):
    return {"result": 1, "obj": {**FIXTURE["obj"], **{k: str(v) for k, v in fields.items()}}}


# ---------- schema / history ----------

OLD_SCHEMA = """CREATE TABLE snapshots (
    ts INTEGER NOT NULL, pv_w REAL, load_w REAL, grid_w REAL, battery_w REAL,
    soc REAL, battery_v REAL, grid_v REAL, grid_present INTEGER)"""


def test_migration_adds_columns_to_old_schema(tmp_path):
    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.execute(OLD_SCHEMA)
    db.execute("INSERT INTO snapshots VALUES (1, 10, 20, 30, 40, 50, 51.2, 220, 1)")
    db.commit()
    db.close()

    clock = Clock()
    h = History(LocalBackend(path), clock=clock)
    a(h.add_snapshot(load_w=800, load_pct=14.8, inv_status=-10, status=8, dtc=20006))
    rows = h.backend.execute(
        "SELECT ts, load_w, load_pct, inv_status, status, dtc FROM snapshots ORDER BY ts")
    assert rows == [
        {"ts": 1, "load_w": 20.0, "load_pct": None, "inv_status": None, "status": None, "dtc": None},
        {"ts": 1_000_000, "load_w": 800.0, "load_pct": 14.8, "inv_status": -10, "status": 8, "dtc": 20006},
    ]
    # A second process re-runs the migration against the now-current schema.
    h2 = History(LocalBackend(path), clock=clock)
    a(h2.add_snapshot(load_w=1))


def test_migration_reraises_other_errors():
    class FailingAlter:
        def execute(self, sql, params=()):
            if sql.startswith("ALTER"):
                raise sqlite3.OperationalError("database is locked")
            return []

    with pytest.raises(sqlite3.OperationalError):
        a(History(FailingAlter()).get_state("tz"))


def test_add_snapshot_rejects_unknown_field(make_store):
    with pytest.raises(ValueError):
        a(make_store(Clock()).add_snapshot(bogus=1))


def test_state_upsert_and_delete(make_store):
    clock = Clock()
    h = make_store(clock)
    assert a(h.get_state("tz")) is None
    a(h.set_state("tz", "UTC"))
    clock.t += 10
    a(h.set_state("tz", "Africa/Lagos"))
    assert a(h.get_state("tz")) == "Africa/Lagos"
    rows = h.backend.execute("SELECT key, value, updated_ts FROM worker_state")
    assert rows == [{"key": "tz", "value": "Africa/Lagos", "updated_ts": 1_000_010}]
    a(h.delete_state("tz"))
    assert a(h.get_state("tz")) is None


def test_events_round_trip_and_reject_unknown_kind(make_store):
    clock = Clock()
    h = make_store(clock)
    a(h.add_event("grid_down", "⚠️ Grid LOST"))
    clock.t += 60
    a(h.add_event("grid_up", "🔌 Grid RESTORED"))
    assert [e.kind for e in a(h.recent_events())] == ["grid_up", "grid_down"]
    with pytest.raises(ValueError):
        a(h.add_event("made_up"))


def test_energy_split_and_gaps(make_store):
    clock = Clock()
    h = make_store(clock)
    for _ in range(13):
        a(h.add_snapshot(load_w=1000, pv_w=600, grid_w=None))
        clock.t += 300
    clock.t += 3600
    a(h.add_snapshot(load_w=1000, pv_w=600))
    s = a(h.energy_split(24 * 3600))
    assert abs(s.load_kwh - 1.0) < 1e-9
    assert abs(s.pv_kwh - 0.6) < 1e-9
    assert s.grid_kwh == 0
    assert s.covered_seconds == 3600


def test_battery_health_groups_by_week_at_mid_soc(make_store):
    clock = Clock(10 * 7 * 86400)
    h = make_store(clock)
    for v, soc in ((52.0, 50), (52.4, 48), (60.0, 90)):
        a(h.add_snapshot(battery_v=v, soc=soc))
        clock.t += 60
    clock.t += 7 * 86400
    a(h.add_snapshot(battery_v=51.0, soc=55))
    weeks = a(h.battery_health(8))
    assert [(w.week_start_ts, round(w.mean_v, 2), w.samples) for w in weeks] == [
        (10 * 7 * 86400, 52.2, 2),
        (11 * 7 * 86400, 51.0, 1),
    ]


def test_recorder_writes_mode_columns(make_store):
    h = make_store(Clock())
    client = FakeClient()
    client.payload = FIXTURE
    a(make_recorder(client, h)())
    rows = h.backend.execute("SELECT load_pct, inv_status, status, dtc FROM snapshots")
    assert rows == [{"load_pct": 14.8, "inv_status": -10, "status": 8, "dtc": 20006}]


# ---------- daily scheduler ----------

def test_next_daily_run_today_and_tomorrow():
    tz = ZoneInfo("Africa/Lagos")  # UTC+1
    now = datetime(2026, 11, 22, 10, 0, tzinfo=timezone.utc)
    assert next_daily_run("21:00", tz, now) == datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc)
    at_slot = datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc)
    assert next_daily_run("21:00", tz, at_slot) == datetime(2026, 11, 23, 20, 0, tzinfo=timezone.utc)
    assert seconds_until_daily("21:00", tz, now) == 10 * 3600


def test_next_daily_run_across_dst():
    tz = ZoneInfo("Europe/London")
    # Clocks go forward on 29 Mar 2026; 21:00 BST is 20:00 UTC.
    now = datetime(2026, 3, 28, 22, 0, tzinfo=timezone.utc)
    assert next_daily_run("21:00", tz, now) == datetime(2026, 3, 29, 20, 0, tzinfo=timezone.utc)
    assert seconds_until_daily("21:00", tz, now) == 22 * 3600


# ---------- notifier / mute ----------

class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text):
        self.sent.append(text)


def test_mute_silences_alerts_but_records_events(make_store):
    clock = Clock()
    h = make_store(clock)
    bot = FakeBot()
    n = Notifier(bot, "1", h, clock=clock)
    a(n.set_mute(clock.t + 3600))
    a(n.alert("grid_down", "lost"))
    assert bot.sent == []
    assert [e.kind for e in a(h.recent_events())] == ["grid_down"]
    a(n.send("not an alert"))
    assert bot.sent == ["not an alert"]

    # A restarted worker picks the mute up from history.
    bot2 = FakeBot()
    n2 = Notifier(bot2, "1", h, clock=clock)
    a(n2.alert("grid_up", "back"))
    assert bot2.sent == []
    clock.t += 3601
    a(n2.alert("grid_down", "lost again"))
    assert bot2.sent == ["lost again"]


def test_alert_sent_when_history_is_down():
    bot = FakeBot()
    n = Notifier(bot, "1", History(BrokenBackend()), clock=Clock())
    a(n.alert("overload", "hot"))
    assert bot.sent == ["hot"]


# ---------- status alerts ----------

def test_overload_alerts_then_rearms():
    check = make_overload_check(85)
    assert check(payload(loadPrecent=90), 0)[0] == "overload"
    assert check(payload(loadPrecent=95), 0) is None
    assert check(payload(loadPrecent=80), 0) is None  # within the re-arm margin
    assert check(payload(loadPrecent=70), 0) is None
    assert check(payload(loadPrecent=88), 0)[0] == "overload"


def test_fault_alerts_on_dtc_change_and_fault_status():
    check = make_fault_check()
    assert check(payload(), 0) is None  # baseline
    assert check(payload(), 0) is None
    kind, text = check(payload(dtc=1), 0)
    assert kind == "fault" and "20006 → 1" in text
    kind, text = check(payload(dtc=1, status=3), 0)
    assert "fault (status 3)" in text
    assert check(payload(dtc=1, status=3), 0) is None


def test_fault_at_boot_is_only_a_baseline():
    check = make_fault_check()
    assert check(payload(status=3), 0) is None


def test_battery_full_skips_boot_and_rearms_below_95():
    check = make_battery_full_check()
    assert check(payload(capacity=100), 0) is None  # already full at boot
    assert check(payload(capacity=96), 0) is None
    assert check(payload(capacity=99), 0) is None   # never dropped below 95
    assert check(payload(capacity=94), 0) is None
    assert check(payload(capacity=99), 0)[0] == "battery_full"
    assert check(payload(capacity=100), 0) is None


def lagos_ts(hour, minute=0):
    return datetime(2026, 11, 22, hour, minute, tzinfo=ZoneInfo("Africa/Lagos")).timestamp()


def test_solar_stopped_after_30_min_in_window():
    check = make_solar_check((10, 15), ZoneInfo("Africa/Lagos"))
    dead = payload(ppv1=0, vPv1=0)
    assert check(dead, lagos_ts(9, 50)) is None   # before the window
    assert check(dead, lagos_ts(10, 0)) is None
    assert check(dead, lagos_ts(10, 25)) is None
    kind, text = check(dead, lagos_ts(10, 30))
    assert kind == "solar_stopped" and "30m" in text
    assert check(dead, lagos_ts(11, 0)) is None   # once only
    assert check(payload(ppv1=500), lagos_ts(11, 5)) is None  # re-arms
    assert check(dead, lagos_ts(11, 10)) is None
    assert check(dead, lagos_ts(11, 40))[0] == "solar_stopped"


def test_solar_not_stopped_when_panels_have_voltage():
    # The fixture has 21 W at 275.8 V: panels live, inverter not drawing them.
    check = make_solar_check((10, 15), ZoneInfo("Africa/Lagos"))
    for minute in range(0, 60, 5):
        assert check(FIXTURE, lagos_ts(12, minute)) is None


def test_status_alerts_job_sends_through_notifier():
    client, notifier = FakeClient(), FakeNotifier()
    run = make_status_alerts(client, notifier, 85, (10, 15), UTC, clock=lambda: 0)
    a(run())  # offline
    client.payload = payload(loadPrecent=99)
    a(run())
    assert notifier.kinds == ["overload"]


# ---------- health / client listener ----------

def test_health_throttles_ok_writes_and_records_errors(make_store):
    clock = Clock()
    h = make_store(clock)
    health = WorkerHealth(h, clock=clock)

    async def go():
        health.on_call(None)
        clock.t += 10
        health.on_call(None)
        health.on_call(GrowattAPIError("x" * 500))
        await asyncio.gather(*health._tasks)

    a(go())
    assert a(h.get_state("last_ok_ts")) == "1000000"
    err = a(h.get_state("last_error"))
    assert err.startswith("GrowattAPIError: xxx") and len(err) == 200
    assert a(h.get_state("last_error_ts")) == "1000010"
    assert health.last_ok_ts == 1_000_010
    clock.t += OK_WRITE_INTERVAL

    async def again():
        health.on_call(None)
        await asyncio.gather(*health._tasks)

    a(again())
    assert a(h.get_state("last_ok_ts")) == str(int(clock.t))


def test_client_reports_calls_to_listener():
    client = GrowattClient("u", "p", "sn", "plant")
    seen = []
    client.call_listener = seen.append
    client.get_device_status = lambda: FIXTURE
    assert a(client.acall("get_device_status")) is FIXTURE
    assert seen == [None]


def test_client_listener_errors_do_not_break_calls():
    client = GrowattClient("u", "p", "sn", "plant")
    client.call_listener = lambda e: 1 / 0
    client.get_device_status = lambda: FIXTURE
    assert a(client.acall("get_device_status")) is FIXTURE


# ---------- config ----------

def test_new_config_defaults(monkeypatch):
    base_env(monkeypatch)
    cfg = Config.from_env()
    assert (cfg.tz_name, cfg.daily_report_time, cfg.battery_capacity_kwh,
            cfg.load_alert_pct, cfg.solar_check_hours, cfg.battery_sign) == (
        "UTC", "21:00", None, 85.0, (10, 15), None)


def test_new_config_values(monkeypatch):
    base_env(monkeypatch)
    for k, v in {"TZ": "Africa/Lagos", "DAILY_REPORT_TIME": "7:30",
                 "BATTERY_CAPACITY_KWH": "10.24", "LOAD_ALERT_PCT": "90",
                 "SOLAR_CHECK_HOURS": "9-16", "BATTERY_SIGN": "charge_negative"}.items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg.tz.key == "Africa/Lagos"
    assert cfg.daily_report_time == "07:30"
    assert cfg.battery_capacity_kwh == 10.24
    assert cfg.solar_check_hours == (9, 16)
    assert cfg.battery_sign == "charge_negative"


@pytest.mark.parametrize("key,value", [
    ("TZ", "Mars/Olympus"), ("DAILY_REPORT_TIME", "25:00"), ("BATTERY_CAPACITY_KWH", "-1"),
    ("SOLAR_CHECK_HOURS", "15-10"), ("BATTERY_SIGN", "positive"), ("LOAD_ALERT_PCT", "abc"),
])
def test_bad_config_rejected(monkeypatch, key, value):
    base_env(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(ConfigError, match=key):
        Config.from_env()


def test_startup_state_written_and_unset_keys_deleted(make_store, monkeypatch):
    from main import write_startup_state
    base_env(monkeypatch)
    h = make_store(Clock())
    a(h.set_state("battery_sign", "charge_positive"))
    a(write_startup_state(h, Config.from_env(), 123.9))
    assert a(h.get_state("started_ts")) == "123"
    assert a(h.get_state("tz")) == "UTC"
    assert a(h.get_state("battery_sign")) is None
    assert a(h.get_state("battery_capacity_kwh")) is None


# ---------- commands ----------

class FakeMessage:
    def __init__(self):
        self.replies = []
        self.photos = []

    async def reply_text(self, text):
        self.replies.append(text)

    async def reply_photo(self, photo, caption):
        self.photos.append((photo, caption))


def run_cmd(handler, *args):
    update = SimpleNamespace(message=FakeMessage())
    a(handler(update, SimpleNamespace(args=list(args))))
    return update.message


@pytest.fixture
def bound(monkeypatch):
    client = FakeClient()
    clock = Clock()
    monkeypatch.setattr(commands, "_client", client)
    monkeypatch.setattr(commands, "_history", None)
    monkeypatch.setattr(commands, "_notifier", None)
    monkeypatch.setattr(commands, "_health", None)
    monkeypatch.setattr(commands, "_settings", commands.Settings())
    monkeypatch.setattr(commands, "_clock", clock)
    return SimpleNamespace(client=client, clock=clock, monkeypatch=monkeypatch)


def test_status_command_offline_and_error(bound):
    assert run_cmd(commands.cmd_pv).replies == [commands.OFFLINE_MSG]

    async def boom(*_a):
        raise RuntimeError("down")
    bound.client.acall = boom
    assert run_cmd(commands.cmd_pv).replies == [commands.GROWATT_ERROR_MSG]


def test_status_command_renders(bound):
    bound.client.payload = FIXTURE
    assert run_cmd(commands.cmd_status).replies[0].startswith("📟 Growatt status\n☀️ PV:      21 W")


def test_history_command_without_history(bound):
    assert run_cmd(commands.cmd_week).replies == [commands.NO_HISTORY_MSG]


def test_history_command_error(bound):
    bound.monkeypatch.setattr(commands, "_history", History(BrokenBackend()))
    assert run_cmd(commands.cmd_month).replies == [commands.HISTORY_ERROR_MSG]


def test_flow_direction_needs_sign():
    data = payload(batPower=-400)
    assert "battery 400 W (direction unknown)" in commands.render_flow(data, None)
    assert "battery 400 W discharging" in commands.render_flow(data, "charge_positive")
    assert "battery 400 W charging" in commands.render_flow(data, "charge_negative")
    assert commands.render_flow(FIXTURE, None) == (
        "☀️ PV 21 W → ⚡ load 824 W | 🔋 battery idle | 🔌 grid 933 W")


def test_runtime_estimate():
    assert "BATTERY_CAPACITY_KWH" in commands.render_runtime(FIXTURE, None)
    text = commands.render_runtime(payload(loadPrecent=0, loadPower=750, vAcInput=0), 10)
    assert text == "⏳ About 10h 0m left at 750 W (75% of 10 kWh, down to 0%)"
    assert "Grid is ON" in commands.render_runtime(FIXTURE, 10)


def test_faults_shows_words_and_raw_codes():
    text = commands.render_faults(FIXTURE)
    assert "PV + AC charging, grid bypass (status 8)" in text
    assert "invStatus: -10" in text and "dtc): 20006" in text
    assert "status 42 (unknown)" in commands.render_faults(payload(status=42))


@pytest.mark.parametrize("raw,seconds", [
    ("2h", 7200), ("30m", 1800), ("1d", 86400), ("1h30m", 5400), ("45", 2700),
    ("0m", None), ("abc", None), ("2x", None), ("31d", None),
])
def test_parse_duration(raw, seconds):
    assert commands.parse_duration(raw) == seconds


def test_mute_and_unmute_commands(bound, make_store):
    h = make_store(bound.clock)
    bot = FakeBot()
    notifier = Notifier(bot, "1", h, clock=bound.clock)
    bound.monkeypatch.setattr(commands, "_notifier", notifier)
    assert run_cmd(commands.cmd_mute).replies[0].startswith("Usage")
    assert run_cmd(commands.cmd_mute, "2h").replies[0].startswith("🔕 Alerts muted until 15:46")
    assert a(h.get_state("muted_until_ts")) == str(int(bound.clock.t + 7200))
    a(notifier.alert("overload", "hot"))
    assert bot.sent == []
    run_cmd(commands.cmd_unmute)
    a(notifier.alert("overload", "hot"))
    assert bot.sent == ["hot"]


def test_uptime(bound):
    clock = bound.clock
    health = WorkerHealth(clock=clock)
    clock.t += 3 * 3600
    health.on_call(GrowattAPIError("boom"))
    clock.t += 60
    health.on_call(None)
    bound.monkeypatch.setattr(commands, "_health", health)
    text = run_cmd(commands.cmd_uptime).replies[0]
    assert text.startswith("⏱ Up 3h 1m (since 13:46)")
    assert "Last good Growatt call: 0m ago" in text
    assert "• 16:46 GrowattAPIError: boom" in text


def test_week_and_today_from_history(bound, make_store):
    clock = bound.clock
    clock.t = 950_400  # midnight UTC
    h = make_store(clock)
    for i in range(13):
        if i:
            clock.t += 300
        a(h.add_snapshot(load_w=1000, pv_w=400, grid_w=600))
    bound.monkeypatch.setattr(commands, "_history", h)
    week = run_cmd(commands.cmd_week).replies[0]
    assert "⚡ Used:       1.00 kWh" in week and "(from 1h 0m of data)" in week
    today = run_cmd(commands.cmd_today).replies[0]
    assert today.startswith("📊 Energy today\n⚡ Used:       1.00 kWh")


def test_health_command(bound, make_store):
    h = make_store(bound.clock)
    bound.monkeypatch.setattr(commands, "_history", h)
    assert "Not enough data" in run_cmd(commands.cmd_health).replies[0]


def test_chart_sends_png(bound, make_store):
    clock = bound.clock
    clock.t = 950_400 + 3600
    h = make_store(clock)
    bound.monkeypatch.setattr(commands, "_history", h)
    assert "Not enough data" in run_cmd(commands.cmd_chart).replies[0]
    for w in (100, None, 300):
        a(h.add_snapshot(load_w=w, pv_w=50, soc=60))
        clock.t += 300
    msg = run_cmd(commands.cmd_chart)
    assert msg.replies == []
    png, caption = msg.photos[0]
    assert png.startswith(b"\x89PNG") and "Today" in caption


def test_every_command_is_listed_once():
    names = [c.name for c in commands.COMMANDS]
    assert len(names) == len(set(names))
    for n in ("today", "runtime", "flow", "faults", "chart", "mute", "unmute",
              "uptime", "week", "month", "health"):
        assert n in names


def test_fmt_outages_shows_local_clock():
    from bot.notifications import fmt_outages
    from history import Outage
    now = 1_000_000  # 13:46 UTC
    text = fmt_outages([Outage(now - 3600, now - 600)], now, ZoneInfo("Africa/Lagos"))
    assert "• 1h 0m ago (13:46), lasted 50m" in text


def test_every_command_runs_without_error(bound, make_store):
    clock = bound.clock
    h = make_store(clock)
    for i in range(3):
        a(h.add_snapshot(load_w=800, pv_w=100, grid_w=700, soc=50, battery_v=52))
        clock.t += 300
    a(h.start_outage())
    bound.client.payload = FIXTURE
    bound.monkeypatch.setattr(commands, "_history", h)
    bound.monkeypatch.setattr(commands, "_notifier", Notifier(FakeBot(), "1", h, clock=clock))
    bound.monkeypatch.setattr(commands, "_health", WorkerHealth(h, clock=clock))
    bound.monkeypatch.setattr(commands, "_settings", commands.Settings(UTC, 10.0, "charge_positive"))
    for c in commands.COMMANDS:
        args = ["1h"] if c.name == "mute" else []
        msg = run_cmd(c.handler, *args)
        out = msg.replies + [cap for _, cap in msg.photos]
        assert out, c.name
        assert not any(r.startswith("⚠️") for r in msg.replies), (c.name, msg.replies)
