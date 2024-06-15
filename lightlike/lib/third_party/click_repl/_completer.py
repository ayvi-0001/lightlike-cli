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
#   - Change parameters to called if is_flag is True
#   - Replace click objects with rich_click objects
#   - Add display_meta param to completion item in autocompletion_functions
#   - Remove path/bool/deprecated completion functions
#   - Remove internal/external commands
#   - Generate param display meta with short option/default/required/multiple
#   - Allow completion for hidden commands
#   - Allow autocompletion on UNPROCESSED param types
#   - Show options for chained commands
#   - Only display called subcommand completions when parent ctx is chained
#   - Remove called subcommands from chained commands
#   - Account for aliased commands in chained command completions


from __future__ import unicode_literals

import typing as t

import rich_click as click
from click.shell_completion import CompletionItem
from prompt_toolkit.completion import Completer, Completion

from lightlike.app.core import AliasedRichGroup
from lightlike.internal.utils import notify_and_log_error

from .utils import _resolve_context, split_arg_string

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: t.Sequence[str] = ("ClickCompleter",)


RG = t.TypeVar("RG", bound=click.RichGroup)
RC = t.TypeVar("RC", bound=click.RichContext)


class ClickCompleter(Completer, t.Generic[RG, RC]):
    __slots__: t.ClassVar[t.Sequence[str]] = (
        "cli",
        "ctx",
        "parsed_args",
        "parsed_ctx",
        "ctx_command",
    )

    def __init__(self, cli: AliasedRichGroup, ctx: click.RichContext) -> None:
        self.cli: AliasedRichGroup = cli
        self.ctx: click.RichContext = ctx
        self.parsed_args: list[str] = []
        self.parsed_ctx: click.RichContext = ctx
        self.ctx_command: click.Command = ctx.command

    def _get_completion_from_autocompletion_functions(
        self,
        autocomplete_ctx: click.RichContext,
        param: click.Parameter,
        args: list[str],
        incomplete: str,
    ) -> list[Completion]:
        param_choices = []
        autocompletions = param.shell_complete(autocomplete_ctx, incomplete)

        for autocomplete in autocompletions:
            start_position = -len(incomplete)

            if isinstance(autocomplete, CompletionItem):
                if autocomplete.value:
                    param_choices.append(
                        Completion(
                            text=f"{autocomplete.value}",
                            start_position=start_position,
                            display_meta=autocomplete.help,
                        )
                    )
            elif isinstance(autocomplete, tuple):
                param_choices.append(
                    Completion(
                        text=f"{autocomplete[0]}",
                        start_position=start_position,
                        display_meta=f"{autocomplete[1]}",
                    )
                )
            else:
                param_choices.append(
                    Completion(
                        text=f"{autocomplete}",
                        start_position=start_position,
                    )
                )
        return param_choices

    def _get_completion_from_params(
        self,
        autocomplete_ctx: click.RichContext,
        param: click.Parameter,
        args: list[str],
        incomplete: str,
    ) -> list[Completion]:
        completions = []
        if getattr(param, "shell_complete"):
            completions = self._get_completion_from_autocompletion_functions(
                autocomplete_ctx=autocomplete_ctx,
                param=param,
                args=args,
                incomplete=incomplete,
            )
        return completions

    def _get_completion_for_cmd_args(
        self,
        autocomplete_ctx: click.RichContext,
        ctx_command: click.Command,
        args: list[str],
        incomplete: str,
    ) -> list[Completion]:
        choices = []
        param_called = False

        for param in ctx_command.params:
            if getattr(param, "hidden", False):
                choices.extend(
                    self._get_completion_from_params(
                        autocomplete_ctx=autocomplete_ctx,
                        args=args,
                        param=param,
                        incomplete=incomplete,
                    )
                )

            elif isinstance(param, click.Option):
                opts = param.opts + param.secondary_opts
                previous_args = args[: param.nargs * -1]
                current_args = args[param.nargs * -1 :]

                already_present = any([opt in previous_args for opt in opts])
                hide = already_present and not param.multiple

                if len(opts) == 2:
                    if any(opt in current_args for opt in opts):
                        param_called = True if not param.is_flag else False
                    elif opts[1].startswith(incomplete) and not hide:
                        completion = Completion(
                            text=opts[1],
                            start_position=-len(incomplete),
                            display_meta=_display_meta(
                                option=param, short_flag=opts[0]
                            ),
                        )
                        choices.append(completion)
                else:
                    option = opts[0]

                    if option in current_args:
                        param_called = True if not param.is_flag else False
                    elif option.startswith(incomplete) and not hide:
                        completion = Completion(
                            text=f"{option}",
                            start_position=-len(incomplete),
                            display_meta=_display_meta(option=param),
                        )
                        choices.append(completion)

                if param_called:
                    choices = self._get_completion_from_params(
                        autocomplete_ctx=autocomplete_ctx,
                        args=args,
                        param=param,
                        incomplete=incomplete,
                    )
                    break

            elif isinstance(param, click.Argument):
                choices.extend(
                    self._get_completion_from_params(
                        autocomplete_ctx=autocomplete_ctx,
                        args=args,
                        param=param,
                        incomplete=incomplete,
                    )
                )

        return choices

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterable[Completion]:
        try:
            text_before_cursor = document.text_before_cursor
            args = split_arg_string(text_before_cursor, posix=False)

            choices = []
            chained_command_choices = []
            cursor_in_command = text_before_cursor.rstrip() == text_before_cursor

            if args and cursor_in_command:
                incomplete = args.pop()
            else:
                incomplete = ""

            if self.parsed_args != args:
                self.parsed_args = args

                try:
                    self.parsed_ctx = _resolve_context(args, self.ctx)
                except Exception:
                    yield from []
                finally:
                    self.ctx_command = t.cast(
                        click.RichCommand, self.parsed_ctx.command
                    )

            choices.extend(
                self._get_completion_for_cmd_args(
                    ctx_command=self.ctx_command,
                    incomplete=incomplete,
                    autocomplete_ctx=self.parsed_ctx,
                    args=args,
                )
            )

            if isinstance(self.ctx_command, click.RichGroup):
                incomplete_lower = incomplete.lower()

                for name in self.ctx_command.list_commands(self.parsed_ctx):  # type: ignore[attr-defined]
                    command = t.cast(
                        click.RichCommand,
                        self.ctx_command.get_command(self.parsed_ctx, name),
                    )

                    if getattr(command, "hidden", False):
                        continue

                    if self.ctx_command.chain is True:
                        # fmt: off
                        if (
                            name.startswith(args[-1]) and 
                            not self.ctx_command.name.startswith(args[-1]) # type:ignore [union-attr]
                        ):
                            chained_command_choices = (
                                self._get_completion_for_cmd_args(
                                    ctx_command=command,
                                    incomplete=incomplete,
                                    autocomplete_ctx=self.parsed_ctx,
                                    args=args,
                                )
                            )
                            if not chained_command_choices and command.params:
                                # Command has argument or option but no completions.
                                # Returning an empty completion item so that the other commands do not appear
                                # until a value is provided for the subcommand being called.
                                chained_command_choices = [Completion("")]
                            continue

                        if name in args:
                            continue
                        # fmt: on

                    if name.lower().startswith(incomplete_lower):
                        completion = Completion(
                            text=f"{name}",
                            start_position=-len(incomplete),
                            display_meta=getattr(command, "short_help", ""),
                        )
                        choices.append(completion)

            if chained_command_choices:
                # Only show choices for the chained command being called.
                yield from chained_command_choices
            else:
                yield from choices

        except Exception as error:
            notify_and_log_error(error)


def _display_meta(option: click.Option, short_flag: str | None = None) -> str:
    flag = "[flag]" if option.is_flag else ""
    required = "[req]" if option.required else "[opt]"
    multiple = "[#]" if option.multiple else ""
    default = (
        f"[default={option.default() if callable(option.default) else option.default}]"
        if option.default is not None and option.show_default
        else ""
    )

    help_ = option.help() if callable(option.help) else option.help  # type: ignore
    ws = " " if any([flag, required, default]) else ""
    display_meta = "".join([flag, multiple, required, default, ws, help_ or ""]) or ""

    return f"[{short_flag}]{display_meta}" if short_flag else display_meta
