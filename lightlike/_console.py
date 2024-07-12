import sys
import typing as t
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import rtoml
from rich import get_console
from rich import reconfigure as rich_reconfigure
from rich.highlighter import RegexHighlighter, _combine_regex
from rich.style import Style
from rich.theme import Theme

from lightlike import _fasteners
from lightlike.__about__ import __appdir__, __config__
from lightlike.internal import appdir, constant, enums

__all__: t.Sequence[str] = (
    "QUIET_START",
    "CONSOLE_CONFIG",
    "Highlighter",
    "if_not_quiet_start",
    "reconfigure",
    "ACTIVE_COMPLETERS",
    "global_completers",
    "reconfigure_completer",
)


QUIET_START: bool = False


@_fasteners.interprocess_locked(__appdir__ / "config.lock")
def _set_quiet_start(config: Path) -> None:
    try:
        if config.exists():
            quiet_start: bool = t.cast(
                bool, rtoml.load(config)["settings"].get("quiet_start")
            )

            global QUIET_START
            if len(sys.argv) > 1:
                QUIET_START = True
            elif quiet_start is not None:
                QUIET_START = bool(quiet_start)
    except Exception as error:
        appdir._log().error(f"Failed to configure quiet start: {error}")


_set_quiet_start(__config__)


def if_not_quiet_start(fn: t.Callable[..., None]) -> t.Callable[..., None]:
    return fn if not QUIET_START else lambda *a, **kw: None


@dataclass()
class ConsoleConfig:
    config: dict[str, t.Any]

    def __post_init__(self) -> None:
        self.style = Style(**self.config["style"])
        self.theme = Theme(**self.config["theme"])


CONSOLE_CONFIG = ConsoleConfig(rtoml.loads(constant.CONSOLE))

GROUP_FIRST_COMMANDS = r"(?P<command>((app|bq|project|summary|timer))):\w+"
GROUP_MID_COMMANDS = (
    r"\w:(?P<command>((set|config|test|general|query|notes|snapshot))):\w"
)
GROUP_LAST_COMMANDS = (
    r":(?P<command>(("
    r"add|archive|create|csv|date-diff|date-parse|default_billable|delete|description|"
    r"dir|edit|editor|end|exit|get|hide_table_render|init|json|list|mouse_support|name|"
    r"note_history|open|pause|projects|query|quiet_start|reset|restore|resume|run|run-bq|"
    r"save_query_info|save_svg|save_txt|set|shell|show|show|stay_logged_in|stop|switch|"
    r"sync|table|timer_add_min|timezone|unarchive|update|week_start)))"
)


class Highlighter(RegexHighlighter):
    highlights = [
        r"(^|[^\w\-])(?P<switch>-([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(^|[^\w\-])(?P<option>--([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(?P<metavar><[^>]+>)",
        r"(?P<code>\[([^\W0-9].*\w\]))",
        # ReprHighlighter
        r"(?P<repr_tag_start><)(?P<repr_tag_name>[-\w.:|]*)(?P<repr_tag_contents>[\w\W]*)(?P<repr_tag_end>>)",
        r'(?P<repr_attrib_name>[\w_]{1,50})=(?P<repr_attrib_value>"?[\w_]+"?)?',
        r"(?P<repr_brace>[][{}()])",
        _combine_regex(
            r"(?P<repr_ipv4>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
            r"(?P<repr_ipv6>([A-Fa-f0-9]{1,4}::?){1,7}[A-Fa-f0-9]{1,4})",
            r"(?P<repr_eui64>(?:[0-9A-Fa-f]{1,2}-){7}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{1,2}:){7}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{4}\.){3}[0-9A-Fa-f]{4})",
            r"(?P<repr_eui48>(?:[0-9A-Fa-f]{1,2}-){5}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4})",
            r"(?P<repr_uuid>[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})",
            r"(?P<repr_call>[\w.]*?)\(",
            r"\b(?P<repr_bool_true>True)\b|\b(?P<repr_bool_false>False)\b|\b(?P<repr_none>None)\b",
            r"(?P<repr_ellipsis>\.\.\.)",
            r"(?P<repr_number_complex>(?<!\w)(?:\-?[0-9]+\.?[0-9]*(?:e[-+]?\d+?)?)(?:[-+](?:[0-9]+\.?[0-9]*(?:e[-+]?\d+)?))?j)",
            r"(?P<repr_number>(?<!\w)\-?[0-9]+\.?[0-9]*(e[-+]?\d+?)?\b|0x[0-9a-fA-F]*)",
            r"(?P<repr_path>\B(/[-\w._+]+)*\/)(?P<repr_filename>[-\w._+]*)?",
            r"(?<![\\\w])(?P<repr_str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
            r"(?P<repr_url>(file|https|http|ws|wss)://[-0-9a-zA-Z$_+!`(),.?/;:&=%#~]*)",
        ),
        GROUP_FIRST_COMMANDS,
        GROUP_MID_COMMANDS,
        GROUP_LAST_COMMANDS,
    ]


def reconfigure(**kwargs: t.Any) -> None:
    rich_reconfigure(
        style=CONSOLE_CONFIG.style,
        theme=CONSOLE_CONFIG.theme,
        highlighter=Highlighter(),
        log_time_format="[%H:%M:%S]",
        **kwargs,
    )

    get_console()._log_render.omit_repeated_times = False

    spinner = "simpleDotsScrolling"
    setattr(get_console(), "status", partial(get_console().status, spinner=spinner))


ACTIVE_COMPLETERS: list[int] = []


def global_completers() -> list[int]:
    global ACTIVE_COMPLETERS
    if not ACTIVE_COMPLETERS:
        ACTIVE_COMPLETERS = [enums.ActiveCompleter.CMD]

    return ACTIVE_COMPLETERS


def reconfigure_completer(
    completer: t.Literal[
        enums.ActiveCompleter.CMD,
        enums.ActiveCompleter.HISTORY,
        enums.ActiveCompleter.PATH,
    ]
) -> None:
    NEW_COMPLETER = completer
    global ACTIVE_COMPLETERS
    active_completers = global_completers()

    if NEW_COMPLETER not in active_completers:
        active_completers.append(NEW_COMPLETER)
    else:
        active_completers.pop(active_completers.index(NEW_COMPLETER))

    ACTIVE_COMPLETERS = active_completers
