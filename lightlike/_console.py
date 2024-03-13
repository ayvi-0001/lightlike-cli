from dataclasses import dataclass
from functools import partial
from pathlib import Path
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
    "_CONSOLE_SVG_FORMAT",
)


@dataclass()
class ConsoleConfig:
    config: dict[str, Any]

    def __post_init__(self) -> None:
        self.style = Style(**self.config["style"])
        self.theme = Theme(**self.config["theme"])


CONSOLE_CONFIG = ConsoleConfig(rtoml.load(Path(f"{__file__}/../console.toml")))


def reconfigure(**kwargs: Any) -> None:
    rich_reconfigure(
        style=CONSOLE_CONFIG.style,
        theme=CONSOLE_CONFIG.theme,
        **kwargs,
    )

    get_console()._log_render.omit_repeated_times = False

    spinner = "simpleDotsScrolling"
    setattr(get_console(), "status", partial(get_console().status, spinner=spinner))


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
