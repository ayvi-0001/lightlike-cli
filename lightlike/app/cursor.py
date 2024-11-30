import getpass
import socket
import typing as t
from datetime import datetime
from pathlib import Path

import rtoml
from prompt_toolkit.formatted_text import fragment_list_width
from rich import get_console
from rich.console import Console

from lightlike.__about__ import __appdir__, __appname_sc__
from lightlike.app.cache import EntriesInMemory
from lightlike.app.config import AppConfig
from lightlike.app.dates import date_diff, now
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
TERMINAL_TITLE: str = ""
RPROMPT_DATE_FORMAT: str = AppConfig().get(
    "settings", "rprompt-date-format", default="[%H:%M:%S]"
)

GIT_INFO_PATH: t.Final[Path] = __appdir__ / ".gitinfo"

if not GIT_INFO_PATH.exists():
    rtoml.dump({"branch": "", "path": ""}, GIT_INFO_PATH)

GIT_INFO: dict[str, str] = rtoml.load(GIT_INFO_PATH)

BRANCH: str | None = GIT_INFO.get("branch")
PATH: str | None = GIT_INFO.get("path")


def build(message: str | None = None) -> t.Callable[[], StyleAndTextTuples]:
    if not message:
        console: Console = get_console()
        cursor: StyleAndTextTuples = []
        cwd: Path = Path.cwd()

        _extend_base(cursor, cwd)
        _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        global TERMINAL_TITLE
        if cache := EntriesInMemory():
            timer: str = _timer(cache)

            if UPDATE_TERMINAL_TITLE:
                title: str = f"{timer} | {cache.project}"
                console.set_window_title(title)
                TERMINAL_TITLE = title

            cursor.extend([("class:prompt.timer", timer)])

        else:
            if UPDATE_TERMINAL_TITLE:
                if TERMINAL_TITLE != __appname_sc__:
                    console.set_window_title(__appname_sc__)
                    TERMINAL_TITLE = __appname_sc__

        cursor.extend([("class:cursor", "\n$ ")])

        return lambda: cursor

    def build_with_message(message: str | None = message) -> StyleAndTextTuples:
        console: Console = get_console()
        cursor: StyleAndTextTuples = []
        cwd: Path = Path.cwd()

        _extend_base(cursor, cwd)
        _extend_active_project(cursor, GCP_PROJECT)
        _extend_git_branch(cursor, cwd)

        global TERMINAL_TITLE
        if cache := EntriesInMemory():
            timer: str = _timer(cache)

            if UPDATE_TERMINAL_TITLE:
                title: str = f"{timer} | {cache.project}"
                console.set_window_title(title)
                TERMINAL_TITLE = title

            cursor.extend([("class:prompt.timer", timer)])

        else:
            if UPDATE_TERMINAL_TITLE:
                if TERMINAL_TITLE != __appname_sc__:
                    console.set_window_title(__appname_sc__)
                    TERMINAL_TITLE = __appname_sc__

        cursor.extend([("class:cursor", f"\n{message} $ ")])

        return cursor

    return build_with_message


def bottom_toolbar() -> t.Callable[..., StyleAndTextTuples]:
    cache = EntriesInMemory()
    columns: int = get_console().width
    toolbar: StyleAndTextTuples = []

    display_active: str = ""
    if cache:
        display_active = f"A[{cache.id[:8]}:{cache.project}"
        cache_note: str = cache.note or ""
        if cache_note:
            max_width: int = min(columns - fragment_list_width(toolbar) - 20, 79)
            note: str = (
                f"{cache_note[:max_width].strip()}..."
                if len(cache_note) > max_width
                else cache_note
            )
            display_active += f":{note}"
        display_active += "] | "

    display_running: str = f"R[{cache.count_running_entries if cache else 0}]"
    display_paused: str = f"P[{cache.count_paused_entries}]"
    sep = " | " if all([display_running, display_paused]) else ""
    rside_toolbar = f"{display_active}{display_running}{sep}{display_paused}"

    side_padding: str = " " * 3
    toolbar.extend(
        [("class:bottom-toolbar.text", f"{side_padding}{rside_toolbar}{side_padding}")]
    )
    active_completers = (
        f"{side_padding}["
        + ",".join(map(lambda c: c._name_[:1], global_completers()))
        + f"]{side_padding}"
    )

    center_padding = " " * (
        columns
        - fragment_list_width(toolbar)
        - fragment_list_width([("class:bottom-toolbar.text", active_completers)])
        - 1
    )

    toolbar.extend(
        [("", center_padding), ("class:bottom-toolbar.text", active_completers)]
    )

    blank_line = (
        "bg:default noreverse noitalic nounderline noblink",
        f"{' ' * (columns)}\n",
    )
    toolbar.insert(0, blank_line)

    return lambda: toolbar


def rprompt() -> t.Callable[..., StyleAndTextTuples]:
    global TIMEZONE
    timestamp: str = now(TIMEZONE).strftime(RPROMPT_DATE_FORMAT)
    return lambda: [("", "\n"), ("class:rprompt.clock", timestamp)]


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


def _timer(cache: EntriesInMemory) -> str:
    global TIMEZONE
    start: datetime = cache.start
    duration, hours = date_diff(start, now(TIMEZONE), cache.paused_hours)
    return f" {duration} "


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
    if not project:
        return
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
