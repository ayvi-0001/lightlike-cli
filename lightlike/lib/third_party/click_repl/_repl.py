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
#   - Replace click objects with rich_click objects
#   - Remap exceptions to rich_click errors
#   - Add app specific error handling
#   - Rename parameters
#   - Add types
#   - Add dynamic completer callable
#   - Remove internal/external commands
#   - Remove bootstrap prompt
#   - Remove break on EOFError
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

from lightlike.app.config import AppConfig
from lightlike.app.core import AliasedRichGroup, _map_click_exception
from lightlike.internal.utils import notify_and_log_error
from lightlike.lib.third_party.click_repl import exceptions
from lightlike.lib.third_party.click_repl._completer import ClickCompleter
from lightlike.lib.third_party.click_repl.utils import split_arg_string

if t.TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer

__all__: t.Sequence[str] = ("register_repl", "repl")


RG = t.TypeVar("RG", bound=click.RichGroup)
RC = t.TypeVar("RC", bound=click.RichContext)


def repl(
    ctx: click.RichContext,
    prompt_kwargs: dict[str, t.Any],
    completer: t.Callable[..., ClickCompleter[RG, RC]],
    dynamic_completer: t.Callable[[ClickCompleter[RG, RC]], Completer] | None = None,
) -> None:
    group_ctx = ctx

    # Switching to the parent context that has a Group as its command
    # as a Group acts as a cli for all of its subcommands
    if ctx.parent and not isinstance(ctx.command, click.RichGroup):
        group_ctx = t.cast(click.RichContext, ctx.parent)

    group = t.cast(AliasedRichGroup, group_ctx.command)

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
    repl_command_name = ctx.command.name
    if isinstance(group_ctx.command, click.RichCommandCollection):
        available_commands = {
            cmd_name: cmd_obj
            for source in group_ctx.command.sources
            for cmd_name, cmd_obj in getattr(source, "commands").items()
        }
    else:
        available_commands = getattr(group_ctx.command, "commands")

    original_command = available_commands.pop(repl_command_name, None)

    isatty = sys.stdin.isatty()

    if isatty:
        if dynamic_completer:
            prompt_kwargs.update(
                completer=dynamic_completer(completer(cli=group, ctx=group_ctx))
            )
        else:
            prompt_kwargs.update(completer=completer(cli=group, ctx=group_ctx))

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
            args = split_arg_string(command)
            if not args:
                continue

        except exceptions.CommandLineParserError:
            continue

        try:
            # The group command will dispatch based on args.
            old_protected_args = group_ctx.protected_args
            try:
                group_ctx.protected_args = args
                group.invoke(group_ctx)
            finally:
                group_ctx.protected_args = old_protected_args

        except click.UsageError as e1:
            usage_ctx = e1.ctx
            if (
                usage_ctx
                and usage_ctx.command_path == ""
                and e1.message.startswith("No such command")
            ):
                try:
                    _execute_system_command(args)
                except Exception as e3:
                    print(e3)
            else:
                _map_click_exception(e1)

        except (
            click.MissingParameter,
            click.BadOptionUsage,
            click.BadParameter,
            click.BadArgumentUsage,
            click.ClickException,
        ) as e4:
            _map_click_exception(e4)

        except (exceptions.ClickExit, SystemExit):
            pass

        except exceptions.ExitReplException:
            break

        except Exception as e5:
            notify_and_log_error(e5)

    if original_command:
        available_commands[repl_command_name] = original_command


def _execute_system_command(args: list[str]) -> None:
    args2cmdline = list2cmdline(args)

    buffer: "Buffer" = get_app().current_buffer
    buffer.append_to_history()
    buffer.reset(append_to_history=True)
    buffer.delete_before_cursor(len(args2cmdline))

    shell = AppConfig().get("system-command", "shell")

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
                if shell:
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
