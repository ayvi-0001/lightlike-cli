import os
import typing as t
from pathlib import Path
from typing import Sequence

import click
from rich import print as rprint
from rich.console import Console

from lightlike.app import shell_complete
from lightlike.app.core import FormattedCommand
from lightlike.cmd import _pass

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
