import os
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
import sqlalchemy as sq
from apscheduler.schedulers.background import BackgroundScheduler
from more_itertools import first, locate, one
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

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
from lightlike.cmd import _pass
from lightlike.internal import appdir, markup, utils

if t.TYPE_CHECKING:
    from lightlike.app.cache import TimeEntryAppData, TimeEntryIdList
    from lightlike.client import CliQueryRoutines

__all__: t.Sequence[str] = (
    "add",
    "delete",
    "edit",
    "focus",
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


SchedulerCallable: t.TypeAlias = t.Callable[[], BackgroundScheduler]


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

    [bold #34e2e2]NOTE PARTS[/]:
        all unprocessed arguments will be joined to create the note field.
        this only takes into effect if the `--note` / `-n` option is unused.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    if note == "None" and note_parts:
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
        appdata.sync(debug=debug)
        data = appdata.load()
        active_projects = data["active"]
        project_default_billable = active_projects[project]["default_billable"]

    debug and console.log(
        "[DEBUG]",
        "getting projects default billable value:",
        project_default_billable,
    )

    time_entry_id = sha1(f"{project}{note}{start_local}".encode()).hexdigest()

    scheduler().add_job(
        func=routine._add_time_entry,
        trigger="date",
        run_date=datetime.now(),
        kwargs={
            "id": time_entry_id,
            "project": project,
            "note": note or "None",
            "start_time": start_local,
            "end_time": end_local,
            "hours": hours,
            "billable": billable if billable in (True, False) else project_default_billable,
        },
    )

    threads.spawn(
        ctx=ctx,
        fn=id_list.add,
        kwargs={"entry_id": time_entry_id, "debug": debug},
    )
    note != "None" and threads.spawn(ctx=ctx, fn=appdata.sync)

    mappings = [
        {
            "id": time_entry_id[:7],
            "project": project,
            "date": start_local.date(),
            "start": start_local.time(),
            "end": end_local.time(),
            "note": note or "None",
            "billable": billable if billable in (True, False) else project_default_billable,
            "hours": hours,
        },
    ]

    console.print(
        "Added record:",
        render.map_sequence_to_rich_table(mappings=mappings),
    )


def yank_flag_help() -> str:
    if appdir.TIMER_LIST_CACHE.exists():
        timer_list_cache: dict[str, str] = loads(appdir.TIMER_LIST_CACHE.read_text())
        len_cache: int = len(timer_list_cache)
        if len_cache > 0:
            return f"Pull id from latest timer:list cmd. Cache range: {-len_cache}<=x<={len_cache}"

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
    callback=validate.callbacks.timer_list_cache_idx,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-y",
    "--yank",
    cls=shell_complete.DynamicHelpOption,
    show_default=True,
    multiple=True,
    type=shell_complete.CallableIntRange(
        min=lambda: -len(loads(appdir.TIMER_LIST_CACHE.read_text())),
        max=lambda: len(loads(appdir.TIMER_LIST_CACHE.read_text())),
    ),
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
        this option supports negative indexing, and can be repeated and combined with --id / -i.
        e.g.

        ```
        $ timer list --current-week

        | row | id      |   ...
        |-----|---------|   ...
        |   1 | a6c8e8e |   ...
        |   2 | e01812e |   ...
        |   3 | dfe6b73 |   ...
        ```

        --yank 2 [d](or -y2)[/d] would be the same as typing --id e01812e
        --yank -1 [d](or -y-1)[/d] would be the same as typing --id dfe6b73

    --use-list-timer-list / -u:
        pass all id's from the most recent timer:list result to this command
        this option can be repeated and combined with --id / -i or --yank / -y.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    ids_to_match: list[str] = [
        *(id_options or []),
        *(yank or []),
        *(use_last_timer_list or []),
    ]

    if not ids_to_match:
        param = one(filter(lambda p: p.name == "id_options", ctx.command.params))
        raise click.MissingParameter(ctx=ctx, param=param)

    with console.status(status=markup.status_message("Deleting entries")):
        matched_ids, non_matched_ids = _match_ids(
            ctx=ctx,
            id_list=id_list,
            ids_to_match=ids_to_match,
        )
        console.print(markup.bg("Matched "), matched_ids, end="")

        if non_matched_ids:
            console.print(markup.red("Non-matched "), non_matched_ids, end="")

        for id_match in matched_ids:
            if cache.id == id_match:
                cache.clear_active()
            elif cache.exists(cache.running_entries, [id_match]):
                cache.remove("id", [id_match], [cache.running_entries])
            elif cache.exists(cache.paused_entries, [id_match]):
                cache.remove("id", [id_match], [cache.paused_entries])

        scheduler().add_job(
            func=routine._delete_time_entries,
            trigger="date",
            run_date=datetime.now(),
            kwargs={"ids": matched_ids},
        )

        console.print("Deleted time entries")

        threads.spawn(
            ctx=ctx,
            fn=appdata.sync,
            kwargs={"debug": debug},
        )
        threads.spawn(
            ctx=ctx,
            fn=id_list.remove,
            kwargs={"entry_ids": matched_ids, "debug": debug},
        )


def _get_entry_edits(
    matched_ids: list[str],
    entry_row: dict[str, t.Any],
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
        # Only include date.
        # Procedure in BigQuery will handle updating each
        # individual time entries start and end times.
        case True, True, True:
            new_date, new_start, new_end = dates.combine_new_date_into_start_and_end(
                in_datetime=date, in_start=start_time, in_end=end_time
            )
            edits["start_time"] = new_start
            edits["end_time"] = new_end
            edits["date"] = new_date
        case True, True, False:
            new_date, new_start, new_end = dates.combine_new_date_into_start(
                in_datetime=date, in_start=start_time, in_end=entry_row["end"]
            )
            edits["start_time"] = new_start
            edits["date"] = new_date
        case True, False, False:
            new_date, new_start, new_end = dates.combine_new_date_into_start_and_end(
                in_datetime=date,
                in_start=entry_row["start"],
                in_end=entry_row["end"],
            )
            edits["date"] = new_date
        case True, False, True:
            new_date, new_start, new_end = dates.combine_new_date_into_end(
                in_datetime=date, in_start=entry_row["start"], in_end=end_time
            )
            edits["end_time"] = new_end
            edits["date"] = new_date
        case False, True, False:
            new_date, new_start, new_end = dates.combine_new_date_into_start(
                in_datetime=entry_row["start"],
                in_start=start_time,
                in_end=entry_row["end"],
            )
            edits["start_time"] = new_start
        case False, False, True:
            new_date, new_start, new_end = dates.combine_new_date_into_end(
                in_datetime=entry_row["start"],
                in_start=entry_row["start"],
                in_end=end_time,
            )
            edits["end_time"] = new_end
        case False, True, True:
            new_date, new_start, new_end = dates.combine_new_date_into_start_and_end(
                in_datetime=entry_row["start"],
                in_start=start_time,
                in_end=end_time,
            )
            edits["start_time"] = new_start
            edits["end_time"] = new_end

    if any([truth(date), truth(start_time), truth(end_time)]):
        paused_hours = entry_row["paused_hours"]
        duration = new_end - new_start
        paused_hours, paused_minutes, paused_seconds = dates.seconds_to_time_parts(
            dates.hours_to_seconds(paused_hours),
        )

        duration = duration - timedelta(
            hours=paused_hours,
            minutes=paused_minutes,
            seconds=paused_seconds,
        )
        total_seconds: float = duration.total_seconds()

        if total_seconds < 0 or copysign(1, duration.days) == -1:
            matched_ids.pop(matched_ids.index(entry_row["id"]))

            _compare_start = (
                f"original start = {entry_row['start'].strftime('%Y-%m-%d %H:%M:%S')}"
                f" | new start {new_start.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            _compare_end = (
                f"original end = {entry_row['end'].strftime('%Y-%m-%d %H:%M:%S')}"
                f" | new end {new_end.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            console.print(
                cleandoc(
                    f"""
            [code]{entry_row["id"]}[/code] updates failed: Negative Duration.
            {_compare_start}
            {_compare_end}
            paused_hours = [repr.number]{entry_row["paused_hours"]}[/repr.number]
            duration = {duration}
            Removed from edits.
                """,
                ),
            )
            return None

        hours = dates.seconds_to_hours(total_seconds, ndigits=4)
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
    callback=validate.callbacks.timer_list_cache_idx,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-y",
    "--yank",
    cls=shell_complete.DynamicHelpOption,
    show_default=True,
    multiple=True,
    type=shell_complete.CallableIntRange(
        min=lambda: -len(loads(appdir.TIMER_LIST_CACHE.read_text())),
        max=lambda: len(loads(appdir.TIMER_LIST_CACHE.read_text())),
    ),
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
        this option supports negative indexing, and can be repeated and combined with --id / -i.
        e.g.

        ```
        $ timer list --current-week

        | row | id      |   ...
        |-----|---------|   ...
        |   1 | a6c8e8e |   ...
        |   2 | e01812e |   ...
        |   3 | dfe6b73 |   ...
        ```

        --yank 2 [d](or -y2)[/d] would be the same as typing --id e01812e
        --yank -1 [d](or -y-1)[/d] would be the same as typing --id dfe6b73

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
            matched_entries: list[dict[str, t.Any]] = [r._asdict() for r in routine._get_time_entries(
                ids=matched_ids,
            )]
        except Exception as error:
            console.print(markup.br("Error:"), error)
            raise click.exceptions.Exit()

        all_edits: list[dict[str, t.Any]] = []
        for row in matched_entries:
            edits = _get_entry_edits(
                matched_ids=matched_ids,
                entry_row=row,
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
            all_edits.append(edits)

        debug and console.log("[DEBUG]", all_edits)

        status_renderable = Text.assemble(
            markup.status_message(
                "Editing %s: " % ("entries" if len(matched_ids) > 1 else "entry"),
            ),
            Text.join(Text(", "), [markup.code(_id[:7]) for _id in matched_ids]),
        )

        if not all_edits:
            ctx.fail("Nothing to edit.")

        edits = first(all_edits)
        status.update(status_renderable)

        routine._update_time_entries(
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

        for row, edits in t.cast(
            "t.Sequence[tuple[sq.Row[t.Any], dict[str, t.Any]]]",
            zip(matched_entries, all_edits, strict=False),
        ):
            _start_datetime = row.get("start")
            _end_datetime = row.get("end")

            try:
                _start_time = _start_datetime.time()
                _end_time = _end_datetime.time()
            except Exception:
                ctx.fail(
                    "Failed to retrieve start/end times. Possible there is "
                    "still a job running on one of these records. "
                    "Please wait a moment and try again.",
                )

            original_record = {
                "id": row.get("id")[:7],
                "project": row.get("project"),
                "date": row.get("date"),
                "start_time": _start_time,
                "end_time": _end_time,
                "note": row.get("note"),
                "billable": row.get("billable"),
                "paused_hours": row.get("paused_hours") or 0,
                "hours": round(Decimal(row.get("hours")), 4),
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
        threads.spawn(ctx, appdata.sync, kwargs={"debug": debug})


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
    rows: t.Sequence[sq.Row[t.Any]] = routine._get_time_entries(
        [id_list.match_id(time_entry_id)],
    )
    if not rows:
        console.print(markup.dimmed("Id not found"))
    else:
        console.print_json(
            data=dict(one(rows).items()),
            default=str,
            indent=4,
        )


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
    multiple=True,
    type=click.STRING,
    help="Regex flags to pass to re.search",
    required=False,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.Param("modifiers").regex_flags,
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
    modifiers: t.Sequence[str],
    limit: int | None,
    offset: int | None,
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

    Example:
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
    ctx, _ = ctx_group

    if offset and not limit:
        console.print(
            "--offset / -o does not do anything without also using --limit / -l"
        )

    where_clause: str = shell_complete.where._parse_click_options(
        flag=prompt_where,
        args=where,
        console=console,
        routine=routine,
    )

    if not exclude:
        lightlike_list_exclude = os.environ.get("LIGHTLIKE_LIST_EXCLUDE")
        if lightlike_list_exclude:
            exclude = lightlike_list_exclude.split(",")

    if all_:
        rows = routine._list_timesheet(
            exclude=exclude,
            include=include,
            limit=limit,
            match_note=match_note,
            match_project=match_project,
            modifiers=modifiers,
            offset=offset,
            where=where_clause,
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
        else:
            raise click.exceptions.Exit()

        rows = routine._list_timesheet(
            start_date=date_params.start.date(),
            end_date=date_params.end.date(),
            where=where_clause,
            include=include,
            exclude=exclude,
            match_project=match_project,
            match_note=match_note,
            modifiers=modifiers,
            limit=limit,
            offset=offset,
        )

    else:
        query_date = date or now
        rows = routine._list_timesheet(
            date=query_date.date(),
            where=where_clause,
            include=include,
            exclude=exclude,
            match_project=match_project,
            match_note=match_note,
            modifiers=modifiers,
            limit=limit,
            offset=offset,
        )

    rows: list[dict[str, t.Any]] = [r._asdict() for r in rows]
    final_rows = []

    final_flags: re.RegexFlag = re.RegexFlag.NOFLAG
    if modifiers:
        for modifier in modifiers:
            final_flags |= getattr(re.RegexFlag, modifier)

    total: Decimal = Decimal(0)

    for row in rows:
        new_row: dict[str, t.Any] = {}
        new_row["row"] = row["row"]
        new_row["id"] = row["id"][:7]
        new_row["date"] = row["date"]
        new_row["start"] = t.cast("datetime", row["start"]).strftime("%H:%M:%S")
        if row["end"] is not None:
            new_row["end"] = t.cast("datetime", row["end"]).strftime("%H:%M:%S")
        else:
            new_row["end"] = None
        new_row["project"] = row["project"]
        new_row["note"] = row["note"]
        new_row["billable"] = row["billable"]
        new_row["active"] = row["active"]
        new_row["paused"] = row["paused"]

        new_row["paused_hours"] = row["paused_hours"]

        if row["paused"] is True:
            _, new_row["paused_hours"] = (
                dates.date_diff(  # TODO combine this with the first if case below
                    date_start=t.cast("datetime", row["timestamp_paused"]),
                    date_end=now,
                    add_hours=row["paused_hours"],
                )
            )

        if row["paused"] is True:
            _, current_paused_hours = dates.date_diff(row["timestamp_paused"], now)
            total_paused_hours = current_paused_hours + (row["paused_hours"] or 0)
            _, hours = dates.date_diff(
                row["timestamp_start"],
                now,
                total_paused_hours,
            )
        elif row["active"] is True:
            _, hours = dates.date_diff(
                row["timestamp_start"],
                row["timestamp_end"] or now,
                row["paused_hours"],
            )
        else:
            hours = row["hours"]

        new_row["hours"] = hours
        total += hours
        new_row["total"] = total

        final_rows.append(new_row)

    appdir.TIMER_LIST_CACHE.write_text(
        dumps({idx: row.get("id") for idx, row in enumerate(final_rows)}),
        encoding="utf-8",
    )

    if console.width < 80:
        console.print_json(data=rows, default=str)
    else:
        table: Table = render.map_sequence_to_rich_table(
            mappings=final_rows,
            exclude_fields=(
                ["paused_hours", "note", "paused", "active"] if console.width < 100 else None
            ),
        )
        if not table.row_count:
            rprint(markup.dimmed("No results"))
            raise click.exceptions.Exit()

        console.print(table)


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
    short_help="Replace notes through the default text editor.",
    syntax=Syntax(
        code="$ timer notes update lightlike-cli",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@click.argument(
    "project",
    nargs=1,
    type=shell_complete.projects.AnyProject,
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_argument,
)
@click.option(
    "-d",
    "--dry-run",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    hidden=True,
    type=click.BOOL,
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.appdata
@_pass.console
@_pass.ctx_group(parents=1)
def update_notes(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    appdata: "TimeEntryAppData",
    routine: "CliQueryRoutines",
    project: str,
    dry_run: bool,
) -> None:
    """
    Update notes for a project through the default text editor.

    A temporary file will open with all notes for the given project.
    There are 2 identical columns. Any edits to the note in the right column will be made against all
    timesheet entries matching the original note on the left.
    If the file is closed without saving, no edits will be applied.
    Use option `--dry-run` / `-d` to see the query without making any changes.
    """
    ctx, _ = ctx_group

    query_job = routine._select(
        resource=routine.timesheet_id,
        distinct=True,
        fields=["note"],
        where=[f'project = "{project}"', "note is not null"],
        order=["note"],
    )

    notes = list[str](map(_get.note, query_job))
    text = ""

    for idx, note in enumerate(notes):
        whitespace = " " * ((max(map(len, notes)) + 4) - len(note))
        text += f"{note}{whitespace}\t{note}"
        if idx < len(notes):
            text += "\n"

    editor: str | None = AppConfig().editor

    if not editor:
        ctx.fail("Cannot determine $EDITOR.")

    result: str | None = click.edit(
        text=text,
        editor=editor,
        require_save=True,
    )

    if not result:
        console.print(markup.dimmed("No edits made."))
        raise click.exceptions.Exit()

    replacements = {}
    for line in result.splitlines():
        old_note, new_note = line.split("\t")
        old_note, new_note = old_note.strip(), new_note.strip()
        if old_note != new_note:
            replacements[old_note] = escape(new_note)

    if not replacements:
        console.print(markup.dimmed("No edits made."))
        raise click.exceptions.Exit()

    case_statement: str = "CASE note "
    where_statement: str = ""

    for idx, (k, v) in enumerate(replacements.items()):
        case_statement += f'WHEN "{k}" THEN "{v}" '
        where_statement += f'"{k}",'

    case_statement += "ELSE note END"
    where_statement = where_statement.strip(",")

    query = " ".join(
        [
            f"UPDATE {routine.timesheet_id}",
            f"SET note = {case_statement}",
            f'WHERE project = "{project}" AND note in ({where_statement})',
        ]
    )

    if dry_run:
        console.print(query)
        console.print(markup.dimmed("Dry run. No changes made against table."))
        return

    with console.status("Updating notes"):
        routine._query(query, wait=True)

    threads.spawn(ctx=ctx, fn=appdata.sync, delay=2)


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
    ctx, _ = ctx_group
    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    if not cache:
        console.print(markup.dimmed("There is no active time entry."))
        return

    scheduler().add_job(
        func=routine._pause_time_entry,
        trigger="date",
        run_date=datetime.now(),
        kwargs={"id": cache.id, "timestamp_paused": now},
    )

    cache.pause_entry(0, now)


@click.command(
    cls=FormattedCommand,
    name="resume",
    short_help="Resume a paused time entry.",
    syntax=Syntax(
        code="""\
        $ timer resume 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        $ t re 36c9fe5\
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

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    if not cache.paused_entries:
        console.print(markup.dimmed("No paused time entries."))
        return

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
        scheduler().add_job(
            func=routine._resume_time_entry,
            trigger="date",
            run_date=datetime.now(),
            kwargs={"id": matched_id, "time_resume": now},
        )
    else:
        if len(entry) < 40:
            matched_id = id_list.match_id(entry)
        else:
            matched_id = entry

        if not cache.exists(cache.paused_entries, [matched_id]):
            raise click.UsageError(message="This entry is not paused.", ctx=ctx)

        cache.resume_entry(matched_id, now)
        scheduler().add_job(
            func=routine._resume_time_entry,
            trigger="date",
            run_date=datetime.now(),
            kwargs={"id": matched_id, "time_resume": now},
        )


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

    [bold #34e2e2]NOTE PARTS[/]:
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

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    if note == "None" and note_parts:
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

    scheduler().add_job(
        func=routine._start_time_entry,
        trigger="date",
        run_date=datetime.now(),
        kwargs={
            "time_entry_id": time_entry_id,
            "project": project,
            "note": note,
            "start_time": start_local,
            "billable": billable if billable in (True, False) else project_default_billable,
        },
    )

    if pause_active:
        if cache:
            entry_to_pause: str = copy(cache.id)
            cache.pause_entry(0, start_local)
            scheduler().add_job(
                func=routine._pause_time_entry,
                trigger="date",
                run_date=datetime.now(),
                kwargs={"id": entry_to_pause, "timestamp_paused": start_local},
            )
        else:
            console.print("No active entry. --pause-active / -P ignored.")

    if cache:
        cache.start_new_active_time_entry()

    with cache.rw() as cache:
        cache.id = time_entry_id
        cache.project = project
        cache.note = note if note != "None" else None  # type: ignore[assignment]
        cache.billable = billable or project_default_billable
        cache.start = start_local

    threads.spawn(
        ctx=ctx,
        fn=appdata.sync,
        kwargs={"debug": debug},
        delay=2,
    )
    threads.spawn(
        ctx=ctx,
        fn=id_list.add,
        kwargs={"entry_id": time_entry_id, "debug": debug},
        delay=2,
    )


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
        code="""\
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
    ctx, _ = ctx_group

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    if not entry:
        if cache:
            scheduler().add_job(
                func=routine._stop_time_entry,
                trigger="date",
                run_date=datetime.now(),
                kwargs={"id": cache.id, "end": now},
            )
            cache.clear_active()
            return

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
    scheduler().add_job(
        func=routine._stop_time_entry,
        trigger="date",
        run_date=datetime.now(),
        kwargs={"id": matched_id, "end": now},
    )

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
        $ t s 36c9fe\
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
) -> None:
    """
    Switch the active time entry.

    Pauses the active entry and resume/focus the selected entry.

    [b]See[/]:
        timer:run --help / -h
    """
    ctx, parent = ctx_group

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    entries: list[dict[str, t.Any]] = cache.running_entries + cache.paused_entries

    if len(entries) == 1:
        console.print(markup.dimmed("No entries to switch to."))
        raise click.exceptions.Exit()

    if not cache:
        ctx.fail("There is no active time entry. Use timer:resume instead.")

    debug: bool = parent.params.get("debug", False)

    if not entry:
        table: Table = render.map_sequence_to_rich_table(entries)
        if not table.row_count:
            rprint(markup.dimmed("No results"))
            raise click.exceptions.Exit()

        console.print(table)

        choices: list[str] = list(
            filter(lambda i: not cache.id.startswith(i), map(_get._id, entries))
        )

        select: str = _questionary.select(
            message="Select a time entry.",
            instruction="(active entry excluded)",
            choices=choices,
        )
    else:
        select = id_list.match_id(entry)

    # pause active entry in db
    scheduler().add_job(
        func=routine._pause_time_entry,
        trigger="date",
        run_date=datetime.now(),
        kwargs={"id": cache.id, "timestamp_paused": now},
    )
    debug and console.log("[DEBUG]", f"pausing entry {cache.id}")

    # resume new active entry in db, if paused
    if cache.index(cache.paused_entries, "id", [select]):
        scheduler().add_job(
            func=routine._resume_time_entry,
            trigger="date",
            run_date=datetime.now(),
            kwargs={"id": select, "time_resume": now},
        )
        debug and console.log("[DEBUG]", f"resuming entry {select}")

    # pause active entry local, switch active entry idx
    cache.switch_entry(select, now, pause=True)


@click.command(
    cls=FormattedCommand,
    name="focus",
    short_help="Set a running entry as active.",
    syntax=Syntax(
        code="""\
        $ timer focus 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        $ t f 36c9fe\
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
@_pass.console
@_pass.id_list
@_pass.routine
@_pass.cache
@_pass.ctx_group(parents=1)
@_pass.now
def focus(
    now: datetime,
    ctx_group: t.Sequence[click.Context],
    cache: "TimeEntryCache",
    routine: "CliQueryRoutines",
    id_list: "TimeEntryIdList",
    console: Console,
    entry: str | None,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    entries: list[dict[str, t.Any]] = cache.running_entries + cache.paused_entries

    if len(entries) == 1:
        console.print(markup.dimmed("No time entries to select from."))
        raise click.exceptions.Exit()

    if not entry:
        table: Table = render.map_sequence_to_rich_table(entries)
        if not table.row_count:
            rprint(markup.dimmed("No results"))
            raise click.exceptions.Exit()

        console.print(table)

        choices: list[str] = list(
            filter(lambda i: not cache.id.startswith(i), map(_get._id, entries)),
        )

        select: str = _questionary.select(
            message="Select a time entry.",
            instruction="(active entry excluded)",
            choices=choices,
        )
    else:
        select = id_list.match_id(entry)

    if cache.index(cache.paused_entries, "id", [select]):
        scheduler().add_job(
            func=routine._resume_time_entry,
            trigger="date",
            run_date=datetime.now(),
            kwargs={"id": select, "time_resume": now},
        )

        debug and console.log("[DEBUG]", f"resuming entry {select}")

    cache.switch_entry(select, now)


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

    [bold #34e2e2]NOTE PARTS[/]:
        all unprocessed arguments will be joined to create the note field.
        this only takes into effect if the `--note` / `-n` option is unused.

    [b]See[/]:
        timer:edit for making changes to entries that have already stopped.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    scheduler: SchedulerCallable = ctx.find_root().obj.get("get_scheduler")

    if not cache:
        ctx.fail("There is no active time entry.")

    if not note and note_parts:
        note = " ".join(note_parts)

    if not any([project, note, billable is not None, start]):
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    copy: dict[str, t.Any] = cache.active.copy()
    edits: dict[str, t.Any] = {}

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

    scheduler().add_job(
        func=routine._update_time_entries,
        trigger="date",
        run_date=datetime.now(),
        kwargs={
            "ids": [cache.id],
            "project": edits.get("project"),
            "note": edits.get("note"),
            "billable": edits.get("billable"),
            "date": start_date,
            "start_time": start_time,
        },
    )

    if stop_active:
        scheduler().add_job(
            func=routine._stop_time_entry,
            trigger="date",
            run_date=datetime.now(),
            kwargs={"id": cache.id, "end": now},
        )
        cache.clear_active()

    threads.spawn(ctx=ctx, fn=appdata.sync, kwargs={"debug": debug})

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
