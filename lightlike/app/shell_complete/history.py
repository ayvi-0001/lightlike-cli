from typing import TYPE_CHECKING, Iterator, Sequence

from more_itertools import unique_everseen
from prompt_toolkit.completion import Completer, Completion

from lightlike.internal import appdir
from lightlike.internal.utils import _match_str

if TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: Sequence[str] = ("HistoryCompleter",)


class HistoryCompleter(Completer):
    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> Iterator[Completion]:
        history_strings = appdir.REPL_FILE_HISTORY.load_history_strings()
        history = unique_everseen(list(map(lambda s: s.strip(), history_strings)))
        start_position = -len(document.text_before_cursor)

        for match in list(
            filter(lambda l: _match_str(document.text_before_cursor, l), history)
        ):
            if match:
                yield Completion(text=match, start_position=start_position)
            else:
                for line in history:
                    yield Completion(text=line, start_position=start_position)
