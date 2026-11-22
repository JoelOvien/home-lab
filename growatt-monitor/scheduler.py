import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, List, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

JobFn = Callable[[], Awaitable[None]]


@dataclass
class Job:
    name: str
    interval_seconds: float
    fn: JobFn
    run_immediately: bool = True
    daily_at: Optional[str] = None
    tz: Optional[ZoneInfo] = None


def next_daily_run(hhmm: str, tz: ZoneInfo, now: datetime) -> datetime:
    """Next wall-clock HH:MM in tz strictly after now, as an aware UTC datetime."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    local_now = now.astimezone(tz)
    day = local_now.date()
    while True:
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
        # Compare in UTC: aware datetimes sharing a tzinfo compare by wall
        # clock, which is wrong across a DST change.
        if candidate.astimezone(timezone.utc) > now.astimezone(timezone.utc):
            return candidate.astimezone(timezone.utc)
        day += timedelta(days=1)


def seconds_until_daily(hhmm: str, tz: ZoneInfo, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    return (next_daily_run(hhmm, tz, now) - now.astimezone(timezone.utc)).total_seconds()


class Scheduler:
    def __init__(self) -> None:
        self._jobs: List[Job] = []

    def register(self, name: str, interval_seconds: float, fn: JobFn,
                 run_immediately: bool = True) -> None:
        self._jobs.append(Job(name, interval_seconds, fn, run_immediately))
        log.info("Registered job %s (every %ss)", name, interval_seconds)

    def register_daily(self, name: str, hhmm: str, tz: ZoneInfo, fn: JobFn) -> None:
        self._jobs.append(Job(name, 0, fn, run_immediately=False, daily_at=hhmm, tz=tz))
        log.info("Registered job %s (daily at %s %s)", name, hhmm, tz.key)

    async def _run_once(self, job: Job) -> None:
        try:
            log.debug("Running job %s", job.name)
            await job.fn()
        except asyncio.CancelledError:
            raise
        except Exception:
            # A crash in one job must not kill the others.
            log.exception("Job %s crashed; will retry on next run", job.name)

    async def _run_job_loop(self, job: Job) -> None:
        if job.daily_at is not None:
            last_target = None
            while True:
                now = datetime.now(timezone.utc)
                # A timer that wakes a hair early must not pick today's slot again.
                if last_target is not None and now < last_target:
                    now = last_target
                last_target = next_daily_run(job.daily_at, job.tz, now)
                await asyncio.sleep(seconds_until_daily(job.daily_at, job.tz, now))
                await self._run_once(job)
        if not job.run_immediately:
            await asyncio.sleep(job.interval_seconds)
        while True:
            await self._run_once(job)
            await asyncio.sleep(job.interval_seconds)

    async def run_forever(self) -> None:
        if not self._jobs:
            log.warning("Scheduler started with no jobs")
            return
        tasks = [asyncio.create_task(self._run_job_loop(j), name=j.name) for j in self._jobs]
        await asyncio.gather(*tasks)
