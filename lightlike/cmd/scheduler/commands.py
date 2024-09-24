import os
import subprocess
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
from prompt_toolkit import prompt
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from pytz import timezone
from rich import box, get_console, print
from rich.table import Table

from lightlike.__about__ import __appname_sc__
from lightlike.app import shell_complete
from lightlike.app._repl import _prepend_exec_to_cmd
from lightlike.app.config import AppConfig
from lightlike.app.core import FormattedCommand
from lightlike.app.dates import parse_date
from lightlike.internal import appdir, constant, utils

if t.TYPE_CHECKING:
    from datetime import _TzInfo

__all__: t.Sequence[str] = (
    "add_job",
    "get_job",
    "modify_job",
    "pause_job",
    "pause",
    "print_jobs",
    "remove_all_jobs",
    "remove_job",
    "reschedule_job",
    "resume_job",
    "resume",
    "run",
    "shutdown",
    "start",
    "status",
    "system_command",
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
        config = rtoml.load(appdir.SCHEDULER_CONFIG)
        for k, v in config["jobs"].get("functions", {}).items():
            completions.append(CompletionItem(value=k, help=str(v)))

    return completions


def available_jobstores(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completions = []

    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    for k, v in scheduler._jobstores.items():
        completions.append(CompletionItem(value=k, help=f"{v!r}"))

    return completions


def available_executors(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completions = []

    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    for k, v in scheduler._executors.items():
        completions.append(CompletionItem(value=k, help=f"{v!r}"))

    return completions


option_func = click.option(
    "--func",
    required=True,
    shell_complete=available_functions,
    type=click.STRING,
    help="callable (or a textual reference to one in the package.module:some.object format) to run at the given time",
)
option_jobstore = click.option(
    "-j",
    "--jobstore",
    type=click.STRING,
    required=True,
    show_default=True,
    shell_complete=available_jobstores,
)
option_job_id = click.option(
    "-i",
    "--job-id",
    "job_id",
    type=click.STRING,
    help="the unique identifier of this job",
)
option_id = click.option(
    "--id",
    "id_",
    type=click.STRING,
    help="the unique identifier of this job",
)
option_name = click.option(
    "--name",
    type=click.STRING,
    help="the description of this job",
)
option_args = click.option(
    "--args",
    cls=shell_complete.LiteralEvalOption,
    type=tuple[t.Any],
    default="()",
    help="positional arguments to the callable",
)
option_kwargs = click.option(
    "--kwargs",
    cls=shell_complete.LiteralEvalOption,
    default="{}",
    type=dict,
    help="keyword arguments to the callable",
)
option_coalesce = click.option(
    "--coalesce",
    type=click.BOOL,
    shell_complete=shell_complete.Param("coalesce").bool,
    help="whether to only run the job once when several run times are due",
)
option_replace_existing = click.option(
    "--replace-existing",
    type=click.BOOL,
    shell_complete=shell_complete.Param("replace-existing").bool,
    help="True to replace an existing job with the same id (but retain the number of runs from the existing one)",
)
option_executor = click.option(
    "--executor",
    shell_complete=available_executors,
    type=click.STRING,
    help="the name of the executor that will run this job",
)
option_misfire_grace_time = click.option(
    "--misfire-grace-time",
    type=click.INT,
    help="the time (in seconds) how much this job's execution is allowed to",
)
option_max_instances = click.option(
    "--max-instances",
    type=click.INT,
    help="the maximum number of concurrently executing instances allowed for this",
)
option_next_run_time = click.option(
    "--next-run-time",
    type=click.STRING,
    help="the next scheduled run time of this job",
)
option_trigger = click.option(
    "--trigger",
    type=click.Choice(["date", "interval", "cron"]),
    help="type of apscheduler.triggers",
    required=True,
)
option_run_date = click.option(
    "--run-date",
    type=click.STRING,
    help="triggers: [DateTrigger], the date/time to run the job at",
)
option_weeks = click.option(
    "--weeks",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of weeks to wait",
)
option_days = click.option(
    "--days",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of days to wait",
)
option_hours = click.option(
    "--hours",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of hours to wait",
)
option_minutes = click.option(
    "--minutes",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of minutes to wait",
)
option_seconds = click.option(
    "--seconds",
    type=click.INT,
    help="triggers: [IntervalTrigger], number of seconds to wait",
)
option_year = click.option(
    "--year",
    type=click.STRING,
    help="triggers: [CronTrigger], 4-digit year",
)
option_month = click.option(
    "--month",
    type=click.STRING,
    help="triggers: [CronTrigger], month (1-12)",
)
option_week = click.option(
    "--week",
    type=click.STRING,
    help="triggers: [CronTrigger], day of month (1-31)",
)
option_day = click.option(
    "--day",
    type=click.STRING,
    help="triggers: [CronTrigger], ISO week (1-53)",
)
option_day_of_week = click.option(
    "--day-of-week",
    type=click.STRING,
    help="triggers: [CronTrigger], number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun)",
)
option_hour = click.option(
    "--hour",
    type=click.STRING,
    help="triggers: [CronTrigger], hour (0-23)",
)
option_minute = click.option(
    "--minute",
    type=click.STRING,
    help="triggers: [CronTrigger], minute (0-59)",
)
option_second = click.option(
    "--second",
    type=click.STRING,
    help="triggers: [CronTrigger], second (0-59)",
)
option_start_date = click.option(
    "--start-date",
    type=click.STRING,
    help="triggers: [CronTrigger], earliest possible date/time to trigger on (inclusive)",
)
option_end_date = click.option(
    "--end-date",
    type=click.STRING,
    help="triggers: [CronTrigger], latest possible date/time to trigger on (inclusive)",
)


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_func
@option_jobstore
@option_job_id
@option_name
@option_args
@option_kwargs
@option_coalesce
@option_replace_existing
@option_executor
@option_misfire_grace_time
@option_max_instances
@option_next_run_time
@option_trigger
@option_run_date
@option_weeks
@option_days
@option_hours
@option_minutes
@option_seconds
@option_year
@option_month
@option_week
@option_day
@option_day_of_week
@option_hour
@option_minute
@option_second
@option_start_date
@option_end_date
@click.pass_context
def add_job(
    ctx: click.Context,
    func: str,
    jobstore: str,
    job_id: str,
    name: str,
    args: tuple[t.Any],
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
    year: str,
    month: str,
    week: str,
    day: str,
    day_of_week: str,
    hour: str,
    minute: str,
    second: str,
    start_date: str,
    end_date: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    tzinfo = AppConfig().tzinfo

    job_kwargs: dict[str, t.Any] = {}
    if appdir.SCHEDULER_CONFIG.exists():
        config = rtoml.load(appdir.SCHEDULER_CONFIG)
        job_kwargs["func"] = config["jobs"].get("functions", {}).get(func, func)
    else:
        job_kwargs["func"] = func

    # fmt: off
    job_kwargs["trigger"] = _match_trigger(
        ctx, trigger, run_date, weeks, days, hours,
        minutes, seconds, year, month, week, day, day_of_week,
        hour, minute, second, start_date, end_date, tzinfo,
    )
    # fmt: on
    if jobstore is not None:
        job_kwargs["jobstore"] = jobstore
    if job_id is not None:
        job_kwargs["id"] = job_id
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
        tzinfo = AppConfig().tzinfo
        job_kwargs["next_run_time"] = parse_date(next_run_time, tzinfo=tzinfo)

    try:
        job: Job = scheduler.add_job(**job_kwargs)
        print(f"Added job:")
        print(_job_info(job, show_jobstore=True))
    except LookupError as error:
        print(f"{error}")


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_job_id
@option_jobstore
@click.pass_context
def get_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    job: Job | None = scheduler.get_job(job_id=job_id, jobstore=jobstore)
    if not job:
        print("[dimmed]Job not found")
        return
    print(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def print_jobs(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()

    jobstore_table = Table(
        box=box.HORIZONTALS,
        show_edge=False,
        show_lines=False,
        show_header=False,
        show_footer=False,
        padding=(0, 0),
        pad_edge=False,
        highlight=True,
        expand=False,
    )
    jobstore_table.add_column(
        ratio=1,
        justify="left",
        no_wrap=False,
        overflow="fold",
    )
    jobstore_table.add_column(
        ratio=2,
        justify="left",
        no_wrap=False,
        overflow="fold",
        min_width=3,
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
            jobstore_table.add_row("[b]Pending jobs")
            if scheduler._pending_jobs:
                for idx, (job, jobstore_alias, replace_existing) in enumerate(
                    scheduler._pending_jobs
                ):
                    if jobstore in (None, jobstore_alias):
                        jobstore_table.add_row(f"\[{idx + 1}] {job.id}", "", f"{job!s}")
            else:
                jobstore_table.add_row("[dimmed]No pending jobs")
        else:
            for alias, store in sorted(six.iteritems(scheduler._jobstores)):
                if jobstore in (None, alias):
                    jobstore_table.add_row("[b]Jobstore %s" % alias)
                    jobs: t.Sequence[Job] = store.get_all_jobs()
                    if not jobs:
                        jobstore_table.add_row("[dimmed]No scheduled jobs")
                        continue
                    for idx, (job) in enumerate(jobs):
                        jobstore_table.add_row(f"\[{idx + 1}] {job.id}", "", f"{job!s}")

    print(jobstore_table)


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_job_id
@option_jobstore
@option_id
@option_name
@option_args
@option_kwargs
@option_coalesce
@option_executor
@option_misfire_grace_time
@option_max_instances
@option_next_run_time
@click.pass_context
def modify_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
    id_: str,
    name: str,
    args: tuple[t.Any],
    kwargs: dict[str, t.Any],
    coalesce: bool,
    executor: str,
    misfire_grace_time: int,
    max_instances: int,
    next_run_time: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
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
        tzinfo = AppConfig().tzinfo
        job_modify_kwargs["next_run_time"] = parse_date(next_run_time, tzinfo=tzinfo)

    job: Job = scheduler.modify_job(
        job_id=job_id, jobstore=jobstore, **job_modify_kwargs
    )
    print(f"Modified job:")
    print(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_job_id
@option_jobstore
@click.pass_context
def pause_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    job: Job = scheduler.pause_job(job_id=job_id, jobstore=jobstore)
    print(f"Paused job:")
    print(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.argument("jobstore", type=click.STRING, shell_complete=available_jobstores)
@click.pass_context
def remove_all_jobs(ctx: click.Context, jobstore: str) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    scheduler.remove_all_jobs(jobstore=jobstore)
    print(f"Removed all jobs from jobstore `{jobstore}`")


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_job_id
@option_jobstore
@click.pass_context
def remove_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    try:
        scheduler.remove_job(job_id=job_id, jobstore=jobstore)
        print(f"Removed job `{job_id}` from jobstore `{jobstore}`")
    except JobLookupError as error:
        print(f"{error}")


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_job_id
@option_jobstore
@option_trigger
@option_run_date
@option_weeks
@option_days
@option_hours
@option_minutes
@option_seconds
@option_year
@option_month
@option_week
@option_day
@option_day_of_week
@option_hour
@option_minute
@option_second
@option_start_date
@option_end_date
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
    year: str,
    month: str,
    week: str,
    day: str,
    day_of_week: str,
    hour: str,
    minute: str,
    second: str,
    start_date: str,
    end_date: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    tzinfo = AppConfig().tzinfo

    # fmt: off
    trigger = _match_trigger(
        ctx, trigger, run_date, weeks, days, hours,
        minutes, seconds, year, month, week, day, day_of_week,
        hour, minute, second, start_date, end_date, tzinfo,
    )
    # fmt: on

    job: Job = scheduler.reschedule_job(
        job_id=job_id, jobstore=jobstore, trigger=trigger
    )
    print(f"Rescheduled job:")
    print(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@option_job_id
@option_jobstore
@click.pass_context
def resume_job(
    ctx: click.Context,
    job_id: str,
    jobstore: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    job: Job = scheduler.resume_job(job_id=job_id, jobstore=jobstore)
    print(f"Resumed job:")
    print(_job_info(job, show_jobstore=True))


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def shutdown(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    if scheduler.state == STATE_STOPPED:
        print("[dimmed]Scheduler already stopped")
    else:
        scheduler.shutdown()


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def start(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    if scheduler.state == STATE_RUNNING:
        print("[dimmed]Scheduler already running")
    else:
        scheduler.start()


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def pause(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    if scheduler.state == STATE_PAUSED:
        print("[dimmed]Scheduler already paused")
    else:
        scheduler.pause()


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def resume(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    if scheduler.state == STATE_RUNNING:
        print("[dimmed]Scheduler already running")
    else:
        scheduler.resume()


@click.command(cls=FormattedCommand)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.pass_context
def status(ctx: click.Context) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()
    if scheduler.state == STATE_RUNNING:
        print("Scheduler is running.")
    else:
        print("Scheduler is shutdown.")


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


def run(*args: t.Any, **kwargs: t.Any) -> None:
    console = get_console()

    result = subprocess.run(*args, **kwargs)

    message: str = "Completed Process: `%s` | returncode=%s" % (
        r"\n".join(result.args.splitlines()),
        result.returncode,
    )

    with patch_stdout(raw=True):
        if result.stdout:
            message += " | STDOUT:"
            console.log(message)
            console.print(result.stdout)
        elif result.stderr:
            message += " | STDERR:"
            console.log(message)
            console.print(result.stderr)
        else:
            console.log(message)


@click.command(cls=FormattedCommand, name="system-command")
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option("--command")
@click.option("--command-multiline", is_flag=True)
@option_jobstore
@option_job_id
@option_args
@option_kwargs
@option_coalesce
@option_replace_existing
@option_executor
@option_misfire_grace_time
@option_max_instances
@option_next_run_time
@option_trigger
@option_run_date
@option_weeks
@option_days
@option_hours
@option_minutes
@option_seconds
@option_year
@option_month
@option_week
@option_day
@option_day_of_week
@option_hour
@option_minute
@option_second
@option_start_date
@option_end_date
@click.pass_context
def system_command(
    ctx: click.Context,
    command: str,
    command_multiline: bool,
    jobstore: str,
    job_id: str,
    args: tuple[t.Any],
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
    year: str,
    month: str,
    week: str,
    day: str,
    day_of_week: str,
    hour: str,
    minute: str,
    second: str,
    start_date: str,
    end_date: str,
) -> None:
    scheduler: BackgroundScheduler = ctx.find_root().obj["get_scheduler"]()

    tzinfo = AppConfig().tzinfo

    if command_multiline:
        style: Style = Style.from_dict(rtoml.load(constant.PROMPT_STYLE))
        _CMD = prompt(message="", multiline=True, style=style)
        _name = _CMD
        _CMD = _prepend_exec_to_cmd(
            _CMD, lambda: AppConfig().get("system-command", "shell", default="")
        )
    else:
        _CMD = command
        _name = command
        _CMD = _prepend_exec_to_cmd(
            _CMD, lambda: AppConfig().get("system-command", "shell", default="")
        )

    if not _CMD:
        ctx.fail("Must specify command.")

    func = f"{__name__}:run"

    job_kwargs: dict[str, t.Any] = {}

    func_kwargs = {
        "args": _CMD,
        "capture_output": True,
        "env": os.environ,
        "shell": True,
        "text": True,
    }
    func_kwargs |= kwargs

    job_kwargs["args"] = args
    job_kwargs["kwargs"] = func_kwargs
    job_kwargs["func"] = func
    job_kwargs["name"] = r"\n".join(_name.splitlines())
    job_kwargs["jobstore"] = jobstore
    # fmt: off
    job_kwargs["trigger"] = _match_trigger(
        ctx, trigger, run_date, weeks, days, hours,
        minutes, seconds, year, month, week, day, day_of_week,
        hour, minute, second, start_date, end_date, tzinfo,
    )
    # fmt: on
    if job_id is not None:
        job_kwargs["id"] = job_id
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
        tzinfo = AppConfig().tzinfo
        job_kwargs["next_run_time"] = parse_date(next_run_time, tzinfo=tzinfo)

    try:
        job: Job = scheduler.add_job(**job_kwargs)
        print(f"Added job:")
        print(_job_info(job, show_jobstore=True))
    except LookupError as error:
        print(f"{error}")


def _match_trigger(
    ctx: click.Context,
    trigger: str,
    run_date: str,
    weeks: int,
    days: int,
    hours: int,
    minutes: int,
    seconds: int,
    year: str,
    month: str,
    week: str,
    day: str,
    day_of_week: str,
    hour: str,
    minute: str,
    second: str,
    start_date: str,
    end_date: str,
    tzinfo: "_TzInfo",
) -> DateTrigger | IntervalTrigger | CronTrigger:
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

    return trigger
