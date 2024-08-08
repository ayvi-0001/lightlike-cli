import typing as t
from datetime import datetime, timedelta
from decimal import Decimal
from os import getenv
from pathlib import Path

from prompt_toolkit.formatted_text import fragment_list_width
from pytz import timezone
from rich import get_console

from lightlike.app.cache import EntriesInMemory
from lightlike.app.config import AppConfig
from lightlike.app.dates import now, seconds_to_time_parts
from lightlike.app.shell_complete.dynamic import global_completers

if t.TYPE_CHECKING:
    from datetime import _TzInfo

    from prompt_toolkit.mouse_events import MouseEvent

    NotImplementedOrNone = object


__all__: t.Sequence[str] = ("build", "bottom_toolbar", "rprompt")


OneStyleAndTextTuple = t.Union[
    tuple[str, str], tuple[str, str, t.Callable[["MouseEvent"], "NotImplementedOrNone"]]
]

StyleAndTextTuples = list[OneStyleAndTextTuple]


USERNAME: str = AppConfig().get("user", "name")
HOSTNAME: str = AppConfig().get("user", "host")
GCP_PROJECT: str = AppConfig().get("client", "active_project")
BRANCH: str = AppConfig().get("git", "branch")
PATH: str = AppConfig().get("git", "path")
TIMEZONE: "_TzInfo" = timezone(AppConfig().get("settings", "timezone"))


def build(message: str | None = None) -> str:
    """
    The actual return for this function is either a sequence of tuples, or a callable returning a sequence of tuples.
    The return value is casted as a string only to signal to the type checker
    that the return value has the required type for :param: `message` in :class: `prompt_toolkit.shortcuts.PromptSession`.
    It should only be used in that context.
    """
    if not message:
        cursor: StyleAndTextTuples = []
        cwd: Path = Path.cwd()

        _extend_base(cursor, cwd)
        _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        if cache := EntriesInMemory():
            timer: str = _timer(cache)
            get_console().set_window_title(f"{timer} | {cache.project}")
            _extend_timer(cursor, timer)

        _extend_cursor_pointer(cursor)

        return t.cast(str, cursor)

    def build_with_message(message: str | None = message) -> StyleAndTextTuples:
        cursor: StyleAndTextTuples = []
        cwd: Path = Path.cwd()

        _extend_base(cursor, cwd)
        _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        if cache := EntriesInMemory():
            timer: str = _timer(cache)
            get_console().set_window_title(f"{timer} | {cache.project}")
            _extend_timer(cursor, timer)

        _extend_cursor_pointer(cursor, message or "")

        return cursor

    return t.cast(str, build_with_message)


def bottom_toolbar() -> t.Callable[..., StyleAndTextTuples]:
    cache = EntriesInMemory()
    columns: int = get_console().width
    toolbar: StyleAndTextTuples = []

    if cache:
        toolbar.extend([("class:bottom-toolbar.text", f" A[{cache.id[:8]}")])
        toolbar.extend([("class:bottom-toolbar.text", f":{cache.project}")])

        cache_note: str = cache.note
        if cache_note:
            max_width: int = min(columns - fragment_list_width(toolbar) - 20, 50)
            note: str = (
                f"{cache_note[:max_width].strip()}…"
                if len(cache_note) > max_width
                else cache_note
            )
            toolbar.extend([("class:bottom-toolbar.text", f":{note}")])

        toolbar.extend([("class:bottom-toolbar.text", "] |")])

    display_running: str = f"R[{cache.count_running_entries if cache else 0}]"
    display_paused: str = f"P[{cache.count_paused_entries}]"
    sep = " | " if all([display_running, display_paused]) else ""
    rside_toolbar = f" {display_running}{sep}{display_paused}"

    toolbar.extend([("class:bottom-toolbar.text", rside_toolbar)])

    active_completers = (
        "[" + ",".join(map(lambda c: c._name_[:1], global_completers())) + "]"
    )

    padding = " " * (
        columns
        - fragment_list_width(toolbar)
        - fragment_list_width([("class:bottom-toolbar.text", active_completers)])
        - 1
    )

    toolbar.extend([("", padding), ("class:bottom-toolbar.text", active_completers)])

    blank_line = (
        "bg:default noreverse noitalic nounderline noblink",
        f"{' ' * (columns)}\n",
    )
    toolbar.insert(0, blank_line)

    return lambda: toolbar


def rprompt() -> t.Callable[..., StyleAndTextTuples]:
    global TIMEZONE
    timestamp: str = now(TIMEZONE).strftime("%H:%M:%S")
    return lambda: [("", f"\n"), ("class:rprompt.clock", "[%s]" % timestamp)]


def _extend_git_branch(cursor: StyleAndTextTuples, cwd: Path) -> None:
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


def _extend_cursor_pointer(cursor: StyleAndTextTuples, message: str = "") -> None:
    pointer = f"\n{message}{'$ ' if not message else ' $ '}"
    cursor.extend([("class:cursor", pointer)])


def _extend_timer(cursor: StyleAndTextTuples, timer: str) -> None:
    cursor.extend([("class:prompt.timer", timer)])


def _timer(cache: EntriesInMemory) -> str:
    paused_hours: Decimal = cache.paused_hours
    start: datetime = cache.start

    global TIMEZONE
    if paused_hours:
        phr, pmin, psec = seconds_to_time_parts(paused_hours * Decimal(3600))
        paused_delta: timedelta = timedelta(hours=phr, minutes=pmin, seconds=psec)
        return f" {(now(TIMEZONE) - start) - paused_delta} "
    else:
        return f" {now(TIMEZONE) - start} "


if all(
    [
        LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"),
        LIGHTLIKE_CLI_DEV_HOSTNAME := getenv("LIGHTLIKE_CLI_DEV_HOSTNAME"),
    ]
):

    def _extend_base(cursor: StyleAndTextTuples, cwd: Path) -> None:
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

    def _extend_base(cursor: StyleAndTextTuples, cwd: Path) -> None:
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


if LIGHTLIKE_CLI_DEV_GCP_PROJECT := getenv("LIGHTLIKE_CLI_DEV_GCP_PROJECT"):

    def _extend_active_project(cursor: StyleAndTextTuples, project: str) -> None:
        cursor.extend(
            [
                ("class:prompt.project.parenthesis", " ("),
                ("class:prompt.project.name", LIGHTLIKE_CLI_DEV_GCP_PROJECT or ""),
                ("class:prompt.project.parenthesis", ") "),
            ]
        )

else:

    def _extend_active_project(cursor: StyleAndTextTuples, project: str) -> None:
        cursor.extend(
            [
                ("class:prompt.project.parenthesis", " ("),
                ("class:prompt.project.name", project),
                ("class:prompt.project.parenthesis", ") "),
            ]
        )


# CONSOLE_WIDTH: int = get_console().width

# def _clear_on_resize(console: Console) -> None:
#     global CONSOLE_WIDTH
#     if console.width != CONSOLE_WIDTH:
#         CONSOLE_WIDTH = console.width
#         console.clear()
