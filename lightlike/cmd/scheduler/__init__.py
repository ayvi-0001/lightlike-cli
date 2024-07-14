import typing as t

import click

from lightlike.app.core import LazyAliasedGroup

__all__: t.Sequence[str] = ("scheduler",)


@click.group(
    name="scheduler",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "add_job": "lightlike.cmd.scheduler.commands:add_job",
        "get_job": "lightlike.cmd.scheduler.commands:get_job",
        "print_jobs": "lightlike.cmd.scheduler.commands:print_jobs",
        "modify_job ": "lightlike.cmd.scheduler.commands:modify_job",
        "pause_job": "lightlike.cmd.scheduler.commands:pause_job",
        "remove_all_jobs": "lightlike.cmd.scheduler.commands:remove_all_jobs",
        "remove_job": "lightlike.cmd.scheduler.commands:remove_job",
        "reschedule_job": "lightlike.cmd.scheduler.commands:reschedule_job",
        "resume_job": "lightlike.cmd.scheduler.commands:resume_job",
        "start": "lightlike.cmd.scheduler.commands:start",
        "shutdown": "lightlike.cmd.scheduler.commands:shutdown",
    },
    short_help="Apscheduler commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def scheduler(debug: bool) -> None: ...
