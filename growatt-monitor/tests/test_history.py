import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from bot.notifications import fmt_outages  # noqa: E402
from history import History, Outage  # noqa: E402
from jobs.energy_report import make_energy_report  # noqa: E402
from jobs.grid_monitor import make_grid_monitor  # noqa: E402
from jobs.recorder import make_recorder  # noqa: E402
from tests.test_jobs import FakeClient, FakeNotifier, status  # noqa: E402


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def store(clock, path=":memory:"):
    return History(path, clock=clock)


def test_load_energy_trapezoid_and_gaps():
    clock = Clock()
    h = store(clock)
    # 1 hour at a steady 1000 W in 5-minute steps = 1 kWh.
    for _ in range(13):
        h.add_snapshot(load_w=1000)
        clock.t += 300
    # A 1-hour gap (worker down) must not be integrated.
    clock.t += 3600
    h.add_snapshot(load_w=1000)
    e = h.load_energy(12 * 3600)
    assert abs(e.kwh - 1.0) < 1e-9
    assert e.covered_seconds == 3600


def test_load_energy_skips_null_samples():
    clock = Clock()
    h = store(clock)
    for w in (1000, None, 1000):
        h.add_snapshot(load_w=w)
        clock.t += 300
    assert h.load_energy(3600).kwh == 0


def test_history_persists_on_disk(tmp_path):
    clock = Clock()
    path = str(tmp_path / "nested" / "h.db")
    store(clock, path).start_outage()
    assert store(clock, path).open_outage() == Outage(int(clock.t), None)


def run_grid(client, notifier, history, clock, readings):
    run = make_grid_monitor(client, notifier, history, clock=clock)
    for vac, dt in readings:
        clock.t += dt
        client.payload = status(vac=vac)
        asyncio.run(run())


def test_outage_recorded_and_resumed_after_restart():
    clock = Clock()
    h = store(clock)
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(220, 0), (0, 60)])
    started = int(clock.t)

    # Worker restarts mid-outage; the restore still reports the full duration.
    notifier2 = FakeNotifier()
    run_grid(client, notifier2, h, clock, [(0, 600), (220, 3000)])
    assert notifier2.sent == ["🔌 Grid RESTORED after 1h 0m (220.0V)"]
    assert h.recent_outages() == [Outage(started, started + 3600)]


def test_open_outage_closed_when_grid_back_at_startup():
    clock = Clock()
    h = store(clock)
    h.start_outage()
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(220, 900)])
    assert h.open_outage() is None
    assert notifier.sent == []


def test_outage_with_unknown_start_is_not_recorded():
    clock = Clock()
    h = store(clock)
    client, notifier = FakeClient(), FakeNotifier()
    run_grid(client, notifier, h, clock, [(0, 0), (220, 300)])
    assert h.recent_outages() == []
    assert notifier.sent == ["🔌 Grid RESTORED (220.0V)"]


def test_recorder_writes_snapshot_and_skips_offline():
    clock = Clock()
    h = store(clock)
    client = FakeClient()
    run = make_recorder(client, h)
    asyncio.run(run())
    client.payload = status(soc=60, vac=220)
    asyncio.run(run())
    rows = h.db.execute("SELECT load_w, soc, grid_present, pv_w FROM snapshots").fetchall()
    assert rows == [(800.0, 60.0, 1, None)]


def test_energy_report_uses_history_or_falls_back():
    clock = Clock()
    h = store(clock)
    client, notifier = FakeClient(), FakeNotifier()
    client.payload = {"result": 1, "obj": {"charts": {"userLoad": [1000] * 12}}}
    run = make_energy_report(client, notifier, hours=12, history=h)

    asyncio.run(run())
    assert notifier.sent[-1] == "📊 Load energy today so far: 1.00 kWh"

    for i in range(12 * 12 + 1):
        if i:
            clock.t += 300
        h.add_snapshot(load_w=500)
    asyncio.run(run())
    assert notifier.sent[-1] == "📊 Load energy, last 12h: 6.00 kWh"


def test_fmt_outages():
    now = 10_000
    text = fmt_outages([Outage(now - 600, None), Outage(now - 7200, now - 3600)], now)
    assert "started 10m ago, still ongoing" in text
    assert "2h 0m ago, lasted 1h 0m" in text
    assert fmt_outages([], now) == "🔌 No outages recorded yet."
