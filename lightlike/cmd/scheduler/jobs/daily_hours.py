import typing as t
from datetime import datetime
from inspect import cleandoc

from apscheduler.triggers.interval import IntervalTrigger
from google.cloud.bigquery import Row
from more_itertools import first
from prompt_toolkit.patch_stdout import patch_stdout
from pytz import timezone
from rich import get_console
from rich.console import Console, NewLine

from lightlike.app.config import AppConfig
from lightlike.app.dates import get_relative_week, now
from lightlike.client import CliQueryRoutines
from lightlike.cmd.scheduler.jobs.types import JobKwargs

if t.TYPE_CHECKING:
    from lightlike.app.dates import DateParams

__all__: t.Sequence[str] = (
    "print_daily_total_hours",
    "default_job_print_daily_total_hours",
)


def print_daily_total_hours() -> None:
    console: Console = get_console()
    routine: CliQueryRoutines = CliQueryRoutines()

    today: datetime = now(timezone(AppConfig().get("settings", "timezone")))
    date_params: "DateParams" = get_relative_week(
        today, AppConfig().get("settings", "week_start")
    )

    base_query: str = cleandoc(
        """
    SELECT
      SUM(hours) AS hours
    FROM
      (
        SELECT
          CASE
            WHEN paused THEN ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(timestamp_paused, timestamp_start, SECOND), 3600) AS NUMERIC) - IFNULL(paused_hours, 0), 4)
            WHEN active THEN ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(IFNULL(timestamp_end, %s.current_timestamp()), timestamp_start, SECOND), 3600) AS NUMERIC) - IFNULL(paused_hours, 0), 4)
            ELSE hours
          END AS hours,
        FROM
          %s
          %s
      )
    """
    )

    query_total_daily: str = base_query % (
        routine.dataset,
        routine.timesheet_id,
        f'WHERE `date` = "{now().date()}"',
    )
    query_total_weekly: str = base_query % (
        routine.dataset,
        routine.timesheet_id,
        f'WHERE `date` BETWEEN "{date_params.start.date()}" AND "{date_params.end.date()}"',
    )

    total_daily = t.cast(Row, first(routine._query(query_total_daily)))
    total_weekly = t.cast(Row, first(routine._query(query_total_weekly)))

    with patch_stdout(raw=True):
        console.print(NewLine())
        console.log(f"Total hours logged today: {total_daily.hours or 0}")
        console.log(f"Total hours logged this week: {total_weekly.hours or 0}")


def default_job_print_daily_total_hours() -> JobKwargs:
    job_kwargs = JobKwargs(
        func=print_daily_total_hours,
        id="print_daily_total_hours",
        name="print_daily_total_hours",
        trigger=IntervalTrigger(hours=1),
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        jobstore="sqlalchemy",
        executor="sqlalchemy",
        misfire_grace_time=10,
    )
    return job_kwargs
