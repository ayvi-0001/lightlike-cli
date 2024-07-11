import importlib
import re
import typing as t
import zlib
from functools import singledispatch
from inspect import cleandoc
from operator import truth
from os import getenv
from types import ModuleType

import click
import rich.console
from click.types import _NumberRangeBase
from more_itertools import first, last
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich.columns import Columns
from rich.highlighter import RegexHighlighter
from rich.markup import render
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from lightlike.__about__ import __appname__, __repo__
from lightlike._console import (
    CONSOLE_CONFIG,
    GROUP_FIRST_COMMANDS,
    GROUP_LAST_COMMANDS,
    GROUP_MID_COMMANDS,
)
from lightlike.internal.constant import _CONSOLE_SVG_FORMAT

__all__: t.Sequence[str] = (
    "FormattedCommand",
    "AliasedGroup",
    "LazyAliasedGroup",
    "_format_click_exception",
)


T = t.TypeVar("T")
P = t.ParamSpec("P")


@t.overload
def _get_maybe_callable(
    obj: t.Any,
    attr: str,
    cast: type[T],
    default: T,
    apply: t.Sequence[t.Callable[..., T]] | None = None,
) -> T: ...


@t.overload
def _get_maybe_callable(
    obj: t.Any,
    attr: str,
    cast: type[T],
    default: t.Literal[None] = None,
    apply: t.Sequence[t.Callable[..., T]] | None = None,
) -> T | None: ...


def _get_maybe_callable(
    obj: t.Any,
    attr: str,
    cast: type[T],
    default: T | None = None,
    apply: t.Sequence[t.Callable[..., T]] | None = None,
) -> T | None:
    _attr: T | None = None
    source: T | None = getattr(obj, attr, None)
    if callable(source):
        _attr = source()
    else:
        _attr = source

    if apply and _attr:
        for fn in apply:
            fn(_attr)

    if _attr is not None:
        return _attr
    else:
        if default is not None:
            if isinstance(default, cast):
                return default
            else:
                raise TypeError(f"Default is not of type T@{cast}")
        else:
            return _attr


class FormattedCommand(click.Command):
    def __init__(
        self,
        syntax: t.Optional[t.Callable[..., Syntax]] = None,
        allow_name_alias: bool = True,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.syntax = syntax
        self.allow_name_alias = allow_name_alias

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        format_help(self, ctx, formatter)


class AliasedGroup(click.Group):
    def __init__(
        self,
        syntax: t.Optional[t.Callable[..., Syntax]] = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.syntax = syntax

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = []
        for m in self.list_commands(ctx):
            if m.startswith(cmd_name):
                command = self.get_command(ctx, m)
                if (
                    getattr(command, "allow_name_alias", None) is False
                    and cmd_name != m
                ):
                    return None
                if not (command and command.hidden):
                    matches.append(m)
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, first(matches))
        else:
            ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(
        self, ctx: click.Context, args: t.Any
    ) -> tuple[str | t.Any | None, click.Command | None, t.Any]:
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name if cmd else None, cmd, args

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        format_help(self, ctx, formatter)


class LazyAliasedGroup(AliasedGroup):
    def __init__(
        self,
        lazy_subcommands: dict[str, str] | None = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        super().__init__(*args, **kwargs)
        #   {command-name} -> {module-name}.{command-object-name}
        self.lazy_subcommands = lazy_subcommands or {}

    def list_commands(self, ctx: click.Context) -> list[str]:
        base: list[str] = super().list_commands(ctx)
        lazy: list[str] = sorted(self.lazy_subcommands.keys())
        return base + lazy

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        if cmd_name in self.lazy_subcommands:
            return self._lazy_load(cmd_name)
        matches = [m for m in self.list_commands(ctx) if m.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1 and (match := first(matches)) in self.lazy_subcommands:
            command = self._lazy_load(match)
            if (
                getattr(command, "allow_name_alias", None) is False
                and cmd_name != match
            ):
                return None
            return command
        else:
            return super().get_command(ctx, cmd_name)

    def _lazy_load(self, cmd_name: str) -> click.Command | None:
        # lazily loading a command, first get the module name and attribute name
        import_path: str | None = self.lazy_subcommands.get(cmd_name)
        if not import_path:
            return None
        modname, cmd_object_name = import_path.rsplit(":", 1)
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
            cmd_object: click.Command = getattr(mod, cmd_object_name)
        except AttributeError:
            self.lazy_subcommands.pop(cmd_name, None)
        # check the result to make debugging easier
        try:
            cmd_object_is_command = isinstance(cmd_object, click.BaseCommand)
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


class ReplHighlighter(RegexHighlighter):
    highlights: list[str] = [
        r"(^|[^\w\-])(?P<switch>-([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(^|[^\w\-])(?P<option>--([^\W0-9][\w\-]*\w|[^\W0-9]))",
        r"(?P<metavar><[^>]+>)",
        GROUP_FIRST_COMMANDS,
        GROUP_MID_COMMANDS,
        GROUP_LAST_COMMANDS,
    ]


class UsageHighlighter(RegexHighlighter):
    highlights = [r"(?P<argument>\w+)"]


class MetavarHighlighter(RegexHighlighter):
    highlights = [
        r"^(?P<metavar_sep>(\[|<))",
        r"(?P<metavar_sep>\|)",
        r"(?P<metavar_sep>(\]|>)$)",
    ]


def _format_click_exception(exception: click.ClickException) -> None:
    console = get_console()
    ctx: click.Context | None = None

    with patch_stdout(raw=True):
        if hasattr(exception, "ctx"):
            ctx = getattr(exception, "ctx")
            if ctx:
                console.print(_group_usage(ctx))

        if ctx and ctx.command.get_help_option(ctx):
            cmd_path = ctx.command_path
            help_option: str = ctx.help_option_names[0]

            console.print(
                f"[dimmed]Try [magenta]{cmd_path} {help_option}[/magenta] for help"
            )

        console.print(
            "[b][red]Error:",
            ReplHighlighter()(
                render(exception.format_message(), style=CONSOLE_CONFIG.style)
            ),
        )


def format_help(
    obj: click.Group | click.Command,
    ctx: click.Context,
    formatter: click.HelpFormatter,
) -> None:
    _export_help = truth(getenv("LIGHTLIKE_CLI_DEV_EXPORT_HELP"))
    console = get_console()
    console.width = 120

    if _export_help:
        console.record = True
        console.export_text(clear=True)

    console.print(_group_usage(ctx))
    console.print(_group_help(obj))
    console.print(_group_syntax(obj))
    console.print(_group_options(obj, ctx))

    if isinstance(obj, click.Group):
        console.print(_group_commands(obj, ctx))

    if _export_help:
        title = "lightlike-cli"
        command_path = ctx.command_path.replace("lightlike", "").strip()

        invoked_subcommand = "".join(
            c if c.isalnum() else "_" for c in str(command_path)
        )
        unique_id = f"{title}-%s" % zlib.adler32(
            invoked_subcommand.encode("utf-8", "ignore")
        )
        console.save_svg(
            path=f"./{invoked_subcommand}.svg",
            title=title,
            code_format=_CONSOLE_SVG_FORMAT,
            clear=True,
            unique_id=unique_id,
        )

    console.width = None  # type: ignore[assignment]


@rich.console.group()
def _group_usage(ctx: click.Context) -> t.Iterable[rich.console.RenderableType]:
    yield rich.console.NewLine()
    yield Columns(
        [
            Text("Usage:", style="bold #f0f0ff"),
            Text(ctx.command_path, style="bold #3465a4 on default"),
            UsageHighlighter()(" ".join(ctx.command.collect_usage_pieces(ctx))),
        ]
    )
    yield rich.console.NewLine()


@rich.console.group()
def _group_help(
    obj: click.Command | click.Group,
) -> t.Iterable[rich.console.RenderableType]:
    if obj.deprecated:
        yield Text("(Deprecated) ", style="red")

    help_text: str = _get_maybe_callable(
        obj=obj,
        attr="help",
        cast=str,
        default="",
        apply=[cleandoc],
    )

    lines = help_text.split("\n")
    if lines != [""]:
        yield ReplHighlighter()(
            render(cleandoc("\n".join(map(lambda l: l.replace("\n", " "), lines))))
        )


@rich.console.group()
def _group_syntax(
    obj: click.Command | click.Group,
) -> t.Iterable[rich.console.RenderableType]:
    syntax: Syntax | None = _get_maybe_callable(
        obj=obj,
        attr="syntax",
        cast=Syntax,
        default=None,
        apply=None,
    )
    if syntax:
        yield rich.console.NewLine()
        yield "[b][u]Syntax:"
        yield rich.console.NewLine()
        yield syntax


@rich.console.group()
def _group_commands(
    obj: click.Group, ctx: click.Context
) -> t.Iterable[rich.console.RenderableType]:
    table = Table(
        highlight=True,
        show_header=False,
        border_style=None,
        show_lines=False,
        box=None,
        show_edge=False,
        style="#f0f0ff",
    )

    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(no_wrap=False, width=7)
    table.add_column(no_wrap=False)

    commands = obj.list_commands(ctx)
    for command in commands:
        cmd = obj.get_command(ctx, command)
        if cmd:
            if cmd.hidden:
                continue
            else:
                help_text = cmd.short_help or cmd.help or ""
                table.add_row(command, "", ReplHighlighter()(help_text))

    if table.row_count != 0:
        yield rich.console.NewLine()
        yield Text("Commands", style="bold underline")
        yield Padding(table, (0, 0, 0, 2))


class OptionGroups(t.TypedDict):
    name: str
    items: list[str]


@rich.console.group()
def _group_options(
    obj: click.Command, ctx: click.Context
) -> t.Iterable[rich.console.RenderableType]:
    groups: list[OptionGroups] = [{"name": "Options", "items": []}]
    arguments: list[str] = []
    params: list[click.Parameter] = obj.get_params(ctx)

    for param in params:
        if param.name == "debug":
            continue
        elif isinstance(param, click.Argument):
            arguments.append(param.opts[0])
        else:
            groups[0]["items"].append(param.opts[0])

    if len(arguments) > 0:
        extra_option_group = OptionGroups(name="Arguments", items=arguments)
        groups.insert(len(groups) - 1, extra_option_group)

    for group in groups:
        rows = []
        for opt in group["items"]:
            for param in params:
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

            metavar = Text(style="not dim cyan", overflow="fold")
            metavar_str = param.make_metavar()

            if (
                isinstance(param, click.Argument)
                and param.name
                and re.match(rf"\[?{param.name.upper()}]?", metavar_str)
            ):
                metavar_str = param.type.name.upper()

            if getattr(param, "is_flag", False):
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
                    metavar.append(f" [{range_str}]")

            required: Text | str = ""
            if param.required:
                required = Text("*", style="red")

            rows.append(
                [
                    required,
                    ReplHighlighter()(ReplHighlighter()(",".join(opt_long_strs))),
                    ReplHighlighter()(ReplHighlighter()(",".join(opt_short_strs))),
                    MetavarHighlighter()(metavar),
                    _get_option_help(param, ctx),
                ]
            )

        if len(rows) > 0:
            table = Table(
                highlight=True,
                show_header=False,
                border_style=None,
                show_lines=False,
                box=None,
                show_edge=False,
                style="#f0f0ff",
            )

            yield rich.console.NewLine()
            yield f"[b][u]{group['name']}"

            for row in rows:
                table.add_row(*row)

            yield table


@singledispatch
def _get_option_help(param: click.Parameter, ctx: click.Context) -> Columns: ...  # type: ignore[empty-body]


@_get_option_help.register
def _(param: click.Argument, ctx: click.Context) -> Columns:
    items: list[rich.console.RenderableType] = []
    envvar = param.envvar
    if envvar:
        envvar = ", ".join(envvar) if isinstance(envvar, list) else envvar

    help_text: str = _get_maybe_callable(
        obj=param,
        attr="help",
        cast=str,
        default="",
        apply=[cleandoc],
    )

    if help_text:
        text = ReplHighlighter()(Text(help_text, style="#f0f0ff"))
        items.append(text)

    if param.default or ctx.show_default:
        help_record = param.get_help_record(ctx)
        if help_record:
            default_str_match = re.search(
                r"\[(?:.+; )?default: (.*)\]", last(help_record)
            )
            if default_str_match:
                default_str = default_str_match.group(1).replace("; required", "")
                items.append(Text(f"[default={default_str}]", style="dimmed"))

    if param.required:
        items.append(Text("[required]", style="bold not dim red"))

    return Columns(items)


@_get_option_help.register
def _(param: click.Option, ctx: click.Context) -> Columns:
    items: list[rich.console.RenderableType] = []
    envvar = param.envvar

    if not envvar:
        if param.allow_from_autoenv and ctx.auto_envvar_prefix and param.name:
            envvar = f"{ctx.auto_envvar_prefix}_{param.name.upper()}"
    if envvar:
        envvar = ", ".join(envvar) if isinstance(envvar, list) else envvar

    if param.show_envvar and envvar:
        items.append(Text(f"[env var: {envvar}]", style="dim yellow"))

    help_text: str = _get_maybe_callable(
        obj=param,
        attr="help",
        cast=str,
        default="",
        apply=[cleandoc],
    )

    if help_text:
        text = ReplHighlighter()(Text(help_text.strip(), style="#f0f0ff"))
        items.append(text)

    if param.default or ctx.show_default:
        help_record = param.get_help_record(ctx)
        if help_record:
            default_str_match = re.search(
                r"\[(?:.+; )?default: (.*)\]", last(help_record)
            )
            if default_str_match:
                default_str = default_str_match.group(1).replace("; required", "")
                items.append(Text(f"[default={default_str}]", style="dimmed"))

    if param.required:
        items.append(Text("[required]", style="bold not dim red"))

    return Columns(items)
