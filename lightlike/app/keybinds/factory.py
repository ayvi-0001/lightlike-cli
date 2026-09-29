import typing as t
from operator import truth
from pathlib import Path
from subprocess import list2cmdline

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console

from lightlike.app.config import AppConfig
from lightlike.app.shell_complete.dynamic import (
    global_completers,
    reconfigure_completer,
)
from lightlike.internal import markup, utils

if t.TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
    from rich.text import Text

    from lightlike.internal.enums import ActiveCompleter

__all__: t.Sequence[str] = (
    "add_exit_kb",
    "add_global_completer_kb",
    "add_system_cmd_kb",
    "autocomplete_apply",
    "autocomplete_next",
    "is_complete_state",
)


def add_system_cmd_kb(keybinding: KeyBindings, binds: list[list[str]]) -> None:
    if not binds or binds == [[]]:
        return

    def _build(name: str) -> t.Callable[..., t.Any]:
        @utils.nl_start(before=True)
        async def _(event: KeyPressEvent) -> None:
            buffer = event.app.current_buffer
            cmd = buffer.document.text

            shell: str | list[str] | None = AppConfig(path=Path()).get("system-command", "shell")
            if shell:
                if isinstance(shell, str):
                    cmd = f'{shell} "{cmd}"'
                elif isinstance(shell, list):
                    cmd = f'{list2cmdline(shell)} "{cmd}"'

            buffer.append_to_history()
            buffer.reset(append_to_history=True)
            buffer.delete_before_cursor(len(cmd))
            utils.nl()
            utils.nl()
            kb_system_command = event.app.run_system_command(cmd, wait_for_enter=False)
            await kb_system_command

        _.__qualname__ = name
        _.__name__ = name
        return _

    for idx, binding in enumerate(binds):
        kb = _build(name=f"kb_system_cmd_{idx}")
        keybinding.add(*binding)(kb)


def add_exit_kb(keybinding: KeyBindings, binds: list[list[str]]) -> None:
    if not binds or binds == [[]]:
        return

    def _build(name: str) -> t.Callable[..., t.Any]:
        @utils.nl_start(before=True)
        def _(_event: KeyPressEvent) -> None:
            from lightlike.app import call_on_close

            call_on_close()

        _.__qualname__ = name
        _.__name__ = name
        return _

    for idx, binding in enumerate(binds):
        kb = _build(name=f"kb_exit_{idx}")
        keybinding.add(*binding)(kb)


def _log_completer_keypress(completer: ActiveCompleter) -> None:
    message: list[Text | str] = [markup.command(completer._name_.lower())]
    if completer in global_completers():
        message.append("added to completers")
    else:
        message.append("removed from completers")
    with patch_stdout(raw=True):
        get_console().log(*message)


def add_global_completer_kb(
    keybinding: KeyBindings,
    binds: list[list[str]],
    completer: ActiveCompleter,
) -> None:
    if not binds or binds == [[]]:
        return

    def _build(name: str) -> t.Callable[..., t.Any]:
        def _(_event: KeyPressEvent) -> None:
            reconfigure_completer(completer=completer)
            _log_completer_keypress(completer)

        _.__qualname__ = name
        _.__name__ = name
        return _

    for idx, binding in enumerate(binds):
        kb = _build(name=f"kb_{completer}_{idx}")
        keybinding.add(*binding)(kb)


@Condition
def is_complete_state() -> bool:
    return truth(get_app().current_buffer.complete_state)


def autocomplete_apply(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    state = buffer.complete_state
    if state:
        if state.current_completion:
            buffer.apply_completion(state.current_completion)
            buffer.cancel_completion()
        else:
            buffer.cancel_completion()


def autocomplete_next(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    if buffer.complete_state:
        buffer.complete_next()
    else:
        buffer.start_completion()
