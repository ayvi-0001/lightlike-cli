import typing as t

import click

from lightlike.app.core import LazyAliasedGroup

__all__: t.Sequence[str] = ("bq",)


@click.group(
    name="bq",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "init": "lightlike.cmd.bq.commands:init",
        "projects": "lightlike.cmd.bq.commands:projects",
        "query": "lightlike.cmd.bq.commands:query",
        "reset": "lightlike.cmd.bq.commands:reset",
        "run-build": "lightlike.cmd.bq.commands:run_bq_build",
        "show": "lightlike.cmd.bq.commands:show",
        "snapshot": "lightlike.cmd.bq.commands:snapshot",
    },
    short_help="BigQuery client settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def bq(debug: bool) -> None:
    """Command group for handling BigQuery Client configuration."""
