import typing as t
from dataclasses import dataclass

import click
import pytz
from more_itertools import nth, one
from rich import print as rprint
from rich.console import Console
from rich.syntax import Syntax

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import shell_complete, threads, validate
from lightlike.app.cache import TimeEntryAppData
from lightlike.app.config import AppConfig
from lightlike.app.core import AliasedGroup, FormattedCommand
from lightlike.cmd import _pass
from lightlike.internal import markup, utils
from lightlike.internal.enums import CredentialsSource

__all__: t.Sequence[str] = ("open_", "show", "set_")


P = t.ParamSpec("P")


@click.command(
    cls=FormattedCommand,
    name="open",
    short_help="Open config using the default text editor.",
    syntax=Syntax(
        code="$ app config open",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@_pass.console
def open_(console: Console) -> None:
    """Open the config file located in the users home directory using the default text editor."""
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
    cls=FormattedCommand,
    name="show",
    short_help="Show config values.",
    syntax=Syntax(
        code="""\
        $ app config show
        $ a c s
    
        $ app config show --json
        $ a c s -j\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@_pass.console
def show(console: Console) -> None:
    """Show config file in terminal."""
    console.print(
        Syntax(
            __config__.read_text(),
            lexer="toml",
            line_numbers=True,
            background_color="#131310",
        )
    )


@click.group(
    cls=AliasedGroup,
    name="set",
    short_help="Set config values.",
)
def set_() -> None:
    """
    [b]General Settings[/b] Configure behaviour of timer function, authorization, default values.
    [b]Query Settings[/b] Configure behaviour of the bq:query command.
    """


@set_.group(
    cls=AliasedGroup,
    name="general",
    chain=True,
    short_help="General cli settings.",
)
def update_general_settings() -> None:
    """Configure behaviour of timer function, authorization, default values."""


@set_.group(
    cls=AliasedGroup,
    name="query",
    chain=True,
    short_help="bq:query settings.",
)
def update_query_settings() -> None:
    """Configure behaviour of the bq:query command."""


@dataclass()
class SettingsCommand:
    name: str
    config_keys: list[str]
    argument: t.Callable[[click.Command], click.Command]
    help: t.Callable[..., str] | str | None = None
    short_help: t.Callable[..., str] | str | None = None
    callback_fn: t.Callable[..., t.Any] | None = None
    callback_threads: (
        t.Sequence[tuple[t.Callable[[t.Any | None], t.Any], t.Any]] | None
    ) = None
    context_settings: dict[str, t.Any] | None = None
    syntax: "Syntax | None" = None
    no_args_is_help: bool = True


value_arg = click.argument(
    "value",
    type=click.BOOL,
    shell_complete=shell_complete.Param("value").bool,
)


def create_settings_fn(
    cmd: SettingsCommand, config_keys: t.Sequence[str]
) -> click.Command:
    @click.command(
        cls=FormattedCommand,
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
        ctx: click.Context,
        /,
        console: Console,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        val = nth(one(kwargs.items()), 1)

        if val == AppConfig().get(*config_keys, cmd.name):
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
    help="""
    Days to store note history.

    This settings affects how many days to store notes used by option --note / -n for autocompletions.
    e.g. If days = 30, any notes older than 30 days won't appear in autocompletions.
    Default is set to 90 days.
    """,
    short_help="Days to store note history.",
    syntax=Syntax(
        code="$ app config set general note-history 365",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
    help="""
    Shell to use when running external commands.

    e.g.
    unix: ["sh", "-c"] / ["bash", "-c"]
    windows: ["cmd", "/C"]

    When setting value, enclose list in single quotes, and use double quotes for string values.
    """,
    syntax=Syntax(
        code="""\
        # if setting was set to ["bash", "-c"]
        # and the command is `ls`
        # then it will be executed as
        $ bash -c "ls"

        # example setting config key
        $ app config set general shell '["bash", "-c"]'\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    short_help="Shell to use when running external commands.",
    config_keys=["system-command"],
)


def timezone_setting_callback(_locals: dict[str, t.Any]) -> None:
    import lightlike.app.cursor

    tz = pytz.timezone(_locals["kwargs"].get("timezone"))
    lightlike.app.cursor.TIMEZONE = tz

    with AppConfig().rw() as config:
        config["settings"].update(timezone=tz)

    rprint(
        "[b]You will also need to run app:run-bq to",
        "rebuild procedures using this new timezone.",
    )


timezone = SettingsCommand(
    name="timezone",
    argument=click.argument(
        "timezone",
        type=click.STRING,
        callback=validate.callbacks._timezone,
        shell_complete=lambda c, p, i: [
            t for t in pytz.all_timezones if i in t.lower()
        ],
    ),
    help="""
    Timezone used for all date/time conversions.

    If this value is updated, run app:run-bq to rebuild procedures in BigQuery using the new timezone.
    """,
    short_help="Timezone used for all date/time conversions.",
    syntax=Syntax(
        code="$ app config set general timezone UTC",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
    short_help="Update week start for option --current-week / -cw.",
    syntax=Syntax(
        code="$ app config set week_start Sunday",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
    help="Editor should be the full path to the executable, but the regular operating system search path is used for finding the executable.",
    short_help=f"Default text editor. Current: {AppConfig().get('settings', 'editor', default='not-set')}",
    syntax=Syntax(
        code="""\
        $ app config set general editor code
    
        $ app config set general editor vim\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings"],
)


for cmd in t.cast(
    list[SettingsCommand],
    [
        note_history,
        timezone,
        editor,
        week_start,
        quiet_start,
        timer_add_min,
        system_command_shell,
    ],
):
    __cmd = create_settings_fn(cmd=cmd, config_keys=cmd.config_keys)
    update_general_settings.add_command(__cmd)


mouse_support = SettingsCommand(
    name="mouse_support",
    argument=value_arg,
    help="Controls mouse support in bq:query.",
    short_help="Control mouse support in cmd bq:query",
    syntax=Syntax(
        code="$ app config set query mouse_support true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


save_txt = SettingsCommand(
    name="save_txt",
    argument=value_arg,
    help="Queries using bq:query will save the rendered result to a [code].txt[/code] file in the app directory.",
    short_help="Queries using bq:query save the rendered table to a .txt in appdir.",
    syntax=Syntax(
        code="$ app config set query save_txt true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


save_query_info = SettingsCommand(
    name="save_query_info",
    argument=value_arg,
    help="""
    Include query info when saving to file.

    Query info:
        - query string
        - resource url
        - elapsed time
        - cache hit/output
        - statement type
        - slot millis
        - bytes processed/billed
        - row count
        - dml stats
    """,
    short_help="Include query info when saving to file.",
    syntax=Syntax(
        code="$ app config set query save_query_info true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


save_svg = SettingsCommand(
    name="save_svg",
    argument=value_arg,
    help="Queries using bq:query will save the rendered result to an [code].svg[/code] file in the app directory.",
    short_help="Queries using bq:query save the rendered table to an svg in appdir.",
    syntax=Syntax(
        code="$ app config set query save_svg true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


hide_table_render = SettingsCommand(
    name="hide_table_render",
    argument=value_arg,
    help="""
    If save_text or save_svg is enabled, enable/disable table render in console.

    If save_text or save_svg is disabled, this option does not have any affect.
    """,
    short_help="If save_text | save_svg, enable/disable table render in console.",
    syntax=Syntax(
        code="$ app config set query hide_table_render true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
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
        cls=FormattedCommand,
        name="stay_logged_in",
        no_args_is_help=True,
        help="""
        Save login password.

        This setting is only visible if the client is authenticated using a service-account key.
        It's not recommended to leave this setting on, as the password and encryped key are stored in the same place.
        """,
        short_help="Save login password.",
        syntax=Syntax(
            code="$ app config set general stay_logged_in true",
            lexer="fishshell",
            dedent=True,
            line_numbers=True,
            background_color="#131310",
        ),
    )
    @utils._handle_keyboard_interrupt(
        callback=lambda: rprint(markup.dimmed("Did not change settings.")),
    )
    @value_arg
    def stay_logged_in(value: bool) -> None:
        from lightlike.app.auth import AuthPromptSession
        from lightlike.app.client import service_account_key_flow

        if value is True:
            stay_logged_in = AppConfig().get("user", "stay_logged_in")

            if not stay_logged_in:
                rprint("Enter current password.")
                current = AuthPromptSession().prompt_password()
                encrypted_key, salt = service_account_key_flow()

                try:
                    AuthPromptSession().authenticate(
                        salt=salt,
                        encrypted_key=encrypted_key,
                        password=current,
                        retry=False,
                    )
                    AppConfig()._update_user_credentials(
                        password=current, stay_logged_in=value
                    )
                    rprint("Set", markup.scope_key("stay_logged_in"), "to", value)
                except UnboundLocalError:
                    ...

            else:
                rprint(
                    markup.dimmed(f"`stay_logged_in` is already set to `{value}`,"),
                    markup.dimmed("nothing happened."),
                )

        elif value is False:
            if not AppConfig().get("user", "stay_logged_in"):
                rprint(markup.dimmed("Setting is already off."))

            else:
                AppConfig()._update_user_credentials(
                    password="null", stay_logged_in=False
                )
                rprint("Set", markup.scope_key("stay_logged_in"), "to", False)
