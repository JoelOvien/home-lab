import asyncio
import pathlib
import sqlite3
import sys
import threading

from zoneinfo import ZoneInfo

import pytest
import requests

UTC = ZoneInfo("UTC")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from bot.notifications import fmt_outages  # noqa: E402
from config import Config, ConfigError  # noqa: E402
from history import D1Backend, History, HistoryError, LocalBackend, Outage  # noqa: E402
from jobs.energy_report import make_energy_report  # noqa: E402
from jobs.grid_monitor import make_grid_monitor  # noqa: E402
from jobs.recorder import make_recorder  # noqa: E402
from tests.test_jobs import FakeClient, FakeNotifier, status  # noqa: E402


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.ok = status_code < 400
        self._body = body

    def json(self):
        return self._body


class FakeD1Session:
    """Answers like the D1 /query endpoint, backed by in-memory SQLite."""

    def __init__(self):
        self.headers = {}
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.calls = []
        self.lock = threading.Lock()

    def post(self, url, json, timeout):
        with self.lock:
            return self._post(url, json)

    def _post(self, url, json):
        self.calls.append((url, json))
        try:
            rows = [dict(r) for r in self.db.execute(json["sql"], json["params"]).fetchall()]
            self.db.commit()
        except sqlite3.Error as e:
            return FakeResponse(400, {"success": False, "errors": [{"message": str(e)}], "result": []})
        return FakeResponse(200, {"success": True, "errors": [], "result": [{"results": rows, "success": True}]})


def d1_backend():
    backend = D1Backend("acct", "db-id", "secret-token")
    fake = FakeD1Session()
    fake.headers.update(backend.session.headers)
    backend.session = fake
    return backend


BACKENDS = {
    "local": lambda: LocalBackend(":memory:"),
    "d1": d1_backend,
}


@pytest.fixture(params=BACKENDS.keys())
def make_store(request):
    def make(clock):
        return History(BACKENDS[request.param](), clock=clock)
    return make


def a(coro):
    return asyncio.run(coro)


def test_load_energy_trapezoid_and_gaps(make_store):
    clock = Clock()
    h = make_store(clock)
    # 1 hour at a steady 1000 W in 5-minute steps = 1 kWh.
    for _ in range(13):
        a(h.add_snapshot(load_w=1000))
        clock.t += 300
    # A 1-hour gap (worker down) must not be integrated.
    clock.t += 3600
    a(h.add_snapshot(load_w=1000))
    e = a(h.load_energy(12 * 3600))
    assert abs(e.kwh - 1.0) < 1e-9
    assert e.covered_seconds == 3600


def test_load_energy_skips_null_samples(make_store):
    clock = Clock()
    h = make_store(clock)
    for w in (1000, None, 1000):
        a(h.add_snapshot(load_w=w))
        clock.t += 300
    assert a(h.load_energy(3600)).kwh == 0


def test_local_history_persists_on_disk(tmp_path):
    clock = Clock()
    path = str(tmp_path / "nested" / "h.db")
    a(History(LocalBackend(path), clock=clock).start_outage())
    assert a(History(LocalBackend(path), clock=clock).open_outage()) == Outage(int(clock.t), None)


def test_d1_request_shape():
    backend = d1_backend()
    a(History(backend, clock=Clock()).start_outage())
    url, body = backend.session.calls[-1]
    assert url == "https://api.cloudflare.com/client/v4/accounts/acct/d1/database/db-id/query"
    assert body == {"sql": "INSERT INTO outages (start_ts) VALUES (?)", "params": [1_000_000]}
    assert backend.session.headers["Authorization"] == "Bearer secret-token"


def test_d1_error_raises_without_leaking_token():
    backend = d1_backend()
    with pytest.raises(HistoryError) as err:
        backend.execute("SELECT * FROM nope")
    assert "no such table" in str(err.value)
    assert "secret-token" not in str(err.value)


def test_schema_retried_after_failed_first_call():
    backend = d1_backend()
    real_post = backend.session.post
    backend.session.post = lambda *a_, **k: (_ for _ in ()).throw(requests.ConnectionError())
    h = History(backend, clock=Clock())
    with pytest.raises(HistoryError):
        a(h.start_outage())
    backend.session.post = real_post
    a(h.start_outage())
    assert a(h.open_outage()) is not None


def run_grid(client, notifier, history, clock, readings):
    run = make_grid_monitor(client, notifier, history, clock=clock)
    for vac, dt in readings:
        clock.t += dt
        client.payload = status(vac=vac)
        a(run())


def test_outage_recorded_and_resumed_after_restart(make_store):
    clock = Clock()
    h = make_store(clock)
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(220, 0), (0, 60)])
    started = int(clock.t)

    # Worker restarts mid-outage; the restore still reports the full duration.
    notifier2 = FakeNotifier()
    run_grid(client, notifier2, h, clock, [(0, 600), (220, 3000)])
    assert notifier2.sent == ["🔌 Grid RESTORED after 1h 0m (220.0V)"]
    assert a(h.recent_outages()) == [Outage(started, started + 3600)]


def test_open_outage_closed_when_grid_back_at_startup(make_store):
    clock = Clock()
    h = make_store(clock)
    a(h.start_outage())
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(220, 900)])
    assert a(h.open_outage()) is None
    assert notifier.sent == []


def test_outage_with_unknown_start_is_not_recorded(make_store):
    clock = Clock()
    h = make_store(clock)
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(0, 0), (220, 300)])
    assert a(h.recent_outages()) == []
    assert notifier.sent == ["🔌 Grid RESTORED (220.0V)"]


class BrokenBackend:
    def execute(self, sql, params=()):
        raise HistoryError("D1 request failed: ConnectionError")


def test_grid_alerts_still_sent_when_history_is_down():
    clock = Clock()
    h = History(BrokenBackend(), clock=clock)
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(220, 0), (0, 60), (220, 600)])
    assert notifier.sent[0].startswith("⚠️ Grid LOST")
    assert notifier.sent[1] == "🔌 Grid RESTORED after 10m (220.0V)"


def test_recorder_writes_snapshot_and_skips_offline(make_store):
    clock = Clock()
    h = make_store(clock)
    client = FakeClient()
    run = make_recorder(client, h)
    a(run())
    client.payload = status(soc=60, vac=220)
    a(run())
    rows = h.backend.execute("SELECT load_w, soc, grid_present, pv_w FROM snapshots")
    assert rows == [{"load_w": 800.0, "soc": 60.0, "grid_present": 1, "pv_w": None}]


def test_energy_report_uses_history_or_falls_back(make_store):
    # 1_000_000 is 1970-01-12 13:46:40 UTC, so midnight UTC was 49_600 s earlier.
    clock = Clock()
    h = make_store(clock)
    client, notifier = FakeClient(), FakeNotifier()
    client.payload = {"result": 1, "obj": {"charts": {"userLoad": [1000] * 12}}}
    run = make_energy_report(client, notifier, UTC, history=h, clock=clock)

    a(run())
    assert notifier.sent[-1] == "📊 Load energy today so far: 1.00 kWh"

    clock.t = 950_400  # local midnight
    for i in range(12 * 13 + 1):
        if i:
            clock.t += 300
        a(h.add_snapshot(load_w=500, pv_w=200, grid_w=100))
    a(run())
    assert notifier.sent[-1].splitlines()[:4] == [
        "📊 Energy today",
        "⚡ Used:       6.50 kWh",
        "☀️ Solar made: 2.60 kWh",
        "🔌 From grid:  1.30 kWh",
    ]


def test_energy_report_uses_local_date_for_day_chart():
    clock = Clock()  # 13:46 on 12 Jan UTC is 02:46 on 13 Jan in Auckland (UTC+13)
    client = DateClient()
    run = make_energy_report(client, FakeNotifier(), ZoneInfo("Pacific/Auckland"), clock=clock)
    a(run())
    assert client.dates == ["1970-01-13"]


class DateClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.dates = []

    async def acall(self, _method, *args):
        self.dates.append(args[0])
        return None


def test_energy_report_falls_back_when_history_is_down():
    client, notifier = FakeClient(), FakeNotifier()
    client.payload = {"result": 1, "obj": {"charts": {"userLoad": [1000] * 12}}}
    run = make_energy_report(client, notifier, UTC, history=History(BrokenBackend()))
    a(run())
    assert notifier.sent == ["📊 Load energy today so far: 1.00 kWh"]


def test_fmt_outages():
    now = 10_000
    text = fmt_outages([Outage(now - 600, None), Outage(now - 7200, now - 3600)], now)
    assert "started 10m ago, still ongoing" in text
    assert "2h 0m ago, lasted 1h 0m" in text
    assert fmt_outages([], now) == "🔌 No outages recorded yet."


def base_env(monkeypatch):
    for k in ["GROWATT_USERNAME", "GROWATT_PASSWORD", "GROWATT_DEVICE_SN",
              "GROWATT_PLANT_ID", "TELEGRAM_TOKEN"]:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")


def test_d1_config_all_or_nothing(monkeypatch):
    base_env(monkeypatch)
    assert Config.from_env().use_d1 is False
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    with pytest.raises(ConfigError, match="CLOUDFLARE_ACCOUNT_ID"):
        Config.from_env()
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    monkeypatch.setenv("CLOUDFLARE_D1_DATABASE_ID", "d")
    assert Config.from_env().use_d1 is True
