import typing as t
from os import getenv

import click

from lightlike.app.core import LazyAliasedGroup

__all__: t.Sequence[str] = ("app",)


lazy_subcommands: dict[str, str] = {
    "config": "lightlike.cmd.app.commands:config",
    "date-diff": "lightlike.cmd.app.commands:date_diff",
    "dir": "lightlike.cmd.app.commands:dir_",
    "inspect-console": "lightlike.cmd.app.commands:inspect_console",
    "parse-date": "lightlike.cmd.app.commands:parse_date",
    "run-bq": "lightlike.cmd.app.commands:run_bq",
    "source-dir": "lightlike.cmd.app.commands:source_dir",
    "sync": "lightlike.cmd.app.commands:sync",
}

if getenv("LIGHTLIKE_CLI_DEV"):
    lazy_subcommands["reset"] = "lightlike.cmd.app.commands:_reset"


@click.group(
    name="app",
    cls=LazyAliasedGroup,
    lazy_subcommands=lazy_subcommands,
    short_help="Cli internal settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def app(debug: bool) -> None:
    """Cli internal settings & commands."""
