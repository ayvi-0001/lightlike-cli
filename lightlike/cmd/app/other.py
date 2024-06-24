import typing as t
from datetime import datetime
from types import ModuleType

import rich_click as click
from rich import box, get_console
from rich import print as rprint
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from lightlike.app.core import FmtRichCommand

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


def _eval_help(ctx: click.RichContext, param: click.Parameter, value: str) -> None:
    if not value or ctx.resilient_parsing:
        return

    rprint("This command simply runs the args passed to it through eval().")
    rprint("Some additional modules are imported to locals.\n")
    rprint(
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
            def eval_(args: list[str]) -> None:
                global EVAL_GLOBALS
                global EVAL_LOCALS
                try:
                    retval = eval(" ".join(args), EVAL_GLOBALS, EVAL_LOCALS)
                    if retval:
                        print(retval)
                except SyntaxError:
                    exec(" ".join(args), EVAL_GLOBALS, EVAL_LOCALS)
                    EVAL_LOCALS |= locals()\
            """,
            lexer="python",
            dedent=True,
            line_numbers=True,
            background_color="default",
        )
    )
    ctx.exit()


@click.command(
    cls=FmtRichCommand,
    name="eval",
    hidden=True,
)
@click.option(
    "-h",
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_eval_help,
)
@click.argument("args", nargs=-1, type=click.STRING)
def eval_(args: list[str]) -> None:
    def _execute_eval(args) -> None:
        global EVAL_GLOBALS
        global EVAL_LOCALS
        try:
            retval = eval(" ".join(args), EVAL_GLOBALS, EVAL_LOCALS)
            if retval:
                rprint(retval)
        except SyntaxError:
            exec(" ".join(args), EVAL_GLOBALS, EVAL_LOCALS)
            EVAL_LOCALS |= locals()
        finally:
            if "args" in EVAL_LOCALS:
                EVAL_LOCALS.pop("args")

    try:
        _execute_eval(args)
    except Exception:
        get_console().print_exception(
            max_frames=1,
            show_locals=True,
            word_wrap=True,
        )


@click.command(
    cls=FmtRichCommand,
    name="calendar",
    hidden=True,
    allow_name_alias=False,
)
@click.argument(
    "year",
    type=click.INT,
    default=datetime.now().year,
    required=False,
)
def calendar(year: int) -> None:
    import calendar

    from lightlike.app import dates
    from lightlike.app.config import AppConfig

    today = dates.now(AppConfig().tz)
    year = int(year)
    cal = calendar.Calendar()
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
                day_label = Text(str(day or ""), style="#f0f0ff")
                if index in (5, 6):
                    day_label.stylize("blue")
                if day and (day, month, year) == today_tuple:
                    day_label.stylize("on red")
                days.append(day_label)
            table.add_row(*days)

        tables.append(Align.center(table))

    Console().print(Padding(Columns(tables, equal=True), (1, 0, 0, 0)))


# import os
# from pathlib import Path
# from lightlike.app import shell_complete
# from lightlike.internal import markup, utils

# @click.command(
#     cls=FmtRichCommand,
#     name="ls",
#     hidden=True,
#     context_settings=dict(
#         allow_extra_args=True,
#         ignore_unknown_options=True,
#         help_option_names=[],
#     ),
# )
# @click.argument(
#     "path",
#     type=Path,
#     default=lambda: Path.cwd(),
#     shell_complete=shell_complete.path,
# )
# @utils._nl_start(before=True)
# def ls_(path: Path) -> None:
#     import shutil
#     from contextlib import suppress

#     try:
#         table_kwargs = dict(
#             header_style="#f0f0ff",
#             show_edge=False,
#             show_header=False,
#             box=box.SIMPLE_HEAD,
#         )

#         tables = []
#         for _path in path.iterdir():
#             table = Table(**table_kwargs)  # type: ignore
#             name = Text(_path.name)

#             if " " in name:
#                 name = Text(f"'{name}'")

#             is_link = False
#             if _path.is_symlink() or os.path.islink(_path):
#                 is_link = True
#             with suppress(OSError):
#                 _path.readlink()
#                 is_link = True

#             if not str(name).startswith("."):
#                 name.highlight_regex(r"\.(.*)$", "not bold not dim #f0f0ff")
#             elif _path.is_file():
#                 name.style = "#f0f0ff"
#             if is_link:
#                 name += "@"
#                 name.style = "bold #34e2e2"
#             elif _path.is_dir():
#                 name += "/"
#                 name.style = "bold #729fcf"
#             elif _path.is_socket():
#                 name += "="
#             # elif os.access(_path.resolve(), os.X_OK) or (
#             #     _path.stat().st_mode & stat.S_IXUSR
#             # ):
#             #     name += "*"
#             elif shutil.which(_path.resolve()):
#                 name += "*"
#                 name.style = "bold green"

#             name.highlight_regex(r"@|/|=|\*|\'", "not bold not dim #f0f0ff")
#             name.stylize(f"link {_path.resolve().as_uri()}")

#             table.add_row(name)
#             tables.append(table)

#         rprint(Columns(tables, equal=True))
#     except Exception as error:
#         rprint(f"{error!r}; {str(path.resolve())!r}")


# @click.command(
#     cls=FmtRichCommand,
#     name="tree",
#     hidden=True,
#     context_settings=dict(
#         allow_extra_args=True,
#         ignore_unknown_options=True,
#         help_option_names=[],
#     ),
# )
# @utils._handle_keyboard_interrupt(
#     callback=lambda: rprint(markup.dimmed("Aborted.")),
# )
# @click.argument(
#     "path",
#     type=Path,
#     default=lambda: Path.cwd(),
#     shell_complete=shell_complete.path,
# )
# @click.option(
#     "-s",
#     "--size",
#     type=click.BOOL,
#     shell_complete=shell_complete.Param("value").bool,
#     default=True,
# )
# def tree_(path: Path, size: bool) -> None:
#     from rich.filesize import decimal
#     from rich.markup import escape
#     from rich.tree import Tree

#     try:
#         with get_console().status(""):
#             directory = (path or Path.cwd()).resolve()
#             tree = Tree(
#                 f":open_file_folder: [repr.url][link={directory.as_uri()}]"
#                 f"{directory.as_posix()}",
#                 highlight=True,
#             )

#             def walk_directory(directory: Path, tree: Tree) -> None:
#                 paths = sorted(
#                     directory.iterdir(),
#                     key=lambda path: (path.is_file(), path.name.lower()),
#                 )
#                 for _path in paths:
#                     if _path.is_dir():
#                         style = "dim " if _path.name.startswith("__") else ""
#                         style += "#729fcf"
#                         branch = tree.add(
#                             f"[link={_path.resolve().as_uri()}]{escape(_path.name)}/",
#                             style=style,
#                             guide_style=style,
#                         )
#                         walk_directory(_path, branch)
#                     else:
#                         text_filename = Text(_path.name, "#f0f0ff")
#                         if not _path.name.startswith("."):
#                             text_filename.highlight_regex(r"\..*$", "red")
#                         text_filename.stylize(f"link {_path.resolve().as_uri()}")
#                         if size:
#                             text_filename.append(
#                                 f" ({decimal(_path.stat().st_size)})", "blue"
#                             )
#                         tree.add(text_filename)

#             walk_directory(directory, tree)
#             rprint(Padding(tree, (1, 0, 1, 0)))

#     except Exception as error:
#         rprint(f"{error!r}; {str(path.resolve())!r}")