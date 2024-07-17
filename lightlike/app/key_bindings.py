import typing as t
from operator import truth

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console

from lightlike._console import reconfigure_completer
from lightlike.app.config import AppConfig
from lightlike.internal import markup, utils
from lightlike.internal.enums import ActiveCompleter

__all__: t.Sequence[str] = ("PROMPT_BINDINGS",)


PROMPT_BINDINGS = KeyBindings()
prompt_handle = PROMPT_BINDINGS.add


keybinds = AppConfig().get("keybinds")


def _create_kb_exit_fn(name: str) -> t.Callable[..., t.Any]:
    @utils._nl_start(before=True)
    def _exit(event: KeyPressEvent) -> None:
        from lightlike.app import call_on_close

        call_on_close()

    _exit.__qualname__ = name
    _exit.__name__ = name
    return _exit


for k in keybinds["exit"]:
    cmd = _create_kb_exit_fn(f"kb_exit_{k}")
    prompt_handle(*keybinds["exit"][k])(cmd)


def _log_completer_keypress(
    keys: list[str],
    name: str,
    completer: t.Literal[
        ActiveCompleter.CMD,
        ActiveCompleter.HISTORY,
        ActiveCompleter.PATH,
    ],
) -> None:
    from lightlike._console import global_completers

    console = get_console()

    if completer in global_completers():
        with patch_stdout(raw=True):
            console.log(
                "Registered key press", markup.code("".join(keys)), "-",
                markup.command(name), "added to completers",  # fmt: skip
            )
    else:
        with patch_stdout(raw=True):
            console.log(
                "Registered key press", markup.code("".join(keys)), "-",
                markup.command(name), "removed from completers",  # fmt: skip
            )


keys_commands = keybinds["completers"]["commands"]  # fmt: skip
@prompt_handle(*keys_commands)
def _(event: KeyPressEvent) -> None:
    reconfigure_completer(completer=ActiveCompleter.CMD)
    _log_completer_keypress(
        keys_commands,
        "commands",
        ActiveCompleter.CMD,
    )


keys_history = keybinds["completers"]["history"]  # fmt: skip
@prompt_handle(*keys_history)
def _(event: KeyPressEvent) -> None:
    reconfigure_completer(completer=ActiveCompleter.HISTORY)
    _log_completer_keypress(
        keys_history,
        "history",
        ActiveCompleter.HISTORY,
    )


keys_path = keybinds["completers"]["path"]  # fmt: skip
@prompt_handle(*keys_path)
def _(event: KeyPressEvent) -> None:
    reconfigure_completer(completer=ActiveCompleter.PATH)
    _log_completer_keypress(
        keys_path,
        "path",
        ActiveCompleter.PATH,
    )


del keybinds


@Condition
def is_complete_state() -> bool:
    return truth(get_app().current_buffer.complete_state)


@prompt_handle(Keys.Escape, eager=True, filter=is_complete_state)
def _(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    state = buffer.complete_state
    if state:
        if state.current_completion:
            buffer.apply_completion(state.current_completion)
            buffer.cancel_completion()
        else:
            buffer.cancel_completion()


@prompt_handle(Keys.ControlSpace)
def _(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    if buffer.complete_state:
        buffer.complete_next()
    else:
        buffer.start_completion()
