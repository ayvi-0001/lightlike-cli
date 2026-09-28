import typing as t
from datetime import datetime
from os import getenv
from time import perf_counter_ns, time

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
from lightlike.app import cursor, render
from lightlike.app.config import AppConfig
from lightlike.client import CliQueryRoutines
from lightlike.cmd import _pass
from lightlike.cmd.query.completers import query_repl_completer
from lightlike.cmd.query.key_bindings import QUERY_BINDINGS
from lightlike.cmd.query.lexer import BqSqlLexer
from lightlike.internal import appdir, constant, markup, utils
from lightlike.internal.constant import _CONSOLE_SVG_FORMAT

if t.TYPE_CHECKING:
    from google.cloud.bigquery import QueryJob
    from google.cloud.bigquery.table import RowIterator
    from prompt_toolkit.completion import Completer


__all__: t.Sequence[str] = ("_build_query_session", "query_repl")


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
    query_settings: dict[str, bool] = AppConfig().get("settings", "query", default={})
    mouse_support: bool = query_settings.get("mouse-support", True)
    save_txt: bool = query_settings.get("save-txt", False)
    save_query_info: bool = query_settings.get("save-query-info", False)
    save_svg: bool = query_settings.get("save-svg", False)
    hide_table_render: bool = query_settings.get("hide-table-render", False)

    TS = f"{int(datetime.combine(datetime.today(), datetime.min.time()).timestamp())}"

    render.query_start_render(
        query_config=query_settings,
        timestamp=TS,
        print_output_path=save_txt or save_svg,
    )

    with console.status(markup.status_message("Loading BigQuery Resources")):
        query_session = _build_query_session(
            completer=query_repl_completer(),
            mouse_support=mouse_support,
        )
        routine = CliQueryRoutines()

    while True:
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
    completer: "Completer",
    **prompt_kwargs: t.Any,
) -> PromptSession[t.Any]:
    session: PromptSession[str] = PromptSession(
        style=Style.from_dict(
            utils.update_dict(
                rtoml.load(constant.PROMPT_STYLE),
                AppConfig().get("prompt", "style", default={}),
            ),
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
            query_job = routine._query(target=query, wait=True, suppress=True)
        except click.UsageError as e:
            console.log(e.message)
            return

        if query_job._exception:
            console.log(routine._format_error_message(query_job))
            return

        resource = "{base_url}project={project_id}&j=bq:{region}:{job_id}&{end_point}".format(
            base_url="https://console.cloud.google.com/bigquery?",
            project_id=query_job.project,
            region=query_job.location,
            job_id=query_job.job_id,
            end_point="page=queryresults",
        )
        console.log(f"resource_url: [link={resource}][repr.url]{resource}")
        elapsed_time = _elapsed_time(query_job)
        console.log(f"elapsed_time: {elapsed_time}")
        if query_job.cache_hit and not getenv("LIGHTLIKE_CLI_DEV"):
            console.log(f"cache_hit: {True}")
            console.log(f"destination: {query_job.destination}")
        _log_statistics(console, query_job)

        row_iterator: RowIterator = query_job.result()
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

            file_width = max(*row_lengths, 165)  # Minimum width.

            status.stop()

            if not hide_table_render:
                console.print(table, new_line_start=True)

        if save_txt or save_svg:
            status.start()
            status.update(markup.status_message("Saving to file"))

            file_console = Console(
                style=CONSOLE_CONFIG.style,
                theme=CONSOLE_CONFIG.theme,
                record=True,
                width=file_width or get_console().width,
            )
            file_console._log_render.omit_repeated_times = False

            if save_query_info:
                file_console.begin_capture()

                file_console.print("Query:")
                file_console.print(
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
                    ),
                )
                file_console.log(f"resource url = {resource}")
                file_console.log(f"elapsed_time = {elapsed_time}")
                file_console.log(f"cache hit = {True}")
                file_console.log(f"destination = {query_job.destination}")

                _log_statistics(file_console, query_job)

                if total_rows:
                    file_console.log(
                        markup.repr_attrib_name("total_rows"),
                        markup.repr_attrib_equal(),
                        markup.repr_number(total_rows),
                        sep="",
                    )

                file_console.export_text(clear=True)

            file_console.begin_capture()
            file_console.print(table)
            file_console.end_capture()

            dest = appdir.QUERIES.joinpath(TS)
            query_dir = dest.joinpath(f"{query_job.job_id}")
            query_dir.mkdir(exist_ok=True)
            query_path = query_dir.joinpath(f"{query_job.job_id}")

            if save_txt:
                status.update(markup.status_message("Saving as txt"))

                txt = query_path.with_suffix(".txt").resolve()
                console_text = file_console.export_text(clear=False)
                txt.write_text(console_text, encoding="utf-8")
                not getenv("LIGHTLIKE_CLI_DEV") and console.log(
                    markup.link(txt.as_posix(), txt.as_uri()),
                    markup.bold(" ("),
                    markup.repr_number(decimal(txt.stat().st_size)),
                    markup.bold(")"),
                    sep="",
                )

            if save_svg:
                status.update(markup.status_message("Saving as svg"))
                svg = query_path.with_suffix(".svg").resolve()
                console_svg = file_console.export_svg(
                    title="",
                    code_format=_CONSOLE_SVG_FORMAT,
                )
                svg.write_text(console_svg, encoding="utf-8")
                not getenv("LIGHTLIKE_CLI_DEV") and console.log(
                    markup.link(svg.as_posix(), svg.as_uri()),
                    markup.bold(" ("),
                    markup.repr_number(decimal(svg.stat().st_size)),
                    markup.bold(")"),
                    sep="",
                )

        elif not total_rows and query_job.statement_type == "SELECT":
            console.log("[#ec8015]No rows returned")


def _elapsed_time(query_job: "QueryJob", start: float | None = None) -> str:
    if start:
        ns = (perf_counter_ns() - start) * 1.0e-9
    elif query_job.ended:
        ns = query_job.ended.timestamp() - query_job.started.timestamp()
    else:
        ns = time() - query_job.started.timestamp()

    w, d = str(round(ns, 4)).split(".")
    return f"{w}.{'0' * (4 - len(d)) + d}"


def _log_statistics(console: Console, query_job: "QueryJob") -> None:
    statement_type = query_job.statement_type
    if statement_type:
        console.log(
            markup.scope_key("statement_type"),
            markup.repr_attrib_equal(),
            markup.repr_str(statement_type),
            sep="",
        )

    slot_millis = query_job.slot_millis
    if slot_millis:
        console.log(
            markup.scope_key("slot_millis"),
            markup.repr_attrib_equal(),
            markup.repr_number(slot_millis),
            sep="",
        )

    total_bytes_processed = query_job.total_bytes_processed
    if total_bytes_processed:
        console.log(
            markup.scope_key("total_bytes_processed"),
            markup.repr_attrib_equal(),
            markup.repr_number(query_job.total_bytes_processed),
            markup.scope_key(" | total_bytes_billed"),
            markup.repr_attrib_equal(),
            markup.repr_number(query_job.total_bytes_billed),
            sep="",
        )

    if query_job.dml_stats:
        for execution in query_job.query_plan:
            console.log(
                execution.name,
                " (",
                markup.repr_number(execution.end - execution.start),
                ") slot_ms: ",
                markup.repr_number(execution._properties["slotMs"]),
                " ",
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
                sep="",
            )
        console.log(query_job.dml_stats)
