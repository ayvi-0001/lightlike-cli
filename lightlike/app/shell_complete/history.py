import typing as t

from more_itertools import unique_everseen
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText
from rich import get_console

from lightlike.internal import appdir
from lightlike.internal.utils import _match_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document


__all__: t.Sequence[str] = ("HistoryCompleter",)


class HistoryCompleter(Completer):
    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterator[Completion]:
        history_strings = appdir.REPL_FILE_HISTORY().load_history_strings()
        history = unique_everseen(list(map(lambda s: s.strip(), history_strings)))
        start_position = -len(document.text_before_cursor)
        console_width = get_console().width

        for match in list(
            filter(lambda l: _match_str(document.text_before_cursor, l), history)
        ):
            if match:
                yield Completion(
                    text=match,
                    start_position=start_position,
                    display=self._display(match, console_width),
                    display_meta=FormattedText([("bold #a49db0", "history")]),
                    style="#a49db0",
                )
            else:
                for line in history:
                    yield Completion(
                        text=line,
                        start_position=start_position,
                        display=self._display(match, console_width),
                        display_meta=FormattedText([("bold #a49db0", "history")]),
                        style="#a49db0",
                    )

    def _display(self, text, console_width) -> str:
        half_console_width = int(console_width / 2)
        return (
            f"{text[:half_console_width]}…" if len(text) > half_console_width else text
        )
