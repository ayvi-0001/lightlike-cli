import typing as t
from datetime import datetime

from apscheduler.triggers.date import DateTrigger
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console

from lightlike.app.cache import TimeEntryAppData, TimeEntryCache
from lightlike.cmd.scheduler.jobs.types import JobKwargs

__all__: t.Sequence[str] = ("default_job_sync_cache", "sync_cache")


def sync_cache() -> None:
    console = get_console()
    with patch_stdout(raw=True):
        console.log("Syncing appdata & cache")

    TimeEntryCache().sync()
    TimeEntryAppData().sync()

    with patch_stdout(raw=True):
        console.log("Appdata/cache synced.")


def default_job_sync_cache() -> JobKwargs:
    return JobKwargs(
        func=sync_cache,
        id="sync_cache",
        name="sync_cache",
        trigger=DateTrigger(run_date=datetime.now()),
        coalesce=True,
        max_instances=1,
        jobstore="sqlalchemy",
        executor="sqlalchemy",
    )
