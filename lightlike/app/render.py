from datetime import date, datetime, time, timedelta
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Never, Sequence

from rich import box, get_console
from rich.console import Console
from rich.status import Status
from rich.table import Table

from lightlike import _console

if TYPE_CHECKING:
    from _collections_abc import dict_values
    from google.cloud.bigquery.table import RowIterator


__all__: Sequence[str] = (
    "cli_info",
    "query_start_render",
    "mappings_list_to_rich_table",
    "row_iter_to_rich_table",
    "new_console_print",
    "new_table",
    "map_cell_style",
    "_map_s_column_type",
    "_map_s_column_field",
)


def cli_info() -> None:
    from lightlike.__about__ import __appdir__, __appname_sc__, __version__

    console = _console.get_console()
    console.log(
        "[repr.attrib_name]__appname__[/repr.attrib_name]"
        "[repr.attrib_equal]=[/repr.attrib_equal]"
        f"[repr.attrib_value]{__appname_sc__}"
    )
    console.log(
        "[repr.attrib_name]__version__[/repr.attrib_name]"
        "[repr.attrib_equal]=[/repr.attrib_equal]"
        f"[repr.attrib_value]{__version__}"
    )
    console.log(
        "[repr.attrib_name]__appdir__[/repr.attrib_name]"
        "[repr.attrib_equal]=[/repr.attrib_equal]"
        f"[repr.attrib_value]{__appdir__.as_posix()}"
    )
    console.set_window_title(__appname_sc__)

    if console.width >= 150:
        width = f"[b][green]{console.width}[/b][/green]"
    else:
        width = f"[b][red]{console.width}[/b][/red]"

    if console.height >= 40:
        height = f"[b][green]{console.height}[/b][/green]"
    else:
        height = f"[b][red]{console.height}[/b][/red]"

    console.log(
        "[repr.attrib_name]Console[/repr.attrib_name]"
        "[repr.attrib_equal]=[/repr.attrib_equal]"
        f"<console width={width} height={height} {console._color_system!s}>"
    )

    if console.width < 150:
        console.log(f"[d][yellow]Recommended console width </ 150")

    if console.height < 40:
        console.log(f"[d][yellow]Recommended console height </ 40")


def query_start_render(console: Console, query_config: dict[str, bool]) -> None:
    console.clear()

    table = Table(
        show_edge=False,
        show_header=False,
        border_style="",
        show_lines=False,
        row_styles=[""],
        box=box.SIMPLE_HEAD,
        padding=(1, 1, 1, 1),
    )

    general = [
        "[b][#6b90f7]BigQuery Shell[/b][/#6b90f7]",
        "Submit: [code]esc[/code]+[code]enter[/code]",
        "Exit: [code]ctrl[/code]+[code]Q[/code]",
    ]

    query = []
    for name, value in query_config.items():
        setting = f"{name.replace('_', ' ').capitalize()}: "
        setting += (
            "[b][green]on[/b][/green]" if value is True else "[b][red]off[/b][/red]"
        )
        query.append(setting)

    for _ in range(8):
        table.add_column(justify="center", ratio=2)

    table.add_row(*general, *query)
    console.print(table)


def mappings_list_to_rich_table(
    mappings_list: list[dict[str, Any]],
    table_kwargs: Mapping[str, Any] = {},
    column_kwargs: Mapping[str, Any] = {},
    row_kwargs: Mapping[str, Any] = {},
) -> Table:
    table = new_table(table_kwargs)
    reduce(
        lambda n, c: table.add_column(c[0], **_map_s_column_type(c), **column_kwargs),
        mappings_list[0].items(),
        None,
    )
    reduce(
        lambda n, r: table.add_row(*map_cell_style(r.values()), **row_kwargs),
        mappings_list,
        None,
    )
    return table


def new_table(table_kwargs: Mapping[str, Any] = {}) -> Table:
    default = {
        "box": box.MARKDOWN,
        "border_style": "bold",
        "show_header": True,
        "show_edge": True,
    }
    default.update(table_kwargs)
    return Table(**default)  # type: ignore[arg-type]


def new_console_print(
    *renderables,
    svg_path: Path | None = None,
    text_path: Path | None = None,
    status: Status | None = None,
    console_kwargs: Mapping[str, Any] = {},
    print_kwargs: Mapping[str, Any] = {},
) -> None:
    with Console(record=True, **console_kwargs) as console:
        console.print(*renderables, style=_console.CONSOLE_CONFIG.style, **print_kwargs)

        if svg_path is not None:
            uri = svg_path.resolve().as_uri()
            path = svg_path.resolve().as_posix()
            get_console().log(f"Saved to [link={uri}][repr.url]{path}[/repr.url].")
            console.save_svg(path, code_format=_console._CONSOLE_SVG_FORMAT)

        if text_path is not None:
            uri = text_path.resolve().as_uri()
            path = text_path.resolve().as_posix()
            get_console().log(f"Saved to [link={uri}][repr.url]{path}[/repr.url].")
            console.save_text(path)

        if status:
            status.stop()


def row_iter_to_rich_table(
    row_iterator: "RowIterator",
    table_kwargs: Mapping[str, Any] = {},
    column_kwargs: Mapping[str, Any] = {},
    row_kwargs: Mapping[str, Any] = {},
) -> Table:
    table = new_table(table_kwargs)
    reduce(
        lambda n, c: table.add_column(
            c._properties["name"],
            **_map_s_column_field(c, **column_kwargs),
        ),
        row_iterator.schema,
        None,
    )
    reduce(
        lambda n, r: table.add_row(*map_cell_style(r.values()), **row_kwargs),
        list(row_iterator),
        None,
    )
    return table


def map_cell_style(values: "dict_values[str, Any]") -> map:
    display_values: list[Any] = []
    for value in values:
        if not value or value in ("null", "None"):
            display_values.append(f"[#888888]{value}")
            continue
        if isinstance(value, datetime):
            display_values.append(value.replace(tzinfo=None))
            continue
        display_values.append(value)

    return map(str, display_values)


def _map_s_column_type(items: Sequence[Any], no_color: bool = False) -> dict[str, Any]:
    _kwargs: dict[str, Any] = dict(vertical="top")

    if items[0] == "id":
        _kwargs |= dict(
            overflow="crop",
            min_width=7,
            max_width=7,
        )
    elif items[0] == "note":
        if get_console().width >= 150:
            _kwargs |= dict(
                overflow="fold",
                min_width=40,
                max_width=40,
            )
        elif get_console().width < 150:
            _kwargs |= dict(
                overflow="ellipsis",
                no_wrap=True,
                min_width=25,
                max_width=25,
            )
    elif items[0] == "project":
        if get_console().width >= 150:
            _kwargs |= dict(
                overflow="fold",
                min_width=20,
                max_width=20,
            )
        elif get_console().width <= 120:
            _kwargs |= dict(
                overflow="ellipsis",
                no_wrap=True,
                min_width=10,
                max_width=10,
            )

    if isinstance(items[1], bool):
        _kwargs |= dict(justify="left")
        if not no_color:
            _kwargs |= dict(header_style="not bold red")
        if get_console().width < 150:
            _kwargs |= dict(
                overflow="ignore",
                min_width=1,
                max_width=1,
            )
    elif isinstance(items[1], (int, float)):
        _kwargs |= dict(
            justify="right",
            overflow="crop",
            min_width=8,
        )
        if not no_color:
            _kwargs |= dict(header_style="not bold cyan")
    elif isinstance(items[1], str):
        _kwargs |= dict(
            justify="left",
        )
        if not no_color:
            _kwargs |= dict(header_style="not bold green")
    elif isinstance(items[1], (date, datetime, time, timedelta)):
        _kwargs |= dict(justify="left", overflow="crop")
        if not no_color:
            _kwargs |= dict(header_style="not bold yellow")
        if isinstance(items[1], datetime):
            _kwargs |= dict(min_width=19, max_width=19)
        elif isinstance(items[1], (time, timedelta)):
            _kwargs |= dict(min_width=8, max_width=8)
        elif isinstance(items[1], date):
            _kwargs |= dict(min_width=10, max_width=10)
    else:
        _kwargs |= dict(justify="center")

    return _kwargs


def _map_s_column_field(field: Any, **override) -> dict[str, Any]:
    _kwargs: dict[str, Any] = dict(vertical="top")

    if field._properties["name"] == "id":
        _kwargs |= dict(
            overflow="crop",
            min_width=7,
            max_width=7,
        )
    elif field._properties["name"] == "note":
        if get_console().width >= 150:
            _kwargs |= dict(
                overflow="fold",
                min_width=40,
                max_width=40,
            )
        elif get_console().width < 150:
            _kwargs |= dict(
                overflow="ellipsis",
                no_wrap=True,
                min_width=25,
                max_width=25,
            )
    elif field._properties["name"] == "notes":
        if get_console().width >= 150:
            _kwargs |= dict(
                overflow="fold",
                max_width=60,
            )
    elif field._properties["name"] == "project":
        if get_console().width >= 150:
            _kwargs |= dict(
                overflow="fold",
                min_width=20,
                max_width=20,
            )
        elif get_console().width <= 120:
            _kwargs |= dict(
                overflow="ellipsis",
                no_wrap=True,
                min_width=10,
                max_width=10,
            )

    if field._properties["type"].startswith("BOOL"):
        _kwargs |= dict(
            justify="left",
            header_style="not bold red",
        )
        if get_console().width < 150:
            _kwargs |= dict(
                overflow="ignore",
                min_width=1,
                max_width=1,
            )
    elif field._properties["type"] in ("NUMERIC", "INTEGER", "FLOAT"):
        _kwargs |= dict(
            justify="right",
            overflow="crop",
            header_style="not bold cyan",
            min_width=8,
        )
    elif field._properties["type"] == "STRING":
        _kwargs |= dict(
            justify="left",
            header_style="not bold green",
        )
    elif field._properties["type"].startswith("DATETIME") or field._properties[
        "type"
    ].startswith("TIMESTAMP"):
        _kwargs |= dict(
            justify="left",
            header_style="not bold yellow",
            overflow="crop",
            min_width=19,
        )
    elif field._properties["type"] == "DATE":
        _kwargs |= dict(
            justify="left",
            header_style="not bold yellow",
            overflow="crop",
            min_width=10,
        )
    elif field._properties["type"] == "TIME":
        _kwargs |= dict(
            justify="left",
            header_style="not bold yellow",
            overflow="crop",
            min_width=8,
        )
    else:
        _kwargs |= dict(justify="center")

    _kwargs.update(override)
    return _kwargs


def never(arg: Any) -> Never: ...  # type: ignore[empty-body]


# from inspect import cleandoc
# from rich.highlighter import ReprHighlighter
# from rich.layout import Layout
# from rich.padding import Padding
# from rich.panel import Panel
# from rich.pretty import Pretty
# from rich.text import Text
# def console_start_render(console: Console, locals: dict[str, Any]) -> None:
#     scope = {
#         "__appname__": locals.get("__appname_sc__"),
#         "__version__": locals.get("__version__"),
#         "__appdir__": locals.get("__appdir__"),
#         "__lock__": locals.get("__lock__"),
#         "cli": locals.get("cli"),
#         "console": locals.get("console"),
#         "client": locals.get("client"),
#         "app": locals.get("app"),
#         "bq": locals.get("bq"),
#         "project": locals.get("project"),
#         "report": locals.get("report"),
#         "timer": locals.get("timer"),
#     }

#     def info_panel() -> Panel:
#         completer_keys = "[ [code]ctrl[/code] + ]{ [code]F1[/code] | [code]F2[/code] | [code]F3[/code] }"
#         builtin_commands = " [b]|[/b] ".join(
#             [
#                 "[code.command]cd[/code.command]",
#                 "[code.command]ls[/code.command]",
#                 "[code.command]tree[/code.command]",
#             ]
#         )

#         return Panel(
#             cleandoc(
#                 f"""
#                 GENERAL:
#                     ▸ [code]ctrl[/code] + [code]space[/code] [b]|[/b] [code]tab[/code] to display commands/autocomplete.
#                     ▸ [code]ctrl[/code] + [code]Q[/code] [b]|[/b] cmd [code.command]app[/code.command]:[code.command]exit[/code.command] to exit.
#                     ▸ {completer_keys} to cycle between autocompleters.
#                       ( [code]F1[/code] = Commands | [code]F2[/code] = History | [code]F3[/code] = Path )

#                 HELP:
#                     ▸ Add help flag to command/group \[[code.lflag]--help[/code.lflag], [code.sflag]-h[/code.sflag]].

#                 SYSTEM COMMANDS:
#                     ▸ Type cmd and press [code]escape[/code] + [code]enter[/code].
#                     ▸ To enable system prompt, press [code]meta[/code] + [code]shift[/code] + [code]1[/code] and enter cmd.
#                     ▸ Built-in system commands: {builtin_commands}

#                 """
#             ),
#             title="[link=https://github.com/ayvi-0001/lightlike_cli][b][i][purple]Lightlike CLI",
#             box=box.SIMPLE_HEAD,
#         )

#     if console.width < 150:
#         from rich.align import Align

#         console.clear()
#         panel = Panel(Align.center(info_panel()), border_style="bold #9146ff")
#         console.print(Padding(panel, (1, 0, 1, 0)))
#     else:
#         sort_keys: bool = False
#         highlighter = ReprHighlighter()
#         items_table = Table.grid(padding=(0, 1), expand=False)
#         items_table.add_column(justify="right")

#         def sort_items(item: tuple[str, Any]) -> tuple[bool, str]:
#             """Sort special variables first, then alphabetically."""
#             key, _ = item
#             return (not key.startswith("__"), key.lower())

#         items = sorted(scope.items(), key=sort_items) if sort_keys else scope.items()
#         for key, value in items:
#             key_text = Text.assemble(
#                 (key, "scope.key.special" if key.startswith("__") else "scope.key"),
#                 (" =", "scope.equals"),
#             )
#             items_table.add_row(
#                 key_text,
#                 Pretty(
#                     value,
#                     highlighter=highlighter,
#                     indent_guides=True,
#                     max_length=None,
#                     max_string=None,
#                 ),
#             )

#         locals_scope = Panel(
#             items_table,
#             title="[b][i][#9146ff]locals",
#             box=box.SIMPLE_HEAD,
#             padding=(0, 1),
#         )

#         layout = Layout()
#         layout.split_row(
#             Layout(info_panel(), name="start"),
#             Layout(locals_scope, name="scope"),
#         )

#         panel = Panel.fit(layout, border_style="bold #9146ff")

#         console.clear()
#         _console.reconfigure(height=15)
#         console.print(Padding(panel, (1, 0, 1, 0)))
#         _console.reconfigure(height=None)
