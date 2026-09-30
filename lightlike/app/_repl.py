import os
import sys
import typing as t
from subprocess import list2cmdline, run  # ruff: ignore[suspicious-subprocess-import]

import click
import rich
from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app

if sys.platform.startswith("win"):
    import win32console  # ty: ignore[unresolved-import]
else:
    import termios

if t.TYPE_CHECKING:
    from collections.abc import Callable

    from apscheduler.schedulers.background import BackgroundScheduler
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import Completer

__all__: t.Sequence[str] = ("repl",)


type ExceptionCallable = Callable[[Exception], object] | None
type ClickExceptionCallable = Callable[[click.ClickException], object] | None
type CompleterCallable = Callable[
    [click.Group | click.Command, click.Context, ExceptionCallable],
    Completer,
]


def repl(  # ruff: ignore[complex-structure, too-many-branches, too-many-statements]
    ctx: click.Context,
    prompt_kwargs: dict[str, t.Any],
    completer_callable: CompleterCallable,
    format_click_exceptions_callable: ClickExceptionCallable = None,
    shell_cmd_callable: Callable[[], str] | None = None,
    uncaught_exceptions_callable: ExceptionCallable = None,
    scheduler: Callable[[], BackgroundScheduler] | None = None,
    default_jobs_callable: Callable[[], None] | None = None,
    *,
    pass_unknown_commands_to_shell: bool = True,
) -> None:
    """
    :param prompt_kwargs: Dictionary containing keyword arguments passed to prompt_toolkit.PromptSession
    :param completer_callable: A callable that takes click.Group and click.Context as the first 2 args,
                               and an optional callable for unhandled exceptions, that takes only an exception as an arg.
    :param format_click_exceptions_callable: A callable that handles any exceptions derived from click.ClickException.
    :param shell_cmd_callable: An optional callable to configure the default shell used for system commands.
    :param pass_unknown_commands_to_shell: Unrecognized commands get passed to the shell.
    :param uncaught_exceptions_callable: A callable to handle any non-click exceptions. This also gets passed to the completer callable.
    :param scheduler: A calllable returning apscheduler.schedulers.background.BackgroundScheduler.
    :param default_jobs_callable: A callable that creates or replaces jobs in the scheduler.
                                  Jobs will need to have a static id and replace_existing=True
                                  otherwise a new job will be added each time.
    """  # ruff: ignore[line-too-long, missing-blank-line-after-summary]
    cmd_is_group: bool = isinstance(ctx.command, click.Group)
    if ctx.parent and not cmd_is_group:
        ctx = ctx.parent

    ctx_command = ctx.command

    prompt_kwargs.update(
        completer=completer_callable(ctx_command, ctx, uncaught_exceptions_callable),
    )

    session: PromptSession[str] = PromptSession(**prompt_kwargs)

    if scheduler is not None:
        scheduler().start()
        if default_jobs_callable and callable(default_jobs_callable):
            try:
                default_jobs_callable()
            except AttributeError as error:
                if "'NoneType' object has no attribute 'items'" not in f"{error}":
                    raise

    try:
        while True:
            try:
                command = session.prompt(in_thread=True)
            except KeyboardInterrupt, EOFError:
                continue

            args: list[str] = click.parser.split_arg_string(command)
            if not args:
                continue

            try:
                ctx.protected_args = args
                ctx_command.invoke(ctx)
            except click.UsageError as exc1:
                if _is_unknown_command(exc1) and pass_unknown_commands_to_shell:
                    try:
                        _execute_system_command(args, shell_cmd_callable)
                    except Exception as exc2:  # ruff: ignore[blind-except]
                        print(exc2)  # ruff: ignore[print]
                else:
                    _show_click_exception(exc1, format_click_exceptions_callable)
            except click.ClickException as exc3:
                _show_click_exception(exc3, format_click_exceptions_callable)
            except click.exceptions.Exit, SystemExit:
                pass
            except ExitRepl:
                break
            except Exception as exc4:  # ruff: ignore[blind-except]
                if uncaught_exceptions_callable:
                    uncaught_exceptions_callable(exc4)
                else:
                    continue
    finally:
        if scheduler and scheduler().running:
            scheduler().shutdown()


def _show_click_exception(
    exc: click.ClickException,
    format_click_exceptions_callable: (Callable[[click.ClickException], object] | None) = None,
) -> None:
    if format_click_exceptions_callable:
        format_click_exceptions_callable(exc)
    else:
        exc.show()


def _is_unknown_command(error: click.UsageError) -> bool:
    usage_ctx: click.Context | None = error.ctx
    return (
        usage_ctx is not None
        and not usage_ctx.command_path
        and error.message.startswith("No such command")
    )


def _execute_system_command(
    args: list[str],
    shell_cmd_callable: Callable[[], str] | None = None,
) -> None:
    if sys.platform.startswith("win"):
        stdin_handle: win32console.PyConsoleScreenBufferType
        stdout_handle: win32console.PyConsoleScreenBufferType

        stdin_handle = win32console.GetStdHandle(win32console.STD_INPUT_HANDLE)
        stdout_handle = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)

        original_stdin_mode: int = stdin_handle.GetConsoleMode()
        original_stdout_mode: int = stdout_handle.GetConsoleMode()
    else:
        original_attributes: list[t.Any] = termios.tcgetattr(sys.stdin)

    try:  # ruff: ignore[too-many-statements-in-try-clause]
        cmd: str = list2cmdline(args)

        buffer: Buffer = get_app().current_buffer
        buffer.append_to_history()
        buffer.reset(append_to_history=True)
        buffer.delete_before_cursor(len(cmd))

        cmd = _prepend_exec_to_cmd(cmd, shell_cmd_callable)
        run(cmd, check=False, shell=True, env=os.environ)  # ruff: ignore[subprocess-popen-with-shell-equals-true]

    except KeyboardInterrupt:
        rich.print("[#888888]Command killed by keyboard interrupt.")
    except EOFError:
        rich.print("[#888888]End of file. No input.")
    finally:
        if sys.platform.startswith("win"):
            stdin_handle.SetConsoleMode(original_stdin_mode)
            stdout_handle.SetConsoleMode(original_stdout_mode)
        else:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_attributes)


def _prepend_exec_to_cmd(
    _cmd: str,
    shell_cmd_callable: Callable[[], str] | None = None,
) -> str:
    if shell_cmd_callable and (shell := shell_cmd_callable()) is not None:
        if isinstance(shell, str):
            cmd_exec = shell
        elif isinstance(shell, list):
            cmd_exec = list2cmdline(shell)
        else:
            return _cmd

        _cmd = f'{cmd_exec} "{_cmd}"'

    return _cmd


class ExitRepl(Exception):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def exit_repl() -> t.NoReturn:
    raise ExitRepl
