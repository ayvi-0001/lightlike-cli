import getpass
import socket
import typing as t
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import rtoml
from prompt_toolkit.formatted_text import fragment_list_width
from rich import get_console

from lightlike.__about__ import __appdir__
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


USERNAME: str = AppConfig().get("user", "name", default=getpass.getuser())
HOSTNAME: str = AppConfig().get("user", "host", default=socket.gethostname())
GCP_PROJECT: str | None = AppConfig().get("client", "active-project")
TIMEZONE: "_TzInfo" = AppConfig().tzinfo
UPDATE_TERMINAL_TITLE: bool = AppConfig().get(
    "settings", "update-terminal-title", default=True
)
RPROMPT_DATE_FORMAT: str = AppConfig().get(
    "settings", "rprompt-date-format", default="[%H:%M:%S]"
)


def build(message: str | None = None) -> t.Callable[[], StyleAndTextTuples]:
    if not message:
        cursor: StyleAndTextTuples = []
        cwd: Path = Path.cwd()

        _extend_base(cursor, cwd)
        GCP_PROJECT and _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        if cache := EntriesInMemory():
            timer: str = _timer(cache)

            if UPDATE_TERMINAL_TITLE:
                get_console().set_window_title(f"{timer} | {cache.project}")

            _extend_timer(cursor, timer)

        _extend_cursor_pointer(cursor)

        return lambda: cursor

    def build_with_message(message: str | None = message) -> StyleAndTextTuples:
        cursor: StyleAndTextTuples = []
        cwd: Path = Path.cwd()

        _extend_base(cursor, cwd)
        GCP_PROJECT and _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        if cache := EntriesInMemory():
            timer: str = _timer(cache)

            if UPDATE_TERMINAL_TITLE:
                get_console().set_window_title(f"{timer} | {cache.project}")

            _extend_timer(cursor, timer)

        _extend_cursor_pointer(cursor, message or "")

        return cursor

    return build_with_message


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
    timestamp: str = now(TIMEZONE).strftime(RPROMPT_DATE_FORMAT)
    return lambda: [("", f"\n"), ("class:rprompt.clock", timestamp)]


GIT_INFO_PATH: t.Final[Path] = __appdir__ / ".gitinfo"

if not GIT_INFO_PATH.exists():
    rtoml.dump({"branch": "", "path": ""}, GIT_INFO_PATH)

GIT_INFO: dict[str, str] = rtoml.load(GIT_INFO_PATH)

BRANCH: str | None = GIT_INFO.get("branch")
PATH: str | None = GIT_INFO.get("path")


def _extend_git_branch(cursor: StyleAndTextTuples, cwd: Path) -> None:
    global BRANCH, PATH, GIT_INFO
    if BRANCH and PATH:
        if not cwd.is_relative_to(PATH):
            PATH, BRANCH = "", ""
            GIT_INFO["branch"] = ""
            GIT_INFO["path"] = ""
            rtoml.dump(GIT_INFO, GIT_INFO_PATH)
    else:
        if (head_dir := cwd / ".git" / "HEAD").exists():
            PATH = head_dir.parent.parent.resolve().as_posix()
            BRANCH = head_dir.read_text().splitlines()[0].partition("refs/heads/")[2]
            GIT_INFO["branch"] = BRANCH
            GIT_INFO["path"] = PATH
            rtoml.dump(GIT_INFO, GIT_INFO_PATH)

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
