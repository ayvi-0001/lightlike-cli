import os
import typing as t
from pathlib import Path
from typing import Sequence

import rich_click as click
from rich import print as rprint
from rich.console import Console

from lightlike.__about__ import __appdir__
from lightlike.app import _pass, shell_complete
from lightlike.app.core import FmtRichCommand
from lightlike.cmd import _help

__all__: t.Sequence[str] = ("help_", "exit_", "cd_")


P = t.ParamSpec("P")


@click.command(
    name="help",
    short_help="Show help.",
    help=_help.general,
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
@_pass.console
@_pass.ctx_group(parents=1)
def help_(ctx_group: Sequence[click.RichContext], console: Console) -> None:
    ctx, parent = ctx_group
    console.print(parent.get_help())


@click.command(
    cls=FmtRichCommand,
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
    from lightlike.lib.third_party import click_repl

    click_repl.exit_repl()


@click.command(
    cls=FmtRichCommand,
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
