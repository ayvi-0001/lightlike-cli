# ruff: noqa: E731
import typing as t

from rich import get_console
from rich.default_styles import DEFAULT_STYLES
from rich.style import Style
from rich.text import Text


def __getattr__(_name: t.Any) -> t.Callable[..., t.Any]:
    def inner(text: Text | str, style: str) -> t.Any:
        if isinstance(text, Text):
            existing_style = text.style
            parsed_attr = style.replace("_", ".")

            if isinstance(existing_style, Style):
                new_style = Style.combine([existing_style, Style.parse(parsed_attr)])

            elif isinstance(existing_style, str):
                existing_style = existing_style.replace("_", ".")
                theme_stack = get_console()._theme_stack

                if theme_stack.get(existing_style) is not None:
                    new_style = Style.combine(
                        [
                            theme_stack.get(existing_style, Style.null()),
                            Style.parse(parsed_attr),
                        ]
                    )
                elif existing_style in DEFAULT_STYLES:
                    new_style = Style.combine(
                        [DEFAULT_STYLES[existing_style], Style.parse(parsed_attr)]
                    )
                else:
                    new_style = Style.combine(
                        [Style.parse(existing_style), Style.parse(parsed_attr)]
                    )
            return Text(f"{text!s}", style=new_style)

        else:
            return Text(f"{text!s}", style=style)

    return lambda t: inner(t, _name)


# fmt: off
bg: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="bold green")
br: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="bold red")
sdr: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="s dim red")
db: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="dim bold")
dbr: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="dim bold red")
dim: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="dim")
dimmed: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="#888888")
code: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="bold #f08375")
command: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="bold #3465a4")
failure: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="failure")
link: t.Callable[..., Text] = lambda t, l: Text(text=f"{t!s}", style=Style(link=l, underline=True, color="bright_blue", italic=False, bold=False))
log_error: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="log.error")
pygments_keyword: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="#6b90f7")
repr_attrib_equal: t.Callable[..., Text] = lambda: Text(text="=", style="repr_attrib_equal")
repr_attrib_name: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="repr_attrib_name")
repr_attrib_value: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="repr_attrib_value")
repr_number: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="repr_number")
repr_path: t.Callable[..., Text] = lambda t: Text(text=f'"{t!s}"', style="repr_path")
repr_str: t.Callable[..., Text] = lambda t: Text(text=f'"{t!s}"', style="repr_str")
scope_key: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="scope.key")
status_message: t.Callable[..., Text] = lambda t: Text(text=f"{t!s}", style="status.message")
# fmt: on
