import typing as t
from contextlib import suppress
from datetime import datetime
from inspect import cleandoc

from apscheduler.triggers.cron import CronTrigger
from google.cloud.bigquery import Row
from more_itertools import first
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich.console import Console, NewLine

from lightlike.app.config import AppConfig
from lightlike.app.dates import get_relative_week, now
from lightlike.client import CliQueryRoutines
from lightlike.cmd.scheduler.jobs.types import JobKwargs

if t.TYPE_CHECKING:
    from datetime import _TzInfo

    from lightlike.app.dates import DateParams

__all__: t.Sequence[str] = (
    "print_daily_total_hours",
    "default_job_print_daily_total_hours",
)


def print_daily_total_hours() -> None:
    with suppress(Exception):
        console: Console = get_console()
        routine: CliQueryRoutines = CliQueryRoutines()
        tzinfo: "_TzInfo" = AppConfig().tzinfo
        today: datetime = now(tzinfo)
        date_params: "DateParams" = get_relative_week(
            today, AppConfig().get("settings", "week-start", default=0)
        )

        base_query: str = cleandoc(
            """
            WITH
              timesheet AS
                (
                  SELECT
                    CASE
                      WHEN billable AND paused THEN ROUND(
                        SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(timestamp_paused, timestamp_start, SECOND), 3600) AS NUMERIC)
                        - IFNULL(paused_hours, 0), 4
                      )
                      WHEN billable AND active THEN ROUND(
                        SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(IFNULL(timestamp_end, %s.current_timestamp()), timestamp_start, SECOND), 3600) AS NUMERIC)
                        - IFNULL(paused_hours, 0), 4
                      )
                      WHEN billable AND NOT (paused OR active) THEN hours
                    END AS billable_hours,
                    CASE
                      WHEN NOT billable AND paused THEN ROUND(
                        SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(timestamp_paused, timestamp_start, SECOND), 3600) AS NUMERIC)
                        - IFNULL(paused_hours, 0), 4
                      )
                      WHEN NOT billable AND active THEN ROUND(
                        SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(IFNULL(timestamp_end, %s.current_timestamp()), timestamp_start, SECOND), 3600) AS NUMERIC)
                        - IFNULL(paused_hours, 0), 4
                      )
                      WHEN NOT billable AND NOT (paused OR active) THEN hours
                    END AS non_billable_hours,
                  FROM
                    %s
                    %s
                )
            SELECT
              FORMAT("%%.*f", 4, CAST(SUM(billable_hours) AS FLOAT64)) AS billable_hours,
              FORMAT("%%.*f", 4, CAST(SUM(non_billable_hours) AS FLOAT64)) AS non_billable_hours,
              FORMAT("%%.*f", 4, CAST(SUM(billable_hours) + SUM(non_billable_hours) AS FLOAT64)) AS total_hours,
            FROM
              timesheet
      """
        )

        query_total_daily: str = base_query % (
            routine.dataset,
            routine.dataset,
            routine.timesheet_id,
            f'WHERE `date` = "{now().date()}"',
        )
        query_total_weekly: str = base_query % (
            routine.dataset,
            routine.dataset,
            routine.timesheet_id,
            f'WHERE `date` BETWEEN "{date_params.start.date()}" AND "{date_params.end.date()}"',
        )

        total_daily = t.cast(Row, first(routine._query(query_total_daily)))
        total_weekly = t.cast(Row, first(routine._query(query_total_weekly)))

        daily_billable_hours = total_daily.billable_hours or 0
        daily_non_billable = total_daily.non_billable_hours or 0
        daily_total_hours = total_daily.total_hours or 0

        weekly_billable_hours = total_weekly.billable_hours or 0
        weekly_non_billable = total_weekly.non_billable_hours or 0
        weekly_total_hours = total_weekly.total_hours or 0

        with patch_stdout(raw=True):
            console.print(NewLine())
            console.log(
                f"Daily | Billable = {daily_billable_hours} "
                f"Non-Billable {daily_non_billable} "
                f"Total = {daily_total_hours}"
            )
            console.log(
                f"Weekly | Billable = {weekly_billable_hours} "
                f"Non-Billable {weekly_non_billable} "
                f"Total = {weekly_total_hours}"
            )
            console.log(f"Total hours logged this week: {total_weekly.hours or 0}")


def default_job_print_daily_total_hours() -> JobKwargs:
    job_kwargs = JobKwargs(
        func=print_daily_total_hours,
        id="print_daily_total_hours",
        name="print_daily_total_hours",
        trigger=CronTrigger(hour="6-23", minute="0"),
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        jobstore="sqlalchemy",
        executor="sqlalchemy",
        misfire_grace_time=10,
    )
    return job_kwargs
