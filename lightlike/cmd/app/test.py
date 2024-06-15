import typing as t
from datetime import datetime, timedelta
from decimal import Decimal

import rich_click as click
from rich.console import Console

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import _pass, dates, validate
from lightlike.app.core import FmtRichCommand
from lightlike.cmd import _help
from lightlike.internal import utils

__all__: t.Sequence[str] = ("date_parse", "date_diff")


@click.command(
    cls=FmtRichCommand,
    name="date-parse",
    help=_help.app_test_dateparser,
    short_help="Date parser function.",
    syntax=_help.app_test_dateparser_syntax,
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
    hours = round(Decimal(duration.total_seconds()) / 3600, 4)
    console.print("Duration:", duration)
    console.print("Hours:", hours)
