import typing as t
from datetime import datetime, timedelta
from decimal import Decimal

import rich_click as click
from rich.console import Console

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import _pass, dates, validate
from lightlike.app.core import FmtRichCommand
from lightlike.internal import utils

__all__: t.Sequence[str] = ("date_parse", "date_diff")


@click.command(
    cls=FmtRichCommand,
    name="date-parse",
    short_help="Date parser function.",
)
@utils._handle_keyboard_interrupt()
@click.option(
    "-d",
    "--date",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@_pass.console
def date_parse(console: Console, date: str) -> None:
    """
    Test the dateparser function.

    DATE/TIME FIELDS:
        arguments/options asking for datetime will attempt to parse the string provided.
        error will raise if unable to parse.
        dates are relative to today, unless explicitly stated in the string.

        Example values to pass to the date parser:
        | type             | examples                                                  |
        |-----------------:|-----------------------------------------------------------|
        | datetime         | jan1@2pm [d](January 1st current year at 2:00 PM)[/d]            |
        | date (relative)  | today/now, yesterday, monday, 2 days ago, -2d | "\-2d"    |
        | time (relative)  | -15m [d](15 minutes ago)[/d], 1.25 hrs ago, -1.25hr | "\-1.25hr" |
        | date             | jan1, 01/01, 2024-01-01                                   |
        | time             | 2pm, 14:30:00, 2:30pm                                     |

        [b]Note:[/b] If the date is an argument, the minus operator needs to be escaped.
        e.g.
        ```
        $ command --option -2d
        $ c -o-2d
        $ command \-2d # argument
        $ c \-2d # argument
        ```
    """
    console.print(date)


@click.command(
    cls=FmtRichCommand,
    name="date-diff",
    short_help="Diff between 2 times.",
    no_args_is_help=True,
)
@utils._handle_keyboard_interrupt()
@click.argument(
    "date_start",
    type=click.STRING,
    callback=validate.callbacks.datetime_parsed,
)
@click.argument(
    "date_end",
    type=click.STRING,
    callback=validate.callbacks.datetime_parsed,
)
@click.argument(
    "paused_hours",
    type=click.FLOAT,
    required=False,
    default=0,
)
@_pass.console
def date_diff(
    console: Console,
    date_start: datetime,
    date_end: datetime,
    paused_hours: float,
) -> None:
    duration = date_end - date_start
    time_parts = dates.seconds_to_time_parts(Decimal(paused_hours or 0) * 3600)
    paused_hours, paused_minutes, paused_seconds = time_parts
    duration = (date_end - date_start) - timedelta(
        hours=paused_hours,
        minutes=paused_minutes,
        seconds=paused_seconds,
    )
    hours = round(Decimal(duration.total_seconds()) / Decimal(3600), 4)
    console.print("Duration:", duration)
    console.print("Hours:", hours)
