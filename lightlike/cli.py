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

import click
import rtoml
from fasteners import InterProcessLock, try_lock
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from pytz import timezone
from rich import get_console
from rich.traceback import install

from lightlike import _console

install(suppress=[click])

_console.reconfigure()

from lightlike.__about__ import __config__, __lock__, __version__
from lightlike.app import render
from lightlike.app.core import LazyAliasedGroup
from lightlike.internal import appdir, constant, utils

__all__: t.Sequence[str] = ("lightlike",)


def build_cli(
    name: str,
    repl_kwargs: dict[str, t.Any],
    help: str | None = None,
    lazy_subcommands: dict[str, t.Any] | None = None,
    context_settings: dict[str, t.Any] | None = None,
    call_on_close: t.Callable[..., t.Never] | None = None,
    obj: dict[str, t.Any] | None = None,
) -> LazyAliasedGroup:
    @click.group(
        cls=LazyAliasedGroup,
        name=name,
        help=help,
        lazy_subcommands=lazy_subcommands,
        invoke_without_command=True,
        context_settings=context_settings,
    )
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        ctx.obj = obj or {}
        if ctx.invoked_subcommand is None:
            from lightlike.app._repl import repl

            repl(ctx=ctx, **repl_kwargs)
            if call_on_close:
                call_on_close()

    return cli


def lightlike(name: str = "lightlike", lock_path: Path = __lock__) -> None:
    try:
        lock: InterProcessLock = InterProcessLock(lock_path)

        _check_lock(lock)
        render.cli_info()

        try:
            appdir.validate(__version__, __config__)
        except Exception as error:
            appdir.console_log_error(error, notify=True, patch_stdout=True)
            sys.exit(2)

        from lightlike.app import call_on_close, cursor, dates, shell_complete
        from lightlike.app.client import get_client
        from lightlike.app.config import AppConfig
        from lightlike.app.core import _format_click_exception
        from lightlike.app.key_bindings import PROMPT_BINDINGS
        from lightlike.cmd.app.default import general_help

        tzinfo = timezone(AppConfig().get("settings", "timezone"))
        _console.reconfigure(get_datetime=partial(dates.now, tzinfo=tzinfo))

        console = get_console()

        _append_paths(paths=AppConfig().get("cli", "append_path", "paths"))

        not _console.QUIET_START and console.log("Authorizing BigQuery Client")
        get_client()

        prompt_kwargs: dict[str, t.Any] = {}
        prompt_kwargs.update(
            message=cursor.build,
            history=appdir.REPL_FILE_HISTORY(),
            bottom_toolbar=cursor.bottom_toolbar,
            rprompt=cursor.rprompt,
            style=Style.from_dict(
                utils.update_dict(
                    rtoml.load(constant.PROMPT_STYLE),
                    AppConfig().get("prompt", "style", default={}),
                )
            ),
            cursor=CursorShape.BLOCK,
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
                default=10,
            ),
            complete_style=t.cast(
                CompleteStyle,
                AppConfig().get("settings", "complete_style", default="COLUMN"),
            ),
        )

        repl_kwargs = dict(
            prompt_kwargs=prompt_kwargs,
            completer_callable=lambda g, c, e: shell_complete.dynamic_completer(
                shell_complete.repl(g, c, e)
            ),
            format_click_exceptions_callable=_format_click_exception,
            shell_config_callable=lambda: AppConfig().get("system-command", "shell"),
            pass_unknown_commands_to_shell=True,
            uncaught_exceptions_callable=partial(
                appdir.console_log_error, notify=True, patch_stdout=True
            ),
        )

        cli: LazyAliasedGroup = build_cli(
            name=name,
            help=general_help(),
            repl_kwargs=repl_kwargs,
            lazy_subcommands=_build_lazy_subcommands(
                config=AppConfig().get("cli", "lazy_subcommands", default={})
            ),
            context_settings=dict(
                allow_extra_args=True,
                ignore_unknown_options=True,
                help_option_names=["-h", "--help"],
            ),
            call_on_close=call_on_close,
        )

        with lock:
            if not _console.QUIET_START:
                console.log("Starting REPL")

            # If no invoked subcommand, cli is launched through REPL,
            # Don't show cli name in help/usage contexts.
            cli(prog_name=name if len(sys.argv) > 1 else "")

    except Exception as error:
        appdir.console_log_error(error, notify=True, patch_stdout=True)


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


def _build_lazy_subcommands(config: dict[str, str] | None = None) -> dict[str, str]:
    # Nothing imports from the `cmd` module.
    # Commands are all added either by default here, or from the config file.
    if not config:
        config = {}

    default = {
        "help": "lightlike.cmd.app.default:help_",
        "cd": "lightlike.cmd.app.default:cd_",
        "exit": "lightlike.cmd.app.default:exit_",
    }
    config.update(default)

    return config


def _append_paths(paths: list[str] | None) -> None:
    # Commands anywhere on the local machine can be loaded through lazy subcommands,
    # as long as it is on path. There is a key in the config file to add additional paths,
    # before the cli runs.
    try:
        if paths:
            for path in paths:
                sys.path.append(path)
                appdir._log().debug(f"{path} added to path")
    except Exception as error:
        appdir._log().error(error)
