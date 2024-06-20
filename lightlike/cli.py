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

# mypy: disable-error-code="import-untyped, func-returns-value"

import sys
import typing as t

import rich_click as click
from rich.traceback import install

__all__: t.Sequence[str] = ("lightlike",)

install(suppress=[click])

from rich_click.patch import patch

patch()

from lightlike import _console

_console.reconfigure()

from fasteners import InterProcessLock, try_lock

from lightlike.__about__ import __config__, __lock__, __version__
from lightlike.app import render
from lightlike.internal import appdir, utils

LOCK: InterProcessLock = InterProcessLock(__lock__)

if t.TYPE_CHECKING:
    from lightlike.app.core import LazyAliasedRichGroup


def build_cli() -> "LazyAliasedRichGroup":
    from functools import partial

    from lightlike.app import dates, shell_complete, shutdown
    from lightlike.app.client import get_client
    from lightlike.app.config import AppConfig
    from lightlike.app.core import (
        RICH_HELP_CONFIG,
        LazyAliasedRichGroup,
        _map_click_exception,
    )
    from lightlike.app.prompt import REPL_PROMPT_KWARGS
    from lightlike.cmd import _help, lazy_subcommands
    from lightlike.lib.third_party import click_repl

    _console.reconfigure(
        get_datetime=partial(dates.now, tzinfo=AppConfig().tz),
    )

    console = _console.get_console()

    not _console.QUIET_START and console.log("Authorizing BigQuery Client")
    get_client()

    @click.group(
        cls=LazyAliasedRichGroup,
        name="lightlike",
        lazy_subcommands=lazy_subcommands,
        help=_help.general,
        invoke_without_command=True,
        context_settings=dict(
            allow_extra_args=True,
            ignore_unknown_options=True,
            help_option_names=["-h", "--help"],
        ),
    )
    @click.rich_config(
        help_config=RICH_HELP_CONFIG,
        console=console,
    )
    @click.pass_context
    def cli(ctx: click.RichContext) -> None:
        if ctx.invoked_subcommand is None:
            ctx.invoke(repl)
            shutdown()

    @cli.command()
    @click.pass_context
    def repl(ctx: click.RichContext) -> None:
        click_repl.repl(
            ctx=ctx,
            prompt_kwargs=REPL_PROMPT_KWARGS,
            completer_callable=shell_complete.repl_completer,
            dynamic_completer_callable=shell_complete.dynamic_completer,
            format_click_exceptions_callable=_map_click_exception,
            shell_config_callable=lambda: AppConfig().get("system-command", "shell"),
            pass_unknown_commands_to_shell=True,
            uncaught_exceptions_callable=utils.notify_and_log_error,
        )

    return cli


def lightlike(lock: InterProcessLock = LOCK) -> None:
    try:
        _check_lock(lock)
        render.cli_info()

        try:
            appdir.validate(__version__, __config__)
        except Exception as error:
            utils.notify_and_log_error(error)
            sys.exit(2)

        cli: LazyAliasedRichGroup = build_cli()

        from lightlike import cmd

        for command in [
            cmd.app,
            cmd.bq,
            cmd.project,
            cmd.summary,
            cmd.timer,
        ]:
            cli.add_command(command)

        with lock:
            if not _console.QUIET_START:
                with _console.get_console() as console:
                    console.log("Starting REPL")

            # If no invoked subcommand, cli is launched through REPL,
            # Don't show cli name in help/usage contexts.
            cli(prog_name="lightlike" if len(sys.argv) > 1 else "")

    except Exception as error:
        utils.notify_and_log_error(error)


def _check_lock(lock: InterProcessLock) -> None | t.NoReturn:
    with try_lock(lock) as locked:
        if not locked:
            with _console.get_console() as console:
                console.rule(
                    title=f"FAILED TO ACQUIRE LOCK {lock.path}",
                    style="bold red",
                    align="left",
                )
                console.print(
                    "Cli is already running in another interpreter on this machine. "
                    "Please close it before attempting to run again.",
                )
            sys.exit(2)
    return None
