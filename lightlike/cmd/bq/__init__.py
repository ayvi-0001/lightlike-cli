import typing as t

import rich_click as click

from lightlike.app.core import LazyAliasedRichGroup


@click.group(
    name="bq",
    cls=LazyAliasedRichGroup,
    lazy_subcommands={
        "snapshot": "lightlike.cmd.bq.commands.snapshot",
        "query": "lightlike.cmd.bq.commands.query",
        "init": "lightlike.cmd.bq.commands.init",
        "show": "lightlike.cmd.bq.commands.show",
        "projects": "lightlike.cmd.bq.commands.projects",
        "reset": "lightlike.cmd.bq.commands.reset",
    },
    short_help="BigQuery client settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def bq(debug: bool) -> None:
    """Command group for handling BigQuery Client configuration."""


__all__: t.Sequence[str] = ("bq",)
