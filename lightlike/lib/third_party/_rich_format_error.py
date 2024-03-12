from typing import TYPE_CHECKING, NoReturn, Optional, Sequence

import click
from rich import get_console
from rich.columns import Columns
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text
from rich_click.rich_click import _get_rich_formatter, get_rich_usage
from rich_click.rich_help_formatter import RichHelpFormatter

__all__: Sequence[str] = ("_rich_format_error",)


# Slightly modified function from rich_click.rich_click.rich_format_error.
# Original uses a highlighter in the final panel for compatibility with a major Python library,
# This is removed so the message can be formatted, and the console is replaced.


def _rich_format_error(  # type: ignore[misc]
    self: click.ClickException, formatter: Optional[RichHelpFormatter] = None
) -> NoReturn:
    formatter = _get_rich_formatter(formatter)
    console = get_console()
    config = formatter.config

    if getattr(self, "ctx", None) is not None:
        if TYPE_CHECKING:
            assert hasattr(self, "ctx")
        get_rich_usage(self.ctx.command, self.ctx, formatter)
    if config.errors_suggestion:
        console.print(
            Padding(config.errors_suggestion, (0, 1, 0, 1)),
            style=config.style_errors_suggestion,
        )
    elif (
        config.errors_suggestion is None
        and getattr(self, "ctx", None) is not None
        and self.ctx.command.get_help_option(self.ctx) is not None  # type: ignore[attr-defined]
    ):
        cmd_path = self.ctx.command_path  # type: ignore[attr-defined]
        help_option = self.ctx.help_option_names[0]  # type: ignore[attr-defined]
        columns = Columns(
            (
                Text("Try"),
                Text(
                    f"'{cmd_path} {help_option}'",
                    style=config.style_errors_suggestion_command,
                ),
                Text("for help"),
            )
        )
        console.print(
            Padding(columns, (0, 1, 0, 1)),
            style=config.style_errors_suggestion,
        )
    if hasattr(self, "message"):
        console.print(
            Panel(
                self.message,  # highlighter(self.format_message()),
                border_style=config.style_errors_panel_border,
                title=config.errors_panel_title,
                title_align=config.align_errors_panel,
            ),
        )
    if config.errors_epilogue:
        console.print(Padding(config.errors_epilogue, (0, 1, 1, 1)))
