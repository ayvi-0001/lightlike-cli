import re
from datetime import date, datetime, time, timedelta
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from more_itertools import one
from rich import box, get_console
from rich import print as rprint
from rich.console import Console
from rich.status import Status
from rich.table import Table
from rich.text import Text

from lightlike._console import _CONSOLE_SVG_FORMAT, CONSOLE_CONFIG, global_console_log
from lightlike.internal import markup

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
    "create_row_diff",
)


def cli_info() -> None:
    from lightlike.__about__ import __appdir__, __appname_sc__, __version__

    console = get_console()
    console.set_window_title(__appname_sc__)

    global_console_log(
        Text.assemble(
            markup.repr_attrib_name("__appname__"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(__appname_sc__),
        )
    )
    global_console_log(
        Text.assemble(
            markup.repr_attrib_name("__version__"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(__version__),
        )
    )
    global_console_log(
        Text.assemble(
            markup.repr_attrib_name("__appdir__"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(__appdir__.as_posix()),
        )
    )

    if console.width >= 150:
        width = markup.bg(console.width).markup
    else:
        width = markup.br(console.width).markup

    if console.height >= 40:
        height = markup.bg(console.height).markup
    else:
        height = markup.br(console.height).markup

    console_repr = (
        Text.assemble(
            markup.repr_attrib_name("Console"),
            markup.repr_attrib_equal(),
        ).markup
        + f"<console ConsoleDimensions(width={width} height={height}) {console._color_system!s}>"
    )

    global_console_log(console_repr)

    if console.width < 150:
        global_console_log(markup.dbr("Recommended console width </ 150"))

    if console.height < 35:
        global_console_log(markup.dbr("Recommended console height </ 35"))


def query_start_render(query_config: dict[str, bool]) -> None:
    table = Table(
        show_edge=False,
        show_header=False,
        border_style="",
        show_lines=False,
        row_styles=[""],
        box=box.SIMPLE_HEAD,
        padding=1,
    )

    general = [
        markup.pygments_keyword("BigQuery Shell"),
        Text.assemble(Text("Submit: ", end=""), markup.code_sequence("esc+enter", "+")),
        Text.assemble(Text("Exit: ", end=""), markup.code_sequence("ctrl+Q", "+")),
    ]

    query = []
    for name, value in query_config.items():
        setting = Text(f"{name.replace('_', ' ').capitalize()}: ")
        setting += markup.bg("on") if value is True else markup.br("off")
        query.append(setting)

    for _ in range(8):
        table.add_column(justify="center", ratio=2)

    table.add_row(*general, *query)
    rprint(table)


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
        console.print(*renderables, style=CONSOLE_CONFIG.style, **print_kwargs)

        if svg_path is not None:
            resolved = svg_path.resolve()
            uri = resolved.as_uri()
            path = resolved.as_posix()

            rprint(Text.assemble(Text("Saved to "), markup.link(path, uri), "."))
            console.save_svg(path, code_format=_CONSOLE_SVG_FORMAT)

        if text_path is not None:
            uri = text_path.resolve().as_uri()
            path = text_path.resolve().as_posix()
            rprint(Text.assemble(Text("Saved to "), markup.link(path, uri), "."))
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
            display_values.append(markup.dimmed(value).markup)
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

    if isinstance(items[1], bool):
        _kwargs |= dict(justify="left")
        if not no_color:
            _kwargs |= dict(header_style="red")
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
            _kwargs |= dict(header_style="cyan")
    elif isinstance(items[1], str):
        _kwargs |= dict(justify="left")
        if not no_color:
            _kwargs |= dict(header_style="green")
    elif isinstance(items[1], (date, datetime, time, timedelta)):
        _kwargs |= dict(justify="left", overflow="crop")
        if not no_color:
            _kwargs |= dict(header_style="yellow")
        if isinstance(items[1], datetime):
            _kwargs |= dict(min_width=19)
        elif isinstance(items[1], (time, timedelta)):
            _kwargs |= dict(min_width=8)
        elif isinstance(items[1], date):
            _kwargs |= dict(min_width=10)
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

    if field._properties["type"].startswith("BOOL"):
        _kwargs |= dict(
            justify="left",
            header_style="red",
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
            header_style="cyan",
            min_width=8,
        )
    elif field._properties["type"] == "STRING":
        _kwargs |= dict(
            justify="left",
            header_style="green",
        )
    elif field._properties["type"] in ("DATETIME", "TIMESTAMP"):
        _kwargs |= dict(
            justify="left",
            header_style="yellow",
            overflow="crop",
            min_width=19,
        )
    elif field._properties["type"] == "DATE":
        _kwargs |= dict(
            justify="left",
            header_style="yellow",
            overflow="crop",
            min_width=10,
        )
    elif field._properties["type"] == "TIME":
        _kwargs |= dict(
            justify="left",
            header_style="yellow",
            overflow="crop",
            min_width=8,
        )
    else:
        _kwargs |= dict(justify="center")

    _kwargs.update(override)
    return _kwargs


def create_row_diff(original: dict[str, Any], new: dict[str, Any]) -> Table:
    table = Table(
        box=box.MARKDOWN, border_style="bold", show_header=True, show_edge=True
    )

    new_record = {}
    diff = {}

    for k in original.keys():
        if k in new:
            diff[k] = new[k]

        if (diff.get(k) is None or diff.get(k) == 0) and diff.get(k) is not False:
            table.add_column(
                k,
                **_map_s_column_type(one({k: original[k]}.items()), no_color=True),
            )
            new_record[k] = Text(f"{original[k]!s}").markup

        else:
            if f"{original[k]}" == f"{diff[k]}":
                table.add_column(
                    k,
                    header_style="yellow",
                    **_map_s_column_type(one({k: diff[k]}.items()), no_color=True),
                )
                new_record[k] = Text(f"{diff[k]!s}", style="yellow").markup
            else:
                table.add_column(
                    k,
                    header_style="green",
                    **_map_s_column_type(one({k: diff[k]}.items()), no_color=True),
                )
                new_record[k] = Text.assemble(
                    markup.sdr(original[k]), " ", markup.bg(diff[k])
                ).markup

    table.add_row(*map_cell_style(new_record.values()))
    return table
