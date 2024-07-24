import typing as t

import click

from lightlike.app.core import LazyAliasedGroup

__all__: t.Sequence[str] = ("summary",)


@click.group(
    name="summary",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "csv": "lightlike.cmd.timer.summary.commands:summary_csv",
        "json": "lightlike.cmd.timer.summary.commands:summary_json",
        "table": "lightlike.cmd.timer.summary.commands:summary_table",
    },
    short_help="View & Save a summary timesheet.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def summary(debug: bool) -> None:
    """View & Save a summary timesheet."""
