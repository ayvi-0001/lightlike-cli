import sys
import typing as t
from operator import truth

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

__all__: t.Sequence[str] = ("PROMPT_BINDINGS", "QUERY_BINDINGS")


QUERY_BINDINGS = KeyBindings()
query_handle = QUERY_BINDINGS.add


@Condition
def is_complete_state() -> bool:
    return truth(get_app().current_buffer.complete_state)


@query_handle(Keys.Escape, eager=True, filter=is_complete_state)
def _(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    state = buffer.complete_state
    if state:
        if state.current_completion:
            buffer.apply_completion(state.current_completion)
            buffer.cancel_completion()
        else:
            buffer.cancel_completion()


@query_handle(Keys.ControlSpace)
def _(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    if buffer.complete_state:
        buffer.complete_next()
    else:
        buffer.start_completion()


@query_handle(Keys.Tab, eager=True)
def _(event: KeyPressEvent) -> None:
    buffer = event.app.current_buffer
    document = buffer.document

    if document.cursor_position_col == 0 and document.cursor_position_row == 0:
        buffer.start_completion()
    elif not document.get_word_under_cursor(WORD=True):
        buffer.insert_text("  ")
    elif buffer.complete_state:
        buffer.complete_next()


@query_handle(Keys.ControlQ)
def _(event: KeyPressEvent) -> None:
    sys.exit(0)


@query_handle("[", "A")
def _(event: KeyPressEvent) -> None:
    event.current_buffer.auto_up()


@query_handle("[", "B")
def _(event: KeyPressEvent) -> None:
    event.current_buffer.auto_down()


@query_handle("[", "D")
def _(event: KeyPressEvent) -> None:
    event.current_buffer.cursor_left()


@query_handle("[", "C")
def _(event: KeyPressEvent) -> None:
    event.current_buffer.cursor_right()
