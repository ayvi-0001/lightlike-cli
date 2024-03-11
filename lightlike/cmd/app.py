import os
import typing as t
from dataclasses import dataclass

import rich_click as click
from more_itertools import nth, one
from pytz import all_timezones
from rich import get_console

from lightlike.app import _pass, render, shell_complete, threads, validate
from lightlike.app.cache import EntryAppData, TomlCache
from lightlike.app.client import get_client
from lightlike.app.config import AppConfig
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _help
from lightlike.internal import utils
from lightlike.internal.enums import CredentialsSource
from lightlike.lib.third_party import click_repl

if t.TYPE_CHECKING:
    from rich.console import Console

__all__: t.Sequence[str] = ("app",)


P = t.ParamSpec("P")

get_console().log(f"[log.main]Loading command group: {__name__}")


@click.group(
    cls=AliasedRichGroup,
    name="app",
    short_help="CLI internal settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def app(debug: bool) -> None:
    """CLI internal settings & commands."""


@app.command(
    cls=_RichCommand,
    name="exit",
    short_help="Exit the REPL.",
    context_settings=dict(allow_extra_args=True),
)
@click.pass_context
def exit_(ctx: click.Context) -> None:
    """Exit the REPL."""
    click_repl.exit()


@app.command(
    cls=_RichCommand,
    name="clear",
    short_help="Clear the screen and move the cursor to 'home' position.",
)
@click.option(
    "-cs",
    "--clear-scrollback",
    is_flag=True,
    default=False,
    show_default=True,
    help="Clear scrollback. (only works for terminals that support the clear command)",
)
@_pass.console
def clear_(console: "Console", clear_scrollback: bool) -> None:
    """Clear the screen and move the cursor to 'home' position."""
    console.clear()
    if clear_scrollback:
        os.system("clear")


@app.command(cls=_RichCommand, name="cls", hidden=True)
@click.option(
    "-cs",
    "--clear-scrollback",
    is_flag=True,
    default=False,
    show_default=True,
    help="Clear scrollback. (only works for terminals that support the clear command)",
)
@_pass.console
def cls_(console: "Console", clear_scrollback: bool) -> None:
    """Clear the screen and move the cursor to 'home' position."""
    console.clear()
    if clear_scrollback:
        os.system("clear")


@app.group(
    cls=AliasedRichGroup,
    name="dev",
    short_help="Dev options.",
)
def app_dev() -> None:
    """Dev options."""


@app_dev.command(
    cls=_RichCommand,
    name="config",
    short_help="Launch CLI configuration file.",
)
@_pass.console
@utils._nl_start()
def app_launch_config(console: "Console") -> None:
    """Launch CLI configuration file."""
    path = AppConfig().path.resolve()
    editor = AppConfig().get("settings", "editor", default=None) or None
    click.edit(
        editor=editor,
        filename=f"{path}",
        extension=".toml",
        require_save=False,
    )
    console.print(
        "[b][green]Launching[/b][/green] [repr.url][link={uri}]"
        "{path}[/link][/repr.url]{editor}".format(
            uri=path.as_uri(),
            path=path.as_posix(),
            editor=f" through editor [code]{editor}[/code]." if editor else ".",
        )
    )


@app_dev.command(
    cls=_RichCommand,
    name="dir",
    options_metavar="[LAUNCH OPTION]",
    help=_help.app_dir,
    short_help="Launch CLI directory.",
    context_settings=dict(
        obj=dict(syntax=_help.app_dir_syntax),
    ),
)
@click.option(
    "-s",
    "--start",
    "launch",
    is_flag=True,
    type=click.STRING,
    show_default=True,
    flag_value="start",
    default=True,
    help="Launches app dir in explorer.",
)
@click.option(
    "-e",
    "--editor",
    "launch",
    is_flag=True,
    type=click.STRING,
    show_default=True,
    flag_value="editor",
    default=False,
    help="Launches app dir in default text-editor.",
)
@_pass.console
@utils._nl_start()
def app_dir(console: "Console", launch: t.Literal["start", "editor"]) -> None:
    from lightlike.__about__ import __appdir__

    uri = __appdir__.as_uri()
    path = __appdir__.as_posix()

    match launch:
        case "start":
            click.launch(path)
            console.print(
                "[b][green]Launching[/b][/green] [repr.url][link={uri}]"
                "{path}[/link][/repr.url].".format(uri=uri, path=path)
            )
        case "editor":
            editor = AppConfig().get("settings", "editor", default=None) or None
            click.edit(editor=editor, filename=path, require_save=False)
            console.print(
                "[b][green]Launching[/b][/green] [repr.url][link={uri}]"
                "{path}[/link][/repr.url]{editor}".format(
                    uri=uri,
                    path=path,
                    editor=(
                        f" through editor [code]{editor}[/code]." if editor else "."
                    ),
                )
            )


@app_dev.command(
    cls=_RichCommand,
    name="show-console",
    short_help="Inspect global console.",
)
@_pass.console
@utils._nl_start()
def app_dev_show_console(console: "Console") -> None:
    """Inspect global console."""
    from rich._inspect import Inspect

    _inspect = Inspect(
        console,
        help=False,
        methods=False,
        docs=True,
        private=False,
        dunder=False,
        sort=True,
        all=False,
        value=True,
    )

    console.print(
        _inspect,
        width=console.width,
        justify="center",
        new_line_start=True,
    )


@app.group(
    cls=AliasedRichGroup,
    name="test",
    short_help="Test functions.",
)
def app_dev_test() -> None:
    """Test functions."""


@app_dev_test.command(
    cls=_RichCommand,
    name="date-parse",
    help=_help.app_test_dateparser,
    short_help="Test the dateparser function.",
    context_settings=dict(
        obj=dict(syntax=_help.app_test_dateparser_syntax),
    ),
)
@click.argument(
    "date",
    type=click.STRING,
    required=False,
    shell_complete=shell_complete.time,
)
@_pass.console
@utils._nl_start()
def app_test_date_parse(console: "Console", date: str) -> None:
    try:
        if date:
            date_local = PromptFactory._parse_date(date)
        else:
            date_local = PromptFactory.prompt_for_date("(date)")

        if date_local:
            console.print(date_local)

    except click.UsageError:
        console.print("[red]Failed to parse date")


@app_dev.command(
    cls=_RichCommand,
    name="run-bq",
    help=_help.app_run_bq,
    short_help="Run BigQuery scripts. Tables only built if missing.",
    context_settings=dict(
        obj=dict(syntax=_help.app_run_bq_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Canceled Build.\n")
)
def run_bq() -> None:
    from lightlike.internal.bq_resources import build

    mapping = AppConfig().get("bigquery")
    bq_patterns = {
        "${DATASET.NAME}": mapping["dataset"],
        "${TABLES.TIMESHEET}": mapping["timesheet"],
        "${TABLES.PROJECTS}": mapping["projects"],
        "${TIMEZONE}": f"{AppConfig().tz}",
    }

    build.run(client=get_client(), patterns=bq_patterns)


@app.group(
    cls=AliasedRichGroup,
    name="sync",
    chain=True,
    help=_help.app_sync,
    short_help="Sync local files.",
    context_settings=dict(
        obj=dict(syntax=_help.app_sync_syntax),
    ),
)
def app_sync() -> None: ...


@app_sync.command(
    cls=_RichCommand,
    name="appdata",
    help=_help.app_sync,
    short_help="Sync local projects & notes.",
    context_settings=dict(
        obj=dict(syntax=_help.app_sync_syntax),
    ),
)
@_pass.appdata
def app_sync_appdata(appdata: EntryAppData) -> dict[str, EntryAppData]:
    return {"appdata": appdata}


@app_sync.command(
    cls=_RichCommand,
    name="cache",
    help=_help.app_sync,
    short_help="Sync local cache.toml",
    context_settings=dict(
        obj=dict(syntax=_help.app_sync_syntax),
    ),
)
@_pass.cache
def app_sync_cache(cache: TomlCache) -> dict[str, TomlCache]:
    return {"cache": cache}


@app_sync.result_callback()
@_pass.console
@utils._nl_start()
def _app_sync_callback(console: "Console", *args: P.args, **kwargs: P.kwargs) -> None:
    subcommands = t.cast(t.Sequence[dict[str, TomlCache | EntryAppData]], args[0])
    if subcommands:
        with console.status(status="[status.message]Syncing cache") as status:
            for cmd in subcommands:
                k, v = one(cmd.items())
                if "appdata" in k and isinstance(v, EntryAppData):
                    status.update("[status.message]Syncing appdata")
                    v.update()
                elif "cache" in k and isinstance(v, TomlCache):
                    status.update("[status.message]Syncing cache")
                    v._sync_cache()


@app.group(
    cls=AliasedRichGroup,
    name="settings",
    help=_help.app_settings,
    short_help="Config settings.",
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_syntax),
    ),
)
def app_settings() -> None: ...


@app_settings.command(
    cls=_RichCommand,
    name="show",
    help=_help.app_settings,
    short_help="View current configuration settings.",
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_syntax),
    ),
)
@click.option("-j", "--json", "json_", is_flag=True, hidden=True)
def settings_show(json_: bool) -> None:
    settings = AppConfig().general_settings | AppConfig().query_settings

    if json_:
        from rich import print_json

        print_json(data=settings, indent=4)

    else:
        render.new_console_print(render.mappings_list_to_rich_table([settings]))


@app_settings.group(
    cls=AliasedRichGroup,
    name="update",
    help=_help.app_settings,
    short_help="Update current settings.",
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_syntax),
    ),
)
def update_settings() -> None: ...


@update_settings.result_callback()
@utils._nl_start()
def update_settings_callback(*args: P.args, **kwargs: P.kwargs) -> None: ...


@update_settings.group(
    cls=AliasedRichGroup,
    name="general",
    chain=True,
    help=_help.app_settings,
    short_help="General CLI settings.",
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_syntax),
    ),
)
def update_general_settings() -> None: ...


@update_settings.group(
    cls=AliasedRichGroup,
    name="query",
    chain=True,
    help=_help.app_settings,
    short_help="Settings for bq:query.",
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_syntax),
    ),
)
def update_query_settings() -> None: ...


_thread_sequence: t.TypeAlias = t.Sequence[
    tuple[t.Callable[[t.Any | None], t.Any], t.Any]
]


@dataclass()
class SettingsCommand:
    name: str
    argument: t.Callable[[click.RichCommand], click.RichCommand]
    help: str | None = None
    short_help: str | None = None
    callback_fn: t.Optional[t.Callable[..., t.Any]] = None
    callback_threads: t.Optional[_thread_sequence] = None
    context_settings: t.Optional[dict[str, t.Any]] = None
    no_args_is_help: bool = True


def create_settings_fn(
    cmd: SettingsCommand, config_keys: t.Sequence[str]
) -> click.RichCommand:
    @click.command(
        cls=_RichCommand,
        name=cmd.name,
        no_args_is_help=cmd.no_args_is_help,
        help=cmd.help or cmd.short_help,
        short_help=cmd.short_help,
        context_settings=cmd.context_settings,
    )
    @utils._handle_keyboard_interrupt(
        callback=lambda: get_console().print(
            f"[d]Did not update {cmd.name}.\n",
        )
    )
    @_pass.console
    @click.pass_context
    def __cmd(
        ctx: click.Context, console: "Console", *args: P.args, **kwargs: P.kwargs
    ) -> None:
        val = nth(one(kwargs.items()), 1)

        if val == AppConfig().get(*config_keys).get(cmd.name):
            console.print(f"[d]{cmd.name} is already set to {val} - Nothing happened.")
            return

        with AppConfig().update() as config:
            c = config._reduce_keys(*config_keys, sequence=config)
            c["".join(c if c.isalnum() else "_" for c in cmd.name)] = val

        utils.print_updated_val(key=cmd.name, val=val, console=console)

        if cmd.callback_fn:
            cmd.callback_fn(locals())
        if cmd.callback_threads:
            for thread, kwargs in cmd.callback_threads:
                threads.spawn(ctx=ctx, fn=thread, kwargs=kwargs)

    return cmd.argument(__cmd)


is_billable = SettingsCommand(
    name="is_billable",
    argument=click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    ),
    help=_help.app_settings_is_billable,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_is_billable_syntax),
    ),
    short_help="Default billable flag for new time entries.",
)

note_history = SettingsCommand(
    name="note_history",
    argument=click.argument("days", type=click.INT, required=True),
    help=_help.app_settings_note_history,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_note_history_syntax),
    ),
    short_help="Days to store note history.",
    callback_threads=[(EntryAppData().update, None)],
)

timezone = SettingsCommand(
    name="timezone",
    argument=click.argument(
        "timezone",
        type=click.STRING,
        callback=validate.callbacks.timezone,
        shell_complete=shell_complete.Param("timezone", all_timezones).string,
    ),
    help=_help.app_settings_timezone,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_timezone_syntax),
    ),
    short_help="Timezone used for all date/time conversions.",
    callback_fn=lambda l: get_console().print(
        "[bold italic underline]"
        "**Restart for settings to take effect**"
        "[/bold italic underline]\n"
        "You will also need to run [code.command]app[/code.command]"
        ":[code.command]dev[/code.command]"
        ":[code.command]run-bq[/code.command] "
        "to rebuild procedures using this new timezone."
    ),
)

week_start = SettingsCommand(
    name="week_start",
    argument=click.argument(
        "dayofweek",
        type=click.STRING,
        callback=validate.callbacks.weekstart,
        shell_complete=shell_complete.Param(
            "dayofweek",
            ["Sunday", "Monday"],
        ).string,
    ),
    help=_help.app_settings_week_start,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_week_start_syntax),
    ),
    short_help="Update week start for `--current-week` flags.",
)

editor = SettingsCommand(
    name="editor",
    argument=click.argument("executable", type=click.STRING, required=True),
    help=_help.app_settings_editor,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_editor_syntax),
    ),
    short_help="Timezone used for all date/time conversions.",
)

mouse_support = SettingsCommand(
    name="mouse_support",
    argument=click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    ),
    help=_help.app_settings_mouse_support,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_mouse_support_syntax),
    ),
    short_help="Control mouse support in cmd bq:query",
)

save_txt = SettingsCommand(
    name="save_txt",
    argument=click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    ),
    help=_help.app_settings_save_txt,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_save_txt_syntax),
    ),
    short_help="Queries using bq:query save the rendered table to a .txt in appdir.",
)

save_query_info = SettingsCommand(
    name="save_query_info",
    argument=click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    ),
    help=_help.app_settings_save_query_info,
    short_help="Include query info when saving to file.",
    context_settings=dict(
        obj=dict(
            syntax=_help.app_settings_save_query_info_syntax,
        )
    ),
)

save_svg = SettingsCommand(
    name="save_svg",
    argument=click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    ),
    help=_help.app_settings_save_svg,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_save_svg_syntax),
    ),
    short_help="Queries using bq:query save the rendered table to an svg in appdir.",
)

hide_table_render = SettingsCommand(
    name="hide_table_render",
    argument=click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    ),
    help=_help.app_settings_hide_table_render,
    context_settings=dict(
        obj=dict(syntax=_help.app_settings_hide_table_render_syntax),
    ),
    short_help="If save_text | save_svg, enable/disable table render in console.",
)

for cmd in [is_billable, note_history, timezone, editor, week_start]:
    __cmd = create_settings_fn(cmd=cmd, config_keys=["settings"])
    update_general_settings.add_command(__cmd)

for cmd in [mouse_support, save_txt, save_query_info, save_svg, hide_table_render]:
    __cmd = create_settings_fn(cmd=cmd, config_keys=["settings", "query"])
    update_query_settings.add_command(__cmd)


if AppConfig().credentials_source == CredentialsSource.from_service_account_key:

    @update_general_settings.command(
        cls=_RichCommand,
        name="stay_logged_in",
        no_args_is_help=True,
        help=_help.app_settings_stay_logged_in,
        context_settings=dict(
            obj=dict(syntax=_help.app_settings_stay_logged_in_syntax),
        ),
        short_help="Save login password.",
    )
    @utils._handle_keyboard_interrupt(
        callback=lambda: get_console().print("\n[d]Did not change settings.\n")
    )
    @click.argument(
        "value",
        type=click.BOOL,
        shell_complete=shell_complete.Param("value").bool,
    )
    def stay_logged_in(value: bool) -> None:
        from lightlike.app.auth import _AuthSession

        _AuthSession().stay_logged_in(value)
