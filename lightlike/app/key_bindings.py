import sys
from operator import truth
from typing import TYPE_CHECKING, Sequence

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.keys import Keys
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console

from lightlike._console import reconfigure_completer
from lightlike.internal import enums, utils

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyPressEvent

__all__: Sequence[str] = ("PROMPT_BINDINGS", "QUERY_BINDINGS")


PROMPT_BINDINGS = KeyBindings()
prompt_handle = PROMPT_BINDINGS.add


@Condition
def is_complete_state() -> bool:
    return truth(get_app().current_buffer.complete_state)


@prompt_handle(Keys.Escape, eager=True, filter=is_complete_state)
def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    state = buffer.complete_state
    if state:
        if state.current_completion:
            buffer.apply_completion(state.current_completion)
            buffer.cancel_completion()
        else:
            buffer.cancel_completion()


@prompt_handle(Keys.Escape, Keys.Enter)
@utils._nl_start(before=True, after=True)
async def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    cmd = buffer.document.text
    buffer.append_to_history()
    buffer.reset(append_to_history=True)
    buffer.delete_before_cursor(len(cmd))
    utils._nl()
    utils._nl()
    system_command = event.app.run_system_command(cmd, wait_for_enter=False)
    await system_command


@prompt_handle(Keys.ControlSpace)
def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    if buffer.complete_state:
        buffer.complete_next()
    else:
        buffer.start_completion()


@prompt_handle(Keys.ControlQ)
def _(event: "KeyPressEvent") -> None:
    import logging

    from lightlike.app.client import get_client

    get_client().close()
    utils._log().debug("Closed Bigquery client HTTPS connection.")
    utils._log().debug("Exiting gracefully.")
    logging.shutdown()
    sys.exit(0)


@prompt_handle(Keys.F1, eager=True)
@prompt_handle(Keys.ControlF1, eager=True)
def _(event: "KeyPressEvent") -> None:
    reconfigure_completer(completer=enums.ActiveCompleter.CMD)
    with patch_stdout(raw=True):
        get_console().log(
            "Registered KeyPress [code]F1[/code]. "
            "Completer set to [code.command]commands[/code.command].\n"
        )


@prompt_handle(Keys.F2, eager=True)
@prompt_handle(Keys.ControlF2, eager=True)
def _(event: "KeyPressEvent") -> None:
    reconfigure_completer(completer=enums.ActiveCompleter.HISTORY)
    with patch_stdout(raw=True):
        get_console().log(
            "Registered KeyPress [code]F2[/code]. "
            "Completer set to [code.command]history[/code.command].\n"
        )


@prompt_handle(Keys.F3, eager=True)
@prompt_handle(Keys.ControlF3, eager=True)
def _(event: "KeyPressEvent") -> None:
    reconfigure_completer(completer=enums.ActiveCompleter.PATH)
    with patch_stdout(raw=True):
        get_console().log(
            "Registered KeyPress [code]F3[/code]. "
            "Completer set to [code.command]path[/code.command].\n"
        )


@prompt_handle(Keys.F5, eager=True)
@prompt_handle(Keys.ControlF1, Keys.ControlF1, eager=True)
def _(event: "KeyPressEvent") -> None:
    reconfigure_completer(completer=enums.ActiveCompleter.NONE)
    with patch_stdout(raw=True):
        get_console().log(
            "Registered KeyPress [code]F5[/code]. "
            "Completer set to [code.command]none[/code.command].\n"
        )


QUERY_BINDINGS = KeyBindings()
query_handle = QUERY_BINDINGS.add

QUERY_BINDINGS.add("c-w")(get_by_name("backward-kill-word"))


@query_handle(Keys.Escape, eager=True, filter=is_complete_state)
def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    state = buffer.complete_state
    if state:
        if state.current_completion:
            buffer.apply_completion(state.current_completion)
            buffer.cancel_completion()
        else:
            buffer.cancel_completion()


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


@query_handle(Keys.ControlSpace)
def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    if buffer.complete_state:
        buffer.complete_next()
    else:
        buffer.start_completion()


@query_handle(Keys.ShiftDelete)
def _(event: "KeyPressEvent") -> None:
    buffer = event.app.current_buffer
    word_before_cursor = buffer.document.get_word_before_cursor()
    if word_before_cursor:
        buffer.delete_before_cursor(len(word_before_cursor))
    else:
        buffer.delete_before_cursor()
