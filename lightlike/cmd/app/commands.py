import typing as t
from os import getenv
from pathlib import Path

import click
from rich import print as rprint
from rich.console import Console
from rich.syntax import Syntax

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import _questionary
from lightlike.app.cache import TimeEntryAppData, TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.app.core import FormattedCommand, LazyAliasedGroup
from lightlike.client import CliQueryRoutines, get_client
from lightlike.cmd import _pass
from lightlike.internal import markup, utils

__all__: t.Sequence[str] = (
    "config",
    "dir_",
    "run_bq",
    "inspect_console",
    "sync",
    "test",
)


P = t.ParamSpec("P")


if LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"):
    __config = f"/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli/config.toml"
    __appdir = f"/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli"
else:
    __config = __config__.as_posix()
    __appdir = __appdir__.as_posix()


@click.group(
    name="config",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "edit": "lightlike.cmd.app.config:edit",
        "set": "lightlike.cmd.app.config:set_",
        "list": "lightlike.cmd.app.config:list_",
    },
    short_help=f"Cli config file and settings. {__config}",
    syntax=Syntax(
        code="""\
        $ app config edit
        $ a c e
    
        $ app config list
        $ a c l
    
        $ app config set
        $ a c u\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
def config() -> None:
    """
    View/Update cli configuration settings.

    app:config:edit:
        open the config file located in the users home directory using the default text editor.

    app:config:list:
        view config file in terminal.
        this list does not include everything, only the keys that can be updated through the cli.

    app:config:set:
        [b]general settings[/b]:
            configure time entry functions
            login (if auth through a service-account)
            misc. behaviour (e.g. default text-editor).
        [b]query settings[/b]:
            configure behaviour for bq:query.
    """


@click.command(
    cls=FormattedCommand,
    name="dir",
    options_metavar="[LAUNCH OPTION]",
    short_help=f"Open cli dir: {__appdir}",
    syntax=Syntax(
        code="""\
        $ app dir
    
        $ app dir --editor\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@click.option(
    "--start/--editor",
    show_default=False,
    is_flag=True,
    flag_value=False,
    multiple=False,
    type=click.BOOL,
    help="Default opens with cmd `start`.",
    required=False,
    default=True,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.console
def dir_(console: Console, start: bool) -> None:
    """
    Open cli directory.

        --start / -s:
            default option.
            open app directory with the system command [code]start[/code].

        --editor / -e:
            open the app directory using the configured text-editor.
            configure text-editor with app:config:set:general:editor.
    """
    uri = __appdir__.as_uri()
    path = __appdir__.as_posix()

    if start:
        click.launch(path)
        console.print("$ start", markup.link(uri, uri))
    else:
        editor = AppConfig().get("settings", "editor", default=None) or None
        if editor:
            click.edit(editor=editor, filename=path, require_save=False)
            console.print("$", editor, markup.link(uri, uri))
        else:
            console.print("editor not set.")
            click.launch(path)
            console.print("$ start", markup.link(uri, uri))


@click.command(
    cls=FormattedCommand,
    name="run-bq",
    short_help="Run BigQuery scripts. Tables only built if missing.",
    syntax=Syntax(
        code="$ app run-bq",
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Canceled Build.")),
)
@click.option(
    "-y",
    "--yes",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Accept all prompts",
    required=False,
    hidden=True,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
def run_bq(yes: bool) -> None:
    """
    Run BigQuery scripts.

    Executes all necessary scripts in BigQuery for this cli to run. Table's are only built if they do not exist.
    """
    from lightlike.client import provision_bigquery_resources

    provision_bigquery_resources(client=get_client(), force=True, yes=yes)


@click.command(
    cls=FormattedCommand,
    name="show-console",
    hidden=True,
    short_help="Inspect global console.",
)
@_pass.console
def inspect_console(console: Console) -> None:
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


@click.command(
    cls=FormattedCommand,
    name="sync",
    short_help="Sync local files.",
    syntax=Syntax(
        code="""\
        $ app sync --appdata
        $ a s -a

        $ app sync --cache
        $ a s -c

        $ app sync --appdata --cache
        $ a s -ac\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Canceled Sync.")),
)
@click.option("-a", "--appdata", is_flag=True)
@click.option("-c", "--cache", is_flag=True)
@click.option("-q", "--quiet", is_flag=True, default=False, show_default=True)
@_pass.appdata
@_pass.cache
@_pass.console
def sync(
    console: Console,
    _cache: TimeEntryCache,
    _appdata: TimeEntryAppData,
    appdata: bool,
    cache: bool,
    quiet: bool,
) -> None:
    """
    Syncs local files for time entry data, projects, and cache.

    These can be found in the app directory using the app:dir command.

    These tables should only ever be altered through the procedures in this cli.
    If the local files are out of sync with BigQuery, or if logging in from a new location, can use this command to re-sync them.
    """
    if quiet:
        _appdata.sync()
        _cache.sync()
    else:
        with console.status(markup.status_message("Syncing")) as status:
            if appdata:
                status.update(markup.status_message("Syncing appdata"))
                _appdata.sync()
            if cache:
                status.update(markup.status_message("Syncing cache"))
                _cache.sync()
        rprint("[b][green]Sync complete")


@click.command(
    cls=FormattedCommand,
    name="reset-all",
    hidden=True,
    allow_name_alias=False,
)
@utils._handle_keyboard_interrupt()
@click.option("-y", "--yes", is_flag=True, type=click.BOOL, hidden=True)
@_pass.appdata
@_pass.cache
@_pass.routine
@_pass.console
def _reset_all(
    console: Console,
    routine: CliQueryRoutines,
    cache: TimeEntryCache,
    appdata: TimeEntryAppData,
    yes: bool,
) -> None:
    """Delete all timesheet/projects data."""
    if not yes:
        if not _questionary.confirm(
            "This will delete all timesheet and project data. Are you sure?"
        ):
            return

    console.print("truncating timesheet")
    routine._query(f"truncate table {routine.timesheet_id}", wait=True)
    console.print("truncating projects")
    routine._query(
        f'delete from {routine.projects_id} where name != "no-project"',
        wait=True,
    )
    console.print("clearing cache")
    cache._reset()
    console.print("syncing local appdata")
    appdata.sync()
    console.print("[b][green]done")


@click.group(
    name="test",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "date-parse": "lightlike.cmd.app.test:date_parse",
        "date-diff": "lightlike.cmd.app.test:date_diff",
    },
    short_help="Test functions.",
)
def test() -> None:
    """Test functions."""


@click.command(name="locate-source", cls=FormattedCommand, hidden=True)
def locate_source() -> None:
    rprint(Path(__file__).parents[2].resolve())
