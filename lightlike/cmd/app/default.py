import os
import typing as t
from os import getenv
from pathlib import Path
from typing import Sequence

import click
from rich import print as rprint
from rich.console import Console

from lightlike.__about__ import __appdir__, __appname_sc__, __config__, __version__
from lightlike.app import _pass, shell_complete
from lightlike.app.core import FormattedCommand

__all__: t.Sequence[str] = ("help_", "exit_", "cd_")


P = t.ParamSpec("P")


@click.command(
    cls=FormattedCommand,
    name="exit",
    hidden="true",
    short_help="Exit REPL.",
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
def exit_() -> None:
    """Exit REPL."""
    from lightlike.app._repl import exit_repl

    exit_repl()


@click.command(
    cls=FormattedCommand,
    name="cd",
    hidden=True,
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
@click.argument("path", type=Path, shell_complete=shell_complete.path)
def cd_(path: Path) -> None:
    if f"{path}" in ("~", "~/"):
        os.chdir(path.home())
        return
    try:
        os.chdir(path.resolve())
    except Exception as error:
        rprint(f"{error!r}; {str(path.resolve())!r}")


@click.command(
    name="help",
    short_help="Show help.",
    context_settings=dict(help_option_names=[]),
)
@_pass.console
@_pass.ctx_group(parents=1)
def help_(ctx_group: Sequence[click.Context], console: Console) -> None:
    ctx, parent = ctx_group
    console.print(parent.get_help())


if LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"):
    __appname = "lightlike_cli"
    __config = f"/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike.toml"
    __appdir = f"/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli"
else:
    __appname = __appname_sc__
    __config = __config__  # type:ignore [assignment]
    __appdir = __appdir__  # type:ignore [assignment]


def general_help() -> str:
    return f"""
[repr_attrib_name]__appname__[/][b red]=[/][repr_attrib_value]{__appname}[/repr_attrib_value]
[repr_attrib_name]__version__[/][b red]=[/][repr_number]{__version__}[/repr_number]
[repr_attrib_name]__config__[/][b red]=[/][repr_path]{__config}[/repr_path]
[repr_attrib_name]__appdir__[/][b red]=[/][repr_path]{__appdir}[/repr_path]

GENERAL:
    [code]ctrl space[/code] or [code]tab[/code] to display commands/autocomplete.
    [code]:q[/code] or [code]ctrl q[/code] or type exit to exit repl.
    [code]:c{{1 | 2 | 3}}[/code] to add/remove completions from the global completer. [code]1[/code]=commands, [code]2[/code]=history, [code]3[/code]=path

HELP:
    add help option to command/group --help / -h.

SYSTEM COMMANDS:
    any command that's not recognized by top parent commands, will be passed to the shell.
    system commands can also be invoked by:
        - typing command and pressing [code]:[/code][code]![/code]
        - typing command and pressing [code]escape[/code] [code]enter[/code]
        - pressing [code]meta[/code] [code]shift[/code] [code]1[/code] to enable system prompt
    
    see app:config:set:general:shell --help / -h to configure what shell is used.
    path autocompletion is automatic for [code]cd[/code].

TIME ENTRY IDS:
    time entry ids are the sha1 hash of the project, note, and the start timestamp.
    if 2 entries were created with the same project, note, and start-time, they'd have the same id.
    if any fields are later edited, the id will not change.
    there is currently no way to remove duplicate ids other than directly dropping from the table in BigQuery.
    for commands requiring an id, supply the first several characters.
    the command will find the matching id, as long as it is unique.
    if more than 1 id matches the string provided, use more characters until it is unique.

DATE/TIME FIELDS:
    arguments/options asking for datetime will attempt to parse the string provided.
    error will raise if unable to parse.
    dates are relative to today, unless explicitly stated in the string.
"""
