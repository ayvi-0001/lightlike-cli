# mypy: disable-error-code="override"

import importlib
import typing as t
import zlib
from operator import truth
from os import getenv
from types import ModuleType

import rich_click as click
from more_itertools import first
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich.align import Align
from rich.console import Console
from rich.markup import render
from rich.padding import Padding
from rich.syntax import Syntax
from rich_click.rich_context import RichContext
from rich_click.rich_help_configuration import RichHelpConfiguration
from rich_click.rich_help_formatter import RichHelpFormatter
from rich_click.rich_help_rendering import rich_format_error

from lightlike.__about__ import __appname__, __repo__
from lightlike._console import (
    _CONSOLE_SVG_FORMAT,
    CONSOLE_CONFIG,
    GROUP_FIRST_COMMANDS,
    GROUP_LAST_COMMANDS,
    GROUP_MID_COMMANDS,
)
from lightlike.lib.third_party import _patch_rich_click

__all__: t.Sequence[str] = (
    "RICH_HELP_CONFIG",
    "FmtRichCommand",
    "AliasedRichGroup",
    "LazyAliasedRichGroup",
    "_map_click_exception",
)

DEFAULT_STYLE = "#f0f0ff"


RICH_HELP_CONFIG = RichHelpConfiguration(
    style_option="bold #00ffff",
    style_argument="not dim bold cyan",
    style_command="bold cyan",
    style_switch="bold #00ff00",
    style_metavar="not dim cyan",
    style_metavar_append="not dim cyan",
    style_metavar_separator="not dim cyan",
    style_header_text="bold #9146FF",
    style_epilog_text=f"bold {DEFAULT_STYLE}",
    style_footer_text=f"bold {DEFAULT_STYLE}",
    style_usage=f"bold {DEFAULT_STYLE}",
    style_usage_command="bold #3465a4 on default",
    style_deprecated="red",
    style_helptext_first_line=DEFAULT_STYLE,
    style_helptext=DEFAULT_STYLE,
    style_option_help=DEFAULT_STYLE,
    style_option_default="dim",
    style_option_envvar="dim yellow",
    style_required_short="red",
    style_required_long="not dim red",
    style_options_panel_border=DEFAULT_STYLE,
    style_options_panel_box="ROUNDED",
    align_options_panel="left",
    style_options_table_show_lines=False,
    style_options_table_leading=1,
    style_options_table_pad_edge=False,
    style_options_table_padding=(0, 1),
    style_options_table_box="",
    style_options_table_row_styles=[DEFAULT_STYLE],
    style_options_table_border_style=None,
    style_commands_panel_border="dim bright_blue",
    style_commands_panel_box="ROUNDED",
    align_commands_panel="left",
    style_commands_table_show_lines=True,
    style_commands_table_leading=1,
    style_commands_table_pad_edge=False,
    style_commands_table_padding=(0, 1),
    style_commands_table_box="",
    style_commands_table_row_styles=None,
    style_commands_table_border_style=None,
    style_commands_table_column_width_ratio=(None, None),
    style_errors_panel_border="bold red",
    style_errors_panel_box="ROUNDED",
    align_errors_panel="left",
    style_errors_suggestion="bold",
    style_errors_suggestion_command="magenta",
    style_aborted="red",
    width=None,
    max_width=None,
    color_system=None,
    force_terminal=None,
    header_text=f"[link={__repo__}]{__appname__}",
    footer_text=None,
    deprecated_string="(Deprecated) ",
    default_string="[default={}]",
    envvar_string="[env var: {}]",
    required_short_string="*",
    required_long_string="[required]",
    range_string=" [{}]",
    append_metavars_help_string="({})",
    arguments_panel_title=f"[b][not dim][{DEFAULT_STYLE}]Arguments",
    options_panel_title=f"[b][not dim][{DEFAULT_STYLE}]Options",
    commands_panel_title=f"[b][not dim][{DEFAULT_STYLE}]Commands",
    errors_panel_title="Error",
    errors_suggestion=None,
    errors_epilogue=None,
    aborted_text="Aborted.",
    show_arguments=True,
    show_metavars_column=True,
    append_metavars_help=False,
    group_arguments_options=True,
    option_envvar_first=True,
    text_markup="rich",
    use_markdown=False,
    use_markdown_emoji=True,
    command_groups={},
    option_groups={},
    use_click_short_help=False,
    legacy_windows=None,
    highlighter_patterns=[
        r"(^|[^\w\-])(?P<switch>-([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(^|[^\w\-])(?P<option>--([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(?P<metavar><[^>]+>)",
        GROUP_FIRST_COMMANDS,
        GROUP_MID_COMMANDS,
        GROUP_LAST_COMMANDS,
    ],
)

P = t.ParamSpec("P")


EXPORT_HELP = truth(getenv("LIGHTLIKE_CLI_DEV_EXPORT_HELP"))


class FmtRichCommand(click.RichCommand):
    def __init__(
        self,
        syntax: t.Optional[t.Callable[..., Syntax]] = None,
        allow_name_alias: bool = True,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.syntax = syntax
        self.allow_name_alias = allow_name_alias

    def format_help(self, ctx: RichContext, formatter: RichHelpFormatter) -> None:  # type: ignore[override]
        formatter.console.width = 120

        if EXPORT_HELP:
            formatter.console.record = True
            formatter.config.header_text = None
            formatter.console.export_text(clear=True)

        self.format_usage(ctx, formatter)
        self.format_help_text(ctx, formatter)
        self.format_options(ctx, formatter)
        self.format_epilog(ctx, formatter)

        if EXPORT_HELP:
            _export_help(
                console=formatter.console,
                title="lightlike-cli",
                command_path=ctx.command_path.replace("lightlike", "").strip(),
                code_format=_CONSOLE_SVG_FORMAT,
            )

        formatter.console.width = None  # type: ignore[assignment]

    def format_help_text(self, ctx: RichContext, formatter: RichHelpFormatter) -> None:  # type: ignore[override]
        if self.help:
            formatter.write(
                Padding(
                    Align(_patch_rich_click._get_help_text(self, formatter), pad=False),
                    (0, 1, 1, 1),
                )
            )
        if hasattr(self, "syntax"):
            syntax = self.syntax() if callable(self.syntax) else self.syntax
            if syntax:
                formatter.write(Padding(syntax, (0, 1, 1, 1)))

    def format_options(self, ctx: RichContext, formatter: click.HelpFormatter) -> None:
        _patch_rich_click._get_rich_options(self, ctx, formatter)  # type: ignore[arg-type]


class AliasedRichGroup(click.RichGroup):
    def __init__(
        self,
        syntax: t.Optional[t.Callable[..., Syntax]] = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.syntax = syntax

    def get_command(self, ctx: RichContext, cmd_name: str) -> click.Command | None:
        rv = click.RichGroup.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = []
        for m in self.list_commands(ctx):
            if m.startswith(cmd_name):
                command = self.get_command(ctx, m)
                if hasattr(command, "allow_name_alias"):
                    if command.allow_name_alias is False and cmd_name != m:  # type: ignore [union-attr]
                        return None
                if not (command and command.hidden):
                    matches.append(m)
        if not matches:
            return None
        elif len(matches) == 1:
            return click.RichGroup.get_command(self, ctx, first(matches))
        else:
            ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(
        self, ctx: RichContext, args: t.Any
    ) -> tuple[str | t.Any | None, click.Command | None, t.Any]:
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name if cmd else None, cmd, args

    def format_help(self, ctx: RichContext, formatter: RichHelpFormatter) -> None:  # type: ignore[override]
        formatter.console.width = 120

        if EXPORT_HELP:
            formatter.console.record = True
            formatter.config.header_text = None
            formatter.console.export_text(clear=True)

        self.format_usage(ctx, formatter)
        self.format_help_text(ctx, formatter)
        self.format_options(ctx, formatter)
        _patch_rich_click._get_rich_commands(self, ctx, formatter)
        self.format_epilog(ctx, formatter)

        if EXPORT_HELP:
            _export_help(
                console=formatter.console,
                title="lightlike-cli",
                command_path=ctx.command_path.replace("lightlike", "").strip(),
                code_format=_CONSOLE_SVG_FORMAT,
            )

        formatter.console.width = None  # type: ignore[assignment]

    def format_help_text(self, ctx: RichContext, formatter: RichHelpFormatter) -> None:  # type: ignore[override]
        if self.help:
            formatter.write(
                Padding(
                    Align(_patch_rich_click._get_help_text(self, formatter), pad=False),
                    (0, 1, 1, 1),
                )
            )
        if hasattr(self, "syntax"):
            syntax = self.syntax() if callable(self.syntax) else self.syntax
            if syntax:
                formatter.write(Padding(syntax, (0, 1, 1, 1)))

    def format_options(self, ctx: RichContext, formatter: click.HelpFormatter) -> None:
        _patch_rich_click._get_rich_options(self, ctx, formatter)  # type: ignore[arg-type]


def _export_help(
    console: Console,
    title: str,
    command_path: str,
    code_format: str,
) -> None:
    invoked_subcommand = "".join(c if c.isalnum() else "_" for c in str(command_path))
    unique_id = f"{title}-%s" % zlib.adler32(
        invoked_subcommand.encode("utf-8", "ignore")
    )
    console.save_svg(
        path=f"./{invoked_subcommand}.svg",
        title=title,
        code_format=code_format,
        clear=True,
        unique_id=unique_id,
    )


class LazyAliasedRichGroup(AliasedRichGroup):
    """https://click.palletsprojects.com/en/8.1.x/complex/#using-lazygroup-to-define-a-cli"""

    def __init__(
        self,
        lazy_subcommands: dict[str, str] | None = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        super().__init__(*args, **kwargs)
        #   {command-name} -> {module-name}.{command-object-name}
        self.lazy_subcommands = lazy_subcommands or {}

    def list_commands(self, ctx: RichContext) -> list[str]:
        base: list[str] = super().list_commands(ctx)
        lazy: list[str] = sorted(self.lazy_subcommands.keys())
        return base + lazy

    def get_command(self, ctx: RichContext, cmd_name: str) -> click.RichCommand | None:
        if cmd_name in self.lazy_subcommands:
            return self._lazy_load(cmd_name)
        matches = [m for m in self.list_commands(ctx) if m.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1 and (match := first(matches)) in self.lazy_subcommands:
            command = self._lazy_load(match)
            if hasattr(command, "allow_name_alias"):
                if command.allow_name_alias is False and cmd_name != match:  # type: ignore [union-attr]
                    return None
            return command
        else:
            return super().get_command(ctx, cmd_name)  # type: ignore[return-value]

    def _lazy_load(self, cmd_name: str) -> click.RichCommand | None:
        # lazily loading a command, first get the module name and attribute name
        import_path: str | None = self.lazy_subcommands.get(cmd_name)
        if not import_path:
            return None
        modname, cmd_object_name = t.cast(tuple[str, str], import_path.rsplit(".", 1))
        # do the import
        mod: ModuleType | None = None
        try:
            mod = importlib.import_module(modname)
        except ModuleNotFoundError as error:
            with patch_stdout(raw=True):
                get_console().log(f"Failed to load subcommand: {cmd_name}: {error.msg}")
            self.lazy_subcommands.pop(cmd_name, None)
        if not mod:
            return None
        # get the Command object from that module
        try:
            cmd_object: click.RichCommand = getattr(mod, cmd_object_name)
        except AttributeError:
            self.lazy_subcommands.pop(cmd_name, None)
        # check the result to make debugging easier
        try:
            cmd_object_is_command = isinstance(cmd_object, click.BaseCommand)  # type: ignore[arg-type]
        except UnboundLocalError:
            with patch_stdout(raw=True):
                get_console().log(
                    f"Failed to load subcommand: {cmd_name} from {import_path}"
                )
                self.lazy_subcommands.pop(cmd_name, None)
            return None
        if not cmd_object_is_command:
            self.lazy_subcommands.pop(cmd_name, None)
            raise ValueError(
                f"Lazy loading of {import_path} failed by returning "
                "a non-command object"
            )
        return cmd_object


def _cast_text_render(text: str) -> str:
    return t.cast(str, render(text, style=CONSOLE_CONFIG.style))


def _map_click_exception(e: click.ClickException) -> None:
    rich_help_formatter = RichHelpFormatter(
        config=RICH_HELP_CONFIG, console=get_console()
    )

    match type(e):
        case click.MissingParameter:
            e = t.cast(click.MissingParameter, e)
            with patch_stdout(raw=True):
                rich_format_error(
                    click.MissingParameter(
                        message=_cast_text_render(e.message),
                        ctx=e.ctx,
                        param=e.param,
                        param_hint=e.param_hint,
                    ),
                    rich_help_formatter,
                )
        case click.BadOptionUsage:
            e = t.cast(click.BadOptionUsage, e)
            with patch_stdout(raw=True):
                rich_format_error(
                    click.BadOptionUsage(
                        message=_cast_text_render(e.message),
                        ctx=e.ctx,
                        option_name=e.option_name,
                    ),
                    rich_help_formatter,
                )
        case click.BadParameter:
            e = t.cast(click.BadParameter, e)
            with patch_stdout(raw=True):
                rich_format_error(
                    click.BadParameter(
                        message=_cast_text_render(e.message),
                        ctx=e.ctx,
                        param=e.param,
                        param_hint=e.param_hint,
                    ),
                    rich_help_formatter,
                )
        case click.NoSuchOption:
            e = t.cast(click.NoSuchOption, e)
            with patch_stdout(raw=True):
                rich_format_error(
                    click.NoSuchOption(
                        option_name=e.option_name,
                        message=_cast_text_render(e.message),
                        possibilities=e.possibilities,
                        ctx=e.ctx,
                    ),
                    rich_help_formatter,
                )
        case click.UsageError:
            e = t.cast(click.UsageError, e)
            with patch_stdout(raw=True):
                rich_format_error(
                    click.UsageError(
                        message=_cast_text_render(e.message),
                        ctx=e.ctx,
                    ),
                    rich_help_formatter,
                )
        case click.BadArgumentUsage:
            e = t.cast(click.BadArgumentUsage, e)
            with patch_stdout(raw=True):
                rich_format_error(
                    click.BadArgumentUsage(
                        message=_cast_text_render(e.message),
                        ctx=e.ctx,
                    ),
                    rich_help_formatter,
                )
        case click.ClickException:
            with patch_stdout(raw=True):
                rich_format_error(
                    click.ClickException(message=_cast_text_render(e.message)),
                    rich_help_formatter,
                )
        case _:
            with patch_stdout(raw=True):
                rich_format_error(
                    click.ClickException(message="Unknown Error."),
                    rich_help_formatter,
                )
