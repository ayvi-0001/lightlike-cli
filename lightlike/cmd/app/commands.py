# mypy: disable-error-code="import-untyped"

import typing as t
from os import getenv

import rich_click as click
from rich import print as rprint
from rich.console import Console

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import _pass
from lightlike.app.cache import TimeEntryAppData, TimeEntryCache
from lightlike.app.client import get_client
from lightlike.app.config import AppConfig
from lightlike.app.core import FmtRichCommand, LazyAliasedRichGroup
from lightlike.cmd import _help
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
    __config = f"/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike.toml"
    __appdir = f"/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli"
else:
    __config = __config__.as_posix()
    __appdir = __appdir__.as_posix()


@click.group(
    name="config",
    cls=LazyAliasedRichGroup,
    lazy_subcommands={
        "open": "lightlike.cmd.app.config.open_",
        "set": "lightlike.cmd.app.config.set_",
        "show": "lightlike.cmd.app.config.show",
    },
    help=_help.app_config,
    short_help=f"Cli config file and settings. {__config}",
    syntax=_help.app_config_syntax,
)
def config() -> None: ...


@click.command(
    cls=FmtRichCommand,
    name="dir",
    options_metavar="[LAUNCH OPTION]",
    help=_help.app_dir,
    short_help=f"Open cli dir: {__appdir}",
    syntax=_help.app_dir_syntax,
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
    uri = __appdir__.as_uri()
    path = __appdir__.as_posix()

    if start:
        click.launch(path)
        console.print("$ start", markup.link(uri, uri))
    else:
        editor = AppConfig().get("settings", "editor", default=None) or None
        click.edit(editor=editor, filename=path, require_save=False)
        console.print("$", editor, markup.link(uri, uri))


@click.command(
    cls=FmtRichCommand,
    name="run-bq",
    help=_help.app_run_bq,
    short_help="Run BigQuery scripts. Tables only built if missing.",
    syntax=_help.app_run_bq_syntax,
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
    from lightlike.app.client import provision_bigquery_resources

    provision_bigquery_resources(client=get_client(), force=True, yes=yes)


@click.command(
    cls=FmtRichCommand,
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
    cls=FmtRichCommand,
    name="sync",
    help=_help.app_sync,
    short_help="Sync local files.",
    syntax=_help.app_sync_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Canceled Sync.")),
)
@click.option("-a", "--appdata", is_flag=True)
@click.option("-c", "--cache", is_flag=True)
@_pass.appdata
@_pass.cache
@_pass.console
def sync(
    console: Console,
    _cache: TimeEntryCache,
    _appdata: TimeEntryAppData,
    appdata: bool,
    cache: bool,
) -> None:
    with console.status(markup.status_message("Syncing")) as status:
        if appdata:
            status.update(markup.status_message("Syncing appdata"))
            _appdata.sync()
        if cache:
            status.update(markup.status_message("Syncing cache"))
            _cache.sync()


@click.group(
    name="test",
    cls=LazyAliasedRichGroup,
    lazy_subcommands={
        "date-parse": "lightlike.cmd.app.test.date_parse",
        "date-diff": "lightlike.cmd.app.test.date_diff",
    },
    short_help="Test functions.",
)
def test() -> None:
    """Test functions."""
