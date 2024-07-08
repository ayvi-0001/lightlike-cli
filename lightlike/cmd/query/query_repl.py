# mypy: disable-error-code="func-returns-value"

import typing as t
from datetime import datetime
from os import getenv

import click
import rtoml
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession
from prompt_toolkit.styles import Style
from rich import box, get_console
from rich.console import Console
from rich.filesize import decimal
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table

from lightlike._console import CONSOLE_CONFIG
from lightlike.app import _pass, cursor, render
from lightlike.app.config import AppConfig
from lightlike.app.routines import CliQueryRoutines
from lightlike.cmd.query.completers import query_repl_completer
from lightlike.cmd.query.key_bindings import QUERY_BINDINGS
from lightlike.cmd.query.lexer import BqSqlLexer
from lightlike.internal import appdir, constant, markup, utils
from lightlike.internal.constant import _CONSOLE_SVG_FORMAT

if t.TYPE_CHECKING:
    from google.cloud.bigquery import QueryJob
    from google.cloud.bigquery.table import RowIterator
    from prompt_toolkit.completion import Completer

    from lightlike.app.routines import CliQueryRoutines

__all__: t.Sequence[str] = ("query_repl", "_build_query_session")


@click.group(
    name="query",
    invoke_without_command=True,
    subcommand_metavar="",
    short_help="Start an interactive BQ shell.",
)
@_pass.console
@click.pass_context
def query_repl(ctx: click.Context, console: Console) -> None:
    """Start an interactive BQ shell."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(_run_query_repl, console=console)


def _run_query_repl(console: Console) -> None:
    query_settings = AppConfig().get("settings", "query")
    mouse_support: bool = query_settings.get("mouse_support", True)
    save_txt: bool = query_settings.get("save_txt", False)
    save_query_info: bool = query_settings.get("save_query_info", False)
    save_svg: bool = query_settings.get("save_svg", False)
    hide_table_render: bool = query_settings.get("hide_table_render", False)

    TS = f"{int(datetime.combine(datetime.today(), datetime.min.time()).timestamp())}"

    render.query_start_render(
        query_config=query_settings,
        timestamp=TS,
        print_output_dir=save_txt or save_svg,
    )

    with console.status(markup.status_message("Loading BigQuery Resources")):
        query_session = _build_query_session(
            completer=query_repl_completer(),
            mouse_support=mouse_support,
        )
        routine = CliQueryRoutines()

    while 1:
        try:
            query = query_session.prompt(cursor.build("(bigquery)"), in_thread=True)
        except KeyboardInterrupt:
            break
        except EOFError:
            continue

        if query:
            render_query(
                routine,
                console,
                query,
                save_txt,
                save_query_info,
                save_svg,
                hide_table_render,
                TS,
            )


def _build_query_session(
    completer: "Completer", **prompt_kwargs: t.Any
) -> PromptSession[t.Any]:
    session: PromptSession[str] = PromptSession(
        style=Style.from_dict(
            utils.update_dict(
                rtoml.load(constant.PROMPT_STYLE),
                AppConfig().get("prompt", "style", default={}),
            )
        ),
        refresh_interval=1,
        completer=completer,
        bottom_toolbar=cursor.bottom_toolbar,
        rprompt=cursor.rprompt,
        complete_in_thread=True,
        complete_while_typing=True,
        validate_while_typing=True,
        complete_style=CompleteStyle.MULTI_COLUMN,
        history=appdir.SQL_FILE_HISTORY(),
        key_bindings=QUERY_BINDINGS,
        lexer=PygmentsLexer(BqSqlLexer, sync_from_start=True),
        include_default_pygments_style=False,
        reserve_space_for_menu=int(get_console().height * 0.4),
        multiline=True,
        **prompt_kwargs,
    )
    return session


def render_query(
    routine: "CliQueryRoutines",
    console: Console,
    query: str,
    save_txt: bool,
    save_query_info: bool,
    save_svg: bool,
    hide_table_render: bool,
    TS: str,
) -> None:
    with console.status(markup.status_message("Running Query")) as status:
        try:
            query_job = routine._query(
                target=query,
                wait=True,
                render=True,
                status=status,
                suppress=True,
            )
        except click.UsageError as e:
            console.log(e.message)
            return

        if query_job._exception:
            console.log(routine._format_error_message(query_job))
            return

        resource = routine._query_job_url(query_job)
        console.log(f"resource_url: [link={resource}][repr.url]{resource}")
        elapsed_time = routine._elapsed_time(query_job)
        console.log(f"elapsed_time: {elapsed_time}")
        if query_job.cache_hit and not getenv("LIGHTLIKE_CLI_DEV"):
            console.log(f"cache_hit: {True}")
            console.log(f"destination: {query_job.destination}")
        _log_statistics(console, query_job)

        row_iterator: "RowIterator" = query_job.result()
        total_rows: int | None = getattr(row_iterator, "total_rows", None)

        file_width: int = 0
        table = Table(
            box=box.HEAVY_EDGE,
            border_style="bold",
            show_header=True,
            show_lines=True,
            show_edge=True,
        )

    with console.status(markup.status_message("Running Query")) as status:
        if total_rows:
            console.log(
                markup.repr_attrib_name("total_rows"),
                markup.repr_attrib_equal(),
                markup.repr_number(total_rows),
                sep="",
            )
            status.update(markup.status_message("Query Complete. Building table"))

            for field in row_iterator.schema:
                table.add_column(field._properties["name"])

            row_lengths: list[int] = []
            for row in row_iterator:
                table.add_row(*render.map_cell_style(row.values()))
                row_length: int = 0

                items = row.items()
                for k, v in items:
                    field_length = len(str(k))
                    value_length = len(str(v))

                    if field_length > value_length:
                        row_length += field_length
                    else:
                        row_length += value_length

                    row_length += 3  # buffer between columns

                row_lengths.append(row_length)

            file_width = max(max(row_lengths), 165)  # Minimum width.

            status.stop()

            if not hide_table_render:
                console.print(table, new_line_start=True)

        if save_txt or save_svg:
            status.start()
            status.update(markup.status_message("Saving to file"))

            _file_console = Console(
                style=CONSOLE_CONFIG.style,
                theme=CONSOLE_CONFIG.theme,
                record=True,
                width=file_width or get_console().width,
            )
            _file_console._log_render.omit_repeated_times = False

            if save_query_info:
                _file_console.begin_capture()

                _file_console.print("Query:")
                _file_console.print(
                    Padding(
                        Syntax(
                            f"{query}\n",
                            "sql",
                            background_color="default",
                            indent_guides=True,
                            line_numbers=True,
                            dedent=True,
                        ),
                        (0, 0, 1, 0),
                    )
                )
                _file_console.log(f"resource url = {resource}")
                _file_console.log(f"elapsed_time = {elapsed_time}")
                _file_console.log(f"cache hit = {True}")
                _file_console.log(f"destination = {query_job.destination}")

                _log_statistics(_file_console, query_job)

                if total_rows:
                    _file_console.log(
                        markup.repr_attrib_name("total_rows"),
                        markup.repr_attrib_equal(),
                        markup.repr_number(total_rows),
                        sep="",
                    )

                _file_console.export_text(clear=True)

            _file_console.begin_capture()
            _file_console.print(table)
            _file_console.end_capture()

            _dest = appdir.QUERIES.joinpath(TS)
            _query_dir = _dest.joinpath(f"{query_job.job_id}")
            _query_dir.mkdir(exist_ok=True)
            _query_path = _query_dir.joinpath(f"{query_job.job_id}")

            if save_txt:
                status.update(markup.status_message("Saving as txt"))

                _txt = _query_path.with_suffix(".txt").resolve()
                console_text = _file_console.export_text(clear=False)
                _txt.write_text(console_text, encoding="utf-8")
                not getenv("LIGHTLIKE_CLI_DEV") and console.log(
                    markup.link(_txt.as_posix(), _txt.as_uri()),
                    markup.bold(" ("),
                    markup.repr_number(decimal(_txt.stat().st_size)),
                    markup.bold(")"),
                    sep="",
                )

            if save_svg:
                status.update(markup.status_message("Saving as svg"))
                _svg = _query_path.with_suffix(".svg").resolve()
                console_svg = _file_console.export_svg(
                    title="", code_format=_CONSOLE_SVG_FORMAT
                )
                _svg.write_text(console_svg, encoding="utf-8")
                not getenv("LIGHTLIKE_CLI_DEV") and console.log(
                    markup.link(_svg.as_posix(), _svg.as_uri()),
                    markup.bold(" ("),
                    markup.repr_number(decimal(_svg.stat().st_size)),
                    markup.bold(")"),
                    sep="",
                )

        elif not total_rows and query_job.statement_type == "SELECT":
            console.log("[#ec8015]No rows returned")


def _log_statistics(console: Console, query_job: "QueryJob") -> None:
    statement_type = getattr(query_job, "statement_type")
    if statement_type:
        console.log(
            markup.scope_key("statement_type"),
            markup.repr_attrib_equal(),
            markup.repr_str(statement_type),
            sep="",
        )

    slot_millis = getattr(query_job, "slot_millis")
    if slot_millis:
        console.log(
            markup.scope_key("slot_millis"),
            markup.repr_attrib_equal(),
            markup.repr_number(slot_millis),
            sep="",
        )

    total_bytes_processed = getattr(query_job, "total_bytes_processed")
    if total_bytes_processed:
        console.log(
            markup.scope_key("total_bytes_processed"),
            markup.repr_attrib_equal(),
            markup.repr_number(getattr(query_job, "total_bytes_processed")),
            markup.scope_key(" | total_bytes_billed"),
            markup.repr_attrib_equal(),
            markup.repr_number(getattr(query_job, "total_bytes_billed")),
            sep="",
        )

    if query_job.dml_stats:
        for execution in query_job.query_plan:
            console.log(
                # fmt: off
                execution.name,
                " (", markup.repr_number(execution.end - execution.start),") slot_ms: ",
                markup.repr_number(execution._properties["slotMs"]), " ",
                markup.bold(execution.input_stages),
                " shuffle_output_bytes: ",
                markup.repr_number(execution.shuffle_output_bytes),
                " shuffle_output_bytes_spilled: ",
                markup.repr_number(execution.shuffle_output_bytes_spilled),
                markup.scope_key(" records_read"),
                markup.bold(markup.scope_equals("=")),
                markup.repr_number(execution.records_read),
                markup.scope_key(", records_written"),
                markup.bold(markup.scope_equals("=")),
                markup.repr_number(execution.records_written),
                # fmt: on
                sep="",
            )
        console.log(query_job.dml_stats)
