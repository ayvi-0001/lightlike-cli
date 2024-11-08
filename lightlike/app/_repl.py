import os
import sys
import typing as t
from subprocess import list2cmdline, run

import click
from apscheduler.schedulers.background import BackgroundScheduler
from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from rich import print as rprint

if sys.platform.startswith("win"):
    import win32console
else:
    import termios

if t.TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import Completer

__all__: t.Sequence[str] = ("repl",)


ExceptionCallable: t.TypeAlias = t.Callable[[Exception], object] | None
ClickExceptionCallable: t.TypeAlias = t.Callable[[click.ClickException], object] | None
CompleterCallable: t.TypeAlias = t.Callable[
    [click.Group | click.Command, click.Context, ExceptionCallable],
    "Completer",
]


def repl(
    # fmt:off
    ctx: click.Context,
    prompt_kwargs: dict[str, t.Any],
    completer_callable: CompleterCallable,
    format_click_exceptions_callable: ClickExceptionCallable = None,
    shell_cmd_callable: t.Callable[[], str] | None = None,
    pass_unknown_commands_to_shell: bool = True,
    uncaught_exceptions_callable: ExceptionCallable = None,
    scheduler: BackgroundScheduler | t.Callable[[], BackgroundScheduler] | None = None,
    default_jobs_callable: t.Callable[[], None] | None = None,
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
    :param scheduler: A calllable returning apscheduler.schedulers.background.BackgroundScheduler.
    :param default_jobs_callable: A callable that creates or replaces jobs in the scheduler.\
                                            Jobs will need to have a static id and replace_existing=True\
                                            otherwise a new job will be added each time.
    """
    cmd_is_group: bool = isinstance(ctx.command, click.Group)
    if ctx.parent and not cmd_is_group:
        ctx = ctx.parent

    ctx_command = ctx.command

    prompt_kwargs.update(
        completer=completer_callable(ctx_command, ctx, uncaught_exceptions_callable)
    )

    session: PromptSession[str] = PromptSession(**prompt_kwargs)

    if scheduler:
        scheduler().start()
        if default_jobs_callable and callable(default_jobs_callable):
            try:
                default_jobs_callable()
            except AttributeError as error:
                if "'NoneType' object has no attribute 'items'" not in f"{error}":
                    raise error

    try:
        while 1:
            try:
                command = session.prompt(in_thread=True)
            except (KeyboardInterrupt, EOFError):
                continue

            args: list[str] = click.parser.split_arg_string(command)
            if not args:
                continue

            try:
                ctx.protected_args = args
                ctx_command.invoke(ctx)
            except click.UsageError as error1:
                if _is_unknown_command(error1) and pass_unknown_commands_to_shell:
                    try:
                        _execute_system_command(args, shell_cmd_callable)
                    except Exception as error2:
                        print(error2)
                else:
                    _show_click_exception(error1, format_click_exceptions_callable)
            except click.ClickException as error3:
                _show_click_exception(error3, format_click_exceptions_callable)
            except (click.exceptions.Exit, SystemExit):
                pass
            except ExitRepl:
                break
            except Exception as error4:
                if uncaught_exceptions_callable:
                    uncaught_exceptions_callable(error4)
                else:
                    continue
    finally:
        if scheduler and scheduler().running:
            scheduler().shutdown()


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
    if sys.platform.startswith("win"):
        stdin_handle: win32console.PyConsoleScreenBufferType = (
            win32console.GetStdHandle(win32console.STD_INPUT_HANDLE)
        )
        original_stdin_mode: int = stdin_handle.GetConsoleMode()
        stdout_handle: win32console.PyConsoleScreenBufferType = (
            win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
        )
        original_stdout_mode: int = stdout_handle.GetConsoleMode()
    else:
        original_attributes: list[t.Any] = termios.tcgetattr(sys.stdin)

    try:
        _CMD: str = list2cmdline(args)

        buffer: "Buffer" = get_app().current_buffer
        buffer.append_to_history()
        buffer.reset(append_to_history=True)
        buffer.delete_before_cursor(len(_CMD))

        _CMD = _prepend_exec_to_cmd(_CMD, shell_cmd_callable)
        run(_CMD, shell=True, env=os.environ)

    except KeyboardInterrupt:
        rprint("[#888888]Command killed by keyboard interrupt.")
    except EOFError:
        rprint("[#888888]End of file. No input.")
    finally:
        if sys.platform.startswith("win"):
            stdin_handle.SetConsoleMode(original_stdin_mode)
            stdout_handle.SetConsoleMode(original_stdout_mode)
        else:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_attributes)


def _prepend_exec_to_cmd(
    _cmd: str, shell_cmd_callable: t.Callable[[], str] | None = None
) -> str:
    if shell_cmd_callable and (shell := shell_cmd_callable()) is not None:
        if isinstance(shell, str):
            cmd_exec = shell
        elif isinstance(shell, list):
            cmd_exec = list2cmdline(shell)
        else:
            return _cmd

        _cmd = '%s "%s"' % (cmd_exec, _cmd)

    return _cmd


class ExitRepl(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def exit_repl() -> t.NoReturn:
    raise ExitRepl()
