import typing as t

import click
import rich

from lightlike.app.core import LazyAliasedGroup

if t.TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

__all__: t.Sequence[str] = ("scheduler",)

STATE_STOPPED = 0


@click.group(
    name="scheduler",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "add-job": "lightlike.cmd.scheduler.commands:add_job",
        "get-job": "lightlike.cmd.scheduler.commands:get_job",
        "modify-job ": "lightlike.cmd.scheduler.commands:modify_job",
        "pause-job": "lightlike.cmd.scheduler.commands:pause_job",
        "pause": "lightlike.cmd.scheduler.commands:pause",
        "print-jobs": "lightlike.cmd.scheduler.commands:print_jobs",
        "remove-all-jobs": "lightlike.cmd.scheduler.commands:remove_all_jobs",
        "remove-job": "lightlike.cmd.scheduler.commands:remove_job",
        "reschedule-job": "lightlike.cmd.scheduler.commands:reschedule_job",
        "resume-job": "lightlike.cmd.scheduler.commands:resume_job",
        "resume": "lightlike.cmd.scheduler.commands:resume",
        "shutdown": "lightlike.cmd.scheduler.commands:shutdown",
        "start": "lightlike.cmd.scheduler.commands:start",
        "status": "lightlike.cmd.scheduler.commands:status",
        "system-command": "lightlike.cmd.scheduler.commands:system_command",
    },
    short_help="Apscheduler commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
@click.pass_context
def scheduler(ctx: click.Context, debug: bool) -> None:
    if ctx.invoked_subcommand in {
        "add-job",
        "get-job",
        "modify-job ",
        "pause-job",
        "remove-all-jobs",
        "remove-job",
        "reschedule-job",
        "resume-job",
        "system-command",
    }:
        scheduler: BackgroundScheduler = ctx.obj["get_scheduler"]()
        if scheduler.state == STATE_STOPPED:
            rich.print(
                "[dimmed]Scheduler is stopped.",
                "Use scheduler:start before running command.",
            )
            raise click.exceptions.Exit
