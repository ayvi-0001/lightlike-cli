import typing as t

import click

from lightlike.app.core import LazyAliasedGroup


@click.group(
    name="summary",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "table": "lightlike.cmd.summary.commands.summary_table",
        "csv": "lightlike.cmd.summary.commands.summary_csv",
        "json": "lightlike.cmd.summary.commands.summary_json",
    },
    short_help="View & Save a summary timesheet.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def summary(debug: bool) -> None:
    """View & Save a summary timesheet."""


__all__: t.Sequence[str] = ("summary",)
