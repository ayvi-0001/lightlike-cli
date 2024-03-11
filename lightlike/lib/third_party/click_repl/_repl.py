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

# Original Repo: https://github.com/click-contrib/click-repl
# This CLI uses a modified version of the click-repl repo.
#   - Changes from original:
#   - Renamed parameters.
#   - Replace click objects with rich_click objects.
#   - Don't break on EOFError
#   - Remove internal/external commands.
#   - Remap click exceptions and render as rich_click errors.
#   - Use dynamic completer callable for completer.
#   - Bootstrap prompt removed.
#   - Add new line starts after prompts.

from __future__ import with_statement

import sys
from typing import Any, Callable, Sequence, TypeVar, cast

import rich_click as click
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console

from lightlike.app.group import AliasedRichGroup
from lightlike.lib.third_party._map_click_exception import _map_click_exception
from lightlike.lib.third_party.click_repl import exceptions
from lightlike.lib.third_party.click_repl._completer import ClickCompleter
from lightlike.lib.third_party.click_repl.utils import split_arg_string

__all__: Sequence[str] = ("register_repl", "repl")


RG = TypeVar("RG", bound=click.RichGroup)
RC = TypeVar("RC", bound=click.RichContext)


def repl(
    ctx: click.RichContext,
    prompt_kwargs: dict[str, Any],
    completer: Callable[..., ClickCompleter[RG, RC]],
    dynamic_completer: Callable[[ClickCompleter[RG, RC]], Completer] | None = None,
) -> None:
    group_ctx = ctx

    # Switching to the parent context that has a Group as its command
    # as a Group acts as a CLI for all of its subcommands
    if ctx.parent and not isinstance(ctx.command, click.RichGroup):
        group_ctx = cast(click.RichContext, ctx.parent)

    group = cast(AliasedRichGroup, group_ctx.command)

    # An Optional click.Argument in the CLI Group, that has no value
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

        def get_command() -> Any:
            return session.prompt()

    else:
        get_command = sys.stdin.readline

    while 1:
        try:
            command = get_command()
        except (KeyboardInterrupt, EOFError):
            print()  # Newline break before next prompt.
            continue

        if not command:
            if isatty:
                print()  # Newline break before next prompt.
                continue
            else:
                break

        try:
            args = split_arg_string(command)
            if not args:
                print()  # Newline break before next prompt.
                continue

        except exceptions.CommandLineParserError:
            continue

        except exceptions.ExitReplException:
            break

        try:
            # The group command will dispatch based on args.
            old_protected_args = group_ctx.protected_args
            try:
                group_ctx.protected_args = args
                group.invoke(group_ctx)
            finally:
                group_ctx.protected_args = old_protected_args

        except (
            click.MissingParameter,
            click.BadOptionUsage,
            click.BadParameter,
            click.BadArgumentUsage,
            click.UsageError,
            click.ClickException,
        ) as e:
            _map_click_exception(e)

        except (exceptions.ClickExit, SystemExit):
            pass

        except exceptions.ExitReplException:
            break

        except Exception as e:
            with patch_stdout(raw=True):
                with get_console() as console:
                    console.print_exception(show_locals=True, width=console.width)
                    console.print()

    if original_command:
        available_commands[repl_command_name] = original_command


def register_repl(group: click.Context, name: str = "repl") -> None:
    """Register :func:`repl()` as sub-command *name* of *group*."""
    group.command(name=name)(click.pass_context(repl))
