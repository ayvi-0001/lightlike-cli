# mypy: disable-error-code="import-untyped, func-returns-value"

import typing as t
from datetime import datetime, timedelta
from decimal import Decimal
from os import getenv
from pathlib import Path

from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import fragment_list_width
from rich import get_console

from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.app.dates import now, seconds_to_time_parts

if t.TYPE_CHECKING:
    from datetime import _TzInfo


__all__: t.Sequence[str] = ("build",)


USERNAME: str = AppConfig().get("user", "name")
HOSTNAME: str = AppConfig().get("user", "host")
GCP_PROJECT: str = AppConfig().get("client", "active_project")
BRANCH: str = AppConfig().get("git", "branch")
PATH: str = AppConfig().get("git", "path")
TIMEZONE: "_TzInfo" = AppConfig().tz


def build(message: str | None = None, hide_rprompt: bool = False) -> str:
    """
    The actual return for this function is either a sequence of tuples, or a callable returning a sequence of tuples.
    The return value is casted as a string only to signal to the type checker
    that the return value has the required type for :param: `message` in :class: `prompt_toolkit.shortcuts.PromptSession`.
    It should only be used in that context.
    """
    if not message:
        cursor: list[tuple[str, str]] = []
        cwd: Path = Path.cwd()
        columns: int = get_app().output.get_size().columns

        _extend_base(cursor, cwd)
        _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        cache: TimeEntryCache = TimeEntryCache()
        running_entries: int = cache.count_running_entries
        paused_entries: int = cache.count_paused_entries
        entry_counter: str = _entry_counter(running_entries, paused_entries)

        if cache:
            cache_project: str = cache.project
            stopwatch: str = _stopwatch(cache)
            _set_title(stopwatch, cache_project)
            _extend_stopwatch(
                cursor,
                stopwatch,
                cache_project,
                cache.note,
                columns,
                entry_counter,
            )
        not hide_rprompt and _extend_entry_counter(
            cursor,
            columns,
            entry_counter,
        )
        _extend_cursor_pointer(cursor)

        return t.cast(str, cursor)

    def build_with_message() -> t.Sequence[tuple[str, str]]:
        cursor: list[tuple[str, str]] = []
        cwd: Path = Path.cwd()
        columns: int = get_app().output.get_size().columns

        _extend_base(cursor, cwd)
        _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        cache: TimeEntryCache = TimeEntryCache()
        running_entries: int = cache.count_running_entries
        paused_entries: int = cache.count_paused_entries
        entry_counter: str = _entry_counter(running_entries, paused_entries)

        if cache:
            cache_project: str = cache.project
            stopwatch: str = _stopwatch(cache)
            _set_title(stopwatch, cache_project)
            _extend_stopwatch(
                cursor,
                stopwatch,
                cache_project,
                cache.note,
                columns,
                entry_counter,
            )
        not hide_rprompt and _extend_entry_counter(
            cursor,
            columns,
            entry_counter,
        )

        nonlocal message
        _extend_cursor_pointer(cursor, message)

        return cursor

    return t.cast(str, build_with_message)


if all(
    [
        LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"),
        LIGHTLIKE_CLI_DEV_HOSTNAME := getenv("LIGHTLIKE_CLI_DEV_HOSTNAME"),
    ]
):

    def _extend_base(cursor: list[tuple[str, str]], cwd: Path) -> None:
        home: Path = cwd.home()
        home_drive: str = home.drive
        cwd_drive: str = cwd.drive

        if home_drive.startswith(cwd_drive):
            path_prefix: str = " ~"
            drive: str = home_drive
        else:
            path_prefix = " /"
            drive = cwd_drive

        path_name: str = (
            cwd.as_posix()
            .removeprefix(f"{home.as_posix()}")
            .replace(drive, drive.lower().replace(":", ""))
        )

        cursor.extend(
            [
                ("", "\n"),
                ("class:prompt.user", LIGHTLIKE_CLI_DEV_USERNAME or ""),
                ("class:prompt.at", "@"),
                ("class:prompt.host", LIGHTLIKE_CLI_DEV_HOSTNAME or ""),
                ("class:prompt.path.prefix", path_prefix),
                ("class:prompt.path.name", path_name or "/"),
            ]
        )

else:

    def _extend_base(cursor: list[tuple[str, str]], cwd: Path) -> None:
        home: Path = cwd.home()
        home_drive: str = home.drive
        cwd_drive: str = cwd.drive

        if home_drive.startswith(cwd_drive):
            path_prefix: str = " ~"
            drive = home_drive
        else:
            path_prefix = " /"
            drive = cwd_drive

        path_name: str = (
            cwd.as_posix()
            .removeprefix(f"{home.as_posix()}")
            .replace(drive, drive.lower().replace(":", ""))
        )

        global USERNAME, HOSTNAME
        cursor.extend(
            [
                ("", "\n"),
                ("class:prompt.user", USERNAME),
                ("class:prompt.at", "@"),
                ("class:prompt.host", HOSTNAME),
                ("class:prompt.path.prefix", path_prefix),
                ("class:prompt.path.name", path_name or "/"),
            ]
        )


def _set_title(stopwatch: str, cache_project: str) -> None:
    get_console().set_window_title(f"{stopwatch} | {cache_project}")


def _stopwatch(cache: TimeEntryCache) -> str:
    paused_hours: "Decimal" = cache.paused_hours
    start: datetime = cache.start

    global TIMEZONE
    if paused_hours:
        phr, pmin, psec = seconds_to_time_parts(paused_hours * Decimal(3600))
        paused_delta: timedelta = timedelta(hours=phr, minutes=pmin, seconds=psec)
        return f" {(now(TIMEZONE) - start) - paused_delta}"
    else:
        return f" {now(TIMEZONE) - start}"


def _entry_counter(running_entries: int, paused_entries: int) -> str:
    indicator_running = f"R[{running_entries}]" if running_entries > 1 else ""
    indicator_paused = f"P[{paused_entries}]" if paused_entries >= 1 else ""
    separator = " " if all([indicator_running, indicator_paused]) else ""
    extension = f"{indicator_running}{separator}{indicator_paused}"
    return extension


def _extend_entry_counter(
    cursor: list[tuple[str, str]],
    columns: int,
    entry_counter: str,
) -> None:
    global TIMEZONE
    ts = "[%s]" % now(TIMEZONE).strftime("%H:%M:%S")

    if entry_counter:
        padding = " " * (
            columns
            - fragment_list_width(cursor)  # type: ignore[arg-type]
            - (len(entry_counter) + len(ts))
            - (4 if entry_counter else 1)
        )
        cursor.extend(
            [
                ("", padding),
                ("class:rprompt.clock", f" {ts} "),
                ("class:rprompt.entries", f" {entry_counter} "),
            ]
        )
    else:
        padding = " " * (
            columns
            - fragment_list_width(cursor)  # type: ignore[arg-type]
            - len(ts)
            - 1
        )
        cursor.extend([("", padding), ("class:rprompt.clock", f" {ts}")])


def _extend_stopwatch(
    cursor: list[tuple[str, str]],
    stopwatch: str,
    cache_project: str,
    cache_note: str,
    columns: int,
    entry_counter: str,
) -> None:
    cursor.extend([("class:prompt.stopwatch", stopwatch)])
    if cache_project:
        cursor.extend([("class:prompt.stopwatch", f" | {cache_project} ")])
    if cache_note:
        cursor_width = fragment_list_width(cursor)  # type: ignore[arg-type]
        max_width = min(columns - (cursor_width + 19 + len(entry_counter)), 50)
        note_ext = (
            f"{cache_note[:max_width].strip()}…"
            if len(cache_note) > max_width
            else cache_note
        )
        cursor.extend([("class:prompt.note", f" | {note_ext} ")])


if LIGHTLIKE_CLI_DEV_GCP_PROJECT := getenv("LIGHTLIKE_CLI_DEV_GCP_PROJECT"):

    def _extend_active_project(cursor: list[tuple[str, str]], project: str) -> None:
        cursor.extend(
            [
                ("class:prompt.project.parenthesis", " ("),
                ("class:prompt.project.name", LIGHTLIKE_CLI_DEV_GCP_PROJECT or ""),
                ("class:prompt.project.parenthesis", ") "),
            ]
        )

else:

    def _extend_active_project(cursor: list[tuple[str, str]], project: str) -> None:
        cursor.extend(
            [
                ("class:prompt.project.parenthesis", " ("),
                ("class:prompt.project.name", project),
                ("class:prompt.project.parenthesis", ") "),
            ]
        )


def _extend_git_branch(cursor: list[tuple[str, str]], cwd: Path) -> None:
    global BRANCH, PATH
    if BRANCH:
        if not cwd.is_relative_to(PATH):
            PATH, BRANCH = "", ""
            with AppConfig().rw() as config:
                config["git"].update(path=PATH, branch=BRANCH)
    else:
        if (head_dir := cwd / ".git" / "HEAD").exists():
            PATH = head_dir.parent.parent.resolve().as_posix()
            BRANCH = head_dir.read_text().splitlines()[0].partition("refs/heads/")[2]
            with AppConfig().rw() as config:
                config["git"].update(path=PATH, branch=BRANCH)

    BRANCH and cursor.extend(
        [
            ("class:prompt.branch.parenthesis", "("),
            ("class:prompt.branch.name", BRANCH),
            ("class:prompt.branch.parenthesis", ") "),
        ]
    )


def _extend_cursor_pointer(cursor: list[tuple[str, str]], message: str = "") -> None:
    pointer = f"\n{message}{'$ ' if not message else ' $ '}"
    cursor.extend([("class:cursor", pointer)])


# CONSOLE_WIDTH: int = get_console().width

# def _clear_on_resize(console: Console) -> None:
#     global CONSOLE_WIDTH
#     if console.width != CONSOLE_WIDTH:
#         CONSOLE_WIDTH = console.width
#         console.clear()
