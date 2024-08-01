import typing as t

from more_itertools import unique_everseen
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import ThreadedHistory
from rich import get_console

from lightlike.internal import appdir
from lightlike.internal.utils import _match_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document


__all__: t.Sequence[str] = ("HistoryCompleter",)


class HistoryCompleter(Completer):
    style: str = "#a49db0"
    file_history: ThreadedHistory = appdir.REPL_FILE_HISTORY()

    def __init__(self, max_length_string: int | None = None) -> None:
        super().__init__()
        self.max_length_string = max_length_string

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterator[Completion]:
        try:
            history_strings = self.file_history.load_history_strings()
            history = unique_everseen(list(map(lambda s: s.strip(), history_strings)))
            start_position = -len(document.text_before_cursor)
            console_width = get_console().width

            match_word_before_cursor = lambda l: _match_str(
                document.text_before_cursor, l
            )
            matches = list(filter(match_word_before_cursor, history))
            display_meta = f"history{' ' * int(((console_width / 3) * 2) - 20)}"

            if not self.max_length_string:
                self.max_length_string = max(
                    [len(self._display(m, console_width)) for m in matches]
                )

            for match in matches:
                yield Completion(
                    text=match,
                    start_position=start_position,
                    display=self._display(match, console_width),
                    display_meta=FormattedText([(f"bold {self.style}", display_meta)]),
                    style=f"{self.style}",
                )
        except:
            yield from []

    def _display(self, text: str, console_width: int) -> str:
        half_console_width = int(console_width / 3)
        if len(text) > half_console_width:
            return f"{text[:half_console_width]}…"
        else:
            return text
