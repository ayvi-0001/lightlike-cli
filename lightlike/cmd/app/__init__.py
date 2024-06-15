import typing as t

import rich_click as click

from lightlike.app.core import LazyAliasedRichGroup


# Debug param exists but print statements have not been adding to functions yet.
# They will be added in the next udpate.
@click.group(
    name="app",
    cls=LazyAliasedRichGroup,
    lazy_subcommands={
        "config": "lightlike.cmd.app.commands.config",
        "dir": "lightlike.cmd.app.commands.dir_",
        "run-bq": "lightlike.cmd.app.commands.run_bq",
        "inspect-console": "lightlike.cmd.app.commands.inspect_console",
        "sync": "lightlike.cmd.app.commands.sync",
        "test": "lightlike.cmd.app.commands.test",
    },
    short_help="Cli internal settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def app(debug: bool) -> None:
    """Cli internal settings & commands."""


__all__: t.Sequence[str] = ("app",)
