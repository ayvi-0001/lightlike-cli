# mypy: disable-error-code="func-returns-value"

import re
import typing as t
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha1
from inspect import cleandoc
from json import dumps, loads
from math import copysign
from operator import truth

import rich_click as click
from more_itertools import first, locate, one
from prompt_toolkit.patch_stdout import patch_stdout
from rich import print as rprint
from rich.text import Text

from lightlike.__about__ import __appname_sc__
from lightlike.app import _get, _pass, dates, render, shell_complete, threads, validate
from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.app.core import AliasedRichGroup, DynamicHelpOption, FmtRichCommand
from lightlike.app.prompt import PromptFactory
from lightlike.app.shell_complete.types import CallableIntRange
from lightlike.cmd import _help
from lightlike.internal import appdir, markup, utils
from lightlike.lib.third_party import _questionary

if t.TYPE_CHECKING:
    from google.cloud.bigquery import QueryJob
    from google.cloud.bigquery.table import Row
    from rich.console import Console
    from rich.table import Table

    from lightlike.app.cache import TimeEntryAppData, TimeEntryIdList
    from lightlike.app.routines import CliQueryRoutines

__all__: t.Sequence[str] = (
    "add",
    "delete",
    "edit",
    "get",
    "list_",
    "notes",
    "pause",
    "resume",
    "run",
    "show",
    "stop",
    "end",
    "switch",
    "update",
)


P = t.ParamSpec("P")


def default_timer_add(config: AppConfig) -> str:
    timer_add_min: int = config.get("settings", "timer_add_min", default=-6)
    minutes = -timer_add_min if copysign(1, timer_add_min) != -1 else timer_add_min
    return f"{minutes} minutes"


@click.command(
    cls=FmtRichCommand,
    name="add",
    help=_help.timer_add,
    short_help="Insert a time entry.",
    syntax=_help.timer_add_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not add time entry.")),
)
@click.option(
    "-p",
    "--project",
    show_default=True,
    multiple=False,
    type=shell_complete.projects.ActiveProject,
    help=None,
    required=True,
    default="no-project",
    callback=validate.active_project,
    metavar="TEXT",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-s",
    "--start",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=True,
    default=lambda: default_timer_add(config=AppConfig()),
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-e",
    "--end",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=True,
    default="now",
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-n",
    "--note",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default="None",
    callback=None,
    metavar=None,
    shell_complete=shell_complete.notes.from_param,
)
@click.option(
    "-b",
    "--billable",
    show_default=True,
    multiple=False,
    type=click.BOOL,
    help=None,
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.Param("billable").bool,
)
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@_pass.ctx_group(parents=1)
@_pass.now
def add(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    id_list: "TimeEntryIdList",
    appdata: "TimeEntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    project: str,
    start: datetime,
    end: datetime,
    note: str,
    billable: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    project = project or PromptFactory.prompt_project()
    start_param = one(filter(lambda p: p.name == "start", ctx.command.params))
    end_param = one(filter(lambda p: p.name == "end", ctx.command.params))
    start_default = t.cast(float, start_param.get_default(ctx, call=True))
    end_default = t.cast(str, end_param.get_default(ctx))
    date_params = dates.parse_date_range_flags(
        start=(
            start
            if f"{start}" != f"{start_default}"
            else now - timedelta(minutes=-start_default)
        ),
        end=(end if f"{end}" != f"{end_default}" else now),
    )

    end_local, start_local, total_seconds = (
        date_params.end,
        date_params.start,
        date_params.total_seconds,
    )
    hours = round(total_seconds / 3600, 4)

    active_projects: dict[str, t.Any]
    try:
        data = appdata.load()
        active_projects = data["active"]
        project_default_billable: bool = active_projects[project]["default_billable"]
    except KeyError:
        appdata.sync()
        data = appdata.load()
        active_projects = data["active"]
        project_default_billable = active_projects[project]["default_billable"]

    debug and patch_stdout(raw=True)(console.log)(
        "[DEBUG]:",
        "getting projects default billable value:",
        project_default_billable,
    )

    time_entry_id = sha1(f"{project}{note}{start_local}".encode()).hexdigest()

    status_renderable = markup.status_message("Adding time entry")
    with console.status(status_renderable) as status:
        query_job: "QueryJob" = routine.add_time_entry(
            id=time_entry_id,
            project=project,
            note=note,
            start_time=start_local,
            end_time=end_local,
            billable=billable or project_default_billable,
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        threads.spawn(ctx, id_list.reset)
        note != "None" and threads.spawn(
            ctx, appdata.sync, dict(trigger_query_job=query_job, debug=debug)
        )

        table: Table = render.map_sequence_to_rich_table(
            mappings=[
                {
                    "id": time_entry_id[:7],
                    "project": project,
                    "date": start_local.date(),
                    "start": start_local.time(),
                    "end": end_local.time(),
                    "note": note or "None",
                    "billable": billable or project_default_billable,
                    "hours": hours,
                }
            ],
            string_ctype=["project", "note", "id"],
            bool_ctype=["billable"],
            num_ctype=["paused_hours", "hours"],
            time_ctype=["start", "end"],
            date_ctype=["date"],
        )

    console.print("Added record:")
    console.print(table)


def yank_flag_help() -> str:
    if appdir.TIMER_LIST_CACHE.exists():
        timer_list_cache = loads(appdir.TIMER_LIST_CACHE.read_text())
        len_cache = len(timer_list_cache)
        if len_cache > 0:
            return f"Pull id from latest timer:list cmd. Cache range: 1<=x<={len_cache}"

    return "Pull id from latest timer:list cmd. Current cache is empty."


@click.command(
    cls=FmtRichCommand,
    name="delete",
    no_args_is_help=True,
    help=_help.timer_delete,
    short_help="Delete time entries by id.",
    syntax=_help.timer_delete_syntax,
)
@click.option(
    "-i",
    "--id",
    "id_options",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Repeat flag to pass multiple ids.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-u",
    "--use-last-timer-list",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Use all ids from the latest timer:list cmd.",
    required=False,
    default=None,
    callback=validate.callbacks.timer_list_cache_exists,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-y",
    "--yank",
    cls=DynamicHelpOption,
    show_default=True,
    multiple=True,
    type=CallableIntRange(1, lambda: len(loads(appdir.TIMER_LIST_CACHE.read_text()))),
    help=yank_flag_help,
    required=False,
    default=None,
    callback=validate.callbacks.timer_list_cache_idx,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.appdata
@_pass.cache
@_pass.console
@_pass.id_list
@_pass.ctx_group(parents=1)
def delete(
    ctx_group: t.Sequence[click.RichContext],
    id_list: "TimeEntryIdList",
    console: "Console",
    cache: "TimeEntryCache",
    appdata: "TimeEntryAppData",
    routine: "CliQueryRoutines",
    id_options: list[str],
    use_last_timer_list: list[str],
    yank: list[str],
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    ids_to_match: list[str] = [
        *(id_options or []),
        *(yank or []),
        *(use_last_timer_list or []),
    ]

    if not ids_to_match:
        param = one(filter(lambda p: p.name == "id_options", ctx.command.params))
        raise click.MissingParameter(ctx=ctx, param=param)

    with console.status(
        status=markup.status_message("Matching time entry ids")
    ) as status:
        matched_ids, non_matched_ids = _match_ids(
            ctx=ctx,
            id_list=id_list,
            ids_to_match=ids_to_match,
        )
        console.print(markup.saved("Matched "), matched_ids, end="")
        non_matched_ids and console.print(
            markup.red("Non-matched "), non_matched_ids, end=""
        )
        status.update(markup.status_message("Retrieving data."))

        for id_match in matched_ids:
            if cache.id == id_match:
                console.print(markup.scope_key("Active entry found."))
                cache._clear_active()
                console.set_window_title(__appname_sc__)
            elif cache.exists(cache.running_entries, [id_match]):
                console.print(markup.scope_key("Running time entry found."))
                cache.remove([cache.running_entries], "id", [id_match])
            elif cache.exists(cache.paused_entries, [id_match]):
                console.print(markup.scope_key("Paused time entry found."))
                cache.remove([cache.paused_entries], "id", [id_match])

        query_job: "QueryJob" = routine._delete_time_entry(
            matched_ids,
            wait=True,
            render=True,
            status=status,
            status_renderable=markup.status_message("Deleting entries"),
        )

        console.print("Deleted time entries")
        threads.spawn(ctx, appdata.sync, dict(trigger_query_job=query_job, debug=debug))
        threads.spawn(ctx, id_list.reset)


def _get_entry_edits(
    matched_ids: list[str],
    entry_row: "Row",
    console: "Console",
    project: str,
    note: str,
    billable: bool,
    start_time: datetime,
    end_time: datetime,
    date: datetime,
) -> dict[str, t.Any] | None:
    edits: dict[str, t.Any] = {}

    if project is not None:
        edits["project"] = project
    if note is not None:
        edits["note"] = note
    if billable is not None:
        edits["billable"] = billable

    match truth(date), truth(start_time), truth(end_time):
        case True, True, True:
            new_date, new_start, new_end = dates.combine_new_date_into_start_and_end(
                in_datetime=date, in_start=start_time, in_end=end_time
            )
            edits["start_time"] = new_start
            edits["end_time"] = new_end
            edits["date"] = new_date
        case True, True, False:
            new_date, new_start, new_end = dates.combine_new_date_into_start(
                in_datetime=date, in_start=start_time, in_end=entry_row.end
            )
            edits["start_time"] = new_start
            edits["date"] = new_date
        case True, False, False:
            new_date, new_start, new_end = dates.combine_new_date_into_start_and_end(
                in_datetime=date,
                in_start=entry_row.start,
                in_end=entry_row.end,
            )
            # Only include date.
            # Procedure in BigQuery will handle updating each individual time entries start and end times.
            edits["date"] = new_date
        case True, False, True:
            new_date, new_start, new_end = dates.combine_new_date_into_end(
                in_datetime=date, in_start=entry_row.start, in_end=end_time
            )
            edits["end_time"] = new_end
            edits["date"] = new_date
        case False, True, False:
            new_date, new_start, new_end = dates.combine_new_date_into_start(
                in_datetime=entry_row.start,
                in_start=start_time,
                in_end=entry_row.end,
            )
            edits["start_time"] = new_start
        case False, False, True:
            new_date, new_start, new_end = dates.combine_new_date_into_end(
                in_datetime=entry_row.start,
                in_start=entry_row.start,
                in_end=end_time,
            )
            edits["end_time"] = new_end
        case False, True, True:
            new_date, new_start, new_end = dates.combine_new_date_into_start_and_end(
                in_datetime=entry_row.start,
                in_start=start_time,
                in_end=end_time,
            )
            edits["start_time"] = new_start
            edits["end_time"] = new_end

    if any([truth(date), truth(start_time), truth(end_time)]):
        paused_hours = entry_row.paused_hours
        duration = new_end - new_start
        paused_hours, paused_minutes, paused_seconds = dates.seconds_to_time_parts(
            Decimal(paused_hours or 0) * 3600
        )

        duration = duration - timedelta(
            hours=paused_hours,
            minutes=paused_minutes,
            seconds=paused_seconds,
        )

        if duration.total_seconds() < 0 or copysign(1, duration.days) == -1:
            matched_ids.pop(matched_ids.index(entry_row.id))

            console.print(
                cleandoc(
                    f"""
                [code]{entry_row.id}[/code] updates failed: Negative Duration.
                original start = {entry_row.start.strftime('%Y-%m-%d %H:%M:%S')} | new start {new_start.strftime('%Y-%m-%d %H:%M:%S')}
                original end = {entry_row.end.strftime('%Y-%m-%d %H:%M:%S')} | new end = {new_end.strftime('%Y-%m-%d %H:%M:%S')}
                paused_hours = [repr.number]{entry_row.paused_hours}[/repr.number]
                duration = {duration}
                Removed from edits.
                """
                )
            )
            return None

        hours = round(Decimal(duration.total_seconds() / 3600), 4)
        edits["paused_hours"] = None
        edits["hours"] = hours

    return edits


def _match_ids(
    ctx: click.RichContext,
    id_list: "TimeEntryIdList",
    ids_to_match: list[str],
) -> t.Sequence[list[str]]:
    predicate: t.Callable[[str], bool] = lambda i: (
        any([i.startswith(m) for m in ids_to_match])
    )

    matched_idxs: t.Iterator[int] = locate(id_list.ids, predicate)
    matched_ids: list[str] = list(map(lambda i: id_list.ids[i], matched_idxs))
    missing: t.Callable[[str], bool] = lambda i: not any(
        [m.startswith(i) for m in matched_ids]
    )
    non_matched_ids: list[str] = list(filter(missing, ids_to_match))

    if not matched_ids:
        ctx.fail("No matching ids.")
    else:
        return matched_ids, non_matched_ids


@click.command(
    cls=FmtRichCommand,
    name="edit",
    help=_help.timer_edit,
    short_help="Edit completed time entries.",
    syntax=_help.timer_edit_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not edit entries.")),
)
@click.option(
    "-i",
    "--id",
    "id_options",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Repeat flag to pass multiple ids.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-u",
    "--use-last-timer-list",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Use all ids from the latest timer:list cmd.",
    required=False,
    default=None,
    callback=validate.callbacks.timer_list_cache_exists,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-y",
    "--yank",
    cls=DynamicHelpOption,
    show_default=True,
    multiple=True,
    type=CallableIntRange(1, lambda: len(loads(appdir.TIMER_LIST_CACHE.read_text()))),
    help=yank_flag_help,
    required=False,
    default=None,
    callback=validate.callbacks.timer_list_cache_idx,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-p",
    "--project",
    show_default=True,
    multiple=False,
    type=shell_complete.projects.ActiveProject,
    help=None,
    required=False,
    default=None,
    callback=validate.active_project,
    metavar="TEXT",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-d",
    "--date",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-s",
    "--start-time",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-e",
    "--end-time",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-n",
    "--note",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.notes.from_param,
)
@click.option(
    "-b",
    "--billable",
    show_default=True,
    multiple=False,
    type=click.BOOL,
    help=None,
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.Param("billable").bool,
)
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@_pass.ctx_group(parents=1)
def edit(
    ctx_group: t.Sequence[click.RichContext],
    id_list: "TimeEntryIdList",
    appdata: "TimeEntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    id_options: list[str],
    use_last_timer_list: list[str],
    yank: list[str],
    project: str,
    note: str,
    billable: bool,
    start_time: datetime,
    end_time: datetime,
    date: datetime,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    ids_to_match: list[str] = [
        *(id_options or []),
        *(yank or []),
        *(use_last_timer_list or []),
    ]

    validate.callbacks.edit_params(ctx, ctx.params, ids_to_match, debug)

    with console.status(
        status=markup.status_message("Matching time entry ids")
    ) as status:
        matched_ids, non_matched_ids = _match_ids(
            ctx=ctx, id_list=id_list, ids_to_match=ids_to_match
        )

        console.print(markup.saved("Matched "), matched_ids, end="")
        non_matched_ids and console.print(
            markup.red("Non-matched "), non_matched_ids, end=""
        )

        status.update(markup.status_message("Retrieving data"))
        try:
            matched_entries: "QueryJob" = routine._get_time_entries(matched_ids)
        except Exception as error:
            console.print(markup.br("Error:"), error)
            raise utils.click_exit

        debug and patch_stdout(raw=True)(console.log)("[DEBUG]:", matched_entries)

        all_edits: list[dict[str, t.Any]] = []
        for entry_row in matched_entries:
            edits = _get_entry_edits(
                matched_ids=matched_ids,
                entry_row=entry_row,
                console=console,
                project=project,
                note=note,
                billable=billable,
                start_time=start_time,
                end_time=end_time,
                date=date,
            )

            if not edits:
                continue
            else:
                all_edits.append(edits)

        debug and patch_stdout(raw=True)(console.log)("[DEBUG]:", all_edits)

        status_renderable = Text.assemble(
            markup.status_message(
                "Editing %s: " % ("entries" if len(matched_ids) > 1 else "entry")
            ),
            Text.join(Text(", "), [markup.code(_id[:7]) for _id in matched_ids]),
        )

        if not all_edits:
            console.print(markup.dimmed("Nothing to edit."))
            return

        edits = first(all_edits)
        status.update(status_renderable)

        query_job: "QueryJob" = routine.update_time_entries(
            ids=matched_ids,
            project=edits.get("project"),
            note=edits.get("note"),
            billable=edits.get("billable"),
            start=edits["start_time"].time() if "start_time" in edits else None,
            end=edits["end_time"].time() if "end_time" in edits else None,
            date=edits.get("date"),
            wait=True,
            render=True,
            status=status,
            status_renderable=status_renderable,
        )

        console.print(
            "Updated",
            "records:" if len(matched_ids) > 1 else "record:",
        )

        original_records = []
        new_records = []

        for entry_row, edits in zip(matched_entries, all_edits):
            original_record = {
                "id": entry_row.id[:7],
                "project": entry_row.project,
                "date": entry_row.date,
                "start_time": entry_row.start.time(),
                "end_time": entry_row.end.time(),
                "note": entry_row.note,
                "billable": entry_row.billable,
                "paused_hours": entry_row.paused_hours or 0,
                "hours": round(Decimal(entry_row.hours), 4),
            }
            original_records.append(original_record)

            for k in edits:
                if k in ("start_time", "end_time"):
                    edits[k] = edits[k].time()

            new_records.append(edits)

        debug and patch_stdout(raw=True)(console.log)(
            "[DEBUG]:", "original_records:", original_records
        )
        debug and patch_stdout(raw=True)(console.log)(
            "[DEBUG]:", "new_records:", new_records
        )

        console.print(render.create_table_diff(original_records, new_records))
        threads.spawn(ctx, appdata.sync, dict(trigger_query_job=query_job, debug=debug))


@click.command(
    cls=FmtRichCommand,
    name="get",
    no_args_is_help=True,
    short_help="Retrieve a time entry by id.",
    syntax=_help.timer_get_syntax,
)
@click.argument(
    "time_entry_id",
    type=click.STRING,
    metavar="ID",
)
@_pass.routine
@_pass.id_list
@_pass.console
def get(
    console: "Console",
    id_list: "TimeEntryIdList",
    routine: "CliQueryRoutines",
    time_entry_id: str,
) -> None:
    """Retrieve a time entry by id."""
    query_job: "QueryJob" = routine._get_time_entries(
        [id_list.match_id(time_entry_id)], wait=True, render=True
    )
    data = {k: v for k, v in one(query_job.result()).items()}
    console.print_json(data=data, default=str, indent=4)


@click.command(
    cls=FmtRichCommand,
    name="list",
    help=_help.timer_list,
    short_help="List time entries.",
    syntax=_help.timer_list_syntax,
    context_settings=dict(
        allow_extra_args=True,
        allow_interspersed_args=True,
    ),
)
@utils._handle_keyboard_interrupt()
@click.option(
    "-d",
    "--date",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Date to query.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-t",
    "--today",
    show_default=True,
    is_flag=True,
    flag_value="today",
    multiple=False,
    type=click.STRING,
    help="Query today's date.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-y",
    "--yesterday",
    show_default=True,
    is_flag=True,
    flag_value="yesterday",
    multiple=False,
    type=click.STRING,
    help="Query yesterday's date.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-s",
    "--start",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Query a date range.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-e",
    "--end",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Query a date range.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
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
@click.option(
    "-pw",
    "--previous-week",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Query range = previous week.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
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
@click.option(
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
@click.option(
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
@click.option(
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
@click.option(
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
@click.option(
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
@click.option(
    "-l",
    "--limit",
    show_default=True,
    multiple=False,
    type=click.INT,
    help="Limits the number of rows to produce.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-o",
    "--offset",
    show_default=True,
    multiple=False,
    type=click.INT,
    help="Skips a specific number of rows before applying LIMIT.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-nc",
    "--no-cache",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Don't use query cache. *Deprecated*",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.argument(
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
@_pass.console
@_pass.routine
@_pass.ctx_group(parents=1)
@_pass.now
def list_(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    routine: "CliQueryRoutines",
    console: "Console",
    date: datetime | None,
    today: datetime | None,
    yesterday: datetime | None,
    start: datetime | None,
    end: datetime | None,
    current_week: bool,
    previous_week: bool,
    current_month: bool,
    current_year: bool,
    all_: bool,
    match_project: str | None,
    match_note: str | None,
    limit: int | None,
    offset: int | None,
    no_cache: bool,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if offset and not limit:
        console.print(
            "--offset / -o does not do anything without also using --limit / -l"
        )

    query_job: "QueryJob"

    if all_:
        where_clause: str = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._list_timesheet(
            where=where_clause,
            use_query_cache=not no_cache,
            match_project=match_project,
            match_note=match_note,
            limit=limit,
            offset=offset,
        )

    elif any((start, end, current_week, current_month, current_year, previous_week)):
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
        elif previous_week:
            date_params = dates.get_relative_week(
                now, AppConfig().get("settings", "week_start"), week="previous"
            )
        elif current_month:
            date_params = dates.get_month_to_date(now)
        elif current_year:
            date_params = dates.get_year_to_date(now)
        elif start or end:
            date_params = dates.parse_date_range_flags(
                start or PromptFactory.prompt_date("(start-date)"),
                end or PromptFactory.prompt_date("(end-date)"),
            )

        where_clause = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._list_timesheet(
            start_date=date_params.start.date(),
            end_date=date_params.end.date(),
            where=where_clause,
            use_query_cache=not no_cache,
            match_project=match_project,
            match_note=match_note,
            limit=limit,
            offset=offset,
        )

    else:
        query_date: datetime = (
            date or today or yesterday or PromptFactory.prompt_date("(date)")
        )

        where_clause = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._list_timesheet(
            date=query_date.date(),
            where=where_clause,
            use_query_cache=not no_cache,
            match_project=match_project,
            match_note=match_note,
            limit=limit,
            offset=offset,
        )

    rows: list[dict[str, t.Any]] = list(map(lambda r: dict(r.items()), query_job))
    table = render.map_sequence_to_rich_table(
        mappings=rows,
        string_ctype=["project", "note", "id"],
        bool_ctype=["billable", "active", "paused"],
        num_ctype=["paused_hours", "hours", "total", "row"],
        time_ctype=["start", "end"],
        date_ctype=["date"],
    )
    appdir.TIMER_LIST_CACHE.write_text(
        dumps({idx: row.get("id") for idx, row in enumerate(rows)})
    )
    console.print(table)


@click.group(
    cls=AliasedRichGroup,
    help=_help.timer_notes_update,
    short_help="Manage notes.",
    syntax=_help.timer_notes_update_syntax,
)
def notes() -> None: ...


@notes.command(
    cls=FmtRichCommand,
    name="update",
    no_args_is_help=True,
    help=_help.timer_notes_update,
    short_help="Interactively update notes.",
    syntax=_help.timer_notes_update_syntax,
)
@click.argument(
    "project",
    nargs=1,
    type=shell_complete.projects.AnyProject,
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_argument,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not update notes.")),
)
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.ctx_group(parents=1)
def update_notes(
    ctx_group: t.Sequence[click.RichContext],
    appdata: "TimeEntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    project: str,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    try:
        notes_to_edit: t.Sequence[str] = _questionary.checkbox(
            message="Select notes to edit",
            choices=shell_complete.notes.Notes().get(project),
        )
    except AttributeError:
        console.print(
            markup.code(project),
            "has no notes to edit.",
            "If this was not the expected outcome,",
            "Try adjusting the lookback window with",
            "app:config:set:general:note_history",
        )
        return

    if not notes_to_edit:
        console.print(markup.dimmed("No notes selected, nothing happened."))
        return

    notes_to_replace: str = "\n".join(
        map(lambda n: utils._alter_str(n, add_quotes=True), notes_to_edit)
    )

    new_note = PromptFactory.prompt_note(
        project,
        message="(new-note)",
        rprompt="\nNotes being replaced:\n%s" % notes_to_replace,
        bottom_toolbar=lambda: "Replacing notes for %s." % project,
    )

    query_job: "QueryJob" = routine.update_notes(
        new_note=new_note,
        old_note="".join(["(", "|".join(n for n in notes_to_edit), ")"]),
        project=project,
        wait=True,
        render=True,
        status_renderable=markup.status_message("Updating notes"),
    )

    threads.spawn(ctx, appdata.sync, dict(trigger_query_job=query_job, debug=debug))
    console.print("Updated notes for", markup.code(project))


@click.command(
    cls=FmtRichCommand,
    name="pause",
    help=_help.timer_pause,
    short_help="Pause active entry.",
    syntax=_help.timer_pause_syntax,
)
@_pass.routine
@_pass.console
@_pass.active_time_entry
@_pass.now
def pause(
    now: datetime,
    cache: "TimeEntryCache",
    console: "Console",
    routine: "CliQueryRoutines",
) -> None:
    routine.pause_time_entry(cache.id, now)
    cache.put_active_entry_on_pause(now)
    console.set_window_title(__appname_sc__)


@click.command(
    cls=FmtRichCommand,
    name="resume",
    help=_help.timer_resume,
    short_help="Resume a paused time entry.",
    syntax=_help.timer_resume_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not resume time entry.")),
)
@click.argument(
    "entry",
    type=click.STRING,
    required=False,
    shell_complete=shell_complete.entries.paused,
)
@click.option(
    "-S",
    "--stop",
    "stop_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Immediately stop the resumed time entry.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.cache
@_pass.console
@_pass.id_list
@_pass.ctx_group(parents=1)
@_pass.now
def resume(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    id_list: "TimeEntryIdList",
    console: "Console",
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    entry: str,
    stop_: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not cache.paused_entries:
        console.print(markup.dimmed("No paused time entries."))
        return

    if not entry:
        paused_entries = cache.get_updated_paused_entries(now)

        table: Table = render.map_sequence_to_rich_table(
            mappings=paused_entries,
            string_ctype=["project", "note", "id"],
            bool_ctype=["billable", "paused"],
            num_ctype=["paused_hours"],
            datetime_ctype=["timestamp_paused"],
            time_ctype=["start"],
        )
        console.print(table)

        select: str = _questionary.select(
            message="Select an entry to resume",
            choices=list(map(_get._id, paused_entries)),
        )

        cache.resume_paused_time_entry(select, now)
        routine.resume_time_entry(cache.id, now)
    else:
        if len(entry) < 40:
            matched_id: str = id_list.match_id(entry)
        else:
            matched_id = entry

        if not cache.exists(cache.paused_entries, [matched_id]):
            raise click.UsageError(message="This entry is not paused.", ctx=ctx)

        if stop_:
            cache.remove([cache.paused_entries], "id", [matched_id])
            routine.stop_time_entry(matched_id, now)
        else:
            cache.resume_paused_time_entry(matched_id, now)
            routine.resume_time_entry(cache.id, now)


@click.command(
    cls=FmtRichCommand,
    name="run",
    help=_help.timer_run,
    short_help="Start a new time entry.",
    syntax=_help.timer_run_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not start time entry.")),
)
@click.option(
    "-p",
    "--project",
    show_default=True,
    multiple=False,
    type=shell_complete.projects.ActiveProject,
    help="Project to log entry under.",
    required=True,
    default="no-project",
    callback=validate.active_project,
    metavar="TEXT",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-s",
    "--start",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Earlier start time. Ignore option to start now.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-n",
    "--note",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Add a new/existing note.",
    required=False,
    default="None",
    callback=None,
    metavar=None,
    shell_complete=shell_complete.notes.from_param,
)
@click.option(
    "-b",
    "--billable",
    show_default=True,
    multiple=False,
    type=click.BOOL,
    help="Set time entries billable flag.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.Param("billable").bool,
)
@click.option(
    "-P",
    "--pause-active",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Pause active entry before running a new one.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.cache
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@_pass.ctx_group(parents=1)
@_pass.now
def run(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    id_list: "TimeEntryIdList",
    appdata: "TimeEntryAppData",
    console: "Console",
    routine: "CliQueryRoutines",
    cache: "TimeEntryCache",
    billable: bool,
    project: str,
    start: datetime,
    note: str,
    pause_active: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    project_default_billable: bool = False
    if billable is None:
        active_projects: dict[str, t.Any]
        try:
            active_projects = appdata.load()["active"]
        except KeyError:
            appdata.sync()
            active_projects = appdata.load()["active"]
        project_default_billable = active_projects[project]["default_billable"]
        debug and patch_stdout(raw=True)(console.log)(
            "[DEBUG]:",
            "getting projects default billable value:",
            project_default_billable,
        )

    start_local: datetime = start or now
    time_entry_id: str = sha1(f"{project}{note}{start_local}".encode()).hexdigest()
    query_job: "QueryJob" = routine.start_time_entry(
        time_entry_id, project, note, start_local, billable or project_default_billable
    )

    if pause_active:
        if cache:
            cache.put_active_entry_on_pause(start_local)
            routine.pause_time_entry(cache.id, start_local)
        else:
            console.print("No active entry. --pause-active / -P ignored.")
    elif cache:
        cache.start_new_active_time_entry()

    with cache.rw() as cache:
        cache.id = time_entry_id
        cache.project = project
        cache.note = note if note != "None" else None  # type: ignore[assignment]
        cache.billable = billable or project_default_billable
        cache.start = start_local

    threads.spawn(ctx, appdata.sync, dict(trigger_query_job=query_job, debug=debug))
    threads.spawn(ctx, id_list.add, dict(input_id=time_entry_id, debug=debug))


@click.command(
    cls=FmtRichCommand,
    name="show",
    help=_help.timer_show,
    short_help="Show local running/paused entries.",
    syntax=_help.timer_show_syntax,
)
@click.option(
    "-j",
    "--json",
    "json_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help=None,
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.cache
@_pass.console
def show(console: "Console", cache: "TimeEntryCache", json_: bool) -> None:
    if json_:
        console.print_json(data=cache._entries, default=str, indent=4)
    else:
        console.print(cache)


@click.command(
    cls=FmtRichCommand,
    name="stop",
    help=_help.timer_stop,
    short_help="Stop active entry.",
    syntax=_help.timer_stop_syntax,
)
@_pass.routine
@_pass.console
@_pass.active_time_entry
@_pass.now
def stop(
    now: datetime,
    cache: "TimeEntryCache",
    console: "Console",
    routine: "CliQueryRoutines",
) -> None:
    routine.stop_time_entry(cache.id, now)
    cache._clear_active()
    console.set_window_title(__appname_sc__)


@click.command(
    cls=FmtRichCommand,
    name="switch",
    help=_help.timer_switch,
    short_help="Switch active entry.",
    syntax=_help.timer_switch_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not switch.")),
)
@click.argument(
    "entry",
    type=click.STRING,
    required=False,
    shell_complete=shell_complete.entries.all_,
)
@click.option(
    "-c",
    "--continue",
    "continue_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Active entry continues to run after switching.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.console
@_pass.routine
@_pass.active_time_entry
@_pass.now
def switch(
    now: datetime,
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    console: "Console",
    entry: str | None,
    continue_: bool,
) -> None:
    entries: list[dict[str, t.Any]] = cache.running_entries + cache.paused_entries

    if len(entries) == 1:
        console.print(markup.dimmed("Nothing to switch."))
        raise utils.click_exit

    select: str
    if not entry:
        table: "Table" = render.map_sequence_to_rich_table(
            mappings=entries,
            string_ctype=["project", "note", "id"],
            bool_ctype=["billable", "paused"],
            num_ctype=["paused_hours"],
            datetime_ctype=["timestamp_paused"],
            time_ctype=["start"],
        )
        console.print(table)

        choices: list[str] = list(
            filter(lambda i: not cache.id.startswith(i), map(_get._id, entries))
        )

        select = _questionary.select(
            message="Select a time entry.",
            instruction="(active entry excluded)",
            choices=choices,
        )
    else:
        select = entry

    if cache.index(cache.paused_entries, "id", [select]):
        routine.resume_time_entry(select, now)

    not continue_ and routine.pause_time_entry(cache.id, now)
    cache.switch_active_entry(select, now, continue_)


@click.command(
    cls=FmtRichCommand,
    name="update",
    help=_help.timer_update,
    short_help="Update active entry.",
    syntax=_help.timer_update_syntax,
)
@click.option(
    "-p",
    "--project",
    show_default=True,
    multiple=False,
    type=shell_complete.projects.ActiveProject,
    help="Update entry project.",
    required=True,
    default=lambda: TimeEntryCache().project or "no-project",
    callback=validate.active_project,
    metavar="TEXT",
    shell_complete=shell_complete.projects.from_option,
)
@click.option(
    "-s",
    "--start",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Update entry start-time.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-n",
    "--note",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Update entry note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.notes.from_param,
)
@click.option(
    "-b",
    "--billable",
    show_default=True,
    multiple=False,
    type=click.BOOL,
    help="Update entry billable flag.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.Param("billable").bool,
)
@click.option(
    "-S",
    "--stop",
    "stop_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Stop active entry after updating.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.active_time_entry
@_pass.console
@_pass.appdata
@_pass.ctx_group(parents=1)
@_pass.now
def update(
    now: datetime,
    ctx_group: t.Sequence[click.RichContext],
    appdata: "TimeEntryAppData",
    console: "Console",
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    billable: bool | None,
    project: str | None,
    start: datetime | None,
    note: str | None,
    stop_: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not any([project, note, billable is not None, start]):
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    copy: dict[str, t.Any] = cache.active.copy()
    edits: dict[str, t.Any] = {}

    status_renderable = Text.assemble(
        markup.status_message("Updating time entry: "), markup.code(cache.id[:7])
    )

    with console.status(status_renderable) as status:
        if note:
            if note == cache.note:
                console.print(
                    "note is already set to",
                    markup.repr_str(note),
                    "- skipping update.",
                )
            else:
                updated_note: str = re.compile(r"(\"|')").sub("", note)

                with cache.rw() as cache:
                    cache.note = updated_note

                edits["note"] = updated_note

        if start:
            if start == cache.start:
                console.print("start is already set to", start, "- skipping update.")
            else:
                paused_hours, paused_minutes, paused_seconds = (
                    dates.seconds_to_time_parts(Decimal(cache.paused_hours or 0) * 3600)
                )
                duration = (dates.now(AppConfig().tz) - start) - timedelta(
                    hours=paused_hours,
                    minutes=paused_minutes,
                    seconds=paused_seconds,
                )

                if duration.total_seconds() < 0 or copysign(1, duration.days) == -1:
                    raise click.BadArgumentUsage(
                        message="Invalid value for args [START] | [END]. New duration cannot be negative. "
                        f"Existing paused hours = {cache.paused_hours}",
                        ctx=ctx,
                    )

                with cache.rw() as cache:
                    cache.start = start

                edits["start"] = start

        if billable is not None:
            if billable == cache.billable:
                console.print(
                    "billable is already set to",
                    billable,
                    "- skipping update.",
                )
            else:
                with cache.rw() as cache:
                    cache.billable = billable

                edits["billable"] = billable

        if project and project != cache.project:
            validate.active_project(ctx, None, project)  # type: ignore[arg-type]

            with cache.rw() as cache:
                cache.project = project

            if billable is None:
                active_projects: dict[str, t.Any] = appdata.load()["active"]
                project_appdata: dict[str, t.Any] = active_projects[project]
                default_billable = (
                    project_appdata["default_billable"]
                    if project_appdata["default_billable"] != "null"
                    else None
                )
                billable = default_billable
                edits["billable"] = billable

            edits["project"] = project

        if not any([k in edits for k in ["project", "note", "billable", "start"]]):
            console.print(markup.dimmed("No valid fields to update, nothing happened."))
            return
        else:
            query_job: "QueryJob" = routine.update_time_entries(
                ids=[cache.id],
                project=edits.get("project"),
                note=edits.get("note"),
                billable=edits.get("billable"),
                start=edits["start"].time() if "start" in edits else None,
                wait=True,
                render=True,
                status=status,
                status_renderable=status_renderable,
            )

        if stop_:
            ctx.invoke(stop)

        threads.spawn(
            ctx,
            appdata.sync,
            dict(trigger_query_job=query_job, debug=debug),
        )

        original_record = {
            "id": copy["id"][:7],
            "project": copy["project"],
            "start": copy["start"],
            "note": copy["note"],
            "billable": copy["billable"],
        }

        diff = render.create_row_diff(original=original_record, new=edits)
        console.print("Updated record:", diff)
