# mypy: disable-error-code="func-returns-value, import-untyped"

import typing as t
from datetime import datetime
from operator import truth
from pathlib import Path

import rich_click as click
from rich import print as rprint
from rich.console import Console
from rich.padding import Padding

from lightlike import _console
from lightlike.app import _pass, dates, render, shell_complete, validate
from lightlike.app.config import AppConfig
from lightlike.app.core import FmtRichCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _help
from lightlike.internal import markup, utils

if t.TYPE_CHECKING:
    from pandas import DataFrame

    from lightlike.app.routines import CliQueryRoutines

__all__: t.Sequence[str] = (
    "summary_table",
    "summary_csv",
    "summary_json",
)


P = t.ParamSpec("P")


all_option = click.option(
    "-a",
    "--all",
    "all_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Query full table.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
current_week_option = click.option(
    "-cw",
    "--current-week",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Query range = week to date.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
current_month_option = click.option(
    "-cm",
    "--current-month",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Query range = month to date.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
current_year_option = click.option(
    "-cy",
    "--current-year",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Query range = year to date.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
start_option = click.option(
    "-s",
    "--start",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Start date of summary range.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
end_option = click.option(
    "-e",
    "--end",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="End date of summary range.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
round_option = click.option(
    "-r",
    "--round",
    "round_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Rounds totals to nearest 0.25.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
where_option = click.option(
    "-w",
    "--prompt-where",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Interactive prompt for WHERE clause.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
where_clause = click.argument(
    "where",
    type=click.STRING,
    required=False,
    default=None,
    callback=None,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=None,
)
print_option = click.option(
    "-p",
    "--print",
    "print_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Print results to terminal.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
match_project = click.option(
    "-Rp",
    "--match-project",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Expression to match project name.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
match_note = click.option(
    "-Rn",
    "--match-note",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Expression to match note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)


@click.command(
    cls=FmtRichCommand,
    name="table",
    no_args_is_help=True,
    help=_help.summary_table,
    short_help="Renders a table in terminal. Optional svg download.",
    syntax=_help.summary_table_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Canceled summary.")),
)
@start_option
@end_option
@all_option
@current_week_option
@current_month_option
@current_year_option
@round_option
@match_project
@match_note
@where_option
@where_clause
@click.option(
    "-o",
    "--output",
    show_default=True,
    multiple=False,
    type=Path,
    help="Path to write file.",
    required=False,
    default=None,
    callback=validate.callbacks.summary_path,
    metavar="SVG",
    shell_complete=shell_complete.path,
)
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
@_pass.now
def summary_table(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    console: Console,
    routine: "CliQueryRoutines",
    start: datetime,
    end: datetime,
    all_: bool,
    current_week: bool,
    current_month: bool,
    current_year: bool,
    round_: bool,
    output: Path,
    match_project: str | None,
    match_note: str | None,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            round_=round_,
            is_file=False,
        )
    else:
        validate.callbacks.current_time_period_flags(
            current_week=current_week,
            current_month=current_month,
            current_year=current_year,
            previous_week=False,
            ctx=ctx,
        )
        if current_week:
            date_params = dates.get_relative_week(
                now, AppConfig().get("settings", "week_start")
            )
        elif current_month:
            date_params = dates.get_month_to_date(now)
        elif current_year:
            date_params = dates.get_year_to_date(now)
        else:
            date_params = dates.parse_date_range_flags(
                start or PromptFactory.prompt_date("(start-date)"),
                end or PromptFactory.prompt_date("(end-date)"),
            )

        where_clause = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            start_date=date_params.start.date(),
            end_date=date_params.end.date(),
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            round_=round_,
            is_file=False,
        )

    table = render.map_sequence_to_rich_table(
        mappings=list(map(lambda r: dict(r.items()), query_job)),
        string_ctype=["project", "notes"],
        bool_ctype=["billable"],
        num_ctype=["total_summary", "total_project", "total_day", "hours"],
        datetime_ctype=[""],
        time_ctype=["start", "end"],
        date_ctype=["date"],
    )

    with Console(record=True, style=_console.CONSOLE_CONFIG.style) as console:
        console.print(Padding(table, (1, 0, 0, 0)))

        uri: str
        path: str
        if output is not None:
            resolved: Path = output.resolve()
            uri = resolved.as_uri()
            path = resolved.as_posix()
            console.save_svg(path, code_format=_console._CONSOLE_SVG_FORMAT)
            console.print("Saved to", markup.link(path, uri))


@click.command(
    cls=FmtRichCommand,
    name="csv",
    no_args_is_help=True,
    help=_help.summary_csv,
    short_help="Save/Print summary to a csv file.",
    syntax=_help.summary_csv_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Canceled summary.")),
)
@start_option
@end_option
@all_option
@current_week_option
@current_month_option
@current_year_option
@round_option
@print_option
@match_project
@match_note
@where_option
@where_clause
@click.option(
    "-o",
    "--output",
    show_default=True,
    multiple=False,
    type=Path,
    help="Path to write file.",
    required=False,
    default=None,
    callback=validate.callbacks.summary_path,
    metavar="CSV",
    shell_complete=shell_complete.path,
)
@click.option(
    "--quoting",
    show_default=True,
    multiple=False,
    type=click.Choice(
        ["NONNUMERIC", "ALL", "MINIMAL", "NONE"],
        case_sensitive=False,
    ),
    help="Optional constant from csv module",
    required=False,
    default="NONNUMERIC",
    callback=None,
    metavar=None,
)
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
@_pass.now
def summary_csv(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    console: Console,
    routine: "CliQueryRoutines",
    start: datetime,
    end: datetime,
    all_: bool,
    current_week: bool,
    current_month: bool,
    current_year: bool,
    output: Path,
    round_: bool,
    print_: bool,
    match_project: str | None,
    match_note: str | None,
    prompt_where: bool,
    where: t.Sequence[str],
    quoting: str,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    import csv

    validate.callbacks.print_or_output(output=truth(output), print_=print_)

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            round_=round_,
            is_file=False,
        )
    else:
        validate.callbacks.current_time_period_flags(
            current_week=current_week,
            current_month=current_month,
            current_year=current_year,
            previous_week=False,
            ctx=ctx,
        )
        if current_week:
            date_params = dates.get_relative_week(
                now, AppConfig().get("settings", "week_start")
            )
        elif current_month:
            date_params = dates.get_month_to_date(now)
        elif current_year:
            date_params = dates.get_year_to_date(now)
        else:
            date_params = dates.parse_date_range_flags(
                start or PromptFactory.prompt_date("(start-date)"),
                end or PromptFactory.prompt_date("(end-date)"),
            )

        where_clause = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            start_date=date_params.start.date(),
            end_date=date_params.end.date(),
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            round_=round_,
            is_file=True,
        )

    df: "DataFrame" = query_job.result().to_dataframe()

    if output:
        dest = output.resolve()
        uri = dest.as_uri()
        path = dest.as_posix()
        df.to_csv(
            path,
            index=False,
            quoting=getattr(csv, f"QUOTE_{quoting}"),
            doublequote=True,
            quotechar='"',
            encoding="utf-8",
        )
        console.print("Saved to", markup.link(path, uri))

    if print_:
        if not output:
            import tempfile
            from uuid import uuid4

            with tempfile.TemporaryDirectory() as temp_dir:
                _summary = Path(temp_dir).joinpath(f"{uuid4()}.csv")
                df.to_csv(
                    _summary,
                    index=False,
                    quoting=getattr(csv, f"QUOTE_{quoting}"),
                    doublequote=True,
                    quotechar='"',
                    encoding="utf-8",
                )
                console.print(_summary.read_text())
        else:
            console.print(output.read_text())


@click.command(
    cls=FmtRichCommand,
    name="json",
    no_args_is_help=True,
    help=_help.summary_json,
    short_help="Save/Print summary to a json file.",
    syntax=_help.summary_json_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Canceled summary.")),
)
@start_option
@end_option
@all_option
@current_week_option
@current_month_option
@current_year_option
@round_option
@match_project
@match_note
@where_option
@where_clause
@click.option(
    "-o",
    "--output",
    show_default=True,
    multiple=False,
    type=Path,
    help="Path to write file.",
    required=False,
    default=None,
    callback=validate.callbacks.summary_path,
    metavar="JSON",
    shell_complete=shell_complete.path,
)
@print_option
@click.option(
    "--orient",
    show_default=True,
    multiple=False,
    type=click.Choice(
        ["columns", "index", "records", "split", "table", "values"],
        case_sensitive=False,
    ),
    help="Indication of expected JSON string format",
    required=False,
    default="records",
    callback=None,
    metavar=None,
)
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
@_pass.now
def summary_json(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    console: Console,
    routine: "CliQueryRoutines",
    start: datetime,
    end: datetime,
    all_: bool,
    current_week: bool,
    current_month: bool,
    current_year: bool,
    output: Path,
    round_: bool,
    print_: bool,
    orient: str,
    match_project: str | None,
    match_note: str | None,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    validate.callbacks.print_or_output(output=truth(output), print_=print_)

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            round_=round_,
            is_file=False,
        )
    else:
        validate.callbacks.current_time_period_flags(
            current_week=current_week,
            current_month=current_month,
            current_year=current_year,
            previous_week=False,
            ctx=ctx,
        )
        if current_week:
            date_params = dates.get_relative_week(
                now, AppConfig().get("settings", "week_start")
            )
        elif current_month:
            date_params = dates.get_month_to_date(now)
        elif current_year:
            date_params = dates.get_year_to_date(now)
        else:
            date_params = dates.parse_date_range_flags(
                start or PromptFactory.prompt_date("(start-date)"),
                end or PromptFactory.prompt_date("(end-date)"),
            )

        where_clause = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            start_date=date_params.start.date(),
            end_date=date_params.end.date(),
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            round_=round_,
            is_file=True,
        )

    df: "DataFrame" = query_job.result().to_dataframe()

    if output:
        dest = output.resolve()
        uri = dest.as_uri()
        path = dest.as_posix()
        df.to_json(  # type: ignore[call-overload]
            path,
            orient=orient,
            date_format="iso",
            indent=4,
        )
        console.print("Saved to", markup.link(path, uri))

    if print_:
        if not output:
            import tempfile
            from uuid import uuid4

            with tempfile.TemporaryDirectory() as temp_dir:
                _summary = Path(temp_dir).joinpath(f"{uuid4()}.json")
                df.to_json(  # type: ignore[call-overload]
                    _summary.as_posix(),
                    orient=orient,
                    date_format="iso",
                    indent=4,
                )
                console.print_json(_summary.read_text())
        else:
            console.print_json(dest.read_text())
