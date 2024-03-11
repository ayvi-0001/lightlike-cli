from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Sequence, cast

from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import fragment_list_width
from rich import get_console
from rich.console import Console

from lightlike.app.cache import TomlCache
from lightlike.app.config import AppConfig
from lightlike.internal import utils

__all__: Sequence[str] = ("build",)


USERNAME = AppConfig().username
HOSTNAME = AppConfig().hostname
CONSOLE_WIDTH: int = get_console().width
TIMEZONE = AppConfig().tz


def build(message: str | None = None, hide_rprompt: bool = False) -> str:
    """
    The actual return for this function is either a sequence of tuples,
    or a callable returning a sequence of tuples.\n
    The return value is casted as a string type only to signal to the type checker
    that the return value has the required type for :param: `message` in :class: `prompt_toolkit.shortcuts.PromptSession`.

    It should only be used in that context.
    """
    if not message:
        cache = TomlCache()
        console = get_console()
        cwd = Path.cwd()

        _clear_on_resize(console)
        _set_title_time(console, cache)

        cursor = _base(cwd)
        _extend_active_project(cursor)
        _extend_git_branch(cwd, cursor)
        _extend_stopwatch(cursor, cache)
        if not hide_rprompt:
            _extend_entry_counter(cursor, cache)
        _extend_cursor_shape(cursor, message)
        return cast(str, cursor)

    def build_with_message() -> Sequence[tuple[str, str]]:
        cache = TomlCache()
        console = get_console()
        cwd = Path.cwd()

        _clear_on_resize(console)
        _set_title_time(console, cache)

        cursor = _base(cwd)
        _extend_active_project(cursor)
        _extend_git_branch(cwd, cursor)
        _extend_stopwatch(cursor, cache)
        if not hide_rprompt:
            _extend_entry_counter(cursor, cache)
        _extend_cursor_shape(cursor, message)
        return cursor

    return cast(str, build_with_message)


def _base(
    cwd: Path, user: str = USERNAME, host: str = HOSTNAME
) -> list[tuple[str, str]]:
    return [
        ("class:user", user),
        ("class:at", "@"),
        ("class:host", host),
        ("bold", " ➜ "),
        ("class:path", cwd.as_posix().removeprefix(cwd.drive)),
    ]


def _set_title_time(console: Console, cache: TomlCache) -> None:
    if cache:
        console.set_window_title(f"{_time_diff(cache)}#{cache.project}")


def _clear_on_resize(console: Console) -> None:
    global CONSOLE_WIDTH
    if console.width != CONSOLE_WIDTH:
        CONSOLE_WIDTH = console.width
        console.clear()


def _time_diff(cache: TomlCache) -> str:
    if cache.start is not None:
        if cache.paused_hrs:
            phr, pmin, psec = utils._sec_to_time_parts(Decimal(cache.paused_hrs) * 3600)
            paused_hrs = timedelta(
                hours=phr,
                minutes=pmin,
                seconds=psec,
                microseconds=0,
            )
            return f" {(_now() - cache.start) - paused_hrs}"
        else:
            return f" {_now() - cache.start}"

    return ""


def _now(timezone=TIMEZONE) -> datetime:
    return datetime.now().astimezone(timezone).replace(microsecond=0)


def _extend_entry_counter(cursor: list[tuple[str, str]], cache: TomlCache) -> None:
    if not cache and not cache.count_paused_entries >= 1:
        return

    indicator_running = (
        f"running entries: {cache.count_running_entries}"
        if cache.count_running_entries > 1
        else ""
    )
    indicator_paused = (
        f"paused entries: {cache.count_paused_entries}"
        if cache.count_paused_entries >= 1
        else ""
    )

    buffer = " | " if all([indicator_running, indicator_paused]) else ""
    extension = f"{indicator_running}{buffer}{indicator_paused}"

    if extension:
        padding = " " * (
            get_app().output.get_size().columns
            - fragment_list_width(cursor)  # type: ignore[arg-type]
            - len(extension)
            - 2
        )

        cursor.extend([("", padding), ("class:entries", f" {extension} ")])


def _extend_stopwatch(cursor: list[tuple[str, str]], cache: TomlCache) -> None:
    cursor.extend(
        [
            ("class:timer", _time_diff(cache)),
            ("class:timer", f"#{cache.project} " if cache.project else ""),
        ]
    )


def _extend_active_project(cursor: list[tuple[str, str]]) -> None:
    cursor.extend(
        [
            ("class:project_parenthesis", " ("),
            ("class:project", AppConfig().active_project),
            ("class:project_parenthesis", ") "),
        ]
    )


IN_REPO = AppConfig().get("git", "in_repo")
BRANCH = AppConfig().get("git", "branch")
PATH = AppConfig().get("git", "path")


def _extend_git_branch(cwd: Path, cursor: list[tuple[str, str]]) -> None:
    global IN_REPO, BRANCH, PATH
    if IN_REPO:
        if not cwd.is_relative_to(PATH):
            IN_REPO = False
            PATH = ""
            BRANCH = ""
            with AppConfig().update() as config:
                config["git"].update(in_repo=IN_REPO, path=PATH, branch=BRANCH)
    else:
        if (head_dir := cwd / ".git" / "HEAD").exists():
            IN_REPO = True
            PATH = head_dir.parent.parent.resolve().as_posix()
            BRANCH = head_dir.read_text().splitlines()[0].partition("refs/heads/")[2]
            with AppConfig().update() as config:
                config["git"].update(in_repo=IN_REPO, path=PATH, branch=BRANCH)
    if IN_REPO:
        cursor.extend(
            [
                ("class:git_parenthesis", "("),
                ("class:project", BRANCH),
                ("class:git_parenthesis", ") "),
            ]
        )


def _extend_cursor_shape(
    cursor: list[tuple[str, str]], message: str | None = None
) -> None:
    ext = f"\n{message or ''}" f"{'$ ' if not message else ' $ '}"
    cursor.extend([("class:cursor", ext)])
