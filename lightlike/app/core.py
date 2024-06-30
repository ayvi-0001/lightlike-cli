# mypy: disable-error-code="override"

import importlib
import re
import typing as t
import zlib
from inspect import cleandoc
from operator import truth
from os import getenv
from types import ModuleType

import rich_click as click
from click import Command
from click.types import _NumberRangeBase
from more_itertools import first
from prompt_toolkit.patch_stdout import patch_stdout
from rich import box, get_console
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, NewLine, group
from rich.highlighter import RegexHighlighter
from rich.markdown import Markdown
from rich.markup import render
from rich.padding import Padding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich_click.rich_context import RichContext
from rich_click.rich_help_configuration import RichHelpConfiguration
from rich_click.rich_help_formatter import RichHelpFormatter
from rich_click.rich_help_rendering import (
    _make_rich_rext,
    _resolve_groups,
    get_rich_commands,
    rich_format_error,
)

from lightlike.__about__ import __appname__, __repo__
from lightlike._console import (
    _CONSOLE_SVG_FORMAT,
    CONSOLE_CONFIG,
    GROUP_FIRST_COMMANDS,
    GROUP_LAST_COMMANDS,
    GROUP_MID_COMMANDS,
)

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
                    Align(_get_help_text(self, formatter), pad=False),
                    (0, 1, 1, 1),
                )
            )
        if hasattr(self, "syntax"):
            syntax = self.syntax() if callable(self.syntax) else self.syntax
            if syntax:
                formatter.write(Padding(syntax, (0, 1, 1, 1)))

    def format_options(self, ctx: RichContext, formatter: click.HelpFormatter) -> None:
        _get_rich_options(self, ctx, formatter)  # type: ignore[arg-type]


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
        get_rich_commands(self, ctx, formatter)
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
                    Align(_get_help_text(self, formatter), pad=False),
                    (0, 1, 1, 1),
                )
            )
        if hasattr(self, "syntax"):
            syntax = self.syntax() if callable(self.syntax) else self.syntax
            if syntax:
                formatter.write(Padding(syntax, (0, 1, 1, 1)))

    def format_options(self, ctx: RichContext, formatter: click.HelpFormatter) -> None:
        _get_rich_options(self, ctx, formatter)  # type: ignore[arg-type]


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


# Patch rich_click helper functions to fit repl.

def _get_rich_options(
    obj: click.RichCommand, ctx: click.RichContext, formatter: RichHelpFormatter
) -> None:
    option_groups = _resolve_groups(
        ctx=ctx, groups=formatter.config.option_groups, group_attribute="options"
    )
    argument_group_options = []

    for param in obj.get_params(ctx):
        if (
            isinstance(param, click.Argument) and not formatter.config.show_arguments
        ) or param.name == "debug":
            continue

        for option_group in option_groups:
            if any(
                [
                    opt in (option_group.get("options") or [])
                    for opt in param.opts  # fmt: skip
                ]
            ):
                break
        else:
            if (
                isinstance(param, click.Argument)
                and formatter.config.group_arguments_options
            ):
                argument_group_options.append(param.opts[0])
            else:
                list_of_option_groups = option_groups[-1]["options"]
                list_of_option_groups.append(param.opts[0])

    if len(argument_group_options) > 0:
        for grp in option_groups:
            if (
                grp.get("name", "")  # fmt: skip
                == formatter.config.arguments_panel_title
                and not grp.get("options")
            ):
                extra_option_group = grp.copy()
                extra_option_group["options"] = argument_group_options
                break
        else:
            extra_option_group = {
                "name": formatter.config.arguments_panel_title,
                "options": argument_group_options,
            }
        option_groups.insert(len(option_groups) - 1, extra_option_group)

    for option_group in option_groups:
        options_rows = []
        for opt in option_group.get("options") or []:
            for param in obj.get_params(ctx):
                if any([opt in param.opts]):
                    break
            else:
                continue

            opt_long_strs = []
            opt_short_strs = []
            for idx, opt in enumerate(param.opts):
                opt_str = opt
                try:
                    opt_str += "/" + param.secondary_opts[idx]
                except IndexError:
                    pass

                if isinstance(param, click.Argument):
                    opt_long_strs.append(opt_str.upper())
                elif "--" in opt:
                    opt_long_strs.append(opt_str)
                else:
                    opt_short_strs.append(opt_str)

            metavar = Text(style=formatter.config.style_metavar, overflow="fold")
            metavar_str = param.make_metavar()

            assert isinstance(param, click.Option) or isinstance(param, click.Argument)

            if (
                isinstance(param, click.Argument)
                and param.name
                and re.match(rf"\[?{param.name.upper()}]?", metavar_str)
            ):
                metavar_str = param.type.name.upper()

            if getattr(param, "is_flag", None):
                metavar.append("FLAG")
            else:
                metavar.append(metavar_str)

            if (
                (
                    isinstance(param.type, _NumberRangeBase)
                    or param.type.name.endswith("range")
                )
                and isinstance(param, click.Option)
                and not (
                    param.count and param.type.min == 0 and param.type.max is None  # type: ignore[attr-defined]
                )
            ):
                range_str = param.type._describe_range()  # type: ignore[attr-defined]
                if range_str:
                    metavar.append(formatter.config.range_string.format(range_str))

            required: t.Union[Text, str] = ""
            if param.required:
                required = Text(
                    formatter.config.required_short_string,
                    style=formatter.config.style_required_short,
                )

            class MetavarHighlighter(RegexHighlighter):
                highlights = [
                    r"^(?P<metavar_sep>(\[|<))",
                    r"(?P<metavar_sep>\|)",
                    r"(?P<metavar_sep>(\]|>)$)",
                ]

            metavar_highlighter = MetavarHighlighter()

            rows = [
                required,
                formatter.highlighter(formatter.highlighter(",".join(opt_long_strs))),
                formatter.highlighter(formatter.highlighter(",".join(opt_short_strs))),
                metavar_highlighter(metavar),
                _get_option_help(param, ctx, formatter),
            ]

            options_rows.append(rows)

        if len(options_rows) > 0:
            t_styles = {
                "show_lines": formatter.config.style_options_table_show_lines,
                "leading": formatter.config.style_options_table_leading,
                "box": formatter.config.style_options_table_box,
                "border_style": formatter.config.style_options_table_border_style,
                "row_styles": formatter.config.style_options_table_row_styles,
                "pad_edge": formatter.config.style_options_table_pad_edge,
                "padding": formatter.config.style_options_table_padding,
            }
            if isinstance(formatter.config.style_options_table_box, str):
                t_styles["box"] = getattr(box, t_styles.pop("box"), None)  # type: ignore[arg-type]
            t_styles.update(option_group.get("table_styles", {}))

            options_table = Table(
                highlight=True,
                show_header=False,
                style="#f0f0ff",
                expand=True,
                **t_styles,  # type: ignore[arg-type]
            )
            if all([x[0] == "" for x in options_rows]):
                options_rows = [x[1:] for x in options_rows]
            for row in options_rows:
                options_table.add_row(*row)

            kw: t.Dict[str, t.Any] = {
                "border_style": formatter.config.style_options_panel_border,
                "title": option_group.get("name", formatter.config.options_panel_title),
                "title_align": formatter.config.align_options_panel,
            }

            if isinstance(formatter.config.style_options_panel_box, str):
                box_style = getattr(box, formatter.config.style_options_panel_box, None)
            else:
                box_style = formatter.config.style_options_panel_box

            if box_style:
                kw["box"] = box_style

            kw.update(option_group.get("panel_styles", {}))
            formatter.write(Panel(options_table, **kw))


def _get_option_help(
    param: t.Union[click.Argument, click.Option],
    ctx: click.RichContext,
    formatter: RichHelpFormatter,
) -> Columns:
    config = formatter.config
    items: list[Markdown | Text] = []
    envvar = getattr(param, "envvar", None)

    if envvar is None:
        if (
            getattr(param, "allow_from_autoenv", None)
            and getattr(ctx, "auto_envvar_prefix", None) is not None
            and param.name is not None
        ):
            envvar = f"{ctx.auto_envvar_prefix}_{param.name.upper()}"
    if envvar is not None:
        envvar = ", ".join(envvar) if isinstance(envvar, list) else envvar

    if (
        getattr(param, "show_envvar", None)
        and config.option_envvar_first
        and envvar is not None
    ):
        items.append(
            Text(config.envvar_string.format(envvar), style=config.style_option_envvar),
        )

    help_text: str = ""
    if hasattr(param, "help"):
        if callable(param.help):
            help_text = f"{param.help()}"
        else:
            help_text = f"{param.help or ''}"

    if help_text:
        paragraphs = help_text.split("\n\n")
        rich_text = _make_rich_rext(
            "\n".join(paragraphs).strip(),
            config.style_option_help,
            formatter,
        )
        items.append(rich_text)

    if config.append_metavars_help and param.name:
        metavar_str = param.make_metavar()
        if isinstance(param, click.Argument) and re.match(
            rf"\[?{param.name.upper()}]?", metavar_str
        ):
            metavar_str = param.type.name.upper()
        if isinstance(param, click.Argument) or (
            metavar_str != "BOOLEAN" and not param.is_flag
        ):
            metavar_str = metavar_str.replace("[", "").replace("]", "")
            items.append(
                Text(
                    config.append_metavars_help_string.format(metavar_str),
                    style=config.style_metavar_append,
                    overflow="fold",
                )
            )

    if (
        getattr(param, "show_envvar", None)
        and not config.option_envvar_first
        and envvar is not None
    ):
        items.append(
            Text(
                config.envvar_string.format(envvar),
                style=config.style_option_envvar,
            )
        )

    if not hasattr(param, "show_default"):
        parse_default = False
    else:
        show_default_is_str = isinstance(param.show_default, str)
        parse_default = bool(
            show_default_is_str
            or (param.default is not None and (param.show_default or ctx.show_default))
        )

    if parse_default:
        help_record = param.get_help_record(ctx)
        if help_record:
            default_str_match = re.search(
                r"\[(?:.+; )?default: (.*)\]", help_record[-1]
            )
            if default_str_match:
                default_str = default_str_match.group(1).replace("; required", "")
                items.append(
                    Text(
                        config.default_string.format(default_str),
                        style=config.style_option_default,
                    )
                )

    if param.required:
        items.append(
            Text(
                config.required_long_string,
                style=config.style_required_long,
            )
        )

    return Columns(items)


@group()
def _get_help_text(
    obj: t.Union[Command, click.RichGroup], formatter: RichHelpFormatter
) -> t.Iterable[t.Union[Markdown, Text, NewLine, Padding]]:
    config = formatter.config

    if obj.deprecated:
        yield Text(config.deprecated_string, style=config.style_deprecated)

    if hasattr(obj, "help"):
        if callable(obj.help):
            help_text = cleandoc(obj.help())
        else:
            help_text = cleandoc(obj.help or "")

    lines = help_text.split("\n")

    if len(lines) > 0:
        if not config.use_markdown:
            lines = [x.replace("\n", " ") for x in lines]
            remaining_lines = "\n".join(lines)
        else:
            remaining_lines = "\n\n".join(lines)

        yield _make_rich_rext(remaining_lines, config.style_helptext, formatter)
