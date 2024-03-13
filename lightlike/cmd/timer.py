from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha1
from operator import truth
from typing import TYPE_CHECKING, Any, Sequence

import rich_click as click
from google.api_core.exceptions import BadRequest
from more_itertools import first, one
from rich import box
from rich import print as rprint
from rich import print_json
from rich.console import Console
from rich.table import Table

from lightlike.__about__ import __appname_sc__
from lightlike.app import _get, _pass, render, shell_complete, threads, validate
from lightlike.app.config import AppConfig
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _help, dates
from lightlike.internal import utils
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from rich.console import Console

    from lightlike.app.cache import EntryAppData, EntryIdList, TomlCache
    from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = ("timers",)


@click.group(
    cls=AliasedRichGroup,
    short_help="Run & manage time entries.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def timer(debug: bool) -> None: ...


@timer.command(
    cls=_RichCommand,
    name="run",
    help=_help.timer_run,
    short_help="Start a new time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_run_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not start new time entry."),
)
@click.option(
    "-p",
    "--project",
    type=click.STRING,
    show_default=True,
    is_eager=True,
    required=True,
    expose_value=True,
    default="no-project",
    metavar="ACTIVE_PROJECT",
    callback=validate.active_project,
    help="Project to log entry under.",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-n",
    "--note",
    type=click.STRING,
    show_default=True,
    default="None",
    help="Add a new/existing note.",
    shell_complete=shell_complete.notes.from_param,
)
@click.option(
    "-b",
    "--billable",
    show_default=True,
    type=click.BOOL,
    is_eager=True,
    required=True,
    expose_value=True,
    shell_complete=shell_complete.Param("billable").bool,
    default=lambda: AppConfig().get("settings", "is_billable"),
    help="Flag entry as billable.",
)
@click.option(
    "-s",
    "--start",
    shell_complete=shell_complete.time,
    help="Earlier start time. Ignore option to start now.",
)
@_pass.cache
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@_pass.ctx_group(parents=1)
def run(
    ctx_group: Sequence[click.Context],
    id_list: "EntryIdList",
    appdata: "EntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    cache: "TomlCache",
    billable: bool,
    project: str,
    start: str,
    note: str,
) -> None:
    ctx, parent = ctx_group

    if cache:
        cache.start_new_active_timer()

    start_local = PromptFactory._parse_date(start) if start else AppConfig().now
    time_entry_id = sha1(f"{project}{note}{start_local}".encode()).hexdigest()
    query_job = routine.run_timer(time_entry_id, project, note, start_local, billable)

    with cache.update():
        cache.id = time_entry_id
        cache.project = project
        cache.note = note if note != "None" else None  # type: ignore[assignment]
        cache.is_billable = billable
        cache.start = start_local

    threads.spawn(ctx, appdata.update, kwargs=dict(query_job=query_job))
    threads.spawn(ctx, id_list.add, kwargs=dict(input_id=time_entry_id))

    if parent.params.get("debug"):
        console.print(
            f"Successfully ran timer: {cache._to_meta(cache.active, AppConfig().now)}"
        )


@timer.group(
    cls=AliasedRichGroup,
    name="list",
    short_help="List entries by date/date-range.",
)
def list_() -> None: ...


@list_.command(
    cls=_RichCommand,
    name="date",
    help=_help.timer_list_date,
    short_help="List entries on a given date.",
    context_settings=dict(
        allow_extra_args=True,
        allow_interspersed_args=True,
        obj=dict(syntax=_help.timer_list_date_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Canceled query."),
)
@click.argument(
    "date",
    type=click.STRING,
    required=True,
    shell_complete=shell_complete.time,
)
@click.option(
    "-w",
    "--where",
    is_flag=True,
    type=click.BOOL,
    help="Filter results with a WHERE clause. Prompts for input.",
)
@click.argument(
    "where_clause",
    nargs=-1,
    type=click.STRING,
    required=False,
    metavar="WHERE_CLAUSE",
)
@_pass.console
@_pass.routine
def list_date(
    routine: "CliQueryRoutines",
    console: "Console",
    date: str,
    where: bool,
    where_clause: Sequence[str],
) -> None:
    if date:
        date_local = PromptFactory._parse_date(date)
    else:
        date_local = PromptFactory.prompt_for_date("(date)")

    _where_clause = shell_complete.where._parse_click_options(
        flag=where, args=where_clause, console=console, routine=routine
    )

    query_job = routine.list_time_entries(date=date_local, where_clause=_where_clause)
    row_iterator = query_job.result()
    table = render.row_iter_to_rich_table(
        row_iterator=row_iterator,
    )

    if not table.row_count:
        console.print("[d]No entries found on %s." % date_local.date())
        return

    render.new_console_print(table)


@list_.command(
    cls=_RichCommand,
    name="range",
    help=_help.timer_list_range,
    short_help="List entries in a given date range.",
    context_settings=dict(
        allow_extra_args=True,
        allow_interspersed_args=True,
        obj=dict(syntax=_help.timer_list_range_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Canceled query."),
)
@click.argument(
    "start",
    type=click.STRING,
    nargs=1,
    required=False,
    shell_complete=shell_complete.time,
)
@click.argument(
    "end",
    type=click.STRING,
    nargs=1,
    required=False,
    shell_complete=shell_complete.time,
)
@click.option(
    "-cw",
    "--current-week",
    is_flag=True,
    type=click.BOOL,
    help="Use current week start/end dates.",
)
@click.option(
    "-w",
    "--where",
    is_flag=True,
    type=click.BOOL,
    help="Filter results with a WHERE clause. Prompts for input.",
)
@click.argument(
    "where_clause",
    nargs=-1,
    type=click.STRING,
    required=False,
    metavar="WHERE_CLAUSE",
)
@_pass.console
@_pass.routine
def list_range(
    routine: "CliQueryRoutines",
    console: "Console",
    start: str,
    end: str,
    current_week: bool,
    where: bool,
    where_clause: Sequence[str],
) -> None:
    date_range = (
        dates._get_current_week_range()
        if current_week
        else dates._parse_date_range_flags(start, end)
    )

    str_range = "%s -> %s" % (date_range.start.date(), date_range.end.date())

    _where_clause = shell_complete.where._parse_click_options(
        flag=where, args=where_clause, console=console, routine=routine
    )

    query_job = routine.list_time_entries_range(
        start_date=date_range.start,
        end_date=date_range.end,
        where_clause=_where_clause,
    )
    row_iterator = query_job.result()
    table = render.row_iter_to_rich_table(
        row_iterator=row_iterator,
    )

    if not table.row_count:
        console.print("[d]No entries found between %s." % str_range)
        return

    render.new_console_print(table)


@timer.command(
    cls=_RichCommand,
    name="delete",
    help=_help.timer_delete,
    no_args_is_help=True,
    short_help="Delete time entries by ID.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_delete_syntax),
    ),
)
@click.argument(
    "time_entry_ids",
    type=click.STRING,
    nargs=-1,
    required=True,
)
@_pass.routine
@_pass.appdata
@_pass.cache
@_pass.console
@_pass.id_list
@click.pass_context
def delete(
    ctx: click.Context,
    id_list: "EntryIdList",
    console: "Console",
    cache: "TomlCache",
    appdata: "EntryAppData",
    routine: "CliQueryRoutines",
    time_entry_ids: Sequence[str],
) -> None:
    with console.status("[status.message] Searching ID's") as status:
        for _id in time_entry_ids:
            status.update(f"[status.message] Matching entry ID: [code]{_id}[/code].")
            _id = id_list.match_id(_id)

            try:
                query_job = routine.delete_time_entry(
                    _id,
                    wait=True,
                    render=True,
                    status=status,
                    status_renderable="Deleting entry",
                )

                if query_job.error_result:
                    raise query_job._exception

                if cache.id == _id:
                    console.print("[bright_yellow]Active time entry found.")
                    cache._clear_active()
                    console.set_window_title(__appname_sc__)
                elif cache._if_any_entries(cache.running_entries, [_id]):
                    console.print("[bright_yellow]Running time entry found.")
                    cache._remove_entries([cache.running_entries], "id", [_id])

                if cache._if_any_entries(cache.paused_entries, [_id]):
                    console.print("[bright_yellow]Paused time entry found.")
                    cache._remove_entries([cache.paused_entries], "id", [_id])

                console.print(
                    f"[saved]Saved[/saved]. Deleted time entry [code]{_id}[/code]."
                )

            except BadRequest as e:
                console.print(
                    f"[b][red]Error matching[/red] [code]{_id}[/code][/b]: {e}"
                )

        threads.spawn(ctx, appdata.update, kwargs=dict(query_job=query_job))
        threads.spawn(ctx, id_list.reset)


class SetClause:
    def __init__(self, tz=AppConfig().tz) -> None:
        self._base = "SET "
        self._tz = tz

    def add_date(self, field: str, date_local: date) -> SetClause:
        self._base += f"`{field}` = DATE '{date_local}', "
        return self

    def add_datetime(self, field: str, date_local: datetime) -> SetClause:
        self._base += f"`{field}` = "
        self._base += self._extract_datetime_from_timestamp(date_local)
        return self

    def add_timestamp(self, field: str, date_local: datetime) -> SetClause:
        self._base += f"`{field}` = "
        self._base += self._timestamp(date_local)
        return self

    def add_duration(
        self,
        field: str,
        end_local: datetime | None,
        start_local: datetime,
        paused_hrs: int,
    ) -> SetClause:
        self._base += f"`{field}` = "
        self._base += self._duration(end_local, start_local, paused_hrs)
        return self

    def add_bool(self, field: str, value: bool) -> SetClause:
        self._base += f"`{field}` = {value}, "
        return self

    def add_string(self, field: str, value: str) -> SetClause:
        _value = re.compile(r"(\"|')").sub('\\"', value)
        self._base += f"`{field}` = '{_value}', "
        return self

    def _extract_datetime_from_timestamp(self, date_local: datetime) -> str:
        return f"EXTRACT(DATETIME FROM TIMESTAMP('{date_local}') AT TIME ZONE '{self._tz}'), "

    def _extract_date_from_timestamp(self, date_local: datetime) -> str:
        return (
            f"EXTRACT(DATE FROM TIMESTAMP('{date_local}') AT TIME ZONE '{self._tz}'), "
        )

    def _timestamp(self, date_local: datetime) -> str:
        return f"TIMESTAMP('{date_local}'), "

    def _duration(
        self,
        end_local: datetime | None,
        start_local: datetime,
        paused_hrs: int,
    ) -> str:
        fn = f'`{AppConfig().get("bigquery", "dataset")}.duration`'
        duration_end = f"TIMESTAMP('{end_local}')" if end_local else "NULL"
        return f"{fn}({duration_end}, TIMESTAMP('{start_local}'), FALSE, NULL, {paused_hrs or 'NULL'}), "

    def __repr__(self) -> str:
        return f'"{self._base[:-2]}"' if not self._base == "SET " else self._base


@timer.group(
    cls=AliasedRichGroup,
    help=_help.timer_edit_entry,
    short_help="Edit completed time entries.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_edit_entry_syntax),
    ),
)
def edit() -> None: ...


@edit.group(
    cls=AliasedRichGroup,
    name="entry",
    chain=True,
    help=_help.timer_edit_entry,
    short_help="Edit individual time entries by ID.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_edit_entry_syntax),
    ),
)
@click.option(
    "-i",
    "--id",
    "id_sequence",
    required=True,
    metavar="TIME_ENTRY_IDS",
    type=click.STRING,
    multiple=True,
    help="Time entry ID. Repeat flag to edit entries consecutively.",
)
def edit_entry(id_sequence: tuple[str]) -> None: ...


@edit_entry.command(
    cls=_RichCommand,
    name="note",
    help=_help.timer_edit_entry,
    short_help="Edit note.",
)
@click.argument(
    "note",
    type=click.STRING,
    required=True,
    shell_complete=shell_complete.notes.from_chained_cmd,
)
def _edit_note(note: str) -> dict[str, Any]:
    return {"note": note}


@edit_entry.command(
    cls=_RichCommand,
    name="project",
    short_help="Edit Project.",
    add_help_option=False,
)
@click.argument(
    "project",
    type=click.STRING,
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_chained_cmd,
)
def _edit_project(project: str) -> dict[str, Any]:
    return {"project": project}


@edit_entry.command(
    cls=_RichCommand,
    name="start",
    short_help="Edit start-time.",
    add_help_option=False,
)
@click.argument(
    "start",
    type=click.STRING,
    required=True,
    shell_complete=shell_complete.time,
)
def _edit_start(start: str) -> dict[str, Any]:
    return {"start": PromptFactory._parse_date(start)}


@edit_entry.command(
    cls=_RichCommand,
    name="end",
    short_help="Edit end-time.",
    add_help_option=False,
)
@click.argument(
    "end",
    type=click.STRING,
    required=True,
    shell_complete=shell_complete.time,
)
def _edit_end(end: str) -> dict[str, Any]:
    return {"end": PromptFactory._parse_date(end)}


@edit_entry.command(
    cls=_RichCommand,
    name="date",
    short_help="Edit date.",
    add_help_option=False,
)
@click.argument(
    "date",
    type=click.STRING,
    shell_complete=shell_complete.time,
)
def _edit_date(date: str) -> dict[str, Any]:
    return {"date": PromptFactory._parse_date(date)}


@edit_entry.command(
    cls=_RichCommand,
    name="billable",
    short_help="Edit billable flag.",
    add_help_option=False,
)
@click.argument(
    "billable",
    type=click.BOOL,
    shell_complete=shell_complete.Param("billable").bool,
)
def _edit_billable(billable: bool) -> dict[str, Any]:
    return {"billable": billable}


@edit_entry.result_callback()
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not edit entry."),
)
@_pass.cache
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@click.pass_context
def _edit_entry_callback(
    ctx: click.Context,
    id_list: "EntryIdList",
    appdata: "EntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    cache: "TomlCache",
    editors: Sequence[dict[str, Any]],
    id_sequence: tuple[str],
) -> None:
    validate.callbacks.edit_params(locals())

    edits: dict[str, Any] = {}
    for m in editors:
        edits |= m

    for _id in id_sequence:
        with console.status(
            status=f"[status.message] Searching for time entry ID: [code]{_id}[/code]"
        ) as status:
            set_clause = SetClause()

            _id = id_list.match_id(_id)

            try:
                time_entry = first(routine.get_time_entry(_id))
            except Exception as e:
                console.print(f"[b][red]Error:[/b] {e}")
                continue

        console.print(f"Found matching ID: [code]{time_entry.id}[/code].")

        if "billable" in edits:
            billable = edits["billable"]
            utils.print_updated_val("billable", billable, prefix=None)
            set_clause.add_bool("is_billable", billable)

        if "project" in edits:
            project = edits["project"]
            utils.print_updated_val("project", project, prefix=None)
            set_clause.add_string("project", project)

        if "note" in edits:
            note = edits["note"]
            utils.print_updated_val("note", note, prefix=None)
            set_clause.add_string("note", note)

        _date, _start, _end = edits.get("date"), edits.get("start"), edits.get("end")

        match truth(_date), truth(_start), truth(_end):
            case True, True, True:
                new_date = _date.date()  # type: ignore[union-attr]
                new_start = datetime.combine(new_date, _start.time())  # type: ignore[union-attr]
                new_end = datetime.combine(new_date, _end.time())  # type: ignore[union-attr]
                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(time_entry.paused_hrs or 0) * 3600
                )
                duration = new_end - new_start

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set end before start."
                        ),
                        ctx=ctx,
                    )

                duration = duration - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{time_entry.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                total_seconds = int(duration.total_seconds())
                dhour = round(total_seconds % (24 * 3600) / 3600, 3)

                utils.print_updated_val("date", new_date, prefix=None)
                utils.print_updated_val("start", new_start.time(), prefix=None)
                utils.print_updated_val("end", new_end.time(), prefix=None)
                console.print("Updating duration.")
                if time_entry.paused_hrs:
                    console.print(
                        "Subtracing paused hours "
                        f"[repr.number]{time_entry.paused_hrs}[/repr.number]."
                    )
                utils.print_updated_val(
                    "duration",
                    f"[repr.number]{duration}[/repr.number] ([repr.number]{dhour}[/repr.number])",
                    prefix=None,
                )

                set_clause = (
                    set_clause.add_date("date", new_date)
                    .add_datetime("start", new_start)
                    .add_datetime("end", new_end)
                    .add_timestamp("timestamp_start", new_start)
                    .add_timestamp("timestamp_end", new_end)
                    .add_duration(
                        "duration",
                        new_end,
                        new_start,
                        time_entry.paused_hrs,
                    )
                )

            case True, True, False:
                new_date = _date.date()  # type: ignore[union-attr]
                new_start = datetime.combine(new_date, _start.time())  # type: ignore[union-attr]
                current_end = time_entry.end.replace(microsecond=0)
                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(time_entry.paused_hrs or 0) * 3600
                )
                duration = current_end - new_start

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set start before end."
                        ),
                        ctx=ctx,
                    )

                duration = duration - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{time_entry.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                total_seconds = int(duration.total_seconds())
                dhour = round(total_seconds % (24 * 3600) / 3600, 3)

                utils.print_updated_val("date", new_date, prefix=None)
                utils.print_updated_val("start", new_start.time(), prefix=None)
                console.print("Updating duration with new start.")
                if time_entry.paused_hrs:
                    console.print(
                        "Subtracing paused hours "
                        f"[repr.number]{time_entry.paused_hrs}[/repr.number]."
                    )
                utils.print_updated_val(
                    "duration",
                    f"[repr.number]{duration}[/repr.number] ([repr.number]{dhour}[/repr.number])",
                    prefix=None,
                )

                set_clause = (
                    set_clause.add_date("date", new_date)
                    .add_datetime("start", new_start)
                    .add_timestamp("timestamp_start", new_start)
                    .add_duration(
                        "duration",
                        current_end,
                        new_start,
                        time_entry.paused_hrs,
                    )
                )

            case True, False, False:
                new_date = _date.date()  # type: ignore[union-attr]
                new_start = datetime.combine(new_date, time_entry.start.replace(microsecond=0).time())  # type: ignore[union-attr]
                new_end = datetime.combine(new_date, time_entry.end.replace(microsecond=0).time())  # type: ignore[union-attr]

                utils.print_updated_val("date", new_date, prefix=None)
                utils.print_updated_val("start", new_start, prefix=None)
                utils.print_updated_val("end", new_end, prefix=None)

                set_clause = (
                    set_clause.add_date("date", new_date)
                    .add_datetime("start", new_start)
                    .add_timestamp("timestamp_start", new_start)
                    .add_datetime("end", new_end)
                    .add_timestamp("timestamp_end", new_end)
                )

            case True, False, True:
                new_date = _date.date()  # type: ignore[union-attr]
                current_start = time_entry.start.replace(microsecond=0)
                new_end = datetime.combine(new_date, _end.time())  # type: ignore[union-attr]

                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(time_entry.paused_hrs or 0) * 3600
                )
                duration = new_end - current_start

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set end before start."
                        ),
                        ctx=ctx,
                    )

                duration = duration - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{time_entry.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                total_seconds = int(duration.total_seconds())
                dhour = round(total_seconds % (24 * 3600) / 3600, 3)

                utils.print_updated_val("date", new_date, prefix=None)
                utils.print_updated_val("end", new_end.time(), prefix=None)
                console.print("Updating duration with new end.")
                if time_entry.paused_hrs:
                    console.print(
                        "Subtracing paused hours "
                        f"[repr.number]{time_entry.paused_hrs}[/repr.number]."
                    )
                utils.print_updated_val(
                    "duration",
                    f"[repr.number]{duration}[/repr.number] ([repr.number]{dhour}[/repr.number])",
                    prefix=None,
                )

                set_clause = (
                    set_clause.add_date("date", new_date)
                    .add_datetime("end", new_end)
                    .add_timestamp("timestamp_end", new_end)
                    .add_duration(
                        "duration",
                        new_end,
                        current_start,
                        time_entry.paused_hrs,
                    )
                )

            case False, True, False:
                new_start = datetime.combine(time_entry.date, _start.time())  # type: ignore[union-attr]
                current_end = time_entry.end.replace(microsecond=0)

                if new_start > current_end:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set start before end. "
                            "(Try editing both start and date fields)."
                        ),
                        ctx=ctx,
                    )

                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(time_entry.paused_hrs or 0) * 3600
                )
                duration = current_end - new_start
                duration = duration - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{time_entry.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                total_seconds = int(duration.total_seconds())
                dhour = round(total_seconds % (24 * 3600) / 3600, 3)

                utils.print_updated_val("start", new_start.time(), prefix=None)
                console.print("Updating duration with new start.")
                if time_entry.paused_hrs:
                    console.print(
                        "Subtracing paused hours "
                        f"[repr.number]{time_entry.paused_hrs}[/repr.number]."
                    )
                utils.print_updated_val(
                    "duration",
                    f"[repr.number]{duration}[/repr.number] ([repr.number]{dhour}[/repr.number])",
                    prefix=None,
                )

                set_clause = (
                    set_clause.add_datetime("start", new_start)
                    .add_timestamp("timestamp_start", new_start)
                    .add_duration(
                        "duration",
                        current_end,
                        new_start,
                        time_entry.paused_hrs,
                    )
                )

            case False, False, True:
                current_start = time_entry.start.replace(microsecond=0)
                new_end = datetime.combine(time_entry.date, _end.time())  # type: ignore[union-attr]

                if new_end < current_start:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set end before start. "
                            "(Try editing both end and date fields)."
                        ),
                        ctx=ctx,
                    )

                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(time_entry.paused_hrs or 0) * 3600
                )
                duration = new_end - current_start

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set end before start."
                        ),
                        ctx=ctx,
                    )

                duration = duration - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{time_entry.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                total_seconds = int(duration.total_seconds())
                dhour = round(total_seconds % (24 * 3600) / 3600, 3)

                utils.print_updated_val("end", new_end.time(), prefix=None)
                console.print("Updating duration with new end.")
                if time_entry.paused_hrs:
                    console.print(
                        "Subtracing paused hours "
                        f"[repr.number]{time_entry.paused_hrs}[/repr.number]."
                    )
                utils.print_updated_val(
                    "duration",
                    f"[repr.number]{duration}[/repr.number] ([repr.number]{dhour}[/repr.number])",
                    prefix=None,
                )

                set_clause = (
                    set_clause.add_datetime("end", new_end)
                    .add_timestamp("timestamp_end", new_end)
                    .add_duration(
                        "duration",
                        new_end,
                        current_start,
                        time_entry.paused_hrs,
                    )
                )

            case False, True, True:
                new_start = datetime.combine(time_entry.date, _start.time())  # type: ignore[union-attr]
                new_end = datetime.combine(time_entry.date, _end.time())  # type: ignore[union-attr]
                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(time_entry.paused_hrs or 0) * 3600
                )
                duration = new_end - new_start

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: Cannot set end before start."
                        ),
                        ctx=ctx,
                    )

                duration = duration - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{time_entry.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                total_seconds = int(duration.total_seconds())
                dhour = round(total_seconds % (24 * 3600) / 3600, 3)

                utils.print_updated_val("start", new_start.time(), prefix=None)
                utils.print_updated_val("end", new_end.time(), prefix=None)
                console.print("Updating duration.")
                if time_entry.paused_hrs:
                    console.print(
                        "Subtracing paused hours "
                        f"[repr.number]{time_entry.paused_hrs}[/repr.number]."
                    )
                utils.print_updated_val(
                    "duration",
                    f"[repr.number]{duration}[/repr.number] ([repr.number]{dhour}[/repr.number])",
                    prefix=None,
                )

                set_clause = (
                    set_clause.add_datetime("start", new_start)
                    .add_timestamp("timestamp_start", new_start)
                    .add_datetime("end", new_end)
                    .add_timestamp("timestamp_end", new_end)
                    .add_duration(
                        "duration",
                        new_end,
                        new_start,
                        time_entry.paused_hrs,
                    )
                )

        status_renderable = f"[status.message] Editing entry: [code]{_id}[/code]"
        with console.status(status_renderable) as status:
            query_job = routine.edit_time_entry(
                set_clause=set_clause,
                id=time_entry.id,
                wait=True,
                render=True,
                status=status,
                status_renderable=status_renderable,
            )

            table = Table(
                box=box.MARKDOWN,
                border_style="bold",
                show_header=True,
                show_edge=True,
            )
            keys = ["id", "project", "date", "start", "end", "note", "billable"]

            original_record = {
                "id": time_entry.id[:7],
                "project": time_entry.project,
                "date": time_entry.date,
                "start": time_entry.start.time().replace(microsecond=0),
                "end": time_entry.end.time().replace(microsecond=0),
                "note": time_entry.note,
                "billable": time_entry.is_billable,
            }
            new_record = {}
            _edits = {}

            for k in keys:
                if k in edits:
                    if k in ("start", "end"):
                        _edits[k] = edits[k].time()
                    elif k in ("date"):
                        _edits[k] = edits[k].date()
                    else:
                        _edits[k] = edits[k]

                if _edits.get(k) is None:
                    table.add_column(
                        k,
                        **render._map_s_column_type(
                            one({k: original_record[k]}.items()), no_color=True
                        ),
                    )
                    new_record[k] = f"{original_record[k]}"
                else:
                    if f"{original_record[k]}" == f"{_edits[k]}":
                        table.add_column(
                            k,
                            header_style="yellow",
                            **render._map_s_column_type(
                                one({k: _edits[k]}.items()), no_color=True
                            ),
                        )
                        new_record[k] = f"[yellow]{_edits[k]}[/yellow]"
                    else:
                        table.add_column(
                            k,
                            header_style="green",
                            **render._map_s_column_type(
                                one({k: _edits[k]}.items()), no_color=True
                            ),
                        )
                        new_record[k] = (
                            f"[s][d][red]{original_record[k]}[/s][/d][/red] "
                            f"[b][green]{_edits[k]}[/b][/green]"
                        )

            console.print(f"[saved]Saved[/saved]. Updated record:")
            table.add_row(*render.map_cell_style(new_record.values()))
            render.new_console_print(table, status=status)

    if "note" in edits:
        threads.spawn(ctx, appdata.update, kwargs=dict(query_job=query_job))


@edit.command(
    cls=_RichCommand,
    name="group",
    add_help_option=False,
    options_metavar="",
    short_help="Not implemented.",
)
def edit_group() -> None:
    raise click.UsageError("Function is not implemented yet.")


@timer.command(
    cls=_RichCommand,
    name="add",
    help=_help.timer_add,
    short_help="Retroactively add a time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_add_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not add new time entry."),
)
@click.option(
    "-p",
    "--project",
    type=click.STRING,
    is_eager=True,
    expose_value=True,
    show_default=True,
    metavar="ACTIVE_PROJECT",
    help="Prompts for project if not provided.",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-s",
    "--start",
    type=click.STRING,
    help="Prompts for start if not provided.",
    shell_complete=shell_complete.time,
)
@click.option(
    "-e",
    "--end",
    type=click.STRING,
    help="Prompts for end if not provided.",
    shell_complete=shell_complete.time,
)
@click.option(
    "-n",
    "--note",
    type=click.STRING,
    show_default=True,
    help="Prompts for note if not provided.",
    shell_complete=shell_complete.notes.from_param,
)
@click.option(
    "-b",
    "--billable",
    type=click.BOOL,
    help="Set time entries billable flag.",
    shell_complete=shell_complete.Param("billable").bool,
)
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@click.pass_context
def add(
    ctx: click.Context,
    id_list: "EntryIdList",
    appdata: "EntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    project: str,
    start: str,
    end: str,
    note: str,
    billable: bool,
) -> None:
    if not project:
        project = PromptFactory.prompt_project()

    if start:
        start_local = PromptFactory._parse_date(start)
        if not start_local:
            start_local = PromptFactory.prompt_for_date("(start-date)")
    else:
        start_local = PromptFactory.prompt_for_date("(start-date)")

    if end:
        end_local = PromptFactory._parse_date(end)
        if not end_local:
            end_local = PromptFactory.prompt_for_date("(end-date)")
    else:
        end_local = PromptFactory.prompt_for_date("(end-date)")

    duration = end_local - start_local
    total_seconds = int(duration.total_seconds())
    dhour = round(total_seconds % (24 * 3600) / 3600, 3)

    if total_seconds < 0 or _get.sign(duration.days) == -1:
        raise click.BadArgumentUsage(
            message=(
                "Invalid value for args [[args]START[/args]] | "
                "[[args]END[/args]]: Cannot set end before start."
            ),
            ctx=ctx,
        )

    if billable is None:
        billable = AppConfig().get("settings", "is_billable")

    time_entry_id = sha1(f"{project}{note}{start_local}".encode()).hexdigest()

    status_renderable = "[status.message] Adding time entry"
    with console.status(status_renderable) as status:
        query_job = routine.add_timer(
            id=time_entry_id,
            project=project,
            note=note,
            start_time=start_local,
            end_time=end_local,
            is_billable=billable,
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        if note != "None":
            threads.spawn(ctx, appdata.update, kwargs=dict(query_job=query_job))

        threads.spawn(ctx, id_list.reset)

        console.print(f"[saved]Saved[/saved]. Added record:")
        render.new_console_print(
            render.mappings_list_to_rich_table(
                [
                    {
                        "id": time_entry_id[:7],
                        "project": project,
                        "date": start_local.date(),
                        "start": start_local.time(),
                        "end": end_local.time(),
                        "note": note or "None",
                        "billable": billable,
                        "duration": dhour,
                    }
                ],
            ),
            status=status,
        )


@timer.command(
    cls=_RichCommand,
    name="get",
    no_args_is_help=True,
    short_help="Get a time entry by ID.",
    help=_help.timer_get,
    context_settings=dict(
        obj=dict(syntax=_help.timer_get_syntax),
    ),
)
@click.argument("time_entry_id", type=click.STRING, required=True)
@click.option("-j", "--json", "json_", is_flag=True, help="Get row as json.")
@_pass.routine
@_pass.id_list
def get(
    id_list: "EntryIdList",
    routine: "CliQueryRoutines",
    time_entry_id: str,
    json_: bool,
) -> None:
    _id = id_list.match_id(time_entry_id)
    query_job = routine.get_time_entry(_id, wait=True, render=True)
    row_iterator = query_job.result()

    if json_:
        row = one(row_iterator)
        data = {k: v for k, v in row.items()}
        print_json(data=data, default=str, indent=4)
    else:
        table = render.row_iter_to_rich_table(row_iterator=row_iterator)
        render.new_console_print(table)


@timer.command(
    cls=_RichCommand,
    name="stop",
    help=_help.timer_stop,
    short_help="Stop the active time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_stop_syntax),
    ),
)
@_pass.routine
@_pass.console
@_pass.active_time_entry
def stop(
    cache: "TomlCache",
    console: "Console",
    routine: "CliQueryRoutines",
) -> None:
    routine.end_time_entry(cache.id)
    cache._clear_active()
    console.set_window_title(__appname_sc__)


@timer.command(
    cls=_RichCommand,
    name="end",
    hidden=True,
    help=_help.timer_stop,
    context_settings=dict(
        obj=dict(syntax=_help.timer_stop_syntax),
    ),
)
@click.pass_context
def end(ctx: click.Context) -> None:
    ctx.invoke(stop)


@timer.command(
    cls=_RichCommand,
    name="show",
    help=_help.timer_show,
    short_help="Show running and paused time entries.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_show_syntax),
    ),
)
@click.option("-j", "--json", "json_", is_flag=True, help="Show cache as json.")
@_pass.cache
def show(cache: "TomlCache", json_: bool) -> None:
    if json_:
        print_json(data=cache._entries, default=str, indent=4)
    else:
        render.new_console_print(cache)


@timer.command(
    cls=_RichCommand,
    name="pause",
    help=_help.timer_pause,
    short_help="Pause the active time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_pause_syntax),
    ),
)
@_pass.routine
@_pass.console
@_pass.active_time_entry
@_pass.ctx_group(parents=1)
def pause(
    ctx_group: Sequence[click.Context],
    cache: "TomlCache",
    console: "Console",
    routine: "CliQueryRoutines",
) -> None:
    ctx, parent = ctx_group

    time_paused = AppConfig().now
    routine.pause_timer(cache.id, time_paused)
    cache.put_active_entry_on_pause(time_paused)
    console.set_window_title(__appname_sc__)

    if parent.params.get("debug"):
        paused_entry = cache._to_meta(cache.paused_entries[0], AppConfig().now)
        console.print(f"Successfully paused timer: {paused_entry}")


@timer.command(
    cls=_RichCommand,
    name="resume",
    help=_help.timer_resume,
    short_help="Resume a paused time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_resume_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not resume time entry."),
)
@click.argument(
    "entry",
    type=click.STRING,
    required=False,
    shell_complete=shell_complete.entries.paused,
)
@_pass.routine
@_pass.cache
@_pass.console
@_pass.id_list
@click.pass_context
def resume(
    ctx: click.Context,
    id_list: "EntryIdList",
    console: "Console",
    cache: "TomlCache",
    routine: "CliQueryRoutines",
    entry: str,
) -> None:
    if not cache.paused_entries:
        console.print("[d]No paused time entries.")
        return

    now = AppConfig().now
    if not entry:
        paused_entries = cache.get_updated_paused_entries(now)

        table = render.mappings_list_to_rich_table(mappings_list=paused_entries)
        render.new_console_print(table)

        select = _questionary.select(
            message="Which time entry do you want to resume?",
            choices=list(map(_get.id, paused_entries)),
        )

        cache.resume_paused_time_entry(select, now)
        routine.resume_timer(cache.id, now)
    else:
        entry = id_list.match_id(entry)
        if cache._find_entries(cache.paused_entries, "id", [entry]):
            cache.resume_paused_time_entry(entry, now)
            routine.resume_timer(cache.id, now)
        else:
            raise click.BadParameter(message="This entry is not paused.", ctx=ctx)


@timer.command(
    cls=_RichCommand,
    name="switch",
    help=_help.timer_switch,
    short_help="Switch the active time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_switch_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not switch time entries."),
)
@_pass.console
@_pass.active_time_entry
def switch(
    cache: "TomlCache",
    console: "Console",
) -> None:
    if cache.count_running_entries == 1:
        console.print(
            "[d]Only 1 running time entry. Nothing to switch too.",
        )
        return

    table = render.mappings_list_to_rich_table(mappings_list=cache.running_entries)
    render.new_console_print(table)

    select = _questionary.select(
        message="Select a time entry.",
        instruction="(active entry highlighted)",
        choices=list(map(_get.id, cache.running_entries)),
        default=cache.id,
    )

    if select == cache.id:
        console.print("[d]Already active.")
        return

    cache.switch_active_entry(select)


@timer.command(
    cls=_RichCommand,
    name="update",
    help=_help.timer_update,
    short_help="Update the active time entry.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_update_syntax),
    ),
)
@click.option(
    "-p",
    "--project",
    type=click.STRING,
    is_eager=True,
    expose_value=True,
    show_default=True,
    metavar="ACTIVE_PROJECT",
    help="Project to log entry under.",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-n",
    "--note",
    type=click.STRING,
    show_default=True,
    is_eager=True,
    expose_value=True,
    help="Write a new note.",
    shell_complete=shell_complete.notes.from_cache,
)
@click.option(
    "-s",
    "--start_time",
    type=click.STRING,
    is_eager=True,
    expose_value=True,
    help="Change the start.",
    shell_complete=shell_complete.cached_timer_start,
)
@click.option(
    "-b",
    "--billable",
    type=click.BOOL,
    is_eager=True,
    expose_value=True,
    help="Update billable flag.",
    shell_complete=shell_complete.Param("billable").bool,
)
@_pass.routine
@_pass.active_time_entry
@_pass.console
@_pass.appdata
@click.pass_context
def update(
    ctx: click.Context,
    appdata: "EntryAppData",
    console: "Console",
    cache: "TomlCache",
    routine: "CliQueryRoutines",
    billable: bool,
    project: str,
    start_time: str,
    note: str,
) -> None:
    status_renderable = f"[status.message] Updating time entry: [code]{cache.id}[/code]"
    with console.status(status_renderable) as status:
        set_clause = SetClause()

        with cache.update():
            if note is not None:
                updated_note = re.compile(r"(\"|')").sub("", note)
                set_clause.add_string("note", updated_note)
                cache.note = updated_note

            if start_time is not None:
                start = PromptFactory._parse_date(start_time)
                new_start = AppConfig().in_app_timezone(
                    datetime.combine(cache.start.date(), start.time())
                )
                phours, pminutes, pseconds = utils._sec_to_time_parts(
                    Decimal(cache.paused_hrs or 0) * 3600
                )
                duration = (AppConfig().now - new_start) - timedelta(
                    hours=phours, minutes=pminutes, seconds=pseconds
                )

                if duration.total_seconds() < 0 or _get.sign(duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message=(
                            "Invalid value for args [[args]START[/args]] | "
                            "[[args]END[/args]]: New duration cannot be negative. "
                            f"Existing paused hours = [repr.number]{cache.paused_hrs}[/repr.number]"
                        ),
                        ctx=ctx,
                    )

                set_clause.add_timestamp("timestamp_start", new_start)
                set_clause.add_datetime("start", new_start)
                cache.start = new_start

            if billable is not None:
                set_clause.add_bool("is_billable", billable)
                cache.is_billable = billable

            if project is not None:
                validate.active_project(ctx, None, project)  # type: ignore[arg-type]
                set_clause.add_string("project", project)
                cache.project = project

        query_job = routine.edit_time_entry(
            set_clause=set_clause,
            id=cache.id,
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        if note is not None:
            threads.spawn(ctx, appdata.update, kwargs=dict(query_job=query_job))
            utils.print_updated_val(key="note", val=updated_note)
        if start_time is not None:
            utils.print_updated_val(key="start", val=new_start)
        if billable is not None:
            utils.print_updated_val(key="is_billable", val=billable)
        if project is not None:
            utils.print_updated_val(key="project", val=project)


@timer.group(
    cls=AliasedRichGroup,
    help=_help.timer_notes_update,
    short_help="Manage notes.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_notes_update_syntax),
    ),
)
def notes() -> None:
    """Manage time entry notes."""


@notes.command(
    cls=_RichCommand,
    name="update",
    no_args_is_help=True,
    help=_help.timer_notes_update,
    short_help="Bulk update notes for a project.",
    context_settings=dict(
        obj=dict(syntax=_help.timer_notes_update_syntax),
    ),
)
@click.argument(
    "project",
    nargs=1,
    type=click.STRING,
    required=True,
    metavar="ACTIVE_PROJECT",
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_argument,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not update notes."),
)
@_pass.routine
@_pass.console
@_pass.appdata
@click.pass_context
def update_notes(
    ctx: click.Context,
    appdata: "EntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    project: str,
) -> None:
    try:
        notes_to_edit = _questionary.checkbox(
            message="Select notes to edit",
            choices=shell_complete.notes.Notes().get(project),
        )
    except AttributeError:
        console.print(
            f"[code]{project}[/code] has no notes to edit.\n"
            "If this was not the expected outcome, "
            "try adjusting the lookback window for time entry notes with the command "
            "[code.command]app[/code.command]:[code.command]settings[/code.command]:"
            "[code.command]update[/code.command]:[code.command]note-history[/code.command]"
        )
        return

    if not notes_to_edit:
        console.print(f"[d]No notes selected. Nothing happened.")
        return

    notes_to_replace = "\n".join(
        map(lambda n: utils._alter_str(n, add_quotes=True), notes_to_edit)
    )

    new_note = PromptFactory.prompt_note(
        project,
        message="(new-note)",
        rprompt="\nNotes being replaced:\n%s" % notes_to_replace,
        bottom_toolbar=lambda: "Replacing notes for %s." % project,
    )

    query_job = routine.update_notes(
        new_note=new_note,
        old_note="".join(["(", "|".join(n for n in notes_to_edit), ")"]),
        project=project,
        wait=True,
        render=True,
        status_renderable="Updating notes",
    )

    threads.spawn(ctx, appdata.update, kwargs=dict(query_job=query_job))
    console.print("[saved]Saved[/saved]. Updated notes for [code]%s[/code]." % project)
