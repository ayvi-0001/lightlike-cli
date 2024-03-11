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

import shlex
from typing import NoReturn, Sequence, cast

import rich_click as click

from .exceptions import ExitReplException

__all__: Sequence[str] = (
    "_resolve_context",
    "split_arg_string",
    "_exit_internal",
    "exit",
)


def _resolve_context(args: list[str], ctx: click.RichContext) -> click.RichContext:
    """Produce the context hierarchy starting with the command and
    traversing the complete arguments. This only follows the commands,
    it doesn't trigger input prompts or callbacks.

    :param args: List of complete args before the incomplete value.
    :param cli_ctx: `click.Context` object of the CLI group
    """
    try:
        while args:
            command = ctx.command

            if isinstance(command, click.RichGroup):
                if not command.chain:
                    name, cmd, args = command.resolve_command(ctx, args)

                    if cmd is None:
                        return ctx

                    ctx = cast(
                        click.RichContext,
                        cmd.make_context(
                            name, args, parent=ctx, resilient_parsing=True
                        ),
                    )
                    args = ctx.protected_args + ctx.args
                else:
                    sub_ctx = click.RichContext()

                    while args:
                        name, cmd, args = command.resolve_command(ctx, args)

                        if cmd is None:
                            return ctx

                        sub_ctx = cast(
                            click.RichContext,
                            cmd.make_context(
                                name,
                                args,
                                parent=ctx,
                                allow_extra_args=True,
                                allow_interspersed_args=False,
                                resilient_parsing=True,
                            ),
                        )
                        args = sub_ctx.args

                    ctx = sub_ctx
                    args = [*sub_ctx.protected_args, *sub_ctx.args]
            else:
                break
    except Exception:
        pass

    return ctx


def split_arg_string(string: str, posix=True) -> list[str]:
    """Split an argument string as with :func:`shlex.split`, but don't
    fail if the string is incomplete. Ignores a missing closing quote or
    incomplete escape sequence and uses the partial token as-is.
    .. code-block:: python
        split_arg_string("example 'my file")
        ["example", "my file"]
        split_arg_string("example my\\")
        ["example", "my"]
    :param string: String to split.
    """
    lex = shlex.shlex(string, posix=posix)
    lex.whitespace_split = True
    lex.commenters = ""
    out = []

    try:
        for token in lex:
            out.append(token)
    except ValueError:
        # Raised when end-of-string is reached in an invalid state. Use
        # the partial token as-is. The quote or escape character is in
        # lex.state, not lex.token.
        out.append(lex.token)

    return out


def _exit_internal() -> NoReturn:
    raise ExitReplException()


def exit() -> NoReturn:
    """Exit the repl"""
    _exit_internal()
