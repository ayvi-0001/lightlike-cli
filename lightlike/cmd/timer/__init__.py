import typing as t

import click

from lightlike.app.core import LazyAliasedGroup


@click.group(
    name="timer",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "add": "lightlike.cmd.timer.commands:add",
        "delete": "lightlike.cmd.timer.commands:delete",
        "edit": "lightlike.cmd.timer.commands:edit",
        "get": "lightlike.cmd.timer.commands:get",
        "list": "lightlike.cmd.timer.commands:list_",
        "notes": "lightlike.cmd.timer.commands:notes",
        "pause": "lightlike.cmd.timer.commands:pause",
        "resume": "lightlike.cmd.timer.commands:resume",
        "run": "lightlike.cmd.timer.commands:run",
        "show": "lightlike.cmd.timer.commands:show",
        "stop": "lightlike.cmd.timer.commands:stop",
        "switch": "lightlike.cmd.timer.commands:switch",
        "update": "lightlike.cmd.timer.commands:update",
    },
    short_help="Run & manage time entries.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def timer(debug: bool) -> None:
    """Run & manage time entries."""


__all__: t.Sequence[str] = ("timer",)
