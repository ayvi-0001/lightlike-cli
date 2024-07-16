import typing as t

import click
import rtoml
import six
from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from click.shell_completion import CompletionItem
from pytz import timezone
from rich import box
from rich import print as rprint
from rich.table import Table

from lightlike.__about__ import __appname_sc__
from lightlike.app import shell_complete
from lightlike.app.config import AppConfig
from lightlike.app.core import FormattedCommand
from lightlike.app.dates import parse_date
from lightlike.internal import appdir, utils

__all__: t.Sequence[str] = (
    "add_job",
    "print_jobs",
    "modify_job",
    "pause_job",
    "remove_all_jobs",
    "remove_job",
    "reschedule_job",
    "resume_job",
)


#: constant indicating a scheduler's stopped state
STATE_STOPPED = 0
#: constant indicating a scheduler's running state (started and processing jobs)
STATE_RUNNING = 1
#: constant indicating a scheduler's paused state (started but not processing jobs)
STATE_PAUSED = 2


def available_functions(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completions = []

    if appdir.SCHEDULER_CONFIG.exists():
        for k, v in (
            rtoml.load(appdir.SCHEDULER_CONFIG)["jobs"].get("functions", {}).items()
        ):
            completions.append(CompletionItem(value=k, help=str(v)))

    return completions


def available_jobstores(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completions = []

    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    for k, v in scheduler._jobstores.items():
        completions.append(CompletionItem(value=k, help=f"{v!r}"))

    return completions


def available_executors(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completions = []

    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    for k, v in scheduler._executors.items():
        completions.append(CompletionItem(value=k, help=f"{v!r}"))

    return completions


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "--func",
    required=True,
    shell_complete=available_functions,
    type=click.STRING,
    help="callable (or a textual reference to one in the package.module:some.object format) to run at the given time",
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.option(
    "--id",
    "id_",
    type=click.STRING,
    help="the unique identifier of this job",
)
@click.option(
    "--name",
    type=click.STRING,
    help="the description of this job",
)
@click.option(
    "--args",
    cls=shell_complete.LiteralEvalOption,
    type=tuple,
    default="()",
    help="positional arguments to the callable",
)
@click.option(
    "--kwargs",
    cls=shell_complete.LiteralEvalOption,
    default="{}",
    type=dict,
    help="keyword arguments to the callable",
)
@click.option(
    "--coalesce",
    type=click.BOOL,
    shell_complete=shell_complete.Param("coalesce").bool,
    help="whether to only run the job once when several run times are due",
)
@click.option(
    "--replace-existing",
    type=click.BOOL,
    shell_complete=shell_complete.Param("replace-existing").bool,
    help="True to replace an existing job with the same id (but retain the number of runs from the existing one)",
)
@click.option(
    "--executor",
    shell_complete=available_executors,
    type=click.STRING,
    help="the name of the executor that will run this job",
)
@click.option(
    "--misfire_grace_time",
    type=click.INT,
    help="the time (in seconds) how much this job's execution is allowed to",
)
@click.option(
    "--max_instances",
    type=click.INT,
    help="the maximum number of concurrently executing instances allowed for this",
)
@click.option(
    "--next_run_time",
    type=click.STRING,
    help="the next scheduled run time of this job",
)
@click.option(
    "--trigger",
    type=click.Choice(["date", "interval", "cron"]),
    help="type of apscheduler.triggers",
    required=True,
)
@click.option(
    "--run_date",
    type=click.STRING,
    help="triggers: [DateTrigger], the date/time to run the job at",
)
@click.option(
    "--weeks",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of weeks to wait",
)
@click.option(
    "--days",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of days to wait",
)
@click.option(
    "--hours",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of hours to wait",
)
@click.option(
    "--minutes",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of minutes to wait",
)
@click.option(
    "--seconds",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of seconds to wait",
)
@click.option(
    "--year",
    type=click.INT,
    help="triggers: [CronTrigger], 4-digit year",
)
@click.option(
    "--month",
    type=click.INT,
    help="triggers: [CronTrigger], month (1-12)",
)
@click.option(
    "--week",
    type=click.INT,
    help="triggers: [CronTrigger], day of month (1-31)",
)
@click.option(
    "--day",
    type=click.INT,
    help="triggers: [CronTrigger], ISO week (1-53)",
)
@click.option(
    "--day_of_week",
    type=click.STRING,
    help="triggers: [CronTrigger], number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun)",
)
@click.option(
    "--hour",
    type=click.INT,
    help="triggers: [CronTrigger], hour (0-23)",
)
@click.option(
    "--minute",
    type=click.INT,
    help="triggers: [CronTrigger], minute (0-59)",
)
@click.option(
    "--second",
    type=click.INT,
    help="triggers: [CronTrigger], second (0-59)",
)
@click.option(
    "--start_date",
    type=click.STRING,
    help="triggers: [CronTrigger], earliest possible date/time to trigger on (inclusive)",
)
@click.option(
    "--end_date",
    type=click.STRING,
    help="triggers: [CronTrigger], latest possible date/time to trigger on (inclusive)",
)
@click.pass_context
def add_job(
    ctx: click.Context,
    func: str,
    jobstore: str,
    id_: str,
    name: str,
    args: tuple[t.Any | None],
    kwargs: dict[str, t.Any],
    coalesce: bool,
    replace_existing: bool,
    executor: str,
    misfire_grace_time: int,
    max_instances: int,
    next_run_time: str,
    trigger: str,
    run_date: str,
    weeks: int,
    days: int,
    hours: int,
    minutes: int,
    seconds: int,
    year: int,
    month: int,
    week: int,
    day: int,
    day_of_week: str,
    hour: int,
    minute: int,
    second: int,
    start_date: str,
    end_date: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    trigger_kwargs: dict[str, t.Any] = {}
    tzinfo = timezone(AppConfig().get("settings", "timezone"))

    job_kwargs: dict[str, t.Any] = {}
    if appdir.SCHEDULER_CONFIG.exists():
        job_kwargs["func"] = (
            rtoml.load(appdir.SCHEDULER_CONFIG)["jobs"]
            .get("functions", {})
            .get(func, func)
        )
    else:
        job_kwargs["func"] = func

    match trigger:
        case "date":
            if run_date is not None:
                trigger_kwargs["run_date"] = parse_date(run_date, tzinfo=tzinfo)
            if timezone is not None:
                trigger_kwargs["timezone"] = tzinfo
            trigger = DateTrigger(**trigger_kwargs)
        case "interval":
            if weeks is not None:
                trigger_kwargs["weeks"] = weeks
            if days is not None:
                trigger_kwargs["days"] = days
            if hours is not None:
                trigger_kwargs["hours"] = hours
            if minutes is not None:
                trigger_kwargs["minutes"] = minutes
            if seconds is not None:
                trigger_kwargs["seconds"] = seconds

            trigger = IntervalTrigger(**trigger_kwargs)
        case "cron":
            if year is not None:
                trigger_kwargs["year"] = year
            if month is not None:
                trigger_kwargs["month"] = month
            if week is not None:
                trigger_kwargs["week"] = week
            if day is not None:
                trigger_kwargs["day"] = day
            if day_of_week is not None:
                trigger_kwargs["day_of_week"] = (
                    int(day_of_week) if day_of_week.isnumeric() else day_of_week
                )
            if hour is not None:
                trigger_kwargs["hour"] = hour
            if minute is not None:
                trigger_kwargs["minute"] = minute
            if second is not None:
                trigger_kwargs["second"] = second
            if start_date is not None:
                trigger_kwargs["start_date"] = parse_date(start_date, tzinfo=tzinfo)
            if end_date is not None:
                trigger_kwargs["end_date"] = parse_date(end_date, tzinfo=tzinfo)
            if timezone is not None:
                trigger_kwargs["timezone"] = tzinfo
            trigger = CronTrigger(**trigger_kwargs)
        case _:
            raise click.BadOptionUsage("trigger", "unknown trigger type", ctx)

    if jobstore is not None:
        job_kwargs["jobstore"] = jobstore
    if trigger is not None:
        job_kwargs["trigger"] = trigger
    if id_ is not None:
        job_kwargs["id"] = id_
    if name is not None:
        job_kwargs["name"] = name
    if args != ():  # type: ignore[comparison-overlap]
        job_kwargs["args"] = args
    if kwargs != {}:
        job_kwargs["kwargs"] = kwargs
    if coalesce is not None:
        job_kwargs["coalesce"] = coalesce
    if replace_existing is not None:
        job_kwargs["replace_existing"] = replace_existing
    if executor is not None:
        job_kwargs["executor"] = executor
    if misfire_grace_time is not None:
        job_kwargs["misfire_grace_time"] = misfire_grace_time
    if max_instances is not None:
        job_kwargs["max_instances"] = max_instances
    if next_run_time is not None:
        tzinfo = timezone(AppConfig().get("settings", "timezone"))
        job_kwargs["next_run_time"] = parse_date(next_run_time, tzinfo=tzinfo)

    try:
        job: Job = scheduler.add_job(**job_kwargs)
        rprint(f"Added job:")
        rprint(_job_info(job, show_jobstore=True))
    except LookupError as error:
        rprint(f"{error}")


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-i",
    "--job-id",
    type=click.STRING,
    required=True,
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.pass_context
def get_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    job: Job | None = scheduler.get_job(job_id=job_id, jobstore=jobstore)
    if not job:
        rprint("[dimmed]Job not found")
        return
    rprint(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def print_jobs(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()

    jobstore_table = Table(
        box=box.HORIZONTALS,
        show_edge=False,
        show_lines=False,
        show_header=False,
        show_footer=False,
        padding=(0, 0),
        pad_edge=False,
        highlight=True,
    )
    jobstore_table.add_column(
        ratio=1,
        justify="left",
        no_wrap=False,
        overflow="fold",
    )
    jobstore_table.add_column(
        ratio=3,
        justify="left",
        no_wrap=False,
        overflow="fold",
    )

    jobstore = None
    with scheduler._jobstores_lock:
        if scheduler.state == STATE_STOPPED:
            jobstore_table.add_row("[b][u]Pending jobs")
            if scheduler._pending_jobs:
                for job, jobstore_alias, replace_existing in scheduler._pending_jobs:
                    if jobstore in (None, jobstore_alias):
                        # fmt: off
                        jobstore_table.add_row("jobstore:", f"{job._jobstore_alias}")
                        jobstore_table.add_row("id:", f"{job.id}")
                        jobstore_table.add_row("name:", f"{job.name}")
                        jobstore_table.add_row("trigger:", f"{job.trigger!r}")
                        jobstore_table.add_row("next_run_time:", f"{job.next_run_time}")
                        jobstore_table.add_row("executor:", f"{job.executor}")
                        jobstore_table.add_row("replace_existing:", f"{replace_existing}")
                        jobstore_table.add_row("args:", f"{job.args!r}")
                        jobstore_table.add_row("kwargs:", f"{job.kwargs!r}")
                        jobstore_table.add_row("coalesce:", f"{job.coalesce!r}")
                        jobstore_table.add_row("misfire_grace_time:", f"{job.misfire_grace_time!r}")
                        jobstore_table.add_row("max_instances:", f"{job.max_instances!r}")
                        jobstore_table.add_row("func_ref:", f"{job.func_ref}", end_section=True)
                        # fmt: on
            else:
                jobstore_table.add_row("[dimmed]No pending jobs")
        else:
            for alias, store in sorted(six.iteritems(scheduler._jobstores)):
                if jobstore in (None, alias):
                    jobstore_table.add_row("[b][u]Jobstore %s" % alias)
                    jobs: t.Sequence[Job] = store.get_all_jobs()
                    if not jobs:
                        jobstore_table.add_row("[dimmed]No scheduled jobs")
                        continue
                    for job in jobs:
                        # fmt: off
                        jobstore_table.add_row("id:", f"{job.id}")
                        jobstore_table.add_row("name:", f"{job.name}")
                        jobstore_table.add_row("trigger:", f"{job.trigger!r}")
                        jobstore_table.add_row("next_run_time:", f"{job.next_run_time}")
                        jobstore_table.add_row("executor:", f"{job.executor}")
                        jobstore_table.add_row("args:", f"{job.args!r}")
                        jobstore_table.add_row("kwargs:", f"{job.kwargs!r}")
                        jobstore_table.add_row("coalesce:", f"{job.coalesce!r}")
                        jobstore_table.add_row("misfire_grace_time:", f"{job.misfire_grace_time!r}")
                        jobstore_table.add_row("max_instances:", f"{job.max_instances!r}")
                        jobstore_table.add_row("func_ref:", f"{job.func_ref}", end_section=True)
                        # fmt: on

    rprint(jobstore_table)


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-i",
    "--job-id",
    type=click.STRING,
    required=True,
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.option(
    "--id",
    "id_",
    type=click.STRING,
    help="the unique identifier of this job",
)
@click.option(
    "--name",
    type=click.STRING,
    help="the description of this job",
)
@click.option(
    "--args",
    cls=shell_complete.LiteralEvalOption,
    type=tuple[t.Any],
    default="()",
    help="positional arguments to the callable",
)
@click.option(
    "--kwargs",
    cls=shell_complete.LiteralEvalOption,
    default="{}",
    type=dict,
    help="keyword arguments to the callable",
)
@click.option(
    "--coalesce",
    type=click.BOOL,
    shell_complete=shell_complete.Param("coalesce").bool,
    help="whether to only run the job once when several run times are due",
)
@click.option(
    "--executor",
    shell_complete=available_executors,
    type=click.STRING,
    help="the name of the executor that will run this job",
)
@click.option(
    "--misfire_grace_time",
    type=click.INT,
    help="the time (in seconds) how much this job's execution is allowed to",
)
@click.option(
    "--max_instances",
    type=click.INT,
    help="the maximum number of concurrently executing instances allowed for this",
)
@click.option(
    "--next_run_time",
    type=click.STRING,
    help="the next scheduled run time of this job",
)
@click.pass_context
def modify_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
    id_: str,
    name: str,
    args: tuple[t.Any | None],
    kwargs: dict[str, t.Any],
    coalesce: bool,
    executor: str,
    misfire_grace_time: int,
    max_instances: int,
    next_run_time: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    job_modify_kwargs: dict[str, t.Any] = {}

    if id_ is not None:
        job_modify_kwargs["id"] = id_
    if name is not None:
        job_modify_kwargs["name"] = name
    if args != ():  # type: ignore[comparison-overlap]
        job_modify_kwargs["args"] = args
    if kwargs != {}:
        job_modify_kwargs["kwargs"] = kwargs
    if coalesce is not None:
        job_modify_kwargs["coalesce"] = coalesce
    if executor is not None:
        job_modify_kwargs["executor"] = executor
    if misfire_grace_time is not None:
        job_modify_kwargs["misfire_grace_time"] = misfire_grace_time
    if max_instances is not None:
        job_modify_kwargs["max_instances"] = max_instances
    if next_run_time is not None:
        tzinfo = timezone(AppConfig().get("settings", "timezone"))
        job_modify_kwargs["next_run_time"] = parse_date(next_run_time, tzinfo=tzinfo)

    job: Job = scheduler.modify_job(
        job_id=job_id, jobstore=jobstore, **job_modify_kwargs
    )
    rprint(f"Modified job:")
    rprint(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-i",
    "--job-id",
    type=click.STRING,
    required=True,
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.pass_context
def pause_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    job: Job = scheduler.pause_job(job_id=job_id, jobstore=jobstore)
    rprint(f"Paused job:")
    rprint(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.argument("jobstore", type=click.STRING, shell_complete=available_jobstores)
@click.pass_context
def remove_all_jobs(ctx: click.Context, jobstore: str) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    scheduler.remove_all_jobs(jobstore=jobstore)
    rprint(f"Removed all jobs from jobstore `{jobstore}`")


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-i",
    "--job-id",
    type=click.STRING,
    required=True,
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.pass_context
def remove_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    try:
        scheduler.remove_job(job_id=job_id, jobstore=jobstore)
        rprint(f"Removed job `{job_id}` from jobstore `{jobstore}`")
    except JobLookupError as error:
        rprint(f"{error}")


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-i",
    "--job-id",
    type=click.STRING,
    required=True,
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.option(
    "--trigger",
    type=click.Choice(["date", "interval", "cron"]),
    help="type of apscheduler.triggers",
    required=True,
)
@click.option(
    "--run_date",
    type=click.STRING,
    help="triggers: [DateTrigger], the date/time to run the job at",
)
@click.option(
    "--weeks",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of weeks to wait",
)
@click.option(
    "--days",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of days to wait",
)
@click.option(
    "--hours",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of hours to wait",
)
@click.option(
    "--minutes",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of minutes to wait",
)
@click.option(
    "--seconds",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of seconds to wait",
)
@click.option(
    "--year",
    type=click.INT,
    help="triggers: [CronTrigger], 4-digit year",
)
@click.option(
    "--month",
    type=click.INT,
    help="triggers: [CronTrigger], month (1-12)",
)
@click.option(
    "--week",
    type=click.INT,
    help="triggers: [CronTrigger], day of month (1-31)",
)
@click.option(
    "--day",
    type=click.INT,
    help="triggers: [CronTrigger], ISO week (1-53)",
)
@click.option(
    "--day_of_week",
    type=click.STRING,
    help="triggers: [CronTrigger], number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun)",
)
@click.option(
    "--hour",
    type=click.INT,
    help="triggers: [CronTrigger], hour (0-23)",
)
@click.option(
    "--minute",
    type=click.INT,
    help="triggers: [CronTrigger], minute (0-59)",
)
@click.option(
    "--second",
    type=click.INT,
    help="triggers: [CronTrigger], second (0-59)",
)
@click.option(
    "--start_date",
    type=click.STRING,
    help="triggers: [CronTrigger], earliest possible date/time to trigger on (inclusive)",
)
@click.option(
    "--end_date",
    type=click.STRING,
    help="triggers: [CronTrigger], latest possible date/time to trigger on (inclusive)",
)
@click.pass_context
def reschedule_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
    trigger: str,
    run_date: str,
    weeks: int,
    days: int,
    hours: int,
    minutes: int,
    seconds: int,
    year: int,
    month: int,
    week: int,
    day: int,
    day_of_week: str,
    hour: int,
    minute: int,
    second: int,
    start_date: str,
    end_date: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    tzinfo = timezone(AppConfig().get("settings", "timezone"))

    trigger_kwargs: dict[str, t.Any] = {}

    match trigger:
        case "date":
            if run_date is not None:
                trigger_kwargs["run_date"] = parse_date(run_date, tzinfo=tzinfo)
            if timezone is not None:
                trigger_kwargs["timezone"] = tzinfo
            trigger = DateTrigger(**trigger_kwargs)
        case "interval":
            if weeks is not None:
                trigger_kwargs["weeks"] = weeks
            if days is not None:
                trigger_kwargs["days"] = days
            if hours is not None:
                trigger_kwargs["hours"] = hours
            if minutes is not None:
                trigger_kwargs["minutes"] = minutes
            if seconds is not None:
                trigger_kwargs["seconds"] = seconds

            trigger = IntervalTrigger(**trigger_kwargs)
        case "cron":
            if year is not None:
                trigger_kwargs["year"] = year
            if month is not None:
                trigger_kwargs["month"] = month
            if week is not None:
                trigger_kwargs["week"] = week
            if day is not None:
                trigger_kwargs["day"] = day
            if day_of_week is not None:
                trigger_kwargs["day_of_week"] = (
                    int(day_of_week) if day_of_week.isnumeric() else day_of_week
                )
            if hour is not None:
                trigger_kwargs["hour"] = hour
            if minute is not None:
                trigger_kwargs["minute"] = minute
            if second is not None:
                trigger_kwargs["second"] = second
            if start_date is not None:
                trigger_kwargs["start_date"] = parse_date(start_date, tzinfo=tzinfo)
            if end_date is not None:
                trigger_kwargs["end_date"] = parse_date(end_date, tzinfo=tzinfo)
            if timezone is not None:
                trigger_kwargs["timezone"] = tzinfo
            trigger = CronTrigger(**trigger_kwargs)
        case _:
            raise click.BadOptionUsage("trigger", "unknown trigger type", ctx)

    job: Job = scheduler.reschedule_job(
        job_id=job_id, jobstore=jobstore, trigger=trigger
    )
    rprint(f"Rescheduled job:")
    rprint(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-i",
    "--job-id",
    type=click.STRING,
    required=True,
)
@click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
@click.pass_context
def resume_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    job: Job = scheduler.resume_job(job_id=job_id, jobstore=jobstore)
    rprint(f"Resumed job:")
    rprint(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def shutdown(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    if scheduler.state == STATE_STOPPED:
        rprint("[dimmed]Scheduler already stopped")
    else:
        scheduler.shutdown()
        rprint("Scheduler shutdown")


@click.command(cls=FormattedCommand)
@utils._handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def start(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
    if scheduler.state == STATE_RUNNING:
        rprint("[dimmed]Scheduler already running")
    else:
        scheduler.start()
        rprint("[b][green]Scheduler started")


def _job_info(job: Job, show_jobstore: bool = False) -> Table:
    job_table = Table(
        box=box.HORIZONTALS,
        show_edge=False,
        show_lines=False,
        show_header=False,
        show_footer=False,
        padding=(0, 0),
        pad_edge=False,
        highlight=True,
    )
    job_table.add_column(
        ratio=1,
        justify="left",
        no_wrap=False,
        overflow="fold",
    )
    job_table.add_column(
        ratio=3,
        justify="left",
        no_wrap=False,
        overflow="fold",
    )
    if show_jobstore:
        job_table.add_row("jobstore:", f"{job._jobstore_alias}")
    job_table.add_row("id:", f"{job.id}")
    job_table.add_row("name:", f"{job.name}")
    job_table.add_row("trigger:", f"{job.trigger!r}")
    job_table.add_row("next_run_time:", f"{job.next_run_time}")
    job_table.add_row("executor:", f"{job.executor}")
    job_table.add_row("args:", f"{job.args!r}")
    job_table.add_row("kwargs:", f"{job.kwargs!r}")
    job_table.add_row("coalesce:", f"{job.coalesce!r}")
    job_table.add_row("misfire_grace_time:", f"{job.misfire_grace_time!r}")
    job_table.add_row("max_instances:", f"{job.max_instances!r}")
    job_table.add_row("func_ref:", f"{job.func_ref}", end_section=True)

    return job_table
