import os
import typing as t
from pathlib import Path

import click

from lightlike.app import shell_complete
from lightlike.app._repl import exit_repl
from lightlike.app.core import FormattedCommand
from lightlike.cmd import _pass

if t.TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.console import Console

__all__: t.Sequence[str] = ("cd_", "exit_", "help_")


P = t.ParamSpec("P")


@click.command(
    cls=FormattedCommand,
    name="exit",
    hidden="true",
    short_help="Exit REPL.",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
)
def exit_() -> None:
    """Exit REPL."""
    exit_repl()


@click.command(
    cls=FormattedCommand,
    name="cd",
    hidden=True,
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
)
@click.argument("path", type=Path, shell_complete=shell_complete.path)
def cd_(path: Path) -> None:
    try:
        if f"{path}" in {"~", "~/"}:
            os.chdir(path.home())
        else:
            os.chdir(path.resolve())
    except Exception as error:
        rich.print(f"{error!r}; {path.resolve()}")


@click.command(
    name="help",
    short_help="Show help.",
    context_settings={"help_option_names": []},
)
@_pass.console
@_pass.ctx_group(parents=1)
def help_(ctx_group: Sequence[click.Context], console: Console) -> None:
    _ctx, parent = ctx_group
    console.print(parent.get_help())
