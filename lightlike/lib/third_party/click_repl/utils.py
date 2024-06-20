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
# Changes from original package:
#   - Add types
#   - Replace click objects with rich_click objects
#   - Remove internal commands
#   - Remove handling for older python versions
#   - Rework resolve command to break on chained commands
#   - Rename exit -> exit_repl


import typing as t
from shlex import shlex

import rich_click as click

from . import utils
from .exceptions import ExitReplException

__all__: t.Sequence[str] = ("_resolve_context", "split_arg_string", "exit_repl")


def _resolve_context(args: list[str], ctx: click.Context) -> click.Context:
    try:
        while args:
            command = ctx.command

            if isinstance(command, click.Group) and not command.chain:
                name, cmd, args = t.cast(
                    tuple[str | None, click.Command | None, list[str]],
                    command.resolve_command(ctx, args),
                )

                if cmd is None:
                    return ctx

                ctx = t.cast(
                    click.Context,
                    cmd.make_context(name, args, parent=ctx, resilient_parsing=True),
                )
                args = ctx.protected_args + ctx.args
            else:
                break
    except Exception as error:
        if "No such command" not in f"{error}":
            utils._log().error(f"Failed to resolve context: {error}")

    return ctx


def split_arg_string(string: str, posix=True) -> list[str]:
    lex = shlex(string, posix=posix)
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


def _exit_internal() -> t.NoReturn:
    raise ExitReplException()


def exit_repl() -> t.NoReturn:
    _exit_internal()
