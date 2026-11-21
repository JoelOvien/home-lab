import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_PATH = "data/history.db"

# Snapshot pairs further apart than this are treated as a gap (worker down,
# inverter offline) and not integrated across.
MAX_GAP_SECONDS = 15 * 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    ts INTEGER NOT NULL,
    pv_w REAL,
    load_w REAL,
    grid_w REAL,
    battery_w REAL,
    soc REAL,
    battery_v REAL,
    grid_v REAL,
    grid_present INTEGER
);
CREATE INDEX IF NOT EXISTS snapshots_ts ON snapshots (ts);
CREATE TABLE IF NOT EXISTS outages (
    id INTEGER PRIMARY KEY,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER
);
"""


@dataclass
class Outage:
    start_ts: int
    end_ts: Optional[int]


@dataclass
class Energy:
    kwh: float
    covered_seconds: float


class History:
    def __init__(self, path: str = DEFAULT_PATH, clock: Callable[[], float] = time.time):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.clock = clock
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def now(self) -> int:
        return int(self.clock())

    def add_snapshot(self, **metrics) -> None:
        grid_present = metrics.get("grid_present")
        with self.db:
            self.db.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.now(),
                    metrics.get("pv_w"),
                    metrics.get("load_w"),
                    metrics.get("grid_w"),
                    metrics.get("battery_w"),
                    metrics.get("soc"),
                    metrics.get("battery_v"),
                    metrics.get("grid_v"),
                    None if grid_present is None else int(grid_present),
                ),
            )

    def open_outage(self) -> Optional[Outage]:
        row = self.db.execute(
            "SELECT start_ts, end_ts FROM outages WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
        ).fetchone()
        return Outage(*row) if row else None

    def start_outage(self) -> None:
        with self.db:
            self.db.execute("INSERT INTO outages (start_ts) VALUES (?)", (self.now(),))

    def end_outage(self) -> Optional[Outage]:
        """Close the open outage, if any, and return it."""
        open_ = self.open_outage()
        if open_ is None:
            return None
        end = self.now()
        with self.db:
            self.db.execute("UPDATE outages SET end_ts = ? WHERE end_ts IS NULL", (end,))
        return Outage(open_.start_ts, end)

    def recent_outages(self, limit: int = 10) -> list[Outage]:
        rows = self.db.execute(
            "SELECT start_ts, end_ts FROM outages ORDER BY start_ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Outage(*r) for r in rows]

    def load_energy(self, window_seconds: float) -> Energy:
        """Trapezoidal integration of load watts over the last window."""
        since = self.now() - window_seconds
        rows = self.db.execute(
            "SELECT ts, load_w FROM snapshots WHERE ts >= ? ORDER BY ts", (since,)
        ).fetchall()
        wh = 0.0
        covered = 0.0
        for (t0, w0), (t1, w1) in zip(rows, rows[1:]):
            dt = t1 - t0
            if w0 is None or w1 is None or dt <= 0 or dt > MAX_GAP_SECONDS:
                continue
            wh += (w0 + w1) / 2 * dt / 3600
            covered += dt
        return Energy(kwh=wh / 1000, covered_seconds=covered)
