import os
import sys
import typing as t
from datetime import datetime, timedelta
from decimal import Decimal
from os import getenv
from pathlib import Path
from subprocess import list2cmdline

import click
from rich import print as rprint
from rich.console import Console
from rich.syntax import Syntax

from lightlike.__about__ import __appdir__, __config__
from lightlike.app import _questionary, dates, validate
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
    "_reset_all",
    "parse_date_arg",
    "parse_date_opt",
    "date_diff",
    "source_dir",
)


CYGWIN = sys.platform.startswith("cygwin")
WIN = sys.platform.startswith("win")

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
        "open": "lightlike.cmd.app.config:open_",
        "list": "lightlike.cmd.app.config:list_",
    },
    short_help=f"Cli config file and settings. {__config}",
    syntax=Syntax(
        code="""\
        $ app config edit
        $ a c e
        
        $ app config open
        $ a c o
    
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


# This is a copy of click._termui_impl:open_url, except it only returns the args.
def _start_command(url: str, wait: bool = False, locate: bool = False) -> str:
    def _unquote_file(url: str) -> str:
        from urllib.parse import unquote

        if url.startswith("file://"):
            url = unquote(url[7:])

        return url

    if sys.platform == "darwin":
        args = ["open"]
        if wait:
            args.append("-W")
        if locate:
            args.append("-R")
        args.append(_unquote_file(url))

    elif WIN:
        if locate:
            url = _unquote_file(url.replace('"', ""))
            args = f'explorer /select,"{url}"'
            return args
        else:
            url = url.replace('"', "")
            wait_str = "/WAIT" if wait else ""
            args = f'start {wait_str} "" "{url}"'
            return args

    elif CYGWIN:
        if locate:

            url = os.path.dirname(_unquote_file(url).replace('"', ""))
            args = f'cygstart "{url}"'
        else:
            url = url.replace('"', "")
            wait_str = "-w" if wait else ""
            args = f'cygstart {wait_str} "{url}"'
            return args

    if locate:
        url = os.path.dirname(_unquote_file(url)) or "."
    else:
        url = _unquote_file(url)

    return list2cmdline(["xdg-open", url])


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
    help=f"Default opens with cmd `{_start_command('{uri}', locate=True)}`.",
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
    path: str = f"{__appdir__.resolve()}"

    if start:
        click.launch(path)
        console.print(f"$ {_start_command(path, locate=True)}")
    else:
        default_editor = os.environ.get("EDITOR")
        editor: str | None = (
            AppConfig().get("settings", "editor", default=default_editor) or None
        )
        if editor:
            click.edit(editor=editor, filename=path, require_save=False)
            console.print("$", editor, markup.link(path, path))
        else:
            console.print("editor not set.")
            click.launch(path)
            console.print(f"$ {_start_command(path, locate=True)}")


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
@utils.handle_keyboard_interrupt(
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
@utils.handle_keyboard_interrupt(
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
    if appdata is False and cache is False:
        return None
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
@utils.handle_keyboard_interrupt()
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


@click.command(
    cls=FormattedCommand,
    name="parse-date-arg",
    short_help="Test parser on argument / See examples.",
    no_args_is_help=True,
    syntax=Syntax(
        code="""\
        $ app test parse-date-arg now # `0d` or `today` would give same result
        $ app test parse-date-arg n # if the date string is the single character `n`, it will expand to `now`.
        2024-08-05 07:00:00-07:00

        # prefix with m (minutes), d (days), etc.
        $ app test parse-date-arg 1d  # `yesterday` would give same result
        2024-08-04 07:00:00-07:00

        $ app test parse-date-arg 1d@0:0 # or 1d@12am
        2024-08-04 00:00:00-07:00

        $ app test parse-date-arg 15m
        2024-08-05 06:45:00-07:00

        $ app test parse-date-arg +15m
        2024-08-05 07:15:00-07:00

        $ app test parse-date-arg jan1@1pm # or jan1@13:0
        2024-01-01 13:00:00-08:00
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@click.argument(
    "date",
    type=click.STRING,
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@_pass.console
def parse_date_arg(console: Console, date: datetime) -> None:
    """
    Test the dateparser function.

    See examples in syntax section below.

    You can opt for more verbose strings if you prefer.
    Strings such as "monday at 1pm", "january 1st", "15 minutes ago", "in 2 days",
    or fully qualified dates, such as '2024-01-01' would all work as well.

    Parsed dates prefer the past, unless prefixed with a plus operator.
    Dates are relative to today, unless explicitely stated in the string.

    An error will raise if the string fails to parse.

    [b]Note:[/b] If the date is an argument, the minus operator needs to be escaped.
    You can generally ignore adding a minus, as mentioned above.
    e.g.
    ```
    $ command --option -2d
    $ c -o-2d
    $ command "\-2d" # argument
    $ c "\-2d" # argument
    ```
    """
    console.print(date)


@click.command(
    cls=FormattedCommand,
    name="parse-date-opt",
    short_help="Test parser on option / See examples.",
    no_args_is_help=True,
    syntax=Syntax(
        code="""\
        $ app test parse-date-opt --date now # `0d` or `today` would give same result
        $ app test parse-date-opt -dn # if the date string is the single character `n`, it will expand to `now`.
        2024-08-05 07:00:00-07:00

        # prefix with m (minutes), d (days), etc.
        $ app test parse-date-opt --date 1d  # `yesterday` would give same result
        $ app test parse-date-opt -d1d  # short opt
        2024-08-04 07:00:00-07:00

        $ app test parse-date-opt --date 1d@0:0 # or 1d@12am
        $ app test parse-date-opt -d1d@0:0  # short opt
        2024-08-04 00:00:00-07:00

        $ app test parse-date-opt --date 15m
        $ app test parse-date-opt -d15m  # short opt
        2024-08-05 06:45:00-07:00

        $ app test parse-date-opt --date +15m
        $ app test parse-date-opt -d+15m  # short opt
        2024-08-05 07:15:00-07:00

        $ app test parse-date-opt --date jan1@1pm  # or jan1@13:0
        $ app test parse-date-opt -djan1@1pm  # short opt
        2024-01-01 13:00:00-08:00
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt()
@click.option(
    "-d",
    "--date",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help=None,
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@_pass.console
def parse_date_opt(console: Console, date: datetime) -> None:
    """
    Test the dateparser function.

    See examples in syntax section below.

    You can opt for more verbose strings if you prefer.
    Strings such as "monday at 1pm", "january 1st", "15 minutes ago", "in 2 days",
    or fully qualified dates, such as '2024-01-01' would all work as well.

    Parsed dates prefer the past, unless prefixed with a plus operator.
    Dates are relative to today, unless explicitely stated in the string.

    An error will raise if the string fails to parse.
    """
    console.print(date)


@click.command(
    cls=FormattedCommand,
    name="date-diff",
    short_help="Diff between 2 datetime.",
    no_args_is_help=True,
    allow_name_alias=False,
)
@utils.handle_keyboard_interrupt()
@click.argument(
    "date_start",
    type=click.STRING,
    callback=validate.callbacks.datetime_parsed,
)
@click.argument(
    "date_end",
    type=click.STRING,
    callback=validate.callbacks.datetime_parsed,
)
@click.argument(
    "subtract_hours",
    type=click.FLOAT,
    required=False,
    default=0,
)
@_pass.console
def date_diff(
    console: Console,
    date_start: datetime,
    date_end: datetime,
    subtract_hours: float,
) -> None:
    duration = date_end - date_start
    time_parts = dates.seconds_to_time_parts(
        Decimal(subtract_hours or 0) * Decimal(3600)
    )
    subtract_hours, paused_minutes, paused_seconds = time_parts
    duration = (date_end - date_start) - timedelta(
        hours=subtract_hours,
        minutes=paused_minutes,
        seconds=paused_seconds,
    )
    hours = round(Decimal(duration.total_seconds()) / Decimal(3600), 4)
    console.print("Duration:", duration)
    console.print("Hours:", hours)


@click.command(
    name="source-dir",
    cls=FormattedCommand,
    hidden=True,
    allow_name_alias=False,
)
def source_dir() -> None:
    rprint(Path(__file__).parents[2].resolve().as_uri())
