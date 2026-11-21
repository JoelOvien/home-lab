import asyncio
import logging
import os
import sqlite3
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
        grid_present INTEGER
    )""",
    "CREATE INDEX IF NOT EXISTS snapshots_ts ON snapshots (ts)",
    """CREATE TABLE IF NOT EXISTS outages (
        id INTEGER PRIMARY KEY,
        start_ts INTEGER NOT NULL,
        end_ts INTEGER
    )""",
]

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

    def execute(self, sql: str, params: tuple = ()) -> Rows:
        with self.db:
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


class History:
    def __init__(self, backend, clock: Callable[[], float] = time.time):
        self.backend = backend
        self.clock = clock
        self._schema_ready = False

    def now(self) -> int:
        return int(self.clock())

    def _execute(self, sql: str, params: tuple) -> Rows:
        # Created on first use rather than at startup, so a Cloudflare outage
        # at boot doesn't stop the bot and the tables appear once D1 answers.
        if not self._schema_ready:
            for stmt in SCHEMA:
                self.backend.execute(stmt)
            self._schema_ready = True
        return self.backend.execute(sql, params)

    async def _q(self, sql: str, params: tuple = ()) -> Rows:
        # D1 calls are blocking HTTP, so keep them off the event loop.
        return await asyncio.to_thread(self._execute, sql, params)

    async def add_snapshot(self, **m) -> None:
        gp = m.get("grid_present")
        await self._q(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.now(), m.get("pv_w"), m.get("load_w"), m.get("grid_w"),
                m.get("battery_w"), m.get("soc"), m.get("battery_v"), m.get("grid_v"),
                None if gp is None else int(gp),
            ),
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
        wh = 0.0
        covered = 0.0
        for a, b in zip(rows, rows[1:]):
            w0, w1, dt = a["load_w"], b["load_w"], b["ts"] - a["ts"]
            if w0 is None or w1 is None or dt <= 0 or dt > MAX_GAP_SECONDS:
                continue
            wh += (w0 + w1) / 2 * dt / 3600
            covered += dt
        return Energy(kwh=wh / 1000, covered_seconds=covered)
