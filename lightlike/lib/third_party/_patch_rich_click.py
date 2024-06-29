import re
import typing as t
from inspect import cleandoc

import rich_click as click
from click import Command
from click.types import _NumberRangeBase
from rich import box
from rich.columns import Columns
from rich.console import NewLine, group
from rich.highlighter import RegexHighlighter
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich_click.rich_help_formatter import RichHelpFormatter
from rich_click.rich_help_rendering import (
    _make_command_help,
    _make_rich_rext,
    _resolve_groups,
)

__all__: t.Sequence[str] = (
    "_get_rich_options",
    "_get_option_help",
    "_get_help_text",
    "_rich_format_error",
    "_cast_text_render",
    "_get_rich_commands",
)


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


def _get_rich_commands(
    obj: click.RichGroup, ctx: click.Context, formatter: RichHelpFormatter
) -> None:
    cmd_groups = _resolve_groups(
        ctx=ctx, groups=formatter.config.command_groups, group_attribute="commands"
    )
    for command in obj.list_commands(ctx):
        for cmd_group in cmd_groups:
            if command in cmd_group.get("commands", []):
                break
        else:
            commands = cmd_groups[-1]["commands"]
            commands.append(command)

    for cmd_group in cmd_groups:
        t_styles = {
            "show_lines": formatter.config.style_commands_table_show_lines,
            "leading": formatter.config.style_commands_table_leading,
            "box": formatter.config.style_commands_table_box,
            "border_style": formatter.config.style_commands_table_border_style,
            "row_styles": formatter.config.style_commands_table_row_styles,
            "pad_edge": formatter.config.style_commands_table_pad_edge,
            "padding": formatter.config.style_commands_table_padding,
        }
        if isinstance(formatter.config.style_commands_table_box, str):
            t_styles["box"] = getattr(box, t_styles.pop("box"), None)  # type: ignore[arg-type]
        t_styles.update(cmd_group.get("table_styles", {}))

        commands_table = Table(
            highlight=False,
            show_header=False,
            expand=True,
            **t_styles,  # type: ignore[arg-type]
        )
        if formatter.config.style_commands_table_column_width_ratio is None:
            table_column_width_ratio: t.Union[tuple[None, None], tuple[int, int]] = (
                None,
                None,
            )
        else:
            table_column_width_ratio = (
                formatter.config.style_commands_table_column_width_ratio
            )

        commands_table.add_column(
            style=formatter.config.style_command,
            no_wrap=True,
            ratio=table_column_width_ratio[0],
        )
        commands_table.add_column(
            no_wrap=False,
            ratio=table_column_width_ratio[1],
        )
        for command in cmd_group.get("commands", []):
            if command not in obj.list_commands(ctx):
                continue
            cmd = obj.get_command(ctx, command)
            if t.TYPE_CHECKING:
                assert cmd is not None
            if cmd.hidden:
                continue
            if formatter.config.use_click_short_help:
                helptext = cmd.get_short_help_str()
            else:
                helptext = cmd.short_help or cmd.help or ""
                if callable(helptext):
                    helptext = helptext()
            commands_table.add_row(
                command,
                _make_command_help(helptext, formatter, is_deprecated=cmd.deprecated),
            )
        if commands_table.row_count > 0:

            kw: dict[str, t.Any] = {
                "border_style": formatter.config.style_commands_panel_border,
                "title": cmd_group.get("name", formatter.config.commands_panel_title),
                "title_align": formatter.config.align_commands_panel,
            }

            if isinstance(formatter.config.style_commands_panel_box, str):
                box_style = getattr(
                    box, formatter.config.style_commands_panel_box, None
                )
            else:
                box_style = formatter.config.style_commands_panel_box

            if box_style:
                kw["box"] = box_style

            kw.update(cmd_group.get("panel_styles", {}))
            formatter.write(Panel(commands_table, **kw))
