import typing as t

from rich import get_console
from rich.default_styles import DEFAULT_STYLES
from rich.style import Style
from rich.text import Text

TextCallable = t.Callable[..., Text]


# fmt: off
code: TextCallable = lambda t: Text(text=f"{t!s}", style="code")
code_sequence: TextCallable = lambda t, s: Text(s, style="bold").join(Text(f"{t!s}", style="code").split(s))
code_command: TextCallable = lambda t: Text(text=f"{t!s}", style="code.command")
code_command_sequence: TextCallable = lambda t, s: Text(s, style="bold").join(Text(f"{t!s}", style="code.command").split(s))
args: TextCallable = lambda t: Text(text=f"{t!s}", style="args")
flag_long: TextCallable = lambda t: Text(text=f"{t!s}", style="flag.long")
flag_short: TextCallable = lambda t: Text(text=f"{t!s}", style="flag.short")

def code_flag(long_flag: str, short_flag: str) -> Text:
    return Text.assemble(flag_long(long_flag), " / ", flag_short(short_flag))

br: TextCallable = lambda t: Text(text=f"{t!s}", style="bold red")
dbr: TextCallable = lambda t: Text(text=f"{t!s}", style="dim bold red")
sdr: TextCallable = lambda t: Text(text=f"{t!s}", style="s dim red")
bg: TextCallable = lambda t: Text(text=f"{t!s}", style="bold green")
bu: TextCallable = lambda t: Text(text=f"{t!s}", style="bold underline")
db: TextCallable = lambda t: Text(text=f"{t!s}", style="dim bold")
dim: TextCallable = lambda t: Text(text=f"{t!s}", style="dim")
dimmed: TextCallable = lambda t: Text(text=f"{t!s}", style="dimmed")
repr_attrib_name: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.attrib_name")
repr_attrib_equal: TextCallable = lambda: Text(text="=", style="repr.attrib_equal")
repr_attrib_value: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.attrib_value")
repr_bool_true: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.bool_true")
repr_bool_false: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.bool_false")
repr_number: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.number")
repr_tag_name: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.tag_name")
repr_tag_start: TextCallable = lambda: Text(text="<", style="repr.tag_start")
repr_tag_end: TextCallable = lambda: Text(text=">", style="repr.tag_end")
repr_str: TextCallable = lambda t: Text(text=f'"{t!s}"', style="repr.str")
url: TextCallable = lambda t: Text(text=f"{t!s}", style="repr.url")
link: TextCallable = lambda t, l: Text(text=f"{t!s}", style=Style(link=l, underline=True, color="bright_blue", italic=False, bold=False))
saved: TextCallable = lambda t: Text(text=f"{t!s}", style="saved")
failure: TextCallable = lambda t: Text(text=f"{t!s}", style="failure")
log_error: TextCallable = lambda t: Text(text=f"{t!s}", style="log.error")
iso8601_date: TextCallable = lambda t: Text(text=f"{t!s}", style="iso8601.date")
iso8601_time: TextCallable = lambda t: Text(text=f"{t!s}", style="iso8601.time")
scope_key: TextCallable = lambda t: Text(text=f"{t!s}", style="scope.key")
status_message: TextCallable = lambda t: Text(text=f"{t!s}", style="status.message")
pygments_keyword: TextCallable = lambda t: Text(text=f"{t!s}", style="#6b90f7")
# fmt: on


def __getattr__(__name: t.Any) -> t.Callable[..., t.Any]:
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

    return lambda t: inner(t, __name)
