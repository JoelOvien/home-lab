import asyncio
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests

log = logging.getLogger(__name__)

DEFAULT_PATH = "data/history.db"

# Snapshot pairs further apart than this are treated as a gap (worker down,
# inverter offline) and not integrated across.
MAX_GAP_SECONDS = 15 * 60

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS snapshots (
        ts INTEGER NOT NULL,
        pv_w REAL,
        load_w REAL,
        grid_w REAL,
        battery_w REAL,
        soc REAL,
        battery_v REAL,
        grid_v REAL,
        grid_present INTEGER,
        load_pct REAL,
        inv_status INTEGER,
        status INTEGER,
        dtc INTEGER
    )""",
    "CREATE INDEX IF NOT EXISTS snapshots_ts ON snapshots (ts)",
    """CREATE TABLE IF NOT EXISTS outages (
        id INTEGER PRIMARY KEY,
        start_ts INTEGER NOT NULL,
        end_ts INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS worker_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_ts INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        ts INTEGER,
        kind TEXT,
        detail TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS events_ts ON events (ts)",
]

# Columns added after the first release. CREATE TABLE already has them for new
# databases; older ones get them through ALTER TABLE.
SNAPSHOT_MIGRATIONS = [
    ("load_pct", "REAL"),
    ("inv_status", "INTEGER"),
    ("status", "INTEGER"),
    ("dtc", "INTEGER"),
]

SNAPSHOT_COLUMNS = (
    "pv_w", "load_w", "grid_w", "battery_w", "soc", "battery_v", "grid_v",
    "grid_present", "load_pct", "inv_status", "status", "dtc",
)

EVENT_KINDS = {
    "grid_down", "grid_up", "battery_low", "battery_full",
    "overload", "fault", "solar_stopped", "unreachable",
}

WEEK_SECONDS = 7 * 86400

Rows = list[dict[str, Any]]


class HistoryError(RuntimeError):
    pass


class LocalBackend:
    name = "local SQLite"

    def __init__(self, path: str = DEFAULT_PATH):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        # The store runs queries in a worker thread, so allow cross-thread use.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> Rows:
        with self._lock, self.db:
            return [dict(r) for r in self.db.execute(sql, params).fetchall()]


class D1Backend:
    name = "Cloudflare D1"

    def __init__(self, account_id: str, database_id: str, api_token: str, timeout: float = 10.0):
        self.url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/d1/database/{database_id}/query"
        )
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_token}"
        self.timeout = timeout

    def execute(self, sql: str, params: tuple = ()) -> Rows:
        try:
            resp = self.session.post(
                self.url, json={"sql": sql, "params": list(params)}, timeout=self.timeout
            )
            body = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise HistoryError(f"D1 request failed: {type(e).__name__}") from e
        if not resp.ok or not body.get("success"):
            errors = [e.get("message") for e in body.get("errors", [])]
            raise HistoryError(f"D1 query failed (HTTP {resp.status_code}): {errors}")
        result = body.get("result") or [{}]
        return result[0].get("results") or []


@dataclass
class Outage:
    start_ts: int
    end_ts: Optional[int]


@dataclass
class Energy:
    kwh: float
    covered_seconds: float


@dataclass
class EnergySplit:
    load_kwh: float
    pv_kwh: float
    grid_kwh: float
    covered_seconds: float


@dataclass
class Event:
    ts: int
    kind: str
    detail: Optional[str]


@dataclass
class WeekVoltage:
    week_start_ts: int
    mean_v: float
    samples: int


def _integrate(rows: Rows, field: str) -> Energy:
    """Trapezoid rule over snapshot pairs, skipping nulls and gaps."""
    wh = 0.0
    covered = 0.0
    for a, b in zip(rows, rows[1:]):
        w0, w1, dt = a[field], b[field], b["ts"] - a["ts"]
        if w0 is None or w1 is None or dt <= 0 or dt > MAX_GAP_SECONDS:
            continue
        wh += (w0 + w1) / 2 * dt / 3600
        covered += dt
    return Energy(kwh=wh / 1000, covered_seconds=covered)


def _is_duplicate_column(e: Exception) -> bool:
    return "duplicate column" in str(e).lower()


class History:
    def __init__(self, backend, clock: Callable[[], float] = time.time):
        self.backend = backend
        self.clock = clock
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def now(self) -> int:
        return int(self.clock())

    def _execute(self, sql: str, params: tuple) -> Rows:
        # Created on first use rather than at startup, so a Cloudflare outage
        # at boot doesn't stop the bot and the tables appear once D1 answers.
        if not self._schema_ready:
            with self._schema_lock:
                if not self._schema_ready:
                    self._create_schema()
        return self.backend.execute(sql, params)

    def _create_schema(self) -> None:
        for stmt in SCHEMA:
            self.backend.execute(stmt)
        for col, typ in SNAPSHOT_MIGRATIONS:
            try:
                self.backend.execute(f"ALTER TABLE snapshots ADD COLUMN {col} {typ}")
            except (sqlite3.OperationalError, HistoryError) as e:
                if not _is_duplicate_column(e):
                    raise
        self._schema_ready = True

    async def _q(self, sql: str, params: tuple = ()) -> Rows:
        # D1 calls are blocking HTTP, so keep them off the event loop.
        return await asyncio.to_thread(self._execute, sql, params)

    async def add_snapshot(self, **m) -> None:
        unknown = set(m) - set(SNAPSHOT_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown snapshot fields: {sorted(unknown)}")
        if m.get("grid_present") is not None:
            m["grid_present"] = int(m["grid_present"])
        cols = ("ts",) + SNAPSHOT_COLUMNS
        await self._q(
            f"INSERT INTO snapshots ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (self.now(), *(m.get(c) for c in SNAPSHOT_COLUMNS)),
        )

    async def set_state(self, key: str, value) -> None:
        await self._q(
            "INSERT INTO worker_state (key, value, updated_ts) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_ts = excluded.updated_ts",
            (key, None if value is None else str(value), self.now()),
        )

    async def get_state(self, key: str) -> Optional[str]:
        rows = await self._q("SELECT value FROM worker_state WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    async def delete_state(self, key: str) -> None:
        await self._q("DELETE FROM worker_state WHERE key = ?", (key,))

    async def add_event(self, kind: str, detail: Optional[str] = None) -> None:
        if kind not in EVENT_KINDS:
            raise ValueError(f"Unknown event kind {kind!r}")
        await self._q(
            "INSERT INTO events (ts, kind, detail) VALUES (?, ?, ?)", (self.now(), kind, detail)
        )

    async def recent_events(self, limit: int = 20) -> list[Event]:
        rows = await self._q(
            f"SELECT ts, kind, detail FROM events ORDER BY ts DESC, id DESC LIMIT {int(limit)}"
        )
        return [Event(r["ts"], r["kind"], r["detail"]) for r in rows]

    async def series(self, since: float) -> Rows:
        return await self._q(
            "SELECT ts, pv_w, load_w, grid_w, soc FROM snapshots WHERE ts >= ? ORDER BY ts",
            (int(since),),
        )

    async def open_outage(self) -> Optional[Outage]:
        rows = await self._q(
            "SELECT start_ts, end_ts FROM outages WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
        )
        return Outage(rows[0]["start_ts"], None) if rows else None

    async def start_outage(self) -> None:
        await self._q("INSERT INTO outages (start_ts) VALUES (?)", (self.now(),))

    async def end_outage(self) -> Optional[Outage]:
        """Close the open outage, if any, and return it."""
        open_ = await self.open_outage()
        if open_ is None:
            return None
        end = self.now()
        await self._q("UPDATE outages SET end_ts = ? WHERE end_ts IS NULL", (end,))
        return Outage(open_.start_ts, end)

    async def recent_outages(self, limit: int = 10) -> list[Outage]:
        rows = await self._q(
            f"SELECT start_ts, end_ts FROM outages ORDER BY start_ts DESC LIMIT {int(limit)}"
        )
        return [Outage(r["start_ts"], r["end_ts"]) for r in rows]

    async def load_energy(self, window_seconds: float) -> Energy:
        """Trapezoidal integration of load watts over the last window."""
        since = int(self.now() - window_seconds)
        rows = await self._q(
            "SELECT ts, load_w FROM snapshots WHERE ts >= ? ORDER BY ts", (since,)
        )
        return _integrate(rows, "load_w")

    async def energy_split(self, window_seconds: float) -> EnergySplit:
        """Load, PV and grid-drawn kWh over the last window. They don't add up:
        the battery sits in between, and grid draw may include charging."""
        rows = await self.series(self.now() - window_seconds)
        load = _integrate(rows, "load_w")
        return EnergySplit(
            load_kwh=load.kwh,
            pv_kwh=_integrate(rows, "pv_w").kwh,
            grid_kwh=_integrate(rows, "grid_w").kwh,
            covered_seconds=load.covered_seconds,
        )

    async def battery_health(self, weeks: int = 8) -> list[WeekVoltage]:
        """Mean battery voltage per week, from snapshots taken at 45-55% SOC
        so the readings are comparable across weeks."""
        since = int(self.now() - weeks * WEEK_SECONDS)
        rows = await self._q(
            f"SELECT (ts / {WEEK_SECONDS}) * {WEEK_SECONDS} AS wk, AVG(battery_v) AS v, "
            "COUNT(*) AS n FROM snapshots "
            "WHERE ts >= ? AND soc BETWEEN 45 AND 55 AND battery_v IS NOT NULL "
            "GROUP BY wk ORDER BY wk",
            (since,),
        )
        return [WeekVoltage(int(r["wk"]), float(r["v"]), int(r["n"])) for r in rows]
