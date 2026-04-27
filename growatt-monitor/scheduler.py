import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, List

log = logging.getLogger(__name__)

JobFn = Callable[[], Awaitable[None]]


@dataclass
class Job:
    name: str
    interval_seconds: float
    fn: JobFn
    run_immediately: bool = True


class Scheduler:
    def __init__(self) -> None:
        self._jobs: List[Job] = []

    def register(self, name: str, interval_seconds: float, fn: JobFn,
                 run_immediately: bool = True) -> None:
        self._jobs.append(Job(name, interval_seconds, fn, run_immediately))
        log.info("Registered job %s (every %ss)", name, interval_seconds)

    async def _run_job_loop(self, job: Job) -> None:
        if not job.run_immediately:
            await asyncio.sleep(job.interval_seconds)
        while True:
            try:
                log.debug("Running job %s", job.name)
                await job.fn()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A crash in one job must not kill the others.
                log.exception("Job %s crashed; will retry on next interval", job.name)
            await asyncio.sleep(job.interval_seconds)

    async def run_forever(self) -> None:
        if not self._jobs:
            log.warning("Scheduler started with no jobs")
            return
        tasks = [asyncio.create_task(self._run_job_loop(j), name=j.name) for j in self._jobs]
        await asyncio.gather(*tasks)
