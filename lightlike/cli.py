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
from functools import partial
from pathlib import Path

import rich_click as click
from fasteners import InterProcessLock, try_lock
from rich import get_console
from rich.traceback import install
from rich_click.patch import patch
from rich_click.rich_help_configuration import RichHelpConfiguration

from lightlike import _console

install(suppress=[click])

patch()

_console.reconfigure()


from lightlike.__about__ import __config__, __lock__, __version__
from lightlike.app import render
from lightlike.internal import appdir, utils
from lightlike.lib.third_party import click_repl

if t.TYPE_CHECKING:
    from lightlike.app.core import LazyAliasedRichGroup

__all__: t.Sequence[str] = ("lightlike",)


def build_cli(
    name: str,
    repl_kwargs: dict[str, t.Any],
    help: str | None = None,
    lazy_subcommands: dict[str, t.Any] | None = None,
    context_settings: dict[str, t.Any] | None = None,
    help_config: RichHelpConfiguration | None = None,
    shutdown_callable: t.Callable[..., t.Never] | None = None,
) -> "LazyAliasedRichGroup":
    from lightlike.app.core import LazyAliasedRichGroup

    @click.group(
        cls=LazyAliasedRichGroup,
        name=name,
        help=help,
        lazy_subcommands=lazy_subcommands,
        invoke_without_command=True,
        context_settings=context_settings,
    )
    @click.rich_config(
        help_config=help_config,
        console=get_console(),
    )
    @click.pass_context
    def cli(ctx: click.RichContext) -> None:
        if ctx.invoked_subcommand is None:
            ctx.invoke(repl)
            if shutdown_callable:
                shutdown_callable()

    @cli.command()
    @click.pass_context
    def repl(ctx: click.RichContext) -> None:
        click_repl.repl(ctx=ctx, **repl_kwargs)

    return cli


def lightlike(name: str = "lightlike", lock_path: Path = __lock__) -> None:
    try:
        lock: InterProcessLock = InterProcessLock(lock_path)

        _check_lock(lock)
        render.cli_info()

        try:
            appdir.validate(__version__, __config__)
        except Exception as error:
            utils.notify_and_log_error(error)
            sys.exit(2)

        from lightlike.app import dates, shutdown
        from lightlike.app.client import get_client
        from lightlike.app.config import AppConfig
        from lightlike.app.core import RICH_HELP_CONFIG
        from lightlike.cmd.app.default import general_help

        _console.reconfigure(
            get_datetime=partial(dates.now, tzinfo=AppConfig().tz),
        )

        console = get_console()

        _append_paths()

        not _console.QUIET_START and console.log("Authorizing BigQuery Client")
        get_client()

        cli: LazyAliasedRichGroup = build_cli(
            name=name,
            help=general_help(),
            repl_kwargs=_build_repl_kwargs(),
            lazy_subcommands=_build_lazy_subcommands(),
            context_settings=dict(
                allow_extra_args=True,
                ignore_unknown_options=True,
                help_option_names=["-h", "--help"],
            ),
            help_config=RICH_HELP_CONFIG,
            shutdown_callable=shutdown,
        )

        from lightlike import cmd

        for command in filter(lambda p: not p.startswith("_"), dir(cmd)):
            cli.add_command(getattr(cmd, command))

        with lock:
            if not _console.QUIET_START:
                console.log("Starting REPL")

            # If no invoked subcommand, cli is launched through REPL,
            # Don't show cli name in help/usage contexts.
            cli(prog_name=name if len(sys.argv) > 1 else "")

    except Exception as error:
        utils.notify_and_log_error(error)


def _check_lock(lock: InterProcessLock) -> None | t.NoReturn:
    with try_lock(lock) as locked:
        if not locked:
            with get_console() as console:
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


def _build_lazy_subcommands() -> dict[str, str]:
    from lightlike.app.config import AppConfig

    from_config: dict[str, str] = AppConfig().get("cli", "lazy_subcommands", default={})
    default = {
        "help": "lightlike.cmd.app.default.help_",
        "cd": "lightlike.cmd.app.default.cd_",
        "exit": "lightlike.cmd.app.default.exit_",
    }
    from_config.update(default)
    return from_config


def _append_paths() -> None:
    from lightlike.app.config import AppConfig

    try:
        paths: dict[str, str] | None = AppConfig().get("cli", "append_path", "paths")
        if paths:
            for path in paths:
                sys.path.append(path)
                appdir._log().debug(f"{path} added to path")
    except Exception as error:
        appdir._log().error(error)


def _build_repl_kwargs() -> dict[str, t.Any]:
    from prompt_toolkit.shortcuts import CompleteStyle

    from lightlike.app import cursor, shell_complete
    from lightlike.app.config import AppConfig
    from lightlike.app.core import _map_click_exception
    from lightlike.app.key_bindings import PROMPT_BINDINGS

    prompt_kwargs = dict(
        message=cursor.build,
        history=appdir.REPL_FILE_HISTORY(),
        style=AppConfig().prompt_style,
        cursor=AppConfig().cursor_shape,
        key_bindings=PROMPT_BINDINGS,
        refresh_interval=1,
        complete_in_thread=True,
        complete_while_typing=True,
        validate_while_typing=True,
        enable_system_prompt=True,
        enable_open_in_editor=True,
        reserve_space_for_menu=AppConfig().get(
            "settings",
            "reserve_space_for_menu",
            default=7,
        ),
        complete_style=t.cast(
            CompleteStyle,
            AppConfig().get("settings", "complete_style", default="COLUMN"),
        ),
    )

    repl_kwargs = dict(
        prompt_kwargs=prompt_kwargs,
        completer_callable=shell_complete.repl_completer,
        dynamic_completer_callable=shell_complete.dynamic_completer,
        format_click_exceptions_callable=_map_click_exception,
        shell_config_callable=lambda: AppConfig().get("system-command", "shell"),
        pass_unknown_commands_to_shell=True,
        uncaught_exceptions_callable=utils.notify_and_log_error,
    )

    return repl_kwargs
