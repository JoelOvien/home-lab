import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)

# last_ok_ts is refreshed by every Growatt call; writing it to history more
# often than this would double the D1 traffic for no gain.
OK_WRITE_INTERVAL = 300
MAX_ERROR_LEN = 200


@dataclass
class ErrorRecord:
    ts: float
    text: str


def describe_error(e: Exception) -> str:
    text = f"{type(e).__name__}: {e}"
    return text if len(text) <= MAX_ERROR_LEN else text[: MAX_ERROR_LEN - 1] + "…"


class WorkerHealth:
    """Tracks Growatt call outcomes for /uptime and mirrors them into
    worker_state so the app can show them."""

    def __init__(self, history=None, clock: Callable[[], float] = time.time):
        self.history = history
        self.clock = clock
        self.started_ts = clock()
        self.last_ok_ts: Optional[float] = None
        self.recent_errors: deque[ErrorRecord] = deque(maxlen=5)
        self._last_ok_written = 0.0
        self._tasks: set[asyncio.Task] = set()

    def on_call(self, error: Optional[Exception]) -> None:
        now = self.clock()
        if error is None:
            self.last_ok_ts = now
            if now - self._last_ok_written >= OK_WRITE_INTERVAL:
                self._last_ok_written = now
                self._persist({"last_ok_ts": int(now)})
            return
        rec = ErrorRecord(now, describe_error(error))
        self.recent_errors.append(rec)
        self._persist({"last_error": rec.text, "last_error_ts": int(now)})

    def _persist(self, values: dict) -> None:
        if self.history is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._write(values))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _write(self, values: dict) -> None:
        for key, value in values.items():
            try:
                await self.history.set_state(key, value)
            except Exception:
                log.warning("Could not write %s to history", key, exc_info=True)
                return
