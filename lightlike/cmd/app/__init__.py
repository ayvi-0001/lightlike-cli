import typing as t
from os import getenv

import click

from lightlike.app.core import LazyAliasedGroup

lazy_subcommands: dict[str, str] = {
    "config": "lightlike.cmd.app.commands:config",
    "dir": "lightlike.cmd.app.commands:dir_",
    "run-bq": "lightlike.cmd.app.commands:run_bq",
    "inspect-console": "lightlike.cmd.app.commands:inspect_console",
    "sync": "lightlike.cmd.app.commands:sync",
    "test": "lightlike.cmd.app.commands:test",
    "scheduler": "lightlike.cmd.scheduler:scheduler",
}

if getenv("LIGHTLIKE_CLI_DEV"):
    lazy_subcommands["reset-all"] = "lightlike.cmd.app.commands:_reset_all"


@click.group(
    name="app",
    cls=LazyAliasedGroup,
    lazy_subcommands=lazy_subcommands,
    short_help="Cli internal settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def app(debug: bool) -> None:
    """Cli internal settings & commands."""


__all__: t.Sequence[str] = ("app",)
