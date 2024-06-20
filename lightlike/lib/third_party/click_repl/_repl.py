# Copyright (c) 2014-2015 Markus Unterwaditzer & contributors.
# Copyright (c) 2016-2026 Asif Saif Uddin & contributors.

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# This cli uses a modified version of the click-repl repo.
# Original Repo: https://github.com/click-contrib/click-repl
# Changes from original:
#   - Add callable params to handle exceptions
#   - Rename parameters
#   - Add type hints
#   - Add dynamic completer callable
#   - Remove bootstrap prompt
#   - Remove break on EOFError
#   - Remove internal/external commands prefix
#   - Add system command default if command does not exist


from __future__ import with_statement

import sys
import typing as t
from subprocess import PIPE, STDOUT, Popen, list2cmdline

import rich_click as click
from more_itertools import first, last
from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer

from . import exceptions
from ._completer import ReplCompleter
from .utils import split_arg_string

if t.TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer

__all__: t.Sequence[str] = ("register_repl", "repl")


def repl(
    ctx: click.Context,
    prompt_kwargs: dict[str, t.Any],
    completer_callable: t.Callable[
        [click.Group, click.Context, t.Callable[[Exception], object] | None],
        ReplCompleter,
    ],
    dynamic_completer_callable: t.Callable[..., Completer] | None = None,
    format_click_exceptions_callable: (
        t.Callable[[click.ClickException], object] | None
    ) = None,
    shell_config_callable: t.Callable[[], str] | None = None,
    pass_unknown_commands_to_shell: bool = True,
    uncaught_exceptions_callable: t.Callable[[Exception], object] | None = None,
) -> None:
    group_ctx: click.Context = ctx

    # Switching to the parent context that has a Group as its command
    # as a Group acts as a cli for all of its subcommands
    if ctx.parent and not isinstance(ctx.command, click.Group):
        group_ctx = t.cast(click.Context, ctx.parent)

    group: click.Group = t.cast(click.Group, group_ctx.command)

    # An Optional click.Argument in the cli Group, that has no value
    # will consume the first word from the REPL input, causing issues in
    # executing the command
    # So, if there's an empty Optional Argument
    for param in group.params:
        if (
            isinstance(param, click.Argument)
            and group_ctx.params[param.name] is None  # type: ignore[attr-defined, index]
            and not param.required  # type: ignore[index]
        ):
            raise exceptions.InvalidGroupFormat(
                f"{type(group).__name__} '{group.name}' requires value for "
                f"an optional argument '{param.name}' in REPL mode"
            )

    # Delete the REPL command from those available, as we don't want to allow
    # nesting REPLs (note: pass `None` to `pop` as we don't want to error if
    # REPL command already not present for some reason).
    repl_command_name: str | None = ctx.command.name
    if isinstance(group_ctx.command, click.CommandCollection):
        available_commands = {
            cmd_name: cmd_obj
            for source in group_ctx.command.sources
            for cmd_name, cmd_obj in getattr(source, "commands").items()
        }
    else:
        available_commands = getattr(group_ctx.command, "commands")

    original_command: click.Command = available_commands.pop(repl_command_name, None)

    isatty: bool = sys.stdin.isatty()

    if isatty:
        repl_completer: ReplCompleter = completer_callable(
            group, group_ctx, uncaught_exceptions_callable
        )
        if dynamic_completer_callable:
            prompt_kwargs.update(completer=dynamic_completer_callable(repl_completer))
        else:
            prompt_kwargs.update(completer=repl_completer)

        session: PromptSession = PromptSession(**prompt_kwargs)

        def get_command() -> t.Any:
            return session.prompt()

    else:
        get_command = sys.stdin.readline

    while 1:
        try:
            command = get_command()
        except (KeyboardInterrupt, EOFError):
            continue

        if not command:
            if isatty:
                continue
            else:
                break

        try:
            args: list[str] = split_arg_string(command)
            if not args:
                continue

        except exceptions.CommandLineParserError:
            continue

        try:
            # The group command will dispatch based on args.
            old_protected_args: list[str] = group_ctx.protected_args
            try:
                group_ctx.protected_args = args
                group.invoke(group_ctx)
            finally:
                group_ctx.protected_args = old_protected_args

        except click.UsageError as e1:
            if _unknown_cli_command(error=e1) and pass_unknown_commands_to_shell:
                try:
                    _execute_system_command(args, shell_config_callable)
                except Exception as e3:
                    print(e3)
            else:
                _show_click_exception(e1, format_click_exceptions_callable)

        except (
            click.MissingParameter,
            click.BadOptionUsage,
            click.BadParameter,
            click.BadArgumentUsage,
            click.ClickException,
        ) as e4:
            _show_click_exception(e4, format_click_exceptions_callable)

        except (exceptions.ClickExit, SystemExit):
            pass

        except exceptions.ExitReplException:
            break

        except Exception as e5:
            if uncaught_exceptions_callable:
                uncaught_exceptions_callable(e5)

    if original_command:
        available_commands[repl_command_name] = original_command


def _show_click_exception(
    error: click.ClickException,
    format_click_exceptions_callable: (
        t.Callable[[click.ClickException], object] | None
    ) = None,
) -> None:
    if format_click_exceptions_callable:
        format_click_exceptions_callable(error)
    else:
        error.show()


def _unknown_cli_command(error: click.UsageError) -> bool:
    usage_ctx: click.Context | None = error.ctx
    return (
        usage_ctx is not None
        and usage_ctx.command_path == ""
        and error.message.startswith("No such command")
    )


def _execute_system_command(
    args: list[str],
    shell_config_callable: t.Callable[[], str] | None = None,
) -> None:
    args2cmdline = list2cmdline(args)

    buffer: "Buffer" = get_app().current_buffer
    buffer.append_to_history()
    buffer.reset(append_to_history=True)
    buffer.delete_before_cursor(len(args2cmdline))

    for cmd_args in args2cmdline.split("&&"):
        commands = list(map(lambda c: c.strip(), cmd_args.split("|")))
        processes: list[Popen] = []

        while commands:
            try:
                last_process = last(processes)
                last_process.wait()
            except ValueError:
                last_process = None

            proc_args = list(filter(lambda l: l != "", first(commands).split(" ")))

            stdin = last_process.stdout if last_process else PIPE
            stdout = sys.stdout if len(commands) == 1 else PIPE
            stderr = STDOUT

            try:
                _cmd: str = list2cmdline(proc_args)
                if shell_config_callable and (shell := shell_config_callable()):
                    if isinstance(shell, str):
                        _cmd = f'{shell} "{_cmd}"'
                    elif isinstance(shell, list):
                        _cmd = f'{list2cmdline(shell)} "{_cmd}"'

                proc: Popen[str] = Popen(  # type: ignore[call-overload]
                    _cmd,
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                    shell=True,
                    text=True,
                    close_fds=True,
                )

            except Exception as e2:
                print(e2)
                break

            processes.append(proc)
            commands.pop(0)

        if not processes:
            continue

        last(processes).wait()
