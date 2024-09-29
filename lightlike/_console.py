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
from lightlike.internal import appdir, constant

__all__: t.Sequence[str] = (
    "QUIET_START",
    "CONSOLE_CONFIG",
    "Highlighter",
    "if_not_quiet_start",
    "reconfigure",
)


QUIET_START: bool = False


@_fasteners.interprocess_locked(__appdir__ / "config.lock")
def _set_quiet_start(config_path: Path) -> None:
    try:
        if config_path.exists():
            config = rtoml.load(config_path)
            quiet_start: bool = t.cast(bool, config["settings"].get("quiet-start"))

            global QUIET_START
            if len(sys.argv) > 1:
                QUIET_START = True
            elif quiet_start is not None:
                QUIET_START = bool(quiet_start)
    except Exception as error:
        appdir.log().error(f"Failed to configure quiet start: {error}")


_set_quiet_start(__config__)


def if_not_quiet_start(fn: t.Callable[..., None]) -> t.Callable[..., None]:
    return fn if not QUIET_START else lambda *a, **kw: None


@dataclass()
class ConsoleConfig:
    config: dict[str, t.Any]

    def __post_init__(self) -> None:
        self.style = Style(**self.config["style"])
        self.theme = Theme(**self.config["theme"])


CONSOLE_CONFIG = ConsoleConfig(rtoml.load(constant.CONSOLE))

GROUP_COMMANDS = r"(?P<command>((%s)))" % "|".join(
    [
        "timer:add",
        "timer:delete",
        "timer:edit",
        "timer:get",
        "timer:list",
        "timer:notes:update",
        "timer:pause",
        "timer:resume",
        "timer:run",
        "timer:show",
        "timer:stop",
        "timer:summary:csv",
        "timer:summary:json",
        "timer:summary:table",
        "timer:switch",
        "timer:update",
        "project:unarchive",
        "project:set:name",
        "project:set:description",
        "project:set:default-billable",
        "project:set",
        "project:list",
        "project:delete",
        "project:create",
        "project:archive",
        "bq:snapshot:restore",
        "bq:snapshot:list",
        "bq:snapshot:delete",
        "bq:snapshot:create",
        "bq:snapshot",
        "bq:show",
        "bq:reset",
        "bq:query",
        "bq:projects",
        "bq:init",
        "app:parse-date",
        "app:date-diff",
        "app:sync",
        "app:run-bq",
        "app:dir",
        "app:config:edit",
        "app:config:list",
        "app:config:set:general:editor",
        "app:config:set:general:note-history",
        "app:config:set:general:quiet-start",
        "app:config:set:general:shell",
        "app:config:set:general:stay-logged-in",
        "app:config:set:general:timer-add-min",
        "app:config:set:general:timezone",
        "app:config:set:general:week-start",
        "app:config:set:general",
        "app:config:set:query:hide-table-render",
        "app:config:set:query:mouse-support",
        "app:config:set:query:save-query-info",
        "app:config:set:query:save-svg",
        "app:config:set:query:save-txt",
        "app:config:set:query",
        "app:config:set",
        "app:config",
    ]
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
        GROUP_COMMANDS,
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
