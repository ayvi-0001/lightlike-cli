# MIT License

# Copyright (c) 2024 ayvi-0001

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import TYPE_CHECKING, NoReturn, Sequence

import fasteners  # type: ignore[import-untyped, import-not-found]
import rich_click as click
from rich.traceback import install

if TYPE_CHECKING:
    from lightlike.app.group import AliasedRichGroup

__all__: Sequence[str] = ("lightlike",)


install(suppress=[click])


from lightlike import _console
from lightlike.__about__ import __lock__, __version__

_console.reconfigure()

LOCK = fasteners.InterProcessLock(__lock__)


def build_cli() -> "AliasedRichGroup":
    from lightlike.app import shell_complete
    from lightlike.app.client import get_client
    from lightlike.app.group import AliasedRichGroup
    from lightlike.app.prompt import REPL_PROMPT_KWARGS
    from lightlike.cmd import _help
    from lightlike.internal import utils

    get_client()

    @click.group(
        cls=AliasedRichGroup,
        name="lightlike",
        help=_help.general,
        invoke_without_command=True,
        context_settings=dict(
            color=True,
            allow_extra_args=True,
            ignore_unknown_options=True,
            help_option_names=["-h", "--help"],
        ),
    )
    @click.rich_config(console=_console.get_console())
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            _console.get_console().log("Starting REPL")
            ctx.invoke(repl)
            get_client().close()
            utils._log().debug("Closed Bigquery client HTTPS connection.")
            utils._log().debug("Exiting gracefully.")
            utils._shutdown_log()

    @cli.command(name="repl")
    @click.pass_context
    def repl(ctx: click.RichContext) -> None:
        from lightlike.lib.third_party import click_repl

        click_repl.repl(
            ctx=ctx,
            prompt_kwargs=REPL_PROMPT_KWARGS,
            completer=shell_complete.dynamic._click_completer,
            dynamic_completer=shell_complete.dynamic._dynamic_completer,
        )

    return cli


def lightlike(lock: fasteners.InterProcessLock = LOCK) -> None:
    try:
        _check_lock(lock)

        from lightlike.app import render

        render.cli_info()

        from lightlike.internal import appdir

        appdir.validate(__version__)

        cli = build_cli()

        from rich_click.cli import patch

        from lightlike import cmd

        patch()

        for command in [
            cmd.app,
            cmd.bq,
            cmd.project,
            cmd.report,
            cmd.timer,
            cmd.other.help_,
            cmd.other.calc_,
            cmd.other.calendar_,
            cmd.other.cd_,
            cmd.other.ls_,
            cmd.other.tree_,
        ]:
            cli.add_command(command)

        with lock:
            cli(prog_name="")  # Hiding 'python -m lightlike' in help and usage.

    except Exception:
        with _console.get_console() as console:
            console.print_exception(show_locals=True, width=console.width)


def _check_lock(lock: fasteners.InterProcessLock) -> None | NoReturn:
    with fasteners.try_lock(lock) as locked:
        if not locked:
            with _console.get_console() as console:
                console.rule(
                    title=f"FAILED TO ACQUIRE LOCK {lock.path}",
                    style="bold red",
                    align="left",
                )
                console.print(
                    "CLI is already running in another interpreter on this machine. "
                    "Please close it before attempting to run again.",
                )
            exit(2)
    return None
