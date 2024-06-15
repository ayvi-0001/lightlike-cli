import typing as t
from operator import truth
from subprocess import list2cmdline

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

if t.TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyPressEvent

__all__: t.Sequence[str] = ("PROMPT_BINDINGS", "QUERY_BINDINGS")


PROMPT_BINDINGS = KeyBindings()
prompt_handle = PROMPT_BINDINGS.add

QUERY_BINDINGS = KeyBindings()
query_handle = QUERY_BINDINGS.add

keybinds = AppConfig().get("keybinds")


def _create_kb_system_command_fn(name: str) -> t.Callable[..., t.Any]:
    @utils._nl_start(before=True)
    async def _system_command(event: "KeyPressEvent") -> None:
        buffer = event.app.current_buffer
        cmd = buffer.document.text

        shell = AppConfig().get("system-command", "shell")
        if shell:
            if isinstance(shell, str):
                cmd = f'{shell} "{cmd}"'
            elif isinstance(shell, list):
                cmd = f'{list2cmdline(shell)} "{cmd}"'

        buffer.append_to_history()
        buffer.reset(append_to_history=True)
        buffer.delete_before_cursor(len(cmd))
        utils._nl()
        utils._nl()
        kb_system_command = event.app.run_system_command(cmd, wait_for_enter=False)
        await kb_system_command

    _system_command.__qualname__ = name
    _system_command.__name__ = name
    return _system_command


def _create_kb_exit_fn(name: str) -> t.Callable[..., t.Any]:
    @utils._nl_start(before=True)
    def _exit(event: "KeyPressEvent") -> None:
        from lightlike.app import shutdown

        shutdown()

    _exit.__qualname__ = name
    _exit.__name__ = name
    return _exit


for k in keybinds["system-command"]:
    cmd = _create_kb_system_command_fn(f"kb_system_command_{k}")
    prompt_handle(*keybinds["system-command"][k])(cmd)

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

    if completer in global_completers():
        with patch_stdout(raw=True):
            get_console().log(
                "Registered key press", markup.code("".join(keys)), "-",
                markup.command(name), "added to completers",  # fmt: skip
            )
    else:
        with patch_stdout(raw=True):
            get_console().log(
                "Registered key press", markup.code("".join(keys)), "-",
                markup.command(name), "removed from completers",  # fmt: skip
            )


keys_commands = keybinds["completers"]["commands"]  # fmt: skip
@prompt_handle(*keys_commands)
def _(event: "KeyPressEvent") -> None:
    reconfigure_completer(completer=ActiveCompleter.CMD)
    _log_completer_keypress(
        keys_commands,
        "commands",
        ActiveCompleter.CMD,
    )


keys_history = keybinds["completers"]["history"]  # fmt: skip
@prompt_handle(*keys_history)
def _(event: "KeyPressEvent") -> None:
    reconfigure_completer(completer=ActiveCompleter.HISTORY)
    _log_completer_keypress(
        keys_history,
        "history",
        ActiveCompleter.HISTORY,
    )


keys_path = keybinds["completers"]["path"]  # fmt: skip
@prompt_handle(*keys_path)
def _(event: "KeyPressEvent") -> None:
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


for bindings in [PROMPT_BINDINGS, QUERY_BINDINGS]:

    @bindings.add(Keys.Escape, eager=True, filter=is_complete_state)
    def _(event: "KeyPressEvent") -> None:
        buffer = event.app.current_buffer
        state = buffer.complete_state
        if state:
            if state.current_completion:
                buffer.apply_completion(state.current_completion)
                buffer.cancel_completion()
            else:
                buffer.cancel_completion()

    @bindings.add(Keys.ControlSpace)
    def _(event: "KeyPressEvent") -> None:
        buffer = event.app.current_buffer
        if buffer.complete_state:
            buffer.complete_next()
        else:
            buffer.start_completion()


@query_handle(Keys.Tab, eager=True)
def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    document = buffer.document

    if document.cursor_position_col == 0 and document.cursor_position_row == 0:
        buffer.start_completion()
    elif not document.get_word_under_cursor(WORD=True):
        buffer.insert_text("  ")
    elif buffer.complete_state:
        buffer.complete_next()


@query_handle(Keys.ControlQ)
def _(event: "KeyPressEvent") -> None:
    raise KeyboardInterrupt  # query_repl fn will return to main REPL.
