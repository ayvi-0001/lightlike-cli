import sys
import typing as t
from shlex import shlex
from subprocess import list2cmdline, run

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from rich import print as rprint

if t.TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import Completer

__all__: t.Sequence[str] = ("repl",)


def repl(
    # fmt:off
    ctx: click.Context,
    prompt_kwargs: dict[str, t.Any],
    completer_callable: t.Callable[[click.Group, click.Context, t.Callable[[Exception], object] | None], "Completer"],
    format_click_exceptions_callable: t.Callable[[click.ClickException], object] | None = None,
    shell_cmd_callable: t.Callable[[], str] | None = None,
    pass_unknown_commands_to_shell: bool = True,
    uncaught_exceptions_callable: t.Callable[[Exception], object] | None = None,
    # fmt:on
) -> None:
    """
    :param prompt_kwargs: Dictionary containing keyword arguments passed to prompt_toolkit.PromptSession
    :param completer_callable: A callable that takes click.Group and click.Context as the first 2 args,\
                               and an optional callable for unhandled exceptions, that takes only an exception as an arg.
    :param format_click_exceptions_callable: A callable that handles any exceptions derived from click.ClickException.
    :param shell_cmd_callable: An optional callable to configure the default shell used for system commands.
    :param pass_unknown_commands_to_shell: Unrecognized commands get passed to the shell.
    :param uncaught_exceptions_callable: A callable to handle any non-click exceptions. This also gets passed to the completer callable.
    """
    if ctx.parent and not isinstance(ctx.command, click.Group):
        ctx = ctx.parent

    group: click.Group = t.cast(click.Group, ctx.command)

    prompt_kwargs.update(
        completer=completer_callable(group, ctx, uncaught_exceptions_callable)
    )

    session: PromptSession[str] = PromptSession(**prompt_kwargs)

    while 1:
        try:
            command = session.prompt(in_thread=True)
        except (KeyboardInterrupt, EOFError):
            continue

        args: list[str] = split_arg_string(command, posix=True)
        if not args:
            continue

        try:
            ctx.protected_args = args
            group.invoke(ctx)
        except click.UsageError as e1:
            if _is_unknown_command(e1) and pass_unknown_commands_to_shell:
                try:
                    _execute_system_command(args, shell_cmd_callable)
                except Exception as e3:
                    print(e3)
            else:
                _show_click_exception(e1, format_click_exceptions_callable)
        except click.ClickException as e4:
            _show_click_exception(e4, format_click_exceptions_callable)
        except (click.exceptions.Exit, SystemExit):
            pass
        except ExitRepl:
            break
        except Exception as e5:
            if uncaught_exceptions_callable:
                uncaught_exceptions_callable(e5)
            else:
                continue


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


def _is_unknown_command(error: click.UsageError) -> bool:
    usage_ctx: click.Context | None = error.ctx
    return (
        usage_ctx is not None
        and usage_ctx.command_path == ""
        and error.message.startswith("No such command")
    )


def _execute_system_command(
    args: list[str], shell_cmd_callable: t.Callable[[], str] | None = None
) -> None:
    try:
        _CMD: str = list2cmdline(args)

        buffer: "Buffer" = get_app().current_buffer
        buffer.append_to_history()
        buffer.reset(append_to_history=True)
        buffer.delete_before_cursor(len(_CMD))

        if shell_cmd_callable and (shell := shell_cmd_callable()) is not None:
            if isinstance(shell, str):
                cmd_exec = shell
            elif isinstance(shell, list):
                cmd_exec = list2cmdline(shell)

        if sys.platform.startswith("win"):
            import win32console  # type:ignore

            stdin_handle: win32console.PyConsoleScreenBufferType = (
                win32console.GetStdHandle(win32console.STD_INPUT_HANDLE)
            )
            original_stdin_mode: int = stdin_handle.GetConsoleMode()
            stdout_handle: win32console.PyConsoleScreenBufferType = (
                win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
            )
            original_stdout_mode: int = stdout_handle.GetConsoleMode()
        else:
            import termios

            original_attributes: list[t.Any] = termios.tcgetattr(sys.stdin)
        try:
            if cmd_exec:
                _CMD = '%s "%s"' % (cmd_exec, _CMD)

            run(_CMD, shell=True)
        finally:
            if sys.platform.startswith("win"):
                stdin_handle.SetConsoleMode(original_stdin_mode)
                stdout_handle.SetConsoleMode(original_stdout_mode)
            else:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_attributes)

    except KeyboardInterrupt:
        rprint("[#888888]Command killed by keyboard interrupt.")
    except EOFError:
        rprint("[#888888]End of file. No input.")


class ExitRepl(Exception): ...


def exit_repl() -> t.NoReturn:
    raise ExitRepl()


def split_arg_string(string: str, posix: bool = True) -> list[str]:
    lex: shlex = shlex(string, posix=posix)
    lex.whitespace_split = True
    lex.commenters = ""
    out: list[str] = []

    try:
        for token in lex:
            out.append(token)
    except ValueError:
        out.append(lex.token)

    return out
