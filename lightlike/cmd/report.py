import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, ParamSpec, Sequence
from uuid import uuid4

import rich_click as click
from rich import get_console
from rich.padding import Padding

from lightlike.app import _pass, render, shell_complete, validate
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.cmd import _help, dates
from lightlike.internal import utils

if TYPE_CHECKING:
    from pandas import DataFrame
    from rich.console import Console

    from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = ("report",)


get_console().log(f"[log.main]Loading command group: {__name__}")


P = ParamSpec("P")


@click.group(
    cls=AliasedRichGroup,
    short_help="Create & save a report.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def report(debug: bool) -> None: ...


current_week_option = click.option(
    "-cw",
    "--current-week",
    is_flag=True,
    type=click.BOOL,
    help="Use current week start/end dates.",
)
start_option = click.option(
    "-s",
    "--start",
    type=click.STRING,
    help="Start date of report range.",
    shell_complete=shell_complete.time,
)
end_option = click.option(
    "-e",
    "--end",
    type=click.STRING,
    help="End date of report range.",
    shell_complete=shell_complete.time,
)
round_option = click.option(
    "-r",
    "--round",
    "round_",
    is_flag=True,
    type=click.BOOL,
    default=False,
    show_default=True,
    help="Rounds totals to nearest 0.25.",
)
where_option = click.option(
    "-w",
    "--where",
    is_flag=True,
    type=click.BOOL,
    help="Filter results with a WHERE clause. Prompts for input.",
)
where_args = click.argument(
    "where_args",
    nargs=-1,
    type=click.STRING,
    required=False,
    metavar="WHERE CLAUSE",
)
print_option = click.option(
    "-p",
    "--print",
    "print_",
    is_flag=True,
    type=click.BOOL,
    help="Print results to terminal.",
)


@report.command(
    cls=_RichCommand,
    name="table",
    help=_help.report_table,
    short_help="Renders a table in terminal. Optional svg download.",
    context_settings=dict(
        obj=dict(syntax=_help.report_table_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Canceled report.\n")
)
@current_week_option
@start_option
@end_option
@round_option
@click.option(
    "-d",
    "--destination",
    expose_value=True,
    metavar="SVG",
    type=Path,
    shell_complete=shell_complete.path,
    callback=validate.callbacks.report_path,
    help="Destination path to write file.",
)
@where_option
@where_args
@_pass.routine
@_pass.console
def table_report(
    console: "Console",
    routine: "CliQueryRoutines",
    start: str,
    end: str,
    round_: bool,
    destination: Path,
    current_week: bool,
    where: bool,
    where_args: Sequence[str],
) -> None:
    date_range = (
        dates._get_current_week_range()
        if current_week
        else dates._parse_date_range_flags(start, end)
    )

    str_range = "%s -> %s" % (date_range.start.date(), date_range.end.date())

    where_clause = shell_complete.where._parse_click_options(
        flag=where, args=where_args, console=console, routine=routine
    )

    status_renderable = f"[status.message]Building report"
    with console.status(status=status_renderable) as status:
        query_job = routine.report(
            start_date=date_range.start,
            end_date=date_range.end,
            where_clause=where_clause,
            round_=round_,
            type_="table",
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        row_iterator = query_job.result()
        table = render.row_iter_to_rich_table(
            row_iterator=row_iterator,
            table_kwargs=dict(
                title=f"# Report: {str_range}",
                title_justify="left",
            ),
        )

        if not table.row_count:
            console.print("[d]No entries found between %s.\n" % str_range)
            return

        render.new_console_print(
            Padding(table, (1, 0, 0, 0)),
            status=status,
            svg_path=destination,
        )


@report.command(
    cls=_RichCommand,
    name="csv",
    help=_help.report_csv,
    short_help="Save/Print report to a csv file.",
    context_settings=dict(
        obj=dict(syntax=_help.report_csv_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Canceled report.\n")
)
@current_week_option
@start_option
@end_option
@round_option
@click.option(
    "-d",
    "--destination",
    expose_value=True,
    metavar="CSV",
    type=Path,
    shell_complete=shell_complete.path,
    callback=validate.callbacks.report_path,
    help="Destination path to write file.",
)
@print_option
@where_option
@where_args
@_pass.routine
@_pass.console
@utils._nl_start()
def csv_report(
    console: "Console",
    routine: "CliQueryRoutines",
    destination: Path,
    start: str,
    end: str,
    round_: bool,
    print_: bool,
    current_week: bool,
    where: bool,
    where_args: Sequence[str],
) -> None:
    if not destination and not print_:
        raise click.BadParameter(
            message="For csv and json reports, "
            "at least one of --print or --destination flags must be used.",
        )

    date_range = (
        dates._get_current_week_range()
        if current_week
        else dates._parse_date_range_flags(start, end)
    )

    where_clause = shell_complete.where._parse_click_options(
        flag=where, args=where_args, console=console, routine=routine
    )

    status_renderable = f"[status.message]Building report"
    with console.status(status=status_renderable) as status:
        query_job = routine.report(
            start_date=date_range.start,
            end_date=date_range.end,
            where_clause=where_clause,
            round_=round_,
            type_="file",
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        console.log("Converting table to csv")
        row_iterator = query_job.result()
        df: "DataFrame" = row_iterator.to_dataframe()

        if destination:
            dest = destination.resolve()
            uri = dest.as_uri()
            path = dest.as_posix()
            df.to_csv(path, index=False, encoding="utf-8")
            console.log(f"Saved to [link={uri}][repr.url]{path}[/repr.url].")

        if print_:
            console.log(f"Printing to terminal")
            utils._nl()
            if not destination:
                with tempfile.TemporaryDirectory() as temp_dir:
                    _report = Path(temp_dir).joinpath(f"{uuid4()}.csv")
                    df.to_csv(_report, index=False, encoding="utf-8")
                    console.print(_report.read_text())
            else:
                console.print(destination.read_text())


@report.command(
    cls=_RichCommand,
    name="json",
    help=_help.report_json,
    short_help="Save/Print report to a json file.",
    context_settings=dict(
        obj=dict(syntax=_help.report_json_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Canceled report.\n")
)
@current_week_option
@start_option
@end_option
@round_option
@click.option(
    "-d",
    "--destination",
    expose_value=True,
    metavar="JSON",
    type=Path,
    shell_complete=shell_complete.path,
    callback=validate.callbacks.report_path,
    help="Destination path to write file.",
)
@print_option
@click.option(
    "-o",
    "--orient",
    type=click.STRING,
    help="Orient passed to Dataframe.to_json(...)",
    default="records",
    show_default=True,
    shell_complete=shell_complete.Param(
        "orient",
        ["columns", "index", "records", "split", "table", "values"],
    ).string,
)
@where_option
@where_args
@_pass.routine
@_pass.console
@click.pass_context
@utils._nl_start()
def json_report(
    ctx: click.Context,
    console: "Console",
    routine: "CliQueryRoutines",
    destination: Path,
    start: str,
    end: str,
    round_: bool,
    print_: bool,
    orient: str,
    current_week: bool,
    where: bool,
    where_args: Sequence[str],
) -> None:
    if not destination and not print_:
        raise click.UsageError(
            message="For csv and json reports, "
            "at least one of --print or --destination flags must be used.",
            ctx=ctx,
        )

    date_range = (
        dates._get_current_week_range()
        if current_week
        else dates._parse_date_range_flags(start, end)
    )

    where_clause = shell_complete.where._parse_click_options(
        flag=where, args=where_args, console=console, routine=routine
    )

    status_renderable = f"[status.message]Building report"
    with console.status(status=status_renderable) as status:
        query_job = routine.report(
            start_date=date_range.start,
            end_date=date_range.end,
            where_clause=where_clause,
            round_=round_,
            type_="file",
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        console.log("Converting table to json.")
        row_iterator = query_job.result()
        df: "DataFrame" = row_iterator.to_dataframe()

        if destination:
            dest = destination.resolve()
            uri = dest.as_uri()
            path = dest.as_posix()
            df.to_json(path, orient=orient, date_format="iso", indent=4)  # type: ignore[call-overload]
            console.log(f"Saved to [link={uri}][repr.url]{path}[/repr.url].")

        if print_:
            console.log(f"Printing to terminal")
            utils._nl()
            if not destination:
                with tempfile.TemporaryDirectory() as temp_dir:
                    _report = Path(temp_dir).joinpath(f"{uuid4()}.json")
                    df.to_json(_report.as_posix(), orient=orient, date_format="iso", indent=4)  # type: ignore[call-overload]
                    console.print_json(_report.read_text())
            else:
                console.print_json(dest.read_text())
