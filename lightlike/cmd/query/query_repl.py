from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ParamSpec, Sequence

import rich_click as click
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession
from rich import box, get_console
from rich.console import Console
from rich.filesize import decimal
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table

from lightlike._console import _CONSOLE_SVG_FORMAT, CONSOLE_CONFIG
from lightlike.app import _pass, cursor, render
from lightlike.app.config import AppConfig
from lightlike.app.key_bindings import QUERY_BINDINGS
from lightlike.app.routines import CliQueryRoutines
from lightlike.cmd.query.completers import query_repl_completer
from lightlike.cmd.query.lexer import BqSqlLexer
from lightlike.internal import appdir

if TYPE_CHECKING:
    from google.cloud.bigquery import QueryJob
    from prompt_toolkit.completion import Completer

    from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = ("query_repl", "_build_query_session")


P = ParamSpec("P")


@click.group(
    name="query",
    invoke_without_command=True,
    short_help="Start an interactive BQ shell.",
)
@_pass.console
@click.pass_context
def query_repl(ctx: click.Context, console: Console) -> None:
    """Start an interactive BQ shell."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(_run_query_repl, console=console)


def _run_query_repl(console: Console) -> None:
    console.clear()

    query_settings = AppConfig().get("settings", "query")
    mouse_support: bool = query_settings.get("mouse_support", True)
    save_txt: bool = query_settings.get("save_txt", False)
    save_query_info: bool = query_settings.get("save_query_info", False)
    save_svg: bool = query_settings.get("save_svg", False)
    hide_table_render: bool = query_settings.get("hide_table_render", False)

    render.query_start_render(query_settings)

    TS = f"{int(datetime.combine(datetime.today(), datetime.min.time()).timestamp())}"

    if save_txt or save_svg:
        appdir.QUERIES.mkdir(exist_ok=True)
        _dest = appdir.QUERIES.joinpath(TS).resolve()
        _dest.mkdir(exist_ok=True)
        uri = _dest.as_uri()
        console.print(f" Queries saved to: [repr.url][link={uri}]{uri}")

    with console.status("[status.message] Loading BigQuery Resources"):
        query_session = _build_query_session(
            query_repl_completer(), mouse_support=mouse_support
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


def _build_query_session(completer: "Completer", **prompt_kwargs) -> PromptSession:
    return PromptSession(
        style=AppConfig().prompt_style,
        refresh_interval=1,
        completer=completer,
        complete_in_thread=True,
        complete_while_typing=True,
        validate_while_typing=True,
        complete_style=CompleteStyle.MULTI_COLUMN,
        history=appdir.SQL_FILE_HISTORY,
        key_bindings=QUERY_BINDINGS,
        lexer=PygmentsLexer(BqSqlLexer, sync_from_start=True),
        include_default_pygments_style=False,
        reserve_space_for_menu=int(get_console().height * 0.4),
        multiline=True,
        **prompt_kwargs,
    )


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
    with console.status("[status.message] Running Query") as status:
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
        if query_job.cache_hit:
            console.log(f"cache_hit: {True}")
            console.log(f"destination: {query_job.destination}")
        _log_statistics(console, query_job)

        row_iterator = query_job.result()
        total_rows = getattr(row_iterator, "total_rows", None)

        file_width: int = 0
        table = Table(
            box=box.HEAVY_EDGE,
            border_style="bold",
            show_header=True,
            show_lines=True,
            show_edge=True,
        )

    with console.status("[status.message] Running Query") as status:
        if total_rows:
            console.log("[notice]total_rows[/notice] = %s" % total_rows)
            status.update(f"[status.message] Query Complete. Building table")

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
            status.update("[status.message] Saving to file")

            _file_console = Console(
                style=CONSOLE_CONFIG.style,
                theme=CONSOLE_CONFIG.theme,
                record=True,
                width=file_width or get_console().width,
            )
            _file_console._log_render.omit_repeated_times = False

            if save_query_info:
                _file_console.begin_capture()

                _file_console.print(f"Query:")
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
                    _file_console.log("[notice]total_rows[/notice] = %s" % total_rows)

                _file_console.export_text(clear=True)

            _file_console.begin_capture()
            _file_console.print(table)
            _file_console.end_capture()

            _dest = appdir.QUERIES.joinpath(TS)
            _query_dir = _dest.joinpath(f"{query_job.job_id}")
            _query_dir.mkdir(exist_ok=True)
            _query_path = _query_dir.joinpath(f"{query_job.job_id}")

            if save_txt:
                status.update("[status.message] Saving as txt")

                _txt = _query_path.with_suffix(".txt")
                console_text = _file_console.export_text(clear=False)
                _txt.write_text(console_text, encoding="utf-8")
                console.log(
                    f"[link={_txt.as_uri()}][repr.url]{_txt.name}[/repr.url][/link] "
                    f"({decimal(_txt.stat().st_size)})"
                )

            if save_svg:
                status.update("[status.message] Saving as svg")
                _svg = _query_path.with_suffix(".svg")
                console_svg = _file_console.export_svg(
                    title="", code_format=_CONSOLE_SVG_FORMAT
                )
                _svg.write_text(console_svg, encoding="utf-8")
                console.log(
                    f"[link={_svg.as_uri()}][repr.url]{_svg.name}[/repr.url][/link] "
                    f"({decimal(_svg.stat().st_size)})"
                )

        elif not total_rows and query_job.statement_type == "SELECT":
            console.log("[#ec8015]No rows returned")


def _log_statistics(console: Console, query_job: "QueryJob") -> None:
    statement_type = getattr(query_job, "statement_type")
    if statement_type:
        console.log(
            f"[scope.key]statement_type[/scope.key] = [repr.str]{statement_type}"
        )

    slot_millis = getattr(query_job, "slot_millis")
    if slot_millis:
        console.log(f"[scope.key]slot_millis[/scope.key] = {slot_millis}")

    total_bytes_processed = getattr(query_job, "total_bytes_processed")
    if total_bytes_processed:
        console.log(
            (
                "[scope.key]total_bytes_processed[/scope.key] = "
                f"{getattr(query_job, 'total_bytes_processed')} | "
                "[scope.key]total_bytes_billed[/scope.key] = "
                f"{getattr(query_job, 'total_bytes_billed')}"
            )
        )

    if query_job.dml_stats:
        for execution in query_job.query_plan:
            dml_stats = "".join(
                [
                    "{name} ({duration}) {input_stages} ",
                    "slot_ms: {slot_ms} ",
                    "shuffle_output_bytes: {shuffle_output_bytes} ",
                    "shuffle_output_bytes_spilled: {shuffle_output_bytes_spilled} ",
                    "[scope.key]records_read[/scope.key]={records_read}, ",
                    "[scope.key]records_written[/scope.key]={records_written}",
                ]
            )
            console.log(
                dml_stats.format(
                    name=execution.name,
                    duration=(execution.end - execution.start),
                    input_stages=execution.input_stages,
                    slot_ms=execution._properties["slotMs"],
                    shuffle_output_bytes=execution.shuffle_output_bytes,
                    shuffle_output_bytes_spilled=execution.shuffle_output_bytes_spilled,
                    records_read=execution.records_read,
                    records_written=execution.records_written,
                )
            )

        console.log(query_job.dml_stats)
