from __future__ import annotations

import logging
import typing as t
from operator import truth

import click
from click.shell_completion import CompletionItem
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, Completion

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: t.Sequence[str] = ("ReplCompleter", "repl")


def repl(
    cli: click.Group,
    ctx: click.Context,
    uncaught_exceptions_callable: t.Callable[[Exception], object] | None = None,
) -> ReplCompleter:
    return ReplCompleter(cli, ctx, uncaught_exceptions_callable)


class ReplCompleter(Completer):
    __slots__: t.Sequence[str] = (
        "cli",
        "ctx",
        "parsed_args",
        "parsed_ctx",
        "ctx_command",
    )

    def __init__(
        self,
        cli: click.Group,
        ctx: click.Context,
        uncaught_exceptions_callable: t.Callable[[Exception], object] | None = None,
    ) -> None:
        self.cli: click.Group = cli
        self.ctx: click.Context = ctx
        self.parsed_args: list[str] = []
        self.parsed_ctx: click.Context = ctx
        self.ctx_command: click.Command = ctx.command
        self.uncaught_exceptions_callable = uncaught_exceptions_callable

    def _complete_functions(
        self,
        autocomplete_ctx: click.Context,
        param: click.Parameter,
        incomplete: str,
    ) -> list[Completion]:
        param_choices: list[Completion] = []
        autocompletions: list[CompletionItem] = param.shell_complete(
            autocomplete_ctx, incomplete
        )

        document: "Document" = get_app().current_buffer.document
        start_position: int = -len(document.get_word_before_cursor(WORD=True))

        for autocomplete in autocompletions:
            if isinstance(autocomplete, CompletionItem):
                completion = Completion(
                    text=f"{autocomplete.value}",
                    start_position=start_position,
                    display_meta=autocomplete.help,
                )
            elif isinstance(autocomplete, tuple):
                completion = Completion(
                    text=f"{autocomplete[0]}",
                    start_position=start_position,
                    display_meta=f"{autocomplete[1]}",
                )
            else:
                completion = Completion(
                    text=f"{autocomplete}",
                    start_position=start_position,
                )
            param_choices.append(completion)

        return param_choices

    def _complete_params(
        self,
        autocomplete_ctx: click.Context,
        param: click.Parameter,
        args: list[str],
        incomplete: str,
    ) -> list[Completion]:
        completions = []
        if getattr(param, "shell_complete"):
            completions = self._complete_functions(
                autocomplete_ctx=autocomplete_ctx,
                param=param,
                incomplete=incomplete,
            )
        return completions

    def _complete_cmd_args(
        self,
        autocomplete_ctx: click.Context,
        ctx_command: click.Command,
        args: list[str],
        incomplete: str,
    ) -> list[Completion]:
        choices: list[Completion] = []
        param_called: bool = False

        for param in ctx_command.params:
            if getattr(param, "hidden", False):
                choices.extend(
                    self._complete_params(
                        autocomplete_ctx=autocomplete_ctx,
                        args=args,
                        param=param,
                        incomplete=incomplete,
                    )
                )
            elif isinstance(param, click.Option):
                opts: list[str] = param.opts + param.secondary_opts
                previous_args: list[str] = args[: param.nargs * -1]
                current_args: list[str] = args[param.nargs * -1 :]

                already_present: bool = any([opt in previous_args for opt in opts])
                hide: bool = already_present and not param.multiple

                if len(opts) == 2:
                    if any(opt in current_args for opt in opts):
                        param_called = truth(not param.is_flag)
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
                    option: str = opts[0]

                    if option in current_args:
                        param_called = truth(not param.is_flag)
                    elif option.startswith(incomplete) and not hide:
                        completion = Completion(
                            text=f"{option}",
                            start_position=-len(incomplete),
                            display_meta=_display_meta(option=param),
                        )
                        choices.append(completion)

                if param_called:
                    choices = self._complete_params(
                        autocomplete_ctx=autocomplete_ctx,
                        args=args,
                        param=param,
                        incomplete=incomplete,
                    )
                    break
            elif isinstance(param, click.Argument):
                choices.extend(
                    self._complete_params(
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
            text_before_cursor: str = document.text_before_cursor
            args: list[str] = click.parser.split_arg_string(text_before_cursor)

            choices: list[Completion] = []
            chained_command_choices: list[Completion] = []
            cursor_in_command: bool = text_before_cursor.rstrip() == text_before_cursor

            incomplete: str = ""
            if args and cursor_in_command:
                incomplete = args.pop()

            if self.parsed_args != args:
                self.parsed_args = args

                try:
                    self.parsed_ctx = _resolve_context(args, self.ctx)
                except Exception:
                    yield from []
                finally:
                    self.ctx_command = self.parsed_ctx.command

            choices.extend(
                self._complete_cmd_args(
                    ctx_command=self.ctx_command,
                    incomplete=incomplete,
                    autocomplete_ctx=self.parsed_ctx,
                    args=args,
                )
            )

            if isinstance(self.ctx_command, click.Group):
                for cmd_name in self.ctx_command.list_commands(self.parsed_ctx):
                    command: click.Command | None = None
                    command = self.ctx_command.get_command(self.parsed_ctx, cmd_name)

                    if not command or getattr(command, "hidden", False):
                        continue

                    if self.ctx_command.chain is True:
                        if (
                            cmd_name.startswith(args[-1])
                            and not self.ctx_command.name.startswith(args[-1])  # type:ignore [union-attr]
                        ):
                            chained_command_choices = self._complete_cmd_args(
                                ctx_command=command,
                                incomplete=incomplete,
                                autocomplete_ctx=self.parsed_ctx,
                                args=args,
                            )
                            if not chained_command_choices and command.params:
                                # Command has argument or option but no completions.
                                # Returning an empty completion item so that the other commands do not appear
                                # until a value is provided for the subcommand being called.
                                chained_command_choices = [Completion("")]
                            continue

                        if cmd_name in args:
                            continue

                    if cmd_name.lower().startswith(incomplete.lower()):
                        completion = Completion(
                            text=cmd_name,
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
            if callable(self.uncaught_exceptions_callable):
                self.uncaught_exceptions_callable(error)


def _display_meta(option: click.Option, short_flag: str | None = None) -> str:
    # fmt: off
    flag: str = "[flag]" if option.is_flag else ""
    required: str = "[req]" if option.required else "[opt]"
    multiple: str = "[#]" if option.multiple else ""
    default: str = (
        f"[default={option.default() if callable(option.default) else option.default}]"
        if option.default is not None and option.show_default
        else ""
    )

    help_: str = option.help() if callable(option.help) else option.help  # type: ignore
    ws: str = " " if any([flag, required, default]) else ""
    display_meta: str = "".join([flag, multiple, required, default, ws, help_ or ""]) or ""
    # fmt: on
    return f"[{short_flag}]{display_meta}" if short_flag else display_meta


def _resolve_context(args: list[str], ctx: click.Context) -> click.Context:
    try:
        while args:
            command: click.Command = ctx.command
            if isinstance(command, click.Group) and not command.chain:
                name, cmd, args = command.resolve_command(ctx, args)
                if cmd is None:
                    return ctx
                ctx = cmd.make_context(name, args, parent=ctx, resilient_parsing=True)
                args = ctx.protected_args + ctx.args
            else:
                break
    except Exception as error:
        if "No such command" not in f"{error}":
            logging.error(
                f"Failed to resolve context: {error}. "
                f"ctx: {ctx.info_name} | "
                f"args: {' '.join(map(str, args))}"
            )

    return ctx
