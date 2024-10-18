import csv
import platform
import tempfile
import typing as t
from datetime import datetime
from operator import truth
from pathlib import Path
from uuid import uuid4

import click
from rich import print as rprint
from rich.console import Console
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table

from lightlike import _console
from lightlike.app import dates, render, shell_complete, validate
from lightlike.app.config import AppConfig
from lightlike.app.core import FormattedCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _pass
from lightlike.internal import markup, utils
from lightlike.internal.constant import _CONSOLE_SVG_FORMAT

if t.TYPE_CHECKING:
    from pandas import DataFrame

    from lightlike.client import CliQueryRoutines

__all__: t.Sequence[str] = (
    "summary_table",
    "summary_csv",
    "summary_json",
)


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
    multiple=False,
    type=click.Choice([".05", ".1", ".25", ".5", "1"]),
    help="Round hours to the nearest decimal value",
    required=False,
    callback=None,
    metavar=None,
    shell_complete=None,
)
show_null_values = click.option(
    "--null-values/--no-null-values",
    "show_null_values",
    show_default=True,
    is_flag=True,
    flag_value=False,
    multiple=False,
    type=click.BOOL,
    help="If rounding, show values which have been rounded down to 0.",
    required=False,
    default=True,
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
    default=False,
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
    "-rp",
    "--match-project",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Expressions to match project name.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
match_note = click.option(
    "-rn",
    "--match-note",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Expressions to match note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
modifiers = click.option(
    "-M",
    "--modifiers",
    show_default=False,
    multiple=False,
    type=click.STRING,
    help="Modifiers to pass to RegExp. (ECMAScript only)",
    required=False,
    default="",
    callback=None,
    metavar=None,
    shell_complete=None,
)
regex_engine = click.option(
    "-re",
    "--regex-engine",
    show_default=True,
    multiple=False,
    type=click.Choice(["ECMAScript", "re2"]),
    help="Regex engine to use.",
    required=False,
    default="ECMAScript",
    callback=None,
    metavar=None,
    shell_complete=None,
)


@click.command(
    cls=FormattedCommand,
    name="table",
    no_args_is_help=True,
    short_help="Renders a table in terminal. Optional svg download.",
    syntax=Syntax(
        code="""\
        # summary of entries starting 7 days ago, until today. hours rounded to nearest .25
        $ timer summary table --start 7d --end now --round .25
        $ t su t -s7d -en -r.25
    
        # case insensitive regex match - re2
        $ timer summary table --current-year --output timesheet_%Y-%m-%dT%H_%M_%S.svg --regex-engine re2 --match-note (?i)task.*
        $ t su t -cy -o timesheet_%Y-%m-%dT%H_%M_%S.svg -re re2 -rn (?i)task.*
        
        # case insensitive regex match - ECMAScript
        $ timer summary table --current-year --output timesheet_%Y-%m-%dT%H_%M_%S.svg --match-note task.* --modifiers ig
        $ t su t -cy -o timesheet_%Y-%m-%dT%H_%M_%S.svg -rn task.* -Mig

        $ timer summary table --start jan1 --end jul1 billable is true
        $ t su t -sjan1 -ejul1 billable is true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@start_option
@end_option
@all_option
@current_week_option
@current_month_option
@current_year_option
@round_option
@show_null_values
@match_project
@match_note
@modifiers
@regex_engine
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
    shell_complete=shell_complete.snapshot("timesheet", ".svg"),
)
@click.option(
    "-l",
    "--show-lines",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Show lines between rows",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
@_pass.now
def summary_table(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: "CliQueryRoutines",
    start: datetime,
    end: datetime,
    all_: bool,
    current_week: bool,
    current_month: bool,
    current_year: bool,
    round_: str,
    show_null_values: bool,
    show_lines: bool,
    output: Path | None,
    match_project: t.Sequence[str],
    match_note: t.Sequence[str],
    modifiers: str,
    regex_engine: str,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    """
    Create a summary and render a table in terminal. Optional svg download.

    [yellow][b][u]Note: running & paused entries are not included in summaries.[/b][/u][/yellow]

    [b]Fields[/]:
        - total_summary:  The sum of hours, ordered by date, project, billable.
        - total_project:  The sum of hours, partitioned by project, ordered by date, project, billable.
        - total_day:      The sum of hours, partitioned by day, ordered by date, project, billable.
        - date:           Date.
        - project:        Project.
        - billable:       Billable.
        - timer:          The sum of hours for a project on a given day.
        - notes:          String aggregate of all notes on that day. Notes separted by a newline.
                        Sum of hours appended to the end [#888888]('$NOTE - $HOURS')[/]

    --output / -d:
        save the output of this command to this path.
        if the path does not have any suffix, then the expected suffix will be appended.
        if the path with the correct suffix already exists, a prompt will ask whether to overwrite or not.
        if the path ends in any suffix other than what's expected, an error will raise.
        autocomplete format: [code]timesheet_%Y-%m-%dT%H_%M_%S.svg[/code]

    --round / -r:
        round totals to the nearest 0.05 / 0.10 / 0.25 / 0.50 / 1.

    --current-week / -cw:
    --current-month / -cm:
    --current-year / -cy:
        flags are processed before other date options.
        configure week start dates with app:config:set:general:week-start.

    --match-project / -rp:
        match a regular expression against project names.
        this option can be repeated, with each pattern being separated by `|`.

    --match-note / -rn:
        match a regular expression against entry notes.
        this option can be repeated, with each pattern being separated by `|`.

    --modifiers / -M:
        modifiers to pass to RegExp. (ECMAScript only)

    --regex-engine / -re:
        which regex engine to use.
        re2 = google's regular expression library used by all bigquery regex functions.
        ECMAScript = javascript regex syntax.

        example:
        re2 does not allow perl operator's such as negative lookaheads, while ECMAScript does.
        to run a case-insensitive regex match in re2, use the inline modifier [repr.str]"(?i)"[/repr.str],
        for ECMAScript, use the --modifiers / -M option with [repr.str]"i"[/repr.str]

    --prompt-where / -w:
        filter results with a where clause.
        interactive prompt that launches after command runs.
        prompt includes autocompletions for projects and notes.
        note autocompletions will only populate for a project
        if that project name appears in the string.

    [bold #34e2e2]WHERE[/]:
        all remaining arguments at the end of this command are
        joined together by a space to form the where clause.
        the word "WHERE" is stripped from the start of the string, if it exists.
    """
    ctx, parent = ctx_group

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            modifiers=modifiers,
            regex_engine=regex_engine,
            round_=round_,
            show_null_values=not show_null_values,
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
                now, AppConfig().get("settings", "week-start", default=0)
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
            modifiers=modifiers,
            regex_engine=regex_engine,
            round_=round_,
            show_null_values=not show_null_values,
            is_file=False,
        )

    table: Table = render.map_sequence_to_rich_table(
        mappings=list(map(lambda r: dict(r.items()), query_job)),
        table_kwargs={"show_lines": show_lines},
    )
    if not table.row_count:
        rprint(markup.dimmed("No results"))
        raise click.exceptions.Exit()

    with Console(record=True, style=_console.CONSOLE_CONFIG.style) as console:
        console.print(Padding(table, (1, 0, 0, 0)))

        uri: str
        path: str
        if output is not None:
            resolved: Path = output.resolve()
            uri = resolved.as_uri()
            path = resolved.as_posix()
            console.save_svg(path, code_format=_CONSOLE_SVG_FORMAT)
            console.print("Saved to", markup.link(path, uri))


@click.command(
    cls=FormattedCommand,
    name="csv",
    no_args_is_help=True,
    short_help="Save/Print summary to a csv file.",
    syntax=Syntax(
        code="""\
        # summary of entries starting 7 days ago, until today. hours rounded to nearest .25
        $ timer summary csv --start 7d --end now --round .25 --print
        $ t su c -s7d -en -r.25 -p
    
        # case insensitive regex match - re2
        $ timer summary csv --current-year --output timesheet_%Y-%m-%dT%H_%M_%S.csv --regex-engine re2 --match-note (?i)task.*
        $ t su c -cy -o timesheet_%Y-%m-%dT%H_%M_%S.csv -re re2 -rn (?i)task.*
        
        # case insensitive regex match - ECMAScript
        $ timer summary csv --current-year --output timesheet_%Y-%m-%dT%H_%M_%S.csv --match-note task.* --modifiers ig
        $ t su c -cy -o timesheet_%Y-%m-%dT%H_%M_%S.csv -rn task.* -Mig
        
        $ timer summary csv --start jan1 --end jul1 billable is true --print
        $ t su c -sjan1 -ejul1 billable is true -p\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@start_option
@end_option
@all_option
@current_week_option
@current_month_option
@current_year_option
@round_option
@show_null_values
@print_option
@match_project
@match_note
@modifiers
@regex_engine
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
    shell_complete=shell_complete.snapshot("timesheet", ".csv"),
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
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: "CliQueryRoutines",
    start: datetime,
    end: datetime,
    all_: bool,
    current_week: bool,
    current_month: bool,
    current_year: bool,
    output: Path | None,
    round_: str,
    show_null_values: bool,
    print_: bool,
    quoting: str,
    match_project: t.Sequence[str],
    match_note: t.Sequence[str],
    modifiers: str,
    regex_engine: str,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    """
    Create a summary and save to a csv file, or print to terminal.

    [yellow][b][u]Note: running & paused entries are not included in summaries.[/b][/u][/yellow]

    [b]Fields[/]:
        - total_summary:  The sum of hours, ordered by date, project, billable.
        - total_project:  The sum of hours, partitioned by project, ordered by date, project, billable.
        - total_day:      The sum of hours, partitioned by day, ordered by date, project, billable.
        - date:           Date.
        - project:        Project.
        - billable:       Billable.
        - timer:          The sum of hours for a project on a given day.
        - notes:          String aggregate of all notes on that day. Notes separted by a newline.
                        Sum of hours appended to the end [#888888]('$NOTE - $HOURS')[/]

    --print / -p:
        print output to terminal.
        either this, or --output / -d must be provided.

    --output / -d:
        save the output of this command to this path.
        if the path does not have any suffix, then the expected suffix will be appended.
        if the path with the correct suffix already exists, a prompt will ask whether to overwrite or not.
        if the path ends in any suffix other than what's expected, an error will raise.
        autocomplete format: [code]timesheet_%Y-%m-%dT%H_%M_%S.csv[/code]

    --round / -r:
        round totals to the nearest 0.05 / 0.10 / 0.25 / 0.50 / 1.

    --current-week / -cw:
    --current-month / -cm:
    --current-year / -cy:
        flags are processed before other date options.
        configure week start dates with app:config:set:general:week-start.

    --match-project / -rp:
        match a regular expression against project names.
        this option can be repeated, with each pattern being separated by `|`.

    --match-note / -rn:
        match a regular expression against entry notes.
        this option can be repeated, with each pattern being separated by `|`.

    --modifiers / -M:
        modifiers to pass to RegExp. (ECMAScript only)

    --regex-engine / -re:
        which regex engine to use.
        re2 = google's regular expression library used by all bigquery regex functions.
        ECMAScript = javascript regex syntax.

        example:
        re2 does not allow perl operator's such as negative lookaheads, while ECMAScript does.
        to run a case-insensitive regex match in re2, use the inline modifier [repr.str]"(?i)"[/repr.str],
        for ECMAScript, use the --modifiers / -M option with [repr.str]"i"[/repr.str]

    --prompt-where / -w:
        filter results with a where clause.
        interactive prompt that launches after command runs.
        prompt includes autocompletions for projects and notes.
        note autocompletions will only populate for a project
        if that project name appears in the string.

    [bold #34e2e2]WHERE[/]:
        all remaining arguments at the end of this command are
        joined together by a space to form the where clause.
        the word "WHERE" is stripped from the start of the string, if it exists.
    """
    if "android" in platform.release():
        console.print(
            "[b][red]summary:csv and summary:json not currently supported on android."
        )
        raise click.exceptions.Exit()

    ctx, parent = ctx_group

    validate.callbacks.print_or_output(output=truth(output), print_=print_)

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            modifiers=modifiers,
            regex_engine=regex_engine,
            round_=round_,
            show_null_values=not show_null_values,
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
                now, AppConfig().get("settings", "week-start", default=0)
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
            modifiers=modifiers,
            regex_engine=regex_engine,
            round_=round_,
            show_null_values=not show_null_values,
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
    cls=FormattedCommand,
    name="json",
    no_args_is_help=True,
    short_help="Save/Print summary to a json file.",
    syntax=Syntax(
        code="""\
        # summary of entries starting 7 days ago, until today. hours rounded to nearest .25
        $ timer summary json --start 7d --end now --round .25 --print
        $ t su j -s7d -en -r.25 -p
    
        $ timer summary json --current-week --orient index billable is false
        $ t su j -cw --orient index -w\
        
        # case insensitive regex match - re2
        $ timer summary json --current-year --output timesheet_%Y-%m-%dT%H_%M_%S.json --regex-engine re2 --match-note (?i)task.*
        $ t su j -cy -o timesheet_%Y-%m-%dT%H_%M_%S.json -re re2 -rn (?i)task.*
        
        # case insensitive regex match - ECMAScript
        $ timer summary json --current-year --output timesheet_%Y-%m-%dT%H_%M_%S.json --match-note task.* --modifiers ig
        $ t su j -cy -o timesheet_%Y-%m-%dT%H_%M_%S.json -rn task.* -Mig\
        
        $ timer summary json --start jan1 --end jul1 billable is true --print
        $ t su j -sjan1 -ejul1 billable is true -p\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@start_option
@end_option
@all_option
@current_week_option
@current_month_option
@current_year_option
@round_option
@show_null_values
@match_project
@match_note
@modifiers
@regex_engine
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
    shell_complete=shell_complete.snapshot("timesheet", ".json"),
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
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: "CliQueryRoutines",
    start: datetime,
    end: datetime,
    all_: bool,
    current_week: bool,
    current_month: bool,
    current_year: bool,
    output: Path | None,
    round_: str,
    show_null_values: bool,
    print_: bool,
    orient: str,
    match_project: t.Sequence[str],
    match_note: t.Sequence[str],
    modifiers: str,
    regex_engine: str,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    """
    Create a summary and save to a json file, or print to terminal.

    [yellow][b][u]Note: running & paused entries are not included in summaries.[/b][/u][/yellow]

    [b]Fields[/]:
        - total_summary:  The sum of hours, ordered by date, project, billable.
        - total_project:  The sum of hours, partitioned by project, ordered by date, project, billable.
        - total_day:      The sum of hours, partitioned by day, ordered by date, project, billable.
        - date:           Date.
        - project:        Project.
        - billable:       Billable.
        - timer:          The sum of hours for a project on a given day.
        - notes:          String aggregate of all notes on that day. Notes separted by a newline.
                        Sum of hours appended to the end [#888888]('$NOTE - $HOURS')[/]

    --print / -p:
        print output to terminal.
        either this, or --output / -d must be provided.

    --output / -d:
        save the output of this command to this path.
        if the path does not have any suffix, then the expected suffix will be appended.
        if the path with the correct suffix already exists, a prompt will ask whether to overwrite or not.
        if the path ends in any suffix other than what's expected, an error will raise.
        autocomplete format: [code]timesheet_%Y-%m-%dT%H_%M_%S.json[/code]

    --round / -r:
        round totals to the nearest 0.05 / 0.10 / 0.25 / 0.50 / 1.

    --current-week / -cw:
    --current-month / -cm:
    --current-year / -cy:
        flags are processed before other date options.
        configure week start dates with app:config:set:general:week-start.

    --orient / -o:
        default is [code]records[/code].
        available choices are; columns, index, records, split, table, values.
            split = dict like {"index" -> [index], "columns" -> [columns], "data" -> [values]}
            records = list like [{column -> value}, … , {column -> value}]
            index = dict like {index -> {column -> value}}
            columns = dict like {column -> {index -> value}}
            values = just the values array
            table = dict like {"schema": {schema}, "data": {data}}

    --match-project / -rp:
        match a regular expression against project names.
        this option can be repeated, with each pattern being separated by `|`.

    --match-note / -rn:
        match a regular expression against entry notes.
        this option can be repeated, with each pattern being separated by `|`.

    --modifiers / -M:
        modifiers to pass to RegExp. (ECMAScript only)

    --regex-engine / -re:
        which regex engine to use.
        re2 = google's regular expression library used by all bigquery regex functions.
        ECMAScript = javascript regex syntax.

        example:
        re2 does not allow perl operator's such as negative lookaheads, while ECMAScript does.
        to run a case-insensitive regex match in re2, use the inline modifier [repr.str]"(?i)"[/repr.str],
        for ECMAScript, use the --modifiers / -M option with [repr.str]"i"[/repr.str]

    --prompt-where / -w:
        filter results with a where clause.
        interactive prompt that launches after command runs.
        prompt includes autocompletions for projects and notes.
        note autocompletions will only populate for a project
        if that project name appears in the string.

    [bold #34e2e2]WHERE[/]:
        all remaining arguments at the end of this command are
        joined together by a space to form the where clause.
        the word "WHERE" is stripped from the start of the string, if it exists.
    """
    if "android" in platform.release():
        console.print(
            "[b][red]summary:csv and summary:json not currently supported on android."
        )
        raise click.exceptions.Exit()

    ctx, parent = ctx_group

    validate.callbacks.print_or_output(output=truth(output), print_=print_)

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._summary(
            where=where_clause,
            match_project=match_project,
            match_note=match_note,
            modifiers=modifiers,
            regex_engine=regex_engine,
            round_=round_,
            show_null_values=not show_null_values,
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
                now, AppConfig().get("settings", "week-start", default=0)
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
            modifiers=modifiers,
            regex_engine=regex_engine,
            round_=round_,
            show_null_values=not show_null_values,
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
            with tempfile.TemporaryDirectory() as temp_dir:
                _summary = Path(temp_dir).joinpath(f"{uuid4()}.json")
                df.to_json(  # type: ignore[call-overload]
                    _summary.as_posix(),
                    orient=orient,
                    date_format="iso",
                    indent=4,
                )
                console.print_json(_summary.read_text("utf-8"))
        else:
            console.print_json(dest.read_text())
