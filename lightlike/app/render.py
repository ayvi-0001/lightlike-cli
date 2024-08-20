import typing as t
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import reduce
from os import getenv

from more_itertools import one
from rich import box, get_console
from rich import print as rprint
from rich.table import Table
from rich.text import Text

from lightlike.__about__ import __appdir__, __appname_sc__, __config__, __version__
from lightlike.app.config import AppConfig
from lightlike.internal import appdir, markup

if t.TYPE_CHECKING:
    from _collections_abc import dict_items, dict_values


__all__: t.Sequence[str] = (
    "cli_info",
    "query_start_render",
    "map_sequence_to_rich_table",
    "map_cell_style",
    "map_column_style",
    "create_table_diff",
    "create_row_diff",
)


def cli_info() -> None:
    console = get_console()
    if AppConfig().get("settings", "update-terminal-title", default=True):
        console.set_window_title(__appname_sc__)

    console.log(f"__appname__[b][red]=[/red][repr.str]{__appname_sc__}")
    console.log(f"__version__[b][red]=[/red][repr.number]{__version__}")
    console.log(f"__config__[b][red]=[/red][repr.path]{__config__.as_posix()}")

    if LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"):
        console.log(
            f"__appdir__[b red]=[/][repr.path]/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli"
        )
    else:
        console.log(f"__appdir__[b][red]=[/][repr.path]{__appdir__.as_posix()}")

    width = (
        f"[b][green]{console.width}[/]"
        if console.width >= 140
        else f"[b][red]{console.width}[/]"
    )
    height = (
        f"[b][green]{console.height}[/]"
        if console.height >= 40
        else f"[b][red]{console.height}[/]"
    )

    console.log(
        f"console_width[b][red]=[/]{width}",
        "[dim][red](recommended width </ 140)" if console.width < 140 else "",
    )
    console.log(
        f"console_height[b][red]=[/]{height}",
        "[dim][red](recommended height </ 40)" if console.height < 40 else "",
    )


def query_start_render(
    query_config: dict[str, bool],
    timestamp: str,
    print_output_dir: bool = False,
) -> None:
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
        Text.assemble("Submit: ", markup.code("esc enter")),
        Text.assemble("Exit: ", markup.code("ctrl q")),
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

    if print_output_dir:
        appdir.QUERIES.mkdir(exist_ok=True)
        _dest = appdir.QUERIES.joinpath(timestamp).resolve()
        _dest.mkdir(exist_ok=True)
        uri = _dest.as_uri()

        if LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"):
            uri = f"{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli/queries/{timestamp}"
            rprint(f" Queries saved to: [repr.url][link={uri}]{uri}")
        else:
            rprint(f" Queries saved to: [repr.url][link={uri}]{uri}")


def map_sequence_to_rich_table(
    mappings: list[dict[str, t.Any]],
    string_ctype: list[str] | None = None,
    bool_ctype: list[str] | None = None,
    num_ctype: list[str] | None = None,
    datetime_ctype: list[str] | None = None,
    time_ctype: list[str] | None = None,
    date_ctype: list[str] | None = None,
    exclude_fields: list[str] | None = None,
    row_kwargs: t.Mapping[str, t.Any] | None = None,
    table_kwargs: t.Mapping[str, t.Any] | None = None,
    column_kwargs: t.Mapping[str, t.Any] | None = None,
    no_color: bool = False,
) -> Table:
    default = {
        "box": box.MARKDOWN,
        "border_style": "bold",
        "show_header": True,
        "show_edge": True,
    }
    default.update(table_kwargs or {})
    table: Table = Table(**default)  # type: ignore[arg-type]
    console_width: int = get_console().width

    if exclude_fields:
        reduced: list[dict[str, t.Any]] = []
        for row in mappings:
            reduced_row = {}
            for k, v in row.items():
                if k not in exclude_fields:
                    reduced_row[k] = v
            reduced.append(reduced_row)
        mappings = reduced

    first_row: dict[str, t.Any] | None = None

    with suppress(IndexError):
        first_row = mappings[0]

    if first_row is None:
        items = t.cast("dict_items[str, t.Any]", ())
    else:
        items = first_row.items()

    if not no_color:
        fn = lambda c: map_column_style(
            items=c,
            string_ctype=string_ctype or [],
            bool_ctype=bool_ctype or [],
            num_ctype=num_ctype or [],
            datetime_ctype=datetime_ctype or [],
            time_ctype=time_ctype or [],
            date_ctype=date_ctype or [],
            console_width=console_width,
            no_color=False,
        )
    else:
        fn = lambda c: {}

    # fmt: off
    reduce(
        lambda n, c: table.add_column(c[0], **fn(c), **column_kwargs or {}),
        filter(lambda c: c[0] not in (exclude_fields or []), items),
        None,
    )
    reduce(
        lambda n, r: table.add_row(*map_cell_style(r.values()), **row_kwargs or {}),
        mappings,
        None,
    )
    # fmt: on
    return table


def map_cell_style(values: "dict_values[str, t.Any]") -> "map":  # type: ignore
    display_values: list[t.Any] = []
    for value in values:
        if not value or value in ("null", "None"):
            display_values.append(markup.dimmed(value).markup)
        else:
            display_values.append(value)
    return map(str, display_values)


def map_column_style(
    items: t.Sequence[t.Any],
    string_ctype: list[str] = [],
    bool_ctype: list[str] = [],
    num_ctype: list[str] = [],
    datetime_ctype: list[str] = [],
    time_ctype: list[str] = [],
    date_ctype: list[str] = [],
    console_width: int | None = None,
    no_color: bool = False,
) -> dict[str, t.Any]:
    kwargs: dict[str, t.Any] = dict(vertical="top")
    key = items[0]
    value = items[1] if items[1] != "null" else None

    if not console_width:
        console_width = get_console().width

    _datetime_types: list[str] = [*datetime_ctype, *date_ctype, *time_ctype]

    if key in bool_ctype or isinstance(value, bool):
        kwargs |= dict(
            justify="left",
        )
        if not no_color:
            kwargs |= dict(
                header_style="red",
            )
        if console_width <= 150:
            kwargs |= dict(
                overflow="ignore",
                max_width=1,
            )
    elif key in num_ctype or isinstance(value, (int, float, Decimal)):
        kwargs |= dict(
            justify="right",
            overflow="crop",
            min_width=8,
        )
        if not no_color:
            kwargs |= dict(
                header_style="cyan",
            )
    elif key in string_ctype or isinstance(value, str):
        kwargs |= dict(
            justify="left",
        )
        if not no_color:
            kwargs |= dict(
                header_style="green",
            )
    elif key in _datetime_types or isinstance(value, (date, datetime, time, timedelta)):
        kwargs |= dict(
            justify="left",
            overflow="crop",
            min_width=25,
        )
        if not no_color:
            kwargs |= dict(
                header_style="yellow",
            )
        if key in date_ctype or isinstance(value, date):
            kwargs |= dict(
                min_width=10,
            )
        elif key in time_ctype or isinstance(value, time):
            kwargs |= dict(
                min_width=8,
            )
    else:
        kwargs |= dict(
            justify="left",
            header_style="dim",
        )

    if items[0] == "row":
        kwargs |= dict(
            overflow="crop",
            min_width=3,
            ratio=1,
        )
    return kwargs


def create_table_diff(
    list_original: list[dict[str, t.Any]], list_new: list[dict[str, t.Any]]
) -> Table:
    final_table: Table = Table(
        box=box.MARKDOWN,
        border_style="bold",
        show_header=True,
        show_edge=True,
    )
    new_records: list[dict[str, t.Any]] = []
    console_width: int = get_console().width

    for original, new in zip(list_original, list_new):
        table: Table = Table(
            box=box.MARKDOWN,
            border_style="bold",
            show_header=True,
            show_edge=True,
        )

        new_record: dict[str, t.Any] = {}
        diff: dict[str, t.Any] = {}

        for k in original.keys():
            if k in new:
                diff[k] = new[k]

            if (diff.get(k) is None or diff.get(k) == 0) and diff.get(k) is not False:
                table.add_column(
                    k,
                    **map_column_style(
                        one({k: original[k]}.items()),
                        console_width=console_width,
                        no_color=True,
                    ),
                )
                new_record[k] = Text(f"{original[k]!s}").markup

            else:
                if f"{original[k]}" == f"{diff[k]}":
                    table.add_column(
                        k,
                        header_style="yellow",
                        **map_column_style(
                            one({k: diff[k]}.items()),
                            console_width=console_width,
                            no_color=True,
                        ),
                    )
                    new_record[k] = Text(f"{diff[k]!s}", style="yellow").markup
                else:
                    table.add_column(
                        k,
                        header_style="green",
                        **map_column_style(
                            one({k: diff[k]}.items()),
                            console_width=console_width,
                            no_color=True,
                        ),
                    )
                    new_record[k] = Text.assemble(
                        markup.sdr(original[k]), " ", markup.bg(diff[k])
                    ).markup

        new_records.append(new_record)
        final_table.columns = table.columns

    for record in new_records:
        final_table.add_row(*map_cell_style(record.values()))

    return final_table


def create_row_diff(original: dict[str, t.Any], new: dict[str, t.Any]) -> Table:
    table: Table = Table(
        box=box.MARKDOWN,
        border_style="bold",
        show_header=True,
        show_edge=True,
    )
    new_record: dict[str, t.Any] = {}
    diff: dict[str, t.Any] = {}
    console_width: int = get_console().width

    for k in original.keys():
        if k in new:
            diff[k] = new[k]

        if (diff.get(k) is None or diff.get(k) == 0) and diff.get(k) is not False:
            table.add_column(
                k,
                **map_column_style(
                    one({k: original[k]}.items()),
                    console_width=console_width,
                    no_color=True,
                ),
            )
            new_record[k] = Text(f"{original[k]!s}").markup

        else:
            if f"{original[k]}" == f"{diff[k]}":
                table.add_column(
                    k,
                    header_style="yellow",
                    **map_column_style(
                        one({k: diff[k]}.items()),
                        console_width=console_width,
                        no_color=True,
                    ),
                )
                new_record[k] = Text(f"{diff[k]!s}", style="yellow").markup
            else:
                table.add_column(
                    k,
                    header_style="green",
                    **map_column_style(
                        one({k: diff[k]}.items()),
                        console_width=console_width,
                        no_color=True,
                    ),
                )
                new_record[k] = Text.assemble(
                    markup.sdr(original[k]), " ", markup.bg(diff[k])
                ).markup

    table.add_row(*map_cell_style(new_record.values()))
    return table
