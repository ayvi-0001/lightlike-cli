import typing as t
from datetime import datetime

import click
import rtoml
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style
from rich import box
from rich import print as rprint
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from lightlike.app import dates
from lightlike.app.core import FormattedCommand
from lightlike.internal import constant, utils

__all__: t.Sequence[str] = ("eval", "calendar")


import decimal
import fractions
import math
import operator
import random
import statistics
import time

EVAL_GLOBALS = {
    "datetime": datetime,
    "decimal": decimal,
    "fractions": fractions,
    "math": math,
    "operator": operator,
    "random": random,
    "statistics": statistics,
    "time": time,
}
EVAL_LOCALS: dict[str, t.Any] = {}


def _eval_help(ctx: click.Context, param: click.Parameter, value: str) -> None:
    if not value or ctx.resilient_parsing:
        return

    rprint(
        "This command simply runs the args passed to it through eval(). "
        "Some additional modules are imported to locals.",
        "For multiline prompt, press escape enter to submit.",
        Syntax(
            code="""\
            EVAL_GLOBALS = {
                "decimal": decimal,
                "fractions": fractions,
                "math": math,
                "operator": operator,
                "random": random,
                "statistics": statistics,
                "time": time,
            }
            EVAL_LOCALS: dict[str, t.Any] = {}

            @click.command(name="eval", hidden=True)
            @click.argument("args", nargs=-1, type=click.STRING)
            @click.option("--multiline-prompt", is_flag=True)
            def eval_(args: list[str]) -> None:
                global EVAL_GLOBALS
                global EVAL_LOCALS
                try:
                    retval = eval(" ".join(args), EVAL_GLOBALS, EVAL_LOCALS)
                    print(retval)
                except SyntaxError:
                    exec(" ".join(args), EVAL_GLOBALS, EVAL_LOCALS)\
            """,
            lexer="python",
            dedent=True,
            line_numbers=True,
            background_color="default",
        ),
        sep="\n",
    )
    ctx.exit()


@click.command(
    cls=FormattedCommand,
    name="eval",
    hidden=True,
)
@utils.handle_keyboard_interrupt()
@utils.pretty_print_exception
@click.option(
    "-h",
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_eval_help,
)
@click.argument("args", nargs=-1, type=click.STRING)
@click.option("--multiline-prompt", is_flag=True)
def eval_(args: list[str], multiline_prompt: bool) -> None:
    def _execute_eval(eval_args: str) -> None:
        global EVAL_GLOBALS
        global EVAL_LOCALS
        try:
            retval = eval(eval_args, EVAL_GLOBALS, EVAL_LOCALS)
            rprint(retval)
        except SyntaxError:
            exec(eval_args, EVAL_GLOBALS, EVAL_LOCALS)
        finally:
            EVAL_LOCALS.pop("eval_args", None)

    if multiline_prompt:
        style: Style = Style.from_dict(rtoml.load(constant.PROMPT_STYLE))
        _execute_eval(prompt(message="", multiline=True, style=style))
    else:
        _execute_eval(" ".join(args))


@click.command(
    cls=FormattedCommand,
    name="calendar",
    hidden=True,
    allow_name_alias=False,
)
@click.option(
    "-y",
    "--year",
    type=click.INT,
    show_default=True,
    default=datetime.now().year,
    required=False,
)
@click.option(
    "-w",
    "--firstweekday",
    type=click.IntRange(0, 6),
    show_default=True,
    default=0,
    required=False,
    help="0 = Monday, 6 = Sunday",
)
@click.option(
    "--color-weekends",
    type=click.STRING,
    show_default=True,
    default=None,
)
@click.option(
    "--color-weekdays",
    type=click.STRING,
    show_default=True,
    default="#f0f0ff",
)
@click.option(
    "--color-today",
    type=click.STRING,
    show_default=True,
    default="on red",
)
def calendar(
    year: int,
    firstweekday: int,
    color_today: str | None,
    color_weekdays: str,
    color_weekends: str | None,
) -> None:
    import calendar

    from lightlike.app.config import AppConfig

    today = dates.now(AppConfig().tzinfo)
    year = int(year)
    cal = calendar.Calendar(firstweekday)
    today_tuple = today.day, today.month, today.year

    tables = []
    for month in range(1, 13):
        table = Table(
            title=f"{calendar.month_name[month]} {year}",
            title_style="bold #f0f0ff",
            box=box.SIMPLE_HEAVY,
            padding=0,
        )

        for week_day in cal.iterweekdays():
            header = "{:.3}".format(calendar.day_name[week_day])
            table.add_column(header, justify="right", style="#f0f0ff")

        month_days = cal.monthdayscalendar(year, month)
        for weekdays in month_days:
            days = []
            for index, day in enumerate(weekdays):
                day_label = Text(str(day or ""), style=color_weekdays)
                if index in (5, 6) and color_weekends:
                    day_label.stylize(color_weekends)
                if day and (day, month, year) == today_tuple:
                    day_label.stylize(color_today)
                days.append(day_label)
            table.add_row(*days)

        tables.append(Align.center(table))

    Console().print(Padding(Columns(tables, equal=True), (1, 0, 0, 0)))
