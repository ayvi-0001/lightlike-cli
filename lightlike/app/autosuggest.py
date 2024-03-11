from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Sequence

from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.eventloop.utils import run_in_executor_with_context
from prompt_toolkit.history import History

from lightlike.internal.utils import _match_str

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.document import Document

__all__: Sequence[str] = ("_threaded_autosuggest",)


def _threaded_autosuggest(suggestions: list[str]) -> ThreadedAutoSuggest:
    return ThreadedAutoSuggest(ListAutoSuggest(ListHistory(suggestions)))


class ListHistory(History):
    def __init__(self, history_strings: list[str]) -> None:
        super().__init__()
        self._storage = history_strings

    def load_history_strings(self) -> Iterable[str]:
        yield from self._storage[::-1]

    def store_string(self, string: str) -> None:
        self._storage.append(string)

    def get_strings(self) -> list[str]:
        return self._storage[::-1]


class ListAutoSuggest(AutoSuggest):
    def __init__(self, history: History) -> None:
        self.history = history

    def get_suggestion(
        self, buffer: "Buffer", document: "Document"
    ) -> Suggestion | None:
        text = document.text.rsplit("\n", 1)[-1]

        for string in reversed(list(self.history.get_strings())):
            for line in reversed(string.splitlines()):
                if _match_str(text, line, method="startswith"):
                    return Suggestion(line[len(text) :])

        return None


class ThreadedAutoSuggest(AutoSuggest):
    def __init__(self, auto_suggest: AutoSuggest) -> None:
        self.auto_suggest = auto_suggest

    def get_suggestion(self, buff: "Buffer", document: "Document") -> Suggestion | None:
        return self.auto_suggest.get_suggestion(buff, document)

    async def get_suggestion_async(
        self, buff: "Buffer", document: "Document"
    ) -> Suggestion | None:
        def run_get_suggestion_thread() -> Suggestion | None:
            return self.get_suggestion(buff, document)

        return await run_in_executor_with_context(run_get_suggestion_thread)
