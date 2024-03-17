import sys
from dataclasses import dataclass
from functools import partial
from typing import Any, Literal, Sequence

import rtoml
from rich import get_console
from rich import reconfigure as rich_reconfigure
from rich.console import Style, Theme

from lightlike.internal.enums import ActiveCompleter

__all__: Sequence[str] = (
    "reconfigure",
    "global_completer",
    "reconfigure_completer",
    "CONSOLE_TOML",
    "PROMPT_TOML",
    "_CONSOLE_SVG_FORMAT",
)


CONSOLE_TOML = """
[style]
color = "#f0f0ff"
bold = false

[theme.styles]
attr = "bold #fafa19"
notice = "#32ccfe"
code = "bold #f08375"
"code.command" = "bold #3465a4"
"code.lflag" = "bold #00ffff"
"code.sflag" = "bold #00ff00"
args = "bold #34e2e2"
"header.str" = "#ff0000"
"header.dt" = "#ffff00"
"header.bool" = "#ff0000"
"header.num" = "#00ffff"
failure = "#f0f0ff on #ff0000"
none = "#f0f0ff"
prompt = "#f0f0ff"
# d = "#888888"
dimmed = "#888888"
saved = "#00ff00"
"tree.line" = "bold magenta"
"iso8601.date" = "#3465a4"
"iso8601.time" = "#7f007f"
"table.header" = "bold #f0f0ff"
"table.footer" = "dim"
"table.cell" = "#f0f0ff"
"table.cell.empty" = "#888888"
"table.title" = "bold #f0f0ff"
"table.caption" = "dim"
"status.message" = "#19667f"
"status.spinner" = "#32ccfe"
"progress.description" = "#f0f0ff"
"progress.spinner" = "#32ccfe"
"repr.tag_contents" = "bold"
"repr.attrib_equal" = "bold red"
"repr.attrib_name" = "not dim #ffff00"
"repr.attrib_value" = "bold #ad7fa8"
"repr.number" = '#00ffff'
"repr.number_complex" = '#00ffff'
"repr.str" = "#00a500"
"scope.key.special" = "dim #ffff00"
"scope.key" = "not dim #ffff00"
"scope.equals" = "bold #ff0000"
"scope.border" = "#0000ff"
"log.time" = "dim #78787f"
"log.message" = "#f0f0ff"
"log.build" = "dim #fafa19"
"log.validate" = "dim #8205b4"
"log.error" = "#ff0000"
"log.path" = "dim #d2d2e6"
"""


@dataclass()
class ConsoleConfig:
    config: dict[str, Any]

    def __post_init__(self) -> None:
        self.style = Style(**self.config["style"])
        self.theme = Theme(**self.config["theme"])


CONSOLE_CONFIG = ConsoleConfig(rtoml.loads(CONSOLE_TOML))


def reconfigure(**kwargs: Any) -> None:
    rich_reconfigure(
        style=CONSOLE_CONFIG.style,
        theme=CONSOLE_CONFIG.theme,
        **kwargs,
    )

    get_console()._log_render.omit_repeated_times = False

    spinner = "simpleDotsScrolling"
    setattr(get_console(), "status", partial(get_console().status, spinner=spinner))


CONSOLE_QUIET_START: bool = True


def _configure_quiet_start():
    from lightlike.__about__ import __appdir__

    if (config_path := __appdir__.joinpath("config.toml")).exists():
        import rtoml

        config = rtoml.load(config_path)
        quiet_start = config["settings"].get("quiet_start")

        global CONSOLE_QUIET_START
        if len(sys.argv) > 1:
            CONSOLE_QUIET_START = True

        elif quiet_start is not None and isinstance(quiet_start, bool):
            CONSOLE_QUIET_START = quiet_start


_configure_quiet_start()


def global_console_log(message: str) -> None:
    global CONSOLE_QUIET_START
    if CONSOLE_QUIET_START is False:
        get_console().log(message)


COMPLETER: int = ActiveCompleter.CMD


def global_completer():
    global COMPLETER
    if COMPLETER is None:
        COMPLETER = ActiveCompleter.CMD

    return COMPLETER


def reconfigure_completer(
    completer: Literal[
        ActiveCompleter.CMD,
        ActiveCompleter.HISTORY,
        ActiveCompleter.PATH,
        ActiveCompleter.NONE,
    ]
) -> None:
    NEW_COMPLETER = completer
    global COMPLETER
    COMPLETER = global_completer()
    COMPLETER = NEW_COMPLETER


PROMPT_TOML = """
cursor-shape = "BLOCK"

[style]
"" = "fg:#f0f0ff"
user = "fg:#00fa05"
at = "fg:#9146ff"
host = "fg:#00fa05"
timer = "fg:#000000 bg:#f0f0ff"
cursor = "fg:#f0f0ff"
prompt = "fg:#f0f0ff"
entries = "fg:#000000 bg:#f0f0ff"
system = "fg:#555753"
path = "fg:#00b8fc"
project_parenthesis = "fg:#20c5cf"
git_parenthesis = "fg:#ffff00"
project = "fg:#f08375"
selected = "reverse"
cursor-column = "bg:#dddddd"
cursor-line = "underline"
color-column = "bg:#ccaacc"

"pygments.keyword" = "#6b90f7"
"pygments.name.builtin" = "#6b90f7"
"pygments.punctuation" = "#ba7dac"
"pygments.operator" = "#90c0d6"
"pygments.comment.single" = "#f0404e"
"pygments.comment.multiline" = "#f0404e"
"pygments.literal.string.symbol" = "#239551"
"pygments.literal.string.single" = "#239551"
"pygments.literal.number" = "#d32211"
"pygments.generic" = ""
"pygments.text" = ""
"pygments.whitespace" = ""
"pygments.escape" = ""
"pygments.error" = ""
"pygments.other" = ""

"completion-menu" = "bg:#0e0e10 fg:#f0f0ff"
"completion-menu.completion" = "bg:#0e0e10 fg:#f0f0ff"
# (Note: for the current completion, we use 'reverse' on top of fg/bg colors.
# This is to have proper rendering with NO_COLOR=1).
"completion-menu.completion.current" = "bold bg:#f0f0ff fg:#9146ff reverse"
"completion-menu.meta.completion" = "bg:#f0f0ff fg:#000000"
"completion-menu.meta.completion.current" = "bold bg:#f0f0ff fg:#9146ff"
"completion-menu.multi-column-meta" = "bg:#f0f0ff fg:#000000"

"scrollbar.background" = "bg:#f0f0ff"
"scrollbar.button" = "bg:#0e0e10"
"scrollbar.arrow" = "noinherit bold"

"control-character" = 'bold ansired'
"bottom-toolbar" = "reverse"
"validation-toolbar" = "bg:#550000 #ffffff"
"""

_CONSOLE_SVG_FORMAT = """\
<svg class="rich-terminal" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <style>

    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Regular"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Regular.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Regular.woff") format("woff");
        font-style: normal;
        font-weight: 400;
    }}
    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Bold"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Bold.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Bold.woff") format("woff");
        font-style: bold;
        font-weight: 700;
    }}

    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}

    .{unique_id}-title {{
        font-size: 18px;
        font-weight: bold;
        font-family: arial;
    }}

    {styles}
    </style>

    <defs>
    <clipPath id="{unique_id}-clip-terminal">
    <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>
    
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
</svg>
"""

#     @font-face {{
#         font-family: "Source Code Pro";
#         src: local("Source Code Pro"),
#                 url('https://fonts.googleapis.com/css2?family=Source+Code+Pro:ital,wght@0,200..900;1,200..900'),
#         font-style: normal;
#         font-weight: 400;
#     }}


#     .{unique_id}-matrix {{
#         font-family: Source Code Pro, monospace;
#         font-size: {char_height}px;
#         line-height: {line_height}px;
#         font-variant-east-asian: full-width;
#     }}

#     .{unique_id}-title {{
#         font-size: 18px;
#         font-weight: bold;
#         font-family: Source Code Pro;
#     }}
