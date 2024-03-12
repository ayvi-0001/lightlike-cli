import calendar
import os
import shutil
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Sequence

import rich_click as click
from rich import box, get_console
from rich import print as rprint
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.filesize import decimal
from rich.markup import escape
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from lightlike.app import _pass, shell_complete
from lightlike.app.group import _RichCommand
from lightlike.cmd import _help
from lightlike.internal import utils

__all__: Sequence[str] = ("help_", "cd_", "ls_", "tree_", "calendar_", "calc_")


@click.command(name="help", short_help="Show help.", help=_help.general)
@_pass.console
@_pass.ctx_group(parents=1)
def help_(ctx_group: Sequence[click.Context], console: "Console") -> None:
    ctx, parent = ctx_group
    console.print(parent.get_help())


@click.command(
    cls=_RichCommand,
    name="cd",
    hidden=True,
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
@click.argument("path", type=Path, shell_complete=shell_complete.path)
def cd_(path: Path) -> None:
    if f"{path}" in ("~", "~/"):
        os.chdir(path.home())
    else:
        try:
            os.chdir(path.resolve())
        except FileNotFoundError as e:
            rprint(f"[b][red]FileNotFoundError:[/b][/red] {Path(str(e)).as_posix()}")
        except NotADirectoryError as e:
            rprint(f"[b][red]NotADirectoryError:[/b][/red] {Path(str(e)).as_posix()}")


@click.command(
    cls=_RichCommand,
    name="ls",
    hidden=True,
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
@click.argument(
    "path",
    type=Path,
    default=lambda: Path.cwd(),
    shell_complete=shell_complete.path,
)
@utils._nl_start(before=True)
def ls_(path: Path) -> None:
    table_kwargs = dict(
        header_style="#f0f0ff",
        show_edge=False,
        show_header=False,
        box=box.SIMPLE_HEAD,
    )

    tables = []
    for _path in path.iterdir():
        table = Table(**table_kwargs)  # type: ignore
        name = Text(_path.name)

        if " " in name:
            name = Text(f"'{name}'")

        is_link = False
        if _path.is_symlink() or os.path.islink(_path):
            is_link = True
        with suppress(OSError):
            _path.readlink()
            is_link = True

        if not str(name).startswith("."):
            name.highlight_regex(r"\.(.*)$", "not bold not dim #f0f0ff")
        elif _path.is_file():
            name.style = "#f0f0ff"
        if is_link:
            name += "@"
            name.style = "bold #34e2e2"
        elif _path.is_dir():
            name += "/"
            name.style = "bold #729fcf"
        elif _path.is_socket():
            name += "="
        # elif os.access(_path.resolve(), os.X_OK) or (
        #     _path.stat().st_mode & stat.S_IXUSR
        # ):
        #     name += "*"
        elif shutil.which(_path.resolve()):
            name += "*"
            name.style = "bold green"

        name.highlight_regex(r"@|/|=|\*|\'", "not bold not dim #f0f0ff")
        name.stylize(f"link {_path.resolve().as_uri()}")

        table.add_row(name)
        tables.append(table)

    rprint(Columns(tables, equal=True))


@click.command(
    cls=_RichCommand,
    name="tree",
    hidden=True,
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
@utils._handle_keyboard_interrupt(callback=lambda: rprint("[d]Aborted."))
@click.argument(
    "path",
    type=Path,
    default=lambda: Path.cwd(),
    shell_complete=shell_complete.path,
)
def tree_(path: Path) -> None:
    try:
        with get_console().status(""):
            directory = (path or Path.cwd()).resolve()
            tree = Tree(
                f":open_file_folder: [repr.url][link={directory.as_uri()}]"
                f"{directory.as_posix()}",
                highlight=True,
            )

            def walk_directory(directory: Path, tree: Tree) -> None:
                paths = sorted(
                    directory.iterdir(),
                    key=lambda path: (path.is_file(), path.name.lower()),
                )
                for _path in paths:
                    if _path.is_dir():
                        style = "dim " if _path.name.startswith("__") else ""
                        style += "#729fcf"
                        branch = tree.add(
                            f"[link={_path.resolve().as_uri()}]{escape(_path.name)}/",
                            style=style,
                            guide_style=style,
                        )
                        walk_directory(_path, branch)
                    else:
                        text_filename = Text(_path.name, "#f0f0ff")
                        if not _path.name.startswith("."):
                            text_filename.highlight_regex(r"\..*$", "red")
                        text_filename.stylize(f"link {_path.resolve().as_uri()}")
                        text_filename.append(
                            f" ({decimal(_path.stat().st_size)})", "blue"
                        )
                        tree.add(text_filename)

            walk_directory(directory, tree)
            rprint(Padding(tree, (1, 0, 1, 0)))

    except FileNotFoundError as e:
        rprint(f"[b][red]FileNotFoundError:[/b][/red] {Path(str(e)).as_posix()}")
    except NotADirectoryError as e:
        rprint(f"[b][red]NotADirectoryError:[/b][/red] {Path(str(e)).as_posix()}")


@click.command(cls=_RichCommand, name="calc", hidden=True)
@click.argument("args", nargs=-1, type=click.STRING, required=False)
@click.option("-h", "--help", is_flag=True)
def calc_(args: list[str], help: bool) -> None:
    if help:
        from rich.syntax import Syntax

        rprint("This command simply runs the args passed to it through eval().")
        rprint("Modules decimal/math/operator/time are in locals.\n")
        rprint(
            Syntax(
                code="""\
                @click.command(name="calc", hidden=True)
                @click.argument("args", nargs=-1, type=str, required=False)
                def calc(args: list[str]) -> None:
                    import decimal
                    import math
                    import operator
                    import time

                    print(eval(" ".join(args)))
                """,
                lexer="python",
                dedent=True,
                line_numbers=True,
                background_color="default",
            )
        )
        return

    if args:
        import decimal
        import math
        import operator
        import time

        try:
            rprint(eval(" ".join(args)))
        except Exception:
            get_console().print_exception(
                max_frames=1,
                show_locals=True,
                word_wrap=True,
            )


@click.command(cls=_RichCommand, name="cal", hidden=True)
@click.argument(
    "year",
    type=click.INT,
    default=datetime.now().year,
    required=False,
)
def calendar_(year: int) -> None:
    from lightlike.app.config import AppConfig

    today = AppConfig().now
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
