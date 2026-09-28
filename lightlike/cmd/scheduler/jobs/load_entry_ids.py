import typing as t
from datetime import datetime, timedelta

from apscheduler.triggers.date import DateTrigger

from lightlike.app.cache import TimeEntryIdList
from lightlike.cmd.scheduler.jobs.types import JobKwargs

__all__: t.Sequence[str] = ("default_job_load_entry_ids", "load_entry_ids")


def load_entry_ids() -> None:
    TimeEntryIdList().ids


def default_job_load_entry_ids() -> JobKwargs:
    return JobKwargs(
        func=load_entry_ids,
        id="load_entry_ids",
        name="load_entry_ids",
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=5)),
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        jobstore="sqlalchemy",
        executor="sqlalchemy",
        misfire_grace_time=10,
    )
