# mypy: disable-error-code="import-untyped"

import typing as t
from dataclasses import dataclass

import rich_click as click
from more_itertools import nth, one
from pytz import all_timezones
from rich import print as rprint
from rich.console import Console
from rich.syntax import Syntax

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import _pass, shell_complete, threads, validate
from lightlike.app.cache import TimeEntryAppData
from lightlike.app.config import AppConfig
from lightlike.app.core import AliasedRichGroup, FmtRichCommand
from lightlike.cmd import _help
from lightlike.internal import markup, utils
from lightlike.internal.enums import CredentialsSource

__all__: t.Sequence[str] = ("open_", "show", "set_")


P = t.ParamSpec("P")


@click.command(
    cls=FmtRichCommand,
    name="open",
    help=_help.app_config,
    short_help="Open config using the default text editor.",
    syntax=_help.app_config_syntax,
)
@_pass.console
def open_(console: Console) -> None:
    path = __config__.resolve()
    uri = path.as_uri()
    editor = AppConfig().get("settings", "editor", default=None)

    if editor:
        click.edit(
            editor=editor, filename=f"{path}", extension=".toml", require_save=False
        )
        console.print("$", editor, markup.link(uri, uri))
    else:
        click.launch(f"{path}")
        console.print("$ start", markup.link(uri, uri))


@click.command(
    cls=FmtRichCommand,
    name="show",
    help=_help.app_config_show,
    short_help="Show config values.",
    syntax=_help.app_config_show_syntax,
)
@_pass.console
def show(console: Console) -> None:
    console.print(
        Syntax(
            __config__.read_text(),
            lexer="toml",
            line_numbers=True,
            background_color="#131310",
        )
    )


@click.group(
    cls=AliasedRichGroup,
    name="set",
    help=_help.app_config,
    short_help="Set config values.",
    syntax=_help.app_config_syntax,
)
def set_() -> None: ...


@set_.group(
    cls=AliasedRichGroup,
    name="general",
    chain=True,
    help=_help.app_config,
    short_help="General cli settings.",
    syntax=_help.app_config_syntax,
)
def update_general_settings() -> None: ...


@set_.group(
    cls=AliasedRichGroup,
    name="query",
    chain=True,
    help=_help.app_config,
    short_help="bq:query settings.",
    syntax=_help.app_config_syntax,
)
def update_query_settings() -> None: ...


_thread_sequence: t.TypeAlias = t.Sequence[
    tuple[t.Callable[[t.Any | None], t.Any], t.Any]
]


@dataclass()
class SettingsCommand:
    name: str
    config_keys: list[str]
    argument: t.Callable[[click.RichCommand], click.RichCommand]
    help: t.Callable[..., str] | str | None = None
    short_help: t.Callable[..., str] | str | None = None
    callback_fn: t.Callable[..., t.Any] | None = None
    callback_threads: _thread_sequence | None = None
    context_settings: dict[str, t.Any] | None = None
    syntax: t.Callable[..., "Syntax"] | None = None
    no_args_is_help: bool = True


value_arg = click.argument(
    "value",
    type=click.BOOL,
    shell_complete=shell_complete.Param("value").bool,
)


def create_settings_fn(
    cmd: SettingsCommand, config_keys: t.Sequence[str]
) -> click.RichCommand:
    @click.command(
        cls=FmtRichCommand,
        name=cmd.name,
        no_args_is_help=cmd.no_args_is_help,
        help=cmd.help or cmd.short_help,
        short_help=cmd.short_help,
        context_settings=cmd.context_settings,
        syntax=cmd.syntax,
    )
    @utils._handle_keyboard_interrupt(
        callback=lambda: rprint(markup.dimmed(f"Did not update {cmd.name}.")),
    )
    @_pass.console
    @click.pass_context
    def __cmd(
        ctx: click.RichContext,
        console: Console,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        val = nth(one(kwargs.items()), 1)

        if val == AppConfig().get(*config_keys).get(cmd.name):
            console.print(
                markup.dimmed(
                    f"`{cmd.name}` is already set to `{val}`, nothing happened."
                )
            )
            return

        with AppConfig().rw() as config:
            c = utils.reduce_keys(*config_keys, sequence=config)
            c["".join(c if c.isalnum() else "_" for c in cmd.name)] = val

        rprint("Set", markup.scope_key(cmd.name), "to", val)

        if cmd.callback_fn:
            cmd.callback_fn(locals())
        if cmd.callback_threads:
            for thread, kwargs in cmd.callback_threads:
                threads.spawn(ctx=ctx, fn=thread, kwargs=kwargs)

    return cmd.argument(__cmd)


note_history = SettingsCommand(
    name="note_history",
    argument=click.argument("days", type=click.INT),
    help=_help.app_config_note_history,
    short_help="Days to store note history.",
    syntax=_help.app_config_note_history_syntax,
    callback_threads=[(TimeEntryAppData().sync, None)],
    config_keys=["settings"],
)


quiet_start = SettingsCommand(
    name="quiet_start",
    argument=value_arg,
    short_help="Hide logs when starting REPL.",
    config_keys=["settings"],
)


system_command_shell_argument = click.argument(
    "shell",
    cls=shell_complete.LiteralEvalArg,
    default=[],
)

system_command_shell = SettingsCommand(
    name="shell",
    argument=system_command_shell_argument,
    help=_help.app_config_system_command_shell,
    syntax=_help.app_config_system_command_shell_syntax,
    short_help="Shell to use when running external commands.",
    config_keys=["system-command"],
)


def timezone_setting_callback(_locals: dict[str, t.Any]) -> None:
    from pytz import timezone

    import lightlike.app.cursor

    tz = timezone(_locals["kwargs"].get("timezone"))

    lightlike.app.cursor.TIMEZONE = tz
    AppConfig().tz = tz

    rprint(
        "[b]You will also need to run app:run-bq to",
        "rebuild procedures using this new timezone.",
    )


timezone = SettingsCommand(
    name="timezone",
    argument=click.argument(
        "timezone",
        type=click.STRING,
        callback=validate.callbacks.timezone,
        shell_complete=lambda c, p, i: [t for t in all_timezones if i in t.lower()],
    ),
    help=_help.app_config_timezone,
    short_help="Timezone used for all date/time conversions.",
    syntax=_help.app_config_timezone_syntax,
    callback_fn=timezone_setting_callback,
    config_keys=["settings"],
)


week_start = SettingsCommand(
    name="week_start",
    argument=click.argument(
        "dayofweek",
        type=click.Choice(["Sunday", "Monday"]),
        callback=validate.callbacks.weekstart,
    ),
    help=_help.app_config_week_start,
    short_help="Update week start for `--current-week` flags.",
    syntax=_help.app_config_week_start_syntax,
    config_keys=["settings"],
)


timer_add_min = SettingsCommand(
    name="timer_add_min",
    argument=click.argument("minutes", type=click.INT),
    short_help="Default minutes for cmd timer:add.",
    config_keys=["settings"],
)


editor = SettingsCommand(
    name="editor",
    argument=click.argument("executable", type=click.STRING),
    help=_help.app_config_editor,
    short_help=f"Default text editor. Current: {AppConfig().get('settings', 'editor', default='not-set')}",
    syntax=_help.app_config_editor_syntax,
    config_keys=["settings"],
)


for cmd in [
    note_history,
    timezone,
    editor,
    week_start,
    quiet_start,
    timer_add_min,
    system_command_shell,
]:
    __cmd = create_settings_fn(cmd=cmd, config_keys=cmd.config_keys)
    update_general_settings.add_command(__cmd)

mouse_support = SettingsCommand(
    name="mouse_support",
    argument=value_arg,
    help=_help.app_config_mouse_support,
    short_help="Control mouse support in cmd bq:query",
    syntax=_help.app_config_mouse_support_syntax,
    config_keys=["settings", "query"],
)


save_txt = SettingsCommand(
    name="save_txt",
    argument=value_arg,
    help=_help.app_config_save_txt,
    short_help="Queries using bq:query save the rendered table to a .txt in appdir.",
    syntax=_help.app_config_save_txt_syntax,
    config_keys=["settings", "query"],
)


save_query_info = SettingsCommand(
    name="save_query_info",
    argument=value_arg,
    help=_help.app_config_save_query_info,
    short_help="Include query info when saving to file.",
    syntax=_help.app_config_save_query_info_syntax,
    config_keys=["settings", "query"],
)


save_svg = SettingsCommand(
    name="save_svg",
    argument=value_arg,
    help=_help.app_config_save_svg,
    short_help="Queries using bq:query save the rendered table to an svg in appdir.",
    syntax=_help.app_config_save_svg_syntax,
    config_keys=["settings", "query"],
)


hide_table_render = SettingsCommand(
    name="hide_table_render",
    argument=value_arg,
    help=_help.app_config_hide_table_render,
    short_help="If save_text | save_svg, enable/disable table render in console.",
    syntax=_help.app_config_hide_table_render_syntax,
    config_keys=["settings", "query"],
)


for cmd in [mouse_support, save_txt, save_query_info, save_svg, hide_table_render]:
    __cmd = create_settings_fn(cmd=cmd, config_keys=cmd.config_keys)
    update_query_settings.add_command(__cmd)


if (
    AppConfig().get("client", "credentials_source")
    == CredentialsSource.from_service_account_key
):

    @update_general_settings.command(
        cls=FmtRichCommand,
        name="stay_logged_in",
        no_args_is_help=True,
        help=_help.app_config_stay_logged_in,
        short_help="Save login password.",
        syntax=_help.app_config_stay_logged_in_syntax,
    )
    @utils._handle_keyboard_interrupt(
        callback=lambda: rprint(markup.dimmed("Did not change settings.")),
    )
    @value_arg
    def stay_logged_in(value: bool) -> None:
        from lightlike.app.auth import _AuthSession

        _AuthSession().stay_logged_in(value)
