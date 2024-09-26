import os
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from functools import partial

import click
import pytz
import rtoml
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
from lightlike.cmd.app.commands import _start_command
from lightlike.internal import markup, utils
from lightlike.internal.enums import CredentialsSource

__all__: t.Sequence[str] = ("edit", "list_", "open_", "set_")


P = t.ParamSpec("P")


@click.command(
    cls=FormattedCommand,
    name="edit",
    short_help="Edit config using the default text editor.",
    syntax=Syntax(
        code="""\
        $ app config edit
        $ a c e\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@_pass.console
def edit(console: Console) -> None:
    """Edit the config file located in the users home directory using the default text editor."""
    path: str = f"{__config__.resolve().as_posix()}"
    default_editor = os.environ.get("EDITOR")
    editor: str | None = (
        AppConfig().get("settings", "editor", default=default_editor) or None
    )

    if editor:
        click.edit(editor=editor, filename=path, extension=".toml", require_save=False)
        console.print("$", editor, markup.link(path, path))
    else:
        click.launch(path)
        console.print(markup.dimmed("EDITOR not set"))
        console.print(f"$ {_start_command(path)}")


@click.command(
    cls=FormattedCommand,
    name="list",
    short_help="Show current config values.",
    syntax=Syntax(
        code="""\
        $ app config list
        $ a c l
    
        $ app config list --json
        $ a c l -j\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@click.argument(
    "keys",
    type=click.STRING,
    required=False,
    default=None,
    callback=None,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=None,
)
@click.option(
    "-j",
    "--json",
    "json_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help=None,
    required=False,
    hidden=True,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.console
def list_(console: Console, keys: t.Sequence[str], json_: bool) -> None:
    """Show current config file in terminal."""
    if keys:
        content = AppConfig().get(*keys)
    else:
        content = AppConfig().config

    if json_:
        console.print_json(data=content, default=str, indent=4)
    else:
        syntax: Syntax = Syntax(
            rtoml.dumps(content),
            lexer="toml",
            line_numbers=True,
            background_color="#131310",
        )
        console.print(syntax)


@click.command(
    cls=FormattedCommand,
    name="open",
    short_help="Open location of config file.",
    syntax=Syntax(
        code="""\
        $ app config open
        $ a c o\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@_pass.console
def open_(console: Console) -> None:
    """Open location of config file."""
    path: str = f"{__config__.resolve()}"
    click.launch(path, locate=True)
    console.print(f"$ {_start_command(path, locate=True)}")


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
    @utils.handle_keyboard_interrupt(
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
    name="note-history",
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
    name="quiet-start",
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

    if setting was set to ["bash", "-c"] and the command is `ls`,
    then it will be executed as
    $ bash -c "ls"

    When setting value, enclose list in single quotes, and use double quotes for string values.
    """,
    syntax=Syntax(
        code="""\
        # example setting config key.
        $ app config set general shell '["bash", "-c"]'
        
        # login to shell and read rc file.
        $ app config set general shell '["bash", "--rcfile", "~/.bashrc", "-ic", "-c"]'\
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
    name="week-start",
    argument=click.argument(
        "dayofweek",
        type=click.Choice(["Sunday", "Monday"]),
        callback=validate.callbacks.weekstart,
    ),
    short_help="Update week start for option --current-week / -cw.",
    syntax=Syntax(
        code="$ app config set week-start Sunday",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings"],
)


timer_add_min = SettingsCommand(
    name="timer-add-min",
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
        $ app config set general editor code # vscode
        $ app config set general editor hx # helix
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
    name="mouse-support",
    argument=value_arg,
    help="Controls mouse support in bq:query.",
    short_help="Control mouse support in cmd bq:query",
    syntax=Syntax(
        code="$ app config set query mouse-support true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


save_txt = SettingsCommand(
    name="save-txt",
    argument=value_arg,
    help="Queries using bq:query will save the rendered result to a [code].txt[/code] file in the app directory.",
    short_help="Queries using bq:query save the rendered table to a .txt in appdir.",
    syntax=Syntax(
        code="$ app config set query save-txt true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


save_query_info = SettingsCommand(
    name="save-query-info",
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
        code="$ app config set query save-query-info true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


save_svg = SettingsCommand(
    name="save-svg",
    argument=value_arg,
    help="Queries using bq:query will save the rendered result to an [code].svg[/code] file in the app directory.",
    short_help="Queries using bq:query save the rendered table to an svg in appdir.",
    syntax=Syntax(
        code="$ app config set query save-svg true",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
    config_keys=["settings", "query"],
)


hide_table_render = SettingsCommand(
    name="hide-table-render",
    argument=value_arg,
    help="""
    If save_text or save-svg is enabled, enable/disable table render in console.

    If save_text or save-svg is disabled, this option does not have any affect.
    """,
    short_help="If save_text | save-svg, enable/disable table render in console.",
    syntax=Syntax(
        code="$ app config set query hide-table-render true",
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
    AppConfig().get("client", "credentials-source")
    == CredentialsSource.from_service_account_key
):

    @update_general_settings.command(
        cls=FormattedCommand,
        name="stay-logged-in",
        no_args_is_help=True,
        help="""
        Save login password.

        This setting is only visible if the client is authenticated using a service-account key.
        It's not recommended to leave this setting on, as the password and encryped key are stored in the same place.
        """,
        short_help="Save login password.",
        syntax=Syntax(
            code="$ app config set general stay-logged-in true",
            lexer="fishshell",
            dedent=True,
            line_numbers=True,
            background_color="#131310",
        ),
    )
    @utils.handle_keyboard_interrupt(
        callback=lambda: rprint(markup.dimmed("Did not change settings.")),
    )
    @value_arg
    def stay_logged_in(value: bool) -> None:
        from lightlike.client import AuthPromptSession
        from lightlike.client._credentials import service_account_key_flow

        if value is True:
            stay_logged_in = AppConfig().stay_logged_in

            if not stay_logged_in:
                rprint("Enter current password.")
                input_password = AuthPromptSession().prompt_password()
                encrypted_key, salt = service_account_key_flow(AppConfig())

                with suppress(UnboundLocalError):
                    AuthPromptSession().decrypt_key(
                        salt=salt,
                        encrypted_key=encrypted_key,
                        saved_password=AppConfig().saved_password,
                        stay_logged_in=AppConfig().stay_logged_in,
                        input_password=input_password,
                        retry=False,
                        saved_credentials_failed=partial(
                            AppConfig()._update_user_credentials,
                            password="null",
                            stay_logged_in=False,
                        ),
                    )
                    AppConfig()._update_user_credentials(
                        password=input_password, stay_logged_in=value
                    )
                    rprint("Set", markup.scope_key("stay-logged-in"), "to", value)

            else:
                rprint(
                    markup.dimmed(f"`stay-logged-in` is already set to `{value}`,"),
                    markup.dimmed("nothing happened."),
                )

        elif value is False:
            if not AppConfig().stay_logged_in:
                rprint(markup.dimmed("Setting is already off."))

            else:
                AppConfig()._update_user_credentials(
                    password="null", stay_logged_in=False
                )
                rprint("Set", markup.scope_key("stay-logged-in"), "to", False)
