import re
from typing import TYPE_CHECKING, Any, ParamSpec, Sequence

import rich_click as click
from click import Command
from click.types import _NumberRangeBase
from rich import box, get_console
from rich.align import Align
from rich.columns import Columns
from rich.highlighter import RegexHighlighter
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich_click.rich_click import (
    _get_help_text,
    _get_option_help,
    _get_rich_formatter,
    _make_command_help,
    _make_rich_rext,
)

from lightlike.__about__ import __appname__, __repo__

__all__: Sequence[str] = ("AliasedRichGroup", "_RichCommand")


P = ParamSpec("P")


click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_CLICK_SHORT_HELP = False
click.rich_click.HEADER_TEXT = f"[link={__repo__}]{__appname__}"
click.rich_click.STYLE_HEADER_TEXT = "bold #9146FF"
click.rich_click.COLOR_SYSTEM = "truecolor"
click.rich_click.OPTIONS_PANEL_TITLE = "[b][not dim][#f0f0ff]Options"
click.rich_click.OPTION_ENVVAR_FIRST = True
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "#f0f0ff"
click.rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE"
click.rich_click.STYLE_OPTIONS_TABLE_LEADING = 1
click.rich_click.STYLE_OPTION_HELP = "#f0f0ff"
click.rich_click.STYLE_OPTIONS_TABLE_BOX = " "
click.rich_click.STYLE_EPILOG_TEXT = "bold #f0f0ff"
click.rich_click.STYLE_FOOTER_TEXT = "bold #f0f0ff"
click.rich_click.STYLE_USAGE = f"bold #f0f0ff"
click.rich_click.STYLE_USAGE_COMMAND = f"bold #3465a4 on default"
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "dim bright_blue"
click.rich_click.STYLE_COMMANDS_TABLE_SHOW_LINES = True
click.rich_click.STYLE_COMMANDS_TABLE_BOX = "SIMPLE"
click.rich_click.STYLE_COMMANDS_TABLE_SHOW_LINES = True
click.rich_click.STYLE_COMMANDS_TABLE_BOX = " "
click.rich_click.COMMANDS_PANEL_TITLE = "[b][not dim][#f0f0ff]Commands"
click.rich_click.STYLE_ARGUMENT = "not dim bold cyan"
click.rich_click.STYLE_METAVAR = "not dim cyan"
click.rich_click.STYLE_METAVAR_APPEND = "not dim cyan"
click.rich_click.STYLE_METAVAR_SEPARATOR = "not dim cyan"
click.rich_click.SHOW_METAVARS_COLUMN = True
click.rich_click.APPEND_METAVARS_HELP = False
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.ARGUMENTS_PANEL_TITLE = "[b][not dim][#f0f0ff]Arguments"
click.rich_click.DEFAULT_STRING = "[default={}]"
click.rich_click.STYLE_HELPTEXT = "#f0f0ff"
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "#f0f0ff"
click.rich_click.STYLE_REQUIRED_LONG = "not dim red"
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "bold"
click.rich_click.STYLE_ERRORS_SUGGESTION_COMMAND = "magenta"
click.rich_click.STYLE_ERRORS_PANEL_BORDER = "bold red"


@click.rich_config(console=get_console())
class _RichCommand(click.RichCommand):
    def __init__(self, *args: P.args, **kwargs: P.kwargs) -> None:
        super().__init__(*args, **kwargs)

    def format_help(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        _rich_format_help(self, ctx, formatter)


@click.rich_config(console=get_console())
class AliasedRichGroup(click.RichGroup):
    def __init__(self, *args: P.args, **kwargs: P.kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        # fmt: off
        matches = [
            m for m in self.list_commands(ctx) if m.startswith(cmd_name)
            and not ((cmd := self.get_command(ctx, m)) and cmd.hidden)
        ]
        # fmt: on
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(
        self, ctx: click.Context, args: Any
    ) -> tuple[str | Any | None, click.Command | None, Any]:
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name if cmd else None, cmd, args

    def format_help(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        _rich_format_help(self, ctx, formatter)


# rich_format_help() but looks to see if 'syntax' is in the context object. prints syntax if found.
# + other minor modifications.
def _rich_format_help(
    obj: click.RichGroup | click.RichCommand,
    ctx: click.Context,
    formatter: click.HelpFormatter,
) -> None:
    formatter = _get_rich_formatter(formatter)
    config = formatter.config
    console = formatter.console
    highlighter = formatter.config.highlighter

    # Header text if we have it
    if config.header_text:
        console.print(
            Padding(
                _make_rich_rext(
                    config.header_text, config.style_header_text, formatter
                ),
                (1, 1, 0, 1),
            ),
        )

    # Print usage
    class UsageHighlighter(RegexHighlighter):
        highlights = [r"(?P<argument>\w+)"]

    usage_highlighter = UsageHighlighter()
    console.print(
        Padding(
            Columns(
                (
                    Text("Usage:", style=config.style_usage),
                    Text(ctx.command_path, style=config.style_usage_command),
                    usage_highlighter(" ".join(obj.collect_usage_pieces(ctx))),
                )
            ),
            1,
        ),
    )

    # Print command / group help if we have some
    if obj.help:
        # Print with some padding
        console.print(
            Padding(
                Align(_get_help_text(obj, formatter), pad=False),
                (0, 1, 1, 1),
            )
        )

    if ctx.obj and "syntax" in ctx.obj:
        syntax = ctx.obj.get("syntax")
        if syntax:
            console.print(Padding(ctx.obj["syntax"], (0, 1, 1, 1)))

    # Look through config.option_groups for this command
    # stick anything unmatched into a default group at the end
    option_groups = config.option_groups.get(ctx.command_path, []).copy()
    option_groups.append({"options": []})
    argument_group_options = []

    for param in obj.get_params(ctx):
        # Skip positional arguments - they don't have opts or helptext and are covered in usage
        # See https://click.palletsprojects.com/en/8.0.x/documentation/#documenting-arguments
        if isinstance(param, click.Argument) and not config.show_arguments:
            continue

        # # Skip if option is hidden
        # if getattr(param, "hidden", False):
        #     continue
        if param.name == "debug":
            continue

        # Already mentioned in a config option group
        for option_group in option_groups:
            if any([opt in option_group.get("options", []) for opt in param.opts]):
                break

        # No break, no mention - add to the default group
        else:
            if isinstance(param, click.Argument) and not config.group_arguments_options:
                argument_group_options.append(param.opts[0])
            else:
                list_of_option_groups: list[str] = option_groups[-1]["options"]  # type: ignore[assignment]
                list_of_option_groups.append(param.opts[0])

    # If we're not grouping arguments and we got some, prepend before default options
    if len(argument_group_options) > 0:
        extra_option_group = {
            "name": config.arguments_panel_title,
            "options": argument_group_options,
        }
        option_groups.insert(len(option_groups) - 1, extra_option_group)

    # Print each option group panel
    for option_group in option_groups:
        options_rows = []
        for opt in option_group.get("options", []):
            # Get the param
            for param in obj.get_params(ctx):
                if any([opt in param.opts]):
                    break
            # Skip if option is not listed in this group
            else:
                continue

            # Short and long form
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

            # Column for a metavar, if we have one
            metavar = Text(style=config.style_metavar, overflow="fold")
            metavar_str = param.make_metavar()

            if TYPE_CHECKING:
                assert isinstance(param.name, str)
                assert isinstance(param, click.Option)

            # Do it ourselves if this is a positional argument
            if isinstance(param, click.Argument) and re.match(
                rf"\[?{param.name.upper()}]?", metavar_str
            ):
                metavar_str = param.type.name.upper()

            if getattr(param, "is_flag", None):
                metavar.append("FLAG")
            else:
                metavar.append(metavar_str)

            # Range - from
            # https://github.com/pallets/click/blob/c63c70dabd3f86ca68678b4f00951f78f52d0270/src/click/core.py#L2698-L2706  # noqa: E501
            try:
                # skip count with default range type
                if isinstance(param.type, _NumberRangeBase) and not (
                    param.count and param.type.min == 0 and param.type.max is None
                ):
                    range_str = param.type._describe_range()
                    if range_str:
                        metavar.append(config.range_string.format(range_str))
            except AttributeError:
                # click.types._NumberRangeBase is only in Click 8x onwards
                pass

            # Required asterisk
            required: Text | str = ""
            if param.required:
                required = Text(
                    config.required_short_string, style=config.style_required_short
                )

            # Highlighter to make [ | ] and <> dim
            class MetavarHighlighter(RegexHighlighter):
                highlights = [
                    r"^(?P<metavar_sep>(\[|<))",
                    r"(?P<metavar_sep>\|)",
                    r"(?P<metavar_sep>(\]|>)$)",
                ]

            metavar_highlighter = MetavarHighlighter()

            if isinstance(param, click.Argument):
                rows = [
                    required,
                    Text(",".join(opt_long_strs), style=config.style_argument),
                    highlighter(highlighter(",".join(opt_short_strs))),
                    metavar_highlighter(metavar),
                    _get_option_help(param, ctx, formatter),
                ]
            else:
                rows = [
                    required,
                    highlighter(highlighter(",".join(opt_long_strs))),
                    highlighter(highlighter(",".join(opt_short_strs))),
                    metavar_highlighter(metavar),
                    _get_option_help(param, ctx, formatter),
                ]

            # Remove metavar if specified in config
            if not config.show_metavars_column:
                rows.pop(3)

            options_rows.append(rows)

        if len(options_rows) > 0:
            t_styles = {
                "show_lines": config.style_options_table_show_lines,
                "leading": config.style_options_table_leading,
                "box": config.style_options_table_box,
                "border_style": config.style_options_table_border_style,
                "row_styles": config.style_options_table_row_styles,
                "pad_edge": config.style_options_table_pad_edge,
                "padding": config.style_options_table_padding,
            }
            t_styles.update(option_group.get("table_styles", {}))  # type: ignore[arg-type]
            box_style = getattr(box, t_styles.pop("box"), None)  # type: ignore[arg-type]

            options_table = Table(
                highlight=True,
                show_header=False,
                expand=False,
                box=box_style,
                **t_styles,  # type: ignore[arg-type]
            )
            # Strip the required column if none are required
            if all([x[0] == "" for x in options_rows]):
                options_rows = [x[1:] for x in options_rows]
            for row in options_rows:
                options_table.add_row(*row)
            console.print(
                Panel(
                    options_table,
                    border_style=config.style_options_panel_border,
                    title=option_group.get("name", config.options_panel_title),
                    title_align=config.align_options_panel,
                )
            )

    #
    # Groups only:
    # List click command groups
    #

    if isinstance(obj, click.Group):
        # Look through COMMAND_GROUPS for this command
        # stick anything unmatched into a default group at the end
        cmd_groups = config.command_groups.get(ctx.command_path, []).copy()
        cmd_groups.append({"commands": []})
        for command in obj.list_commands(ctx):
            for cmd_group in cmd_groups:
                if command in cmd_group.get("commands", []):
                    break
            else:
                commands: list[str] = cmd_groups[-1]["commands"]  # type: ignore[assignment]
                commands.append(command)

        # Print each command group panel
        for cmd_group in cmd_groups:
            t_styles = {
                "show_lines": config.style_commands_table_show_lines,
                "leading": config.style_commands_table_leading,
                "box": config.style_commands_table_box,
                "border_style": config.style_commands_table_border_style,
                "row_styles": config.style_commands_table_row_styles,
                "pad_edge": config.style_commands_table_pad_edge,
                "padding": config.style_commands_table_padding,
            }
            t_styles.update(cmd_group.get("table_styles", {}))  # type: ignore[arg-type]
            box_style = getattr(box, t_styles.pop("box"), None)  # type: ignore[arg-type]

            commands_table = Table(
                highlight=False,
                show_header=False,
                expand=False,
                box=box_style,
                **t_styles,  # type: ignore[arg-type]
            )
            # Define formatting in first column, as commands don't match highlighter regex
            # and set column ratio for first and second column, if a ratio has been set
            if config.style_commands_table_column_width_ratio is None:
                table_column_width_ratio: tuple[None, None] | tuple[int, int] = (
                    None,
                    None,
                )
            else:
                table_column_width_ratio = (
                    config.style_commands_table_column_width_ratio
                )

            commands_table.add_column(
                style=config.style_command,
                no_wrap=True,
                ratio=table_column_width_ratio[0],
            )
            commands_table.add_column(
                no_wrap=False,
                ratio=table_column_width_ratio[1],
            )
            for command in cmd_group.get("commands", []):
                # Skip if command does not exist
                if command not in obj.list_commands(ctx):
                    continue
                cmd = obj.get_command(ctx, command)
                if TYPE_CHECKING:
                    assert cmd is not None
                if cmd.hidden:
                    continue
                # Use the truncated short text as with vanilla text if requested
                if config.use_click_short_help:
                    helptext = cmd.get_short_help_str()
                else:
                    # Use short_help function argument if used, or the full help
                    helptext = cmd.short_help or cmd.help or ""
                commands_table.add_row(command, _make_command_help(helptext, formatter))
            if commands_table.row_count > 0:
                console.print(
                    Panel(
                        commands_table,
                        border_style=config.style_commands_panel_border,
                        title=cmd_group.get("name", config.commands_panel_title),
                        title_align=config.align_commands_panel,
                    )
                )

    # Epilogue if we have it
    if isinstance(obj, Command) and obj.epilog:
        # Remove single linebreaks, replace double with single
        lines = obj.epilog.split("\n\n")
        epilogue = "\n".join([x.replace("\n", " ").strip() for x in lines])
        console.print(
            Padding(
                Align(
                    _make_rich_rext(epilogue, config.style_epilog_text, formatter),
                    pad=False,
                ),
                1,
            )
        )

    # Footer text if we have it
    if config.footer_text:
        console.print(
            Padding(
                _make_rich_rext(
                    config.footer_text, config.style_footer_text, formatter
                ),
                (1, 1, 0, 1),
            )
        )
