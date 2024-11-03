import re
import typing as t
from contextlib import suppress
from copy import copy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha1
from inspect import cleandoc
from json import dumps, loads
from math import copysign
from operator import truth

import click
from more_itertools import first, locate, one
from rich import print as rprint
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from lightlike.__about__ import __appname_sc__
from lightlike.app import (
    _get,
    _questionary,
    dates,
    render,
    shell_complete,
    threads,
    validate,
)
from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.app.core import AliasedGroup, FormattedCommand
from lightlike.app.prompt import PromptFactory
from lightlike.app.shell_complete.types import CallableIntRange, DynamicHelpOption
from lightlike.cmd import _pass
from lightlike.internal import appdir, markup, utils

if t.TYPE_CHECKING:
    from google.cloud.bigquery import QueryJob
    from google.cloud.bigquery.table import Row

    from lightlike.app.cache import TimeEntryAppData, TimeEntryIdList
    from lightlike.client import CliQueryRoutines

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
    "switch",
    "update",
)


P = t.ParamSpec("P")


def default_timer_add(config: AppConfig) -> str:
    timer_add_min: int = config.get("settings", "timer-add-min", default=-6)
    minutes = -timer_add_min if copysign(1, timer_add_min) != -1 else timer_add_min
    return f"{minutes} minutes"


@click.command(
    cls=FormattedCommand,
    name="add",
    short_help="Add a completed time entry.",
    syntax=Syntax(
        code="""\
        $ timer add # defaults to adding an entry under `no-project`, that started 6 minutes ago, ending now.
        $ t a       # this can be later updated using timer:update
        
        $ timer add --start 1h # started 1 hour ago, ends now
        $ t a -s1h

        $ timer add --project lightlike-cli --start 0900  --end 1130 # 9am -> 11:30am today
        $ t a -plightlike-cli -s0900 -e1130
        
        $ timer add --project lightlike-cli --start jan1@9am --end jan1@1pm --note 'task description'
        $ t a -plightlike-cli -sjan1@9am -ejan1@1pm -n'task description'\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
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
@click.argument(
    "note-parts",
    type=click.UNPROCESSED,
    required=False,
    default=None,
    callback=None,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=None,
)
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.id_list
@_pass.ctx_group(parents=1)
@_pass.now
def add(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    id_list: "TimeEntryIdList",
    appdata: "TimeEntryAppData",
    console: Console,
    routine: "CliQueryRoutines",
    project: str,
    start: datetime,
    end: datetime,
    note: str,
    billable: bool,
    note_parts: t.Sequence[str],
) -> None:
    """
    Add a completed time entry.

    --project / -p:
        set the project for the time entry to this.
        create new projects with project:create.
        projects can be searched for by name or description.
        projects are ordered in created time desc.

    --note / -n:
        set note for time entry. if --project / -p is called,
        then notes for selected project will autocomplete. search with fuzzyfinder.
        there is a lookback window so old notes do not clutter the autocompletions.
        update how many days to look back with app:config:set:general:note-history.

    --start / -s:
        set the entry to start at this time.
        defaults to -6 minutes (1/10th of an hour).
        update the default value using app:config:set:general:timer-add-min.

    --end / -e:
        set the entry to end at this time. defaults to [code]now[/code].

    --billable / -b:
        set billable field. if not provided, the default setting for the project is used.
        set project default billable value when first creating a project
        with project:create, using --default-billable / -b
        update an existing project's with project:set:default-billable.

    [NOTE ARGS]:
        all unprocessed arguments will be joined to create the note field.
        this only takes into effect if the `--note` / `-n` option is unused.

    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not note and note_parts:
        note = " ".join(note_parts)

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
    hours = round(Decimal(total_seconds) / Decimal(3600), 4)

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

    debug and console.log(
        "[DEBUG]",
        "getting projects default billable value:",
        project_default_billable,
    )

    time_entry_id = sha1(f"{project}{note}{start_local}".encode()).hexdigest()

    query_job: "QueryJob" = routine._add_time_entry(
        id=time_entry_id,
        project=project,
        note=note,
        start_time=start_local,
        end_time=end_local,
        billable=billable or project_default_billable,
    )

    sync_kwargs = {"trigger_query_job": query_job, "debug": debug}
    threads.spawn(ctx, id_list.add, {"input_id": time_entry_id, "debug": debug})
    note != "None" and threads.spawn(ctx, appdata.sync, sync_kwargs)

    console.print(
        "Added record:",
        render.map_sequence_to_rich_table(
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
        ),
    )


def yank_flag_help() -> str:
    if appdir.TIMER_LIST_CACHE.exists():
        timer_list_cache = loads(appdir.TIMER_LIST_CACHE.read_text())
        len_cache = len(timer_list_cache)
        if len_cache > 0:
            return f"Pull id from latest timer:list cmd. Cache range: 1<=x<={len_cache}"

    return "Pull id from latest timer:list cmd. Current cache is empty."


@click.command(
    cls=FormattedCommand,
    name="delete",
    no_args_is_help=True,
    short_help="Delete time entries.",
    syntax=Syntax(
        code="""\
        $ timer delete --id b95eb89 --id 22b0140 --id b5b8e24
        $ t d -ib95eb89 -i22b0140 -ib5b8e24
        
        $ timer delete --yank 1
        $ t d -y1
        
        $ timer delete --use-last-timer-list
        $ t d -u\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
    ctx_group: t.Sequence[click.Context],
    id_list: "TimeEntryIdList",
    console: Console,
    cache: "TimeEntryCache",
    appdata: "TimeEntryAppData",
    routine: "CliQueryRoutines",
    id_options: list[str],
    use_last_timer_list: list[str],
    yank: list[str],
) -> None:
    """
    Delete time entries.

    --id / -i:
        ids for entries to edit.
        repeat flag for multiple entries.

    --yank / -y:
        pull an id from the latest timer:list results.
        option must be an integer within the range of the cached list.
        the id of the corresponding row will be passed to the command.
        this option can be repeated and combined with --id / -i.
        e.g.

        ```
        $ timer list --current-week

        | row | id      |   ...
        |-----|---------|   ...
        |   1 | a6c8e8e |   ...
        |   2 | e01812e |   ...
        ```

        --yank 2 [d](or -y2)[/d] would be the same as typing --id e01812e

    --use-list-timer-list / -u:
        pass all id's from the most recent timer:list result to this command
        this option can be repeated and combined with --id / -i or --yank / -y.
    """
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
        console.print(markup.bg("Matched "), matched_ids, end="")
        non_matched_ids and console.print(
            markup.red("Non-matched "), non_matched_ids, end=""
        )
        status.update(markup.status_message("Retrieving data."))

        for id_match in matched_ids:
            if cache.id == id_match:
                cache._clear_active()
                if AppConfig().get("settings", "update-terminal-title", default=True):
                    console.set_window_title(__appname_sc__)
            elif cache.exists(cache.running_entries, [id_match]):
                cache.remove("id", [id_match], [cache.running_entries])
            elif cache.exists(cache.paused_entries, [id_match]):
                cache.remove("id", [id_match], [cache.paused_entries])

        query_job: "QueryJob" = routine._delete_time_entries(matched_ids, wait=True)

        console.print("Deleted time entries")

        kwargs = {"trigger_query_job": query_job, "debug": debug}
        threads.spawn(ctx, appdata.sync, kwargs)
        threads.spawn(ctx, id_list.reset, kwargs)


def _get_entry_edits(
    matched_ids: list[str],
    entry_row: "Row",
    console: Console,
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
            # Procedure in BigQuery will handle updating each
            # individual time entries start and end times.
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
            Decimal(paused_hours or 0) * Decimal(3600)
        )

        duration = duration - timedelta(
            hours=paused_hours,
            minutes=paused_minutes,
            seconds=paused_seconds,
        )

        if duration.total_seconds() < 0 or copysign(1, duration.days) == -1:
            matched_ids.pop(matched_ids.index(entry_row.id))

            _compare_start = (
                f"original start = {entry_row.start.strftime('%Y-%m-%d %H:%M:%S')}"
                f" | new start {new_start.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            _compare_end = (
                f"original end = {entry_row.end.strftime('%Y-%m-%d %H:%M:%S')}"
                f" | new end {new_end.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            console.print(
                cleandoc(
                    f"""
            [code]{entry_row.id}[/code] updates failed: Negative Duration.
            {_compare_start}
            {_compare_end}
            paused_hours = [repr.number]{entry_row.paused_hours}[/repr.number]
            duration = {duration}
            Removed from edits.
                """
                )
            )
            return None

        hours = round(Decimal(duration.total_seconds()) / Decimal(3600), 4)
        edits["paused_hours"] = None
        edits["hours"] = hours

    return edits


def _match_ids(
    ctx: click.Context,
    id_list: "TimeEntryIdList",
    ids_to_match: list[str],
) -> t.Sequence[list[str]]:
    def _match_id_predicate(s: str) -> bool:
        nonlocal ids_to_match
        return any([s.startswith(m) for m in ids_to_match])

    matched_idxs: t.Iterator[int] = locate(id_list.ids, _match_id_predicate)
    matched_ids: list[str] = list(map(lambda i: id_list.ids[i], matched_idxs))

    def _match_id_missing(s: str) -> bool:
        nonlocal matched_ids
        return not any([m.startswith(s) for m in matched_ids])

    non_matched_ids: list[str] = list(filter(_match_id_missing, ids_to_match))

    if not matched_ids:
        ctx.fail("No matching ids.")
    else:
        return matched_ids, non_matched_ids


@click.command(
    cls=FormattedCommand,
    name="edit",
    short_help="Edit completed time entries.",
    syntax=Syntax(
        code="""\
        $ timer edit --id b95eb89 --start 3pm # set start time to 3pm
        $ t e -ib95eb89 -s3pm

        $ timer edit --use-last-timer-list --note 'rewrite task'
        $ t e -u -n'rewrite task'

        $ timer edit --yank 1 --yank 2 --end now # edit both time entries to end now
        $ t e -y1 -y2 -en # `n` expands to `now`
        
        $ timer edit --yank 1 --yank 2 --id 36c9fe5 --date 2d # set 3 entries to 2 days ago
        $ t e -y1 -y2 -i36c9fe5 -d2d\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
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
    ctx_group: t.Sequence[click.Context],
    id_list: "TimeEntryIdList",
    appdata: "TimeEntryAppData",
    console: Console,
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
    """
    Edit completed time entries.

    --id / -i:
        ids for entries to edit.
        repeat flag for multiple entries.

    --yank / -y:
        pull an id from the latest timer:list results.
        option must be an integer within the range of the cached list.
        the id of the corresponding row will be passed to the command.
        this option can be repeated and combined with --id / -i.
        e.g.

        ```
        $ timer list --current-week

        | row | id      |   ...
        |-----|---------|   ...
        |   1 | a6c8e8e |   ...
        |   2 | e01812e |   ...
        ```

        --yank 2 [d](or -y2)[/d] would be the same as typing --id e01812e

    --use-list-timer-list / -u:
        pass all id's from the most recent timer:list result to this command
        this option can be repeated and combined with --id / -i or --yank / -y.

    --project / -p:
        set the project for all selected entries to this.
        create new projects with project:create.
        projects can be searched for by name or description.
        projects are ordered in created time desc.

    --note / -n:
        set note for time entry. if --project / -p is called,
        then notes for selected project will autocomplete. search with fuzzyfinder.
        there is a lookback window so old notes do not clutter the autocompletions.
        update how many days to look back with app:config:set:general:note-history.

    --billable / -b:
        set billable field. if not provided, the default setting for the project is used.
        set project default billable value when first creating a project
        with project:create, using --default-billable / -b
        update an existing project's with project:set:default-billable.

    --start-time / -s / --end-time / -e:
        set the start/end time for all selected entries to this.
        only the time value of the parsed datetime will be used.
        if only one of the 2 are selected, each selected time entry will update
        that respective value, and recalculate the total duration,
        taking any existing paused hours into account.

    --date / -d:
        set the date for all selected entries to this.
        only the date value of the parsed datetime will be used.
        the existing start/end times will remain,
        unless this option is combined with --start-time / -s / --end-time / -e.
    """
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

        console.print(markup.bg("Matched "), matched_ids, end="")
        non_matched_ids and console.print(
            markup.red("Non-matched "), non_matched_ids, end=""
        )

        status.update(markup.status_message("Retrieving data"))
        try:
            matched_entries: "QueryJob" = routine._get_time_entries(matched_ids)
        except Exception as error:
            console.print(markup.br("Error:"), error)
            raise click.exceptions.Exit()

        debug and console.log("[DEBUG]", matched_entries)

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

        debug and console.log("[DEBUG]", all_edits)

        status_renderable = Text.assemble(
            markup.status_message(
                "Editing %s: " % ("entries" if len(matched_ids) > 1 else "entry")
            ),
            Text.join(Text(", "), [markup.code(_id[:7]) for _id in matched_ids]),
        )

        if not all_edits:
            ctx.fail("Nothing to edit.")

        edits = first(all_edits)
        status.update(status_renderable)

        query_job: "QueryJob" = routine._update_time_entries(
            ids=matched_ids,
            project=edits.get("project"),
            note=edits.get("note"),
            billable=edits.get("billable"),
            start_time=edits["start_time"].time() if "start_time" in edits else None,
            end_time=edits["end_time"].time() if "end_time" in edits else None,
            date=edits.get("date"),
        )

        original_records = []
        new_records = []

        for entry_row, edits in t.cast(
            t.Sequence[tuple["Row", dict[str, t.Any]]],
            zip(matched_entries, all_edits),
        ):
            _start_datetime = entry_row.start
            _end_datetime = entry_row.end

            try:
                _start_time = _start_datetime.time()
                _end_time = _end_datetime.time()
            except Exception:
                ctx.fail(
                    "Failed to retrieve start/end times. Possible there is "
                    "still an job running on one of these records. "
                    "Please wait a moment and try again."
                )

            original_record = {
                "id": entry_row.id[:7],
                "project": entry_row.project,
                "date": entry_row.date,
                "start_time": _start_time,
                "end_time": _end_time,
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

        debug and console.log("[DEBUG]", "original_records:", original_records)
        debug and console.log("[DEBUG]", "new_records:", new_records)

        console.print(
            "Updated",
            "records:" if len(matched_ids) > 1 else "record:",
            render.create_table_diff(original_records, new_records),
        )
        sync_kwargs = {"trigger_query_job": query_job, "debug": debug}
        threads.spawn(ctx, appdata.sync, sync_kwargs)


@click.command(
    cls=FormattedCommand,
    name="get",
    no_args_is_help=True,
    short_help="Retrieve a single time entry.",
    syntax=Syntax(
        code="""\
        $ timer get 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        
        $ timer get 36c9fe5
        
        $ t g 36c9fe5\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
    console: Console,
    id_list: "TimeEntryIdList",
    routine: "CliQueryRoutines",
    time_entry_id: str,
) -> None:
    """Retrieve a single time entry."""
    query_job: "QueryJob" = routine._get_time_entries(
        [id_list.match_id(time_entry_id)], wait=True, render=True
    )
    rows: list["Row"] = list(query_job.result())
    if not rows:
        console.print(markup.dimmed("Id not found"))
    else:
        data = {k: v for k, v in one(rows).items()}
        console.print_json(data=data, default=str, indent=4)


@click.command(
    cls=FormattedCommand,
    name="list",
    short_help="List time entries.",
    syntax=Syntax(
        code="""\
        $ timer list --today
        $ t l -t

        $ timer list --date jan1
        $ t l -djan1

        $ timer list --all active is true # where clause as arguments
        $ t l -a active is true
        # Note --all / -a flag will query entire timesheet

        $ timer list --yesterday --prompt-where # interactive prompt for where clause
        $ t l -yw

        $ timer list --current-week billable is false
        $ t l -cw billable is false

        # case insensitive regex match - re2
        $ timer list --date 2d --match-note (?i)task.* --regex-engine re2
        $ t l -d2d -I (?i)task.* -re re2

        # case insensitive regex match - ECMAScript
        $ timer list --date 2d --match-note task.* --modifiers ig
        $ t l -d2d -I task.* -Mig

        # regex 
        $ t l -t -P ^(?!demo) # exclude projects beginning with 'demo'

        # list all entries this month from project 'myproject.example'
        # with notes containing words 'docs' or 'tests'
        $ timer list --current-month --match-project myproject.* --match-note docs --match-note tests
        $ timer list -cm -P myproject.* -I docs -I tests

        # list entries today before 12:00:00
        $ timer list --today time(start) >= \\"12:00:00\\"
        $ t l -t time(start) >= \\"12:00:00\\"\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    context_settings=dict(
        allow_extra_args=True,
        allow_interspersed_args=True,
    ),
)
@utils.handle_keyboard_interrupt()
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
    "-P",
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
@click.option(
    "-N",
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
@click.option(
    "-E",
    "--exclude",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Exclude pattern matched against project name and/or note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-I",
    "--include",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Include pattern matched against project name and/or note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
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
@click.option(
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
    default=False,
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
    default=False,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.argument(
    "where",
    type=click.UNPROCESSED,
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
    ctx_group: t.Sequence[click.Context],
    routine: "CliQueryRoutines",
    console: Console,
    date: datetime | None,
    start: datetime | None,
    end: datetime | None,
    current_week: bool,
    previous_week: bool,
    current_month: bool,
    current_year: bool,
    all_: bool,
    match_project: t.Sequence[str],
    match_note: t.Sequence[str],
    exclude: t.Sequence[str],
    include: t.Sequence[str],
    modifiers: str,
    regex_engine: str,
    limit: int | None,
    offset: int | None,
    no_cache: bool,
    prompt_where: bool,
    where: t.Sequence[str],
) -> None:
    """
    List time entries.

    Run command app:parse-date to see examples of strings to pass to parser.

    --current-week / -cw:
    --current-month / -cm:
    --current-year / -cy:
        flags are processed before other date options.
        configure week start dates with app:config:set:general:week-start

    --match-project / -P:
        match a regular expression against project names.
        this option can be repeated, with each pattern being separated by `|`.

    --match-note / -N:
        match a regular expression against entry notes.
        this option can be repeated, with each pattern being separated by `|`.

    --exclude / -E:
        exclude pattern matched against project name and/or note.
        this option can be repeated, with each pattern being separated by `|`.

    --include / -I:
        include pattern matched against project name and/or note.
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
            exclude=exclude,
            include=include,
            modifiers=modifiers,
            regex_engine=regex_engine,
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
        week_start: int = AppConfig().get("settings", "week-start", default=0)

        if current_week:
            date_params = dates.get_relative_week(now, week_start)
        elif previous_week:
            date_params = dates.get_relative_week(now, week_start, week="previous")
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
            exclude=exclude,
            include=include,
            modifiers=modifiers,
            regex_engine=regex_engine,
            limit=limit,
            offset=offset,
        )

    else:
        query_date = date or now

        where_clause = shell_complete.where._parse_click_options(
            flag=prompt_where, args=where, console=console, routine=routine
        )

        query_job = routine._list_timesheet(
            date=query_date.date(),
            where=where_clause,
            use_query_cache=not no_cache,
            match_project=match_project,
            match_note=match_note,
            exclude=exclude,
            include=include,
            modifiers=modifiers,
            regex_engine=regex_engine,
            limit=limit,
            offset=offset,
        )

    rows: list[dict[str, t.Any]] = list(map(lambda r: dict(r.items()), query_job))

    if console.width < 80:
        console.print_json(data=rows, default=str)
    else:
        table: Table = render.map_sequence_to_rich_table(
            mappings=rows,
            exclude_fields=(
                ["paused_hours", "note", "paused", "active"]
                if console.width < 100
                else None
            ),
        )
        if not table.row_count:
            rprint(markup.dimmed("No results"))
            raise click.exceptions.Exit()

        console.print(table)

    appdir.TIMER_LIST_CACHE.write_text(
        dumps({idx: row.get("id") for idx, row in enumerate(rows)}),
        encoding="utf-8",
    )


@click.group(
    cls=AliasedGroup,
    short_help="Manage notes.",
    syntax=Syntax(
        code="$ timer notes update lightlike-cli # interactive",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
def notes() -> None: ...


@notes.command(
    cls=FormattedCommand,
    name="update",
    no_args_is_help=True,
    short_help="Interactively update notes.",
    syntax=Syntax(
        code="$ timer notes update lightlike-cli # interactive",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@click.argument(
    "project",
    nargs=1,
    type=shell_complete.projects.AnyProject,
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_argument,
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not update notes.")),
)
@_pass.routine
@_pass.console
@_pass.appdata
@_pass.ctx_group(parents=1)
def update_notes(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: "CliQueryRoutines",
    project: str,
) -> None:
    """
    Interactively update notes.

    Select which notes to replace with [code]space[/code]. Press [code]enter[/code] to continue with the selection.
    Enter a new note, and all selected notes will be replaced.
    There is a lookback window so old notes do not clutter the autocompletions.
    Update how many days to look back with app:config:set:general:note-history.
    """
    ctx, parent = ctx_group
    console: Console,


@click.command(
    cls=FormattedCommand,
    name="pause",
    short_help="Pause active entry.",
    syntax=Syntax(
        code="$ timer pause",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@_pass.routine
@_pass.console
@_pass.cache
@_pass.ctx_group(parents=1)
@_pass.now
def pause(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    cache: "TimeEntryCache",
    console: Console,
    routine: "CliQueryRoutines",
) -> None:
    """
    Pause the [b]active[/b] entry.

    [b]See[/]:
        timer:run --help / -h
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not cache:
        console.print(markup.dimmed("There is no active time entry."))
        return

    time_entry_id: str = cache.id
    query_job: "QueryJob" = routine._pause_time_entry(time_entry_id, now, wait=debug)
    cache.pause_entry(0, now)
    if AppConfig().get("settings", "update-terminal-title", default=True):
        console.set_window_title(__appname_sc__)

    if debug:
        query_job.result()
        console.log("[DEBUG]", f"paused entry {time_entry_id}")


@click.command(
    cls=FormattedCommand,
    name="resume",
    short_help="Resume a paused time entry.",
    syntax=Syntax(
        code="""\
        $ timer resume 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        $ t re 36c9fe5
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not resume time entry.")),
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
@_pass.ctx_group(parents=1)
@_pass.now
def resume(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    id_list: "TimeEntryIdList",
    console: Console,
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    entry: str,
) -> None:
    """
    Continue a paused entry.

    A resumed time entry becomes the [b]active[/b] entry.

    [b]See[/]:
        timer:run --help / -h
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not cache.paused_entries:
        console.print(markup.dimmed("No paused time entries."))
        return

    query_job: "QueryJob"
    matched_id: str
    if not entry:
        paused_entries = cache.get_updated_paused_entries(now)
        table: Table = render.map_sequence_to_rich_table(paused_entries)
        if not table.row_count:
            rprint(markup.dimmed("No results"))
            raise click.exceptions.Exit()

        console.print(table)

        select: str = _questionary.select(
            message="Select an entry to resume",
            choices=list(map(_get._id, paused_entries)),
        )

        matched_id = select
        cache.resume_entry(matched_id, now)
        query_job = routine._resume_time_entry(matched_id, now)
    else:
        if len(entry) < 40:
            matched_id = id_list.match_id(entry)
        else:
            matched_id = entry

        if not cache.exists(cache.paused_entries, [matched_id]):
            raise click.UsageError(message="This entry is not paused.", ctx=ctx)

        cache.resume_entry(matched_id, now)
        query_job = routine._resume_time_entry(matched_id, now)

    if debug:
        query_job.result()
        console.log("[DEBUG]", f"resumed entry {matched_id}")


@click.command(
    cls=FormattedCommand,
    name="run",
    short_help="Start a new time entry.",
    syntax=Syntax(
        code="""\
        # create a running entry now under 'no-project' with no note
        $ timer run
        $ t ru

        # start entry with project and note
        $ timer run --project lightlike-cli --note readme
        $ t ru -plightlike-cli -nreadme\
        
        # create a running entry starting 1 hour ago, and override billable to false
        $ timer run --project your-client --start 1h --billable False
        $ t ru -p your-client -s1h -b0\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
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
@click.option(
    "-S",
    "--stop-active",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Stop active entry before running a new one.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.argument(
    "note-parts",
    type=click.UNPROCESSED,
    required=False,
    default=None,
    callback=None,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
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
    ctx_group: t.Sequence[click.Context],
    id_list: "TimeEntryIdList",
    appdata: "TimeEntryAppData",
    console: Console,
    routine: "CliQueryRoutines",
    cache: "TimeEntryCache",
    billable: bool | None,
    project: str,
    start: datetime,
    note: str,
    pause_active: bool,
    stop_active: bool,
    note_parts: t.Sequence[str],
) -> None:
    """
    Start a new time entry.

    When a new entry is started, a stopwatch displaying the duration & project appears in the prompt and in the tab title.
    This is the [b]active[/b] entry. Multiple timers may run at once. Only 1 will be displayed in the cursor.
    If a timer runs and there's an [b]active[/b] entry running, the latest becomes the new [b]active[/b] entry.

    --project / -p:
        project to log time entry under.
        create new projects with project:create.
        projects can be searched for by name or description.
        projects are ordered in created time desc.

    --note / -n:
        set note for time entry. if --project / -p is called,
        then notes for selected project will autocomplete. search with fuzzyfinder.
        there is a lookback window so old notes do not clutter the autocompletions.
        update how many days to look back with app:config:set:general:note-history.

    --billable / -b:
        set billable field. if not provided, the default setting for the project is used.
        set project default billable value when first creating a project
        with project:create, using --default-billable / -b
        update an existing project's with project:set:default-billable.

    --start / -s:
        start the entry at an earlier time.
        if not provided, the entry starts now.

    [NOTE ARGS]:
        all unprocessed arguments will be joined to create the note field.
        this only takes into effect if the `--note` / `-n` option is unused.

    [b]See[/]:
        timer:stop - stop the [b]active[/b] entry.
        timer:pause - pause the [b]active[/b] entry.
        timer:resume - continue a paused entry, this paused entry becomes the [b]active[/b] entry.
        timer:switch - pause and switch the [b]active[/b] entry.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if stop_active and cache:
        routine._stop_time_entry(cache.id, now, wait=debug)
        cache._clear_active()
        if AppConfig().get("settings", "update-terminal-title", default=True):
            console.set_window_title(__appname_sc__)

    if not note and note_parts:
        note = " ".join(note_parts)

    project_default_billable: bool = False
    if billable is None:
        projects: dict[str, t.Any]
        active_projects: dict[str, t.Any]

        projects = appdata.load()
        if "active" not in projects:
            appdata.sync()
            projects = appdata.load()

        active_projects = projects["active"]
        if "default_billable" not in active_projects[project]:
            appdata.sync()
            projects = appdata.load()
            active_projects = projects["active"]

        with suppress(KeyError):
            project_default_billable = active_projects[project]["default_billable"]
            debug and console.log(
                "[DEBUG]",
                "getting projects default billable value:",
                project_default_billable,
            )

    start_local: datetime = start or now
    time_entry_id: str = sha1(f"{project}{note}{start_local}".encode()).hexdigest()

    query_job: "QueryJob" = routine._start_time_entry(
        time_entry_id, project, note, start_local, billable or project_default_billable
    )

    if pause_active:
        if cache:
            entry_to_pause: str = copy(cache.id)
            cache.pause_entry(0, start_local)
            routine._pause_time_entry(entry_to_pause, start_local, wait=debug)
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

    if debug:
        query_job.result()
        console.log("[DEBUG]", f"started entry {time_entry_id}")

    sync_kwargs = {"trigger_query_job": query_job, "debug": debug}
    threads.spawn(ctx, appdata.sync, sync_kwargs)
    threads.spawn(ctx, id_list.add, {"input_id": time_entry_id, "debug": debug})


@click.command(
    cls=FormattedCommand,
    name="show",
    short_help="Show local running/paused entries.",
    syntax=Syntax(
        code="$ timer show\n$ t sh",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
def show(console: Console, cache: "TimeEntryCache", json_: bool) -> None:
    """
    Display a table of local running/paused time entries.
    Entries are sorted top-down from active -> running -> paused:
        The active entry is bolded in the first row.
        Running entries are not bolded.
        Paused entries are dimmed.
    """
    if json_:
        console.print_json(data=cache._entries, default=str, indent=4)
    else:
        console.print(cache)


@click.command(
    cls=FormattedCommand,
    name="stop",
    short_help="Stop a time entry.",
    syntax=Syntax(
        code="""
        $ timer stop
        $ t st

        $ timer stop b95eb89
        $ t st b95eb89\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@click.argument(
    "entry",
    type=click.STRING,
    required=False,
    shell_complete=shell_complete.entries.all_,
)
@_pass.routine
@_pass.console
@_pass.id_list
@_pass.cache
@_pass.ctx_group(parents=1)
@_pass.now
def stop(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    cache: "TimeEntryCache",
    id_list: "TimeEntryIdList",
    console: Console,
    routine: "CliQueryRoutines",
    entry: str,
) -> None:
    """
    No args will stop the [b]active[/b] entry, if it exists.

    Pass an id to stop a specific time entry.

    [b]See[/]:
        timer:run --help / -h
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not entry:
        if cache:
            routine._stop_time_entry(cache.id, now, wait=debug)
            cache._clear_active()
            if AppConfig().get("settings", "update-terminal-title", default=True):
                console.set_window_title(__appname_sc__)
            return
        else:
            paused_entries = cache.get_updated_paused_entries(now)
            table: Table = render.map_sequence_to_rich_table(
                mappings=[*cache.running_entries, *paused_entries],
            )
            if not table.row_count:
                ctx.fail("No paused entries.")

            console.print(table)

            select: str = _questionary.select(
                message="Select an entry to resume",
                choices=list(map(_get._id, paused_entries)),
            )

            entry = select

    if not entry:
        rprint(markup.dimmed("Canceled."))
        return

    matched_id = id_list.match_id(entry)
    routine._stop_time_entry(matched_id, now)
    cache.remove(key="id", sequence=[matched_id])


@click.command(
    cls=FormattedCommand,
    name="switch",
    short_help="Switch active entry.",
    syntax=Syntax(
        code="""\
        $ timer switch
        $ t s # interactive

        $ timer switch 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        $ t s 36c9fe
    
        $ timer switch 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46 --continue
        $ t s 36c9fe -c\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
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
    default=False,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.console
@_pass.id_list
@_pass.routine
@_pass.cache
@_pass.ctx_group(parents=1)
@_pass.now
def switch(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    id_list: "TimeEntryIdList",
    console: Console,
    entry: str | None,
    continue_: bool,
) -> None:
    """
    Switch the active time entry.

    Pauses the active entry and resumes the selected entry.

        --continue / -c:
            do not pause the active entry during switch.

        [b]See[/]:
            timer:run --help / -h
    """
    ctx, parent = ctx_group

    if not cache:
        ctx.fail("There is no active time entry. Use timer:resume instead.")

    debug: bool = parent.params.get("debug", False)

    entries: list[dict[str, t.Any]] = cache.running_entries + cache.paused_entries

    if len(entries) == 1:
        console.print(markup.dimmed("Nothing to switch."))
        raise click.exceptions.Exit()

    select: str
    if not entry:
        table: Table = render.map_sequence_to_rich_table(entries)
        if not table.row_count:
            rprint(markup.dimmed("No results"))
            raise click.exceptions.Exit()

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
        select = id_list.match_id(entry)

    if cache.index(cache.paused_entries, "id", [select]):
        routine._resume_time_entry(select, now, wait=debug)
        debug and console.log("[DEBUG]", f"resuming entry {select}")

    if not continue_:
        routine._pause_time_entry(cache.id, now, wait=debug)
        debug and console.log("[DEBUG]", f"pausing entry {cache.id}")

    cache.switch_active_entry(select, now, continue_)


@click.command(
    cls=FormattedCommand,
    name="update",
    short_help="Update active entry.",
    syntax=Syntax(
        code="""\
        # update active entries project, and set start to 30 min ago
        $ timer update --project lightlike-cli --start 30m
        $ timer update -plightlike-cli -s30m
    
        $ timer update --billable true --note "redefine task"
        $ t u -b1 -n"redefine task"\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
    "stop_active",
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
@click.argument(
    "note-parts",
    type=click.UNPROCESSED,
    required=False,
    default=None,
    callback=None,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=None,
)
@_pass.routine
@_pass.cache
@_pass.console
@_pass.appdata
@_pass.ctx_group(parents=1)
@_pass.now
def update(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    appdata: "TimeEntryAppData",
    console: Console,
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    billable: bool | None,
    project: str | None,
    start: datetime | None,
    note: str | None,
    stop_active: bool,
    note_parts: t.Sequence[str],
) -> None:
    """
    Update the [b]active[/b] time entry.

    [NOTE ARGS]:
        all unprocessed arguments will be joined to create the note field.
        this only takes into effect if the `--note` / `-n` option is unused.

    [b]See[/]:
        timer:edit for making changes to entries that have already stopped.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not cache:
        ctx.fail("There is no active time entry.")

    if not any([project, note, billable is not None, start]):
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    copy: dict[str, t.Any] = cache.active.copy()
    edits: dict[str, t.Any] = {}

    if not note and note_parts:
        note = " ".join(note_parts)

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
            dates.calculate_duration(
                start_date=start,
                end_date=now,
                paused_hours=cache.paused_hours or 0,
                raise_if_negative=True,
                exception=click.BadArgumentUsage(
                    message="Invalid value for args [START] | [END]. New duration cannot be negative. "
                    f"Existing paused hours = {cache.paused_hours}",
                    ctx=ctx,
                ),
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

    if not any(filter(lambda k: k in edits, ["project", "note", "billable", "start"])):
        ctx.fail("No fields to update.")

    start_date: date | None = None
    start_time: time | None = None
    if "start" in edits:
        start_time = edits["start"].time()
        start_date = edits["start"].date()

    query_job: "QueryJob" = routine._update_time_entries(
        ids=[cache.id],
        project=edits.get("project"),
        note=edits.get("note"),
        billable=edits.get("billable"),
        date=start_date,
        start_time=start_time,
    )

    if stop_active:
        routine._stop_time_entry(cache.id, now, wait=debug)
        cache._clear_active()
        if AppConfig().get("settings", "update-terminal-title", default=True):
            console.set_window_title(__appname_sc__)

    sync_kwargs = {"trigger_query_job": query_job, "debug": debug}
    threads.spawn(ctx, appdata.sync, sync_kwargs)

    original_record = {
        "id": copy["id"][:7],
        "project": copy["project"],
        "start": copy["start"],
        "note": copy["note"],
        "billable": copy["billable"],
    }

    console.print(
        "Updated record:",
        render.create_row_diff(original=original_record, new=edits),
    )
