import typing as t
from datetime import datetime

from apscheduler.triggers.date import DateTrigger

from lightlike.app.cache import TimeEntryCache
from lightlike.cmd.scheduler.jobs.types import JobKwargs

__all__: t.Sequence[str] = ("sync_cache", "default_job_sync_cache")


def sync_cache() -> None:
    TimeEntryCache().sync()


def default_job_sync_cache() -> JobKwargs:
    job_kwargs = JobKwargs(
        func=sync_cache,
        id="sync_cache",
        name="sync_cache",
        trigger=DateTrigger(run_date=datetime.now()),
        coalesce=True,
        max_instances=1,
        jobstore="sqlalchemy",
        executor="sqlalchemy",
    )
    return job_kwargs
