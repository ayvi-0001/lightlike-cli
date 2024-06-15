import typing as t

import rich_click as click
from more_itertools import unique_everseen
from prompt_toolkit.completion import (
    Completer,
    Completion,
    DynamicCompleter,
    ThreadedCompleter,
    merge_completers,
)
from rich import get_console

from lightlike._console import global_completers
from lightlike.app.core import AliasedRichGroup
from lightlike.app.shell_complete.path import PathCompleter
from lightlike.internal import appdir
from lightlike.internal.enums import ActiveCompleter
from lightlike.internal.utils import _match_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

    from lightlike.lib.third_party.click_repl import ClickCompleter

__all__: t.Sequence[str] = ("dynamic_completer", "click_completer")


RG = t.TypeVar("RG", bound=AliasedRichGroup)
RC = t.TypeVar("RC", bound=click.RichContext)

CMD_COMPLETER: Completer | None = None
HISTORY_COMPLETER: Completer | None = None
PATH_COMPLETER: Completer | None = None
_COMPLETERS: t.MutableMapping[ActiveCompleter, Completer | None] = {
    ActiveCompleter.CMD: None,
    ActiveCompleter.PATH: None,
    ActiveCompleter.HISTORY: None,
}

_cast_c: t.Callable[..., Completer] = lambda c: t.cast(Completer, c)


def dynamic_completer(
    default_completer: t.Optional["ClickCompleter[RG, RC]"] = None,
) -> ThreadedCompleter:
    return ThreadedCompleter(
        DynamicCompleter(
            lambda: _cast_c(_get_completer(default_completer)),
        )
    )


def click_completer(cli: RG, ctx: RC) -> "ClickCompleter[RG, RC]":
    from lightlike.lib.third_party.click_repl._completer import ClickCompleter

    return ClickCompleter(cli, ctx)


def _get_completer(
    default_completer: t.Optional["ClickCompleter[RG, RC]"] = None,
) -> Completer:
    global _COMPLETERS
    for c in [
        ActiveCompleter.CMD,
        ActiveCompleter.HISTORY,
        ActiveCompleter.PATH,
    ]:
        if c in global_completers():
            match c:
                case ActiveCompleter.CMD:
                    assert default_completer
                    if not _COMPLETERS[ActiveCompleter.CMD]:
                        global CMD_COMPLETER
                        if not CMD_COMPLETER:
                            CMD_COMPLETER = _cast_c(default_completer)
                        _COMPLETERS[ActiveCompleter.CMD] = CMD_COMPLETER

                case ActiveCompleter.HISTORY:
                    if not _COMPLETERS[ActiveCompleter.HISTORY]:
                        global HISTORY_COMPLETER
                        if not HISTORY_COMPLETER:
                            HISTORY_COMPLETER = _cast_c(HistoryCompleter())
                        _COMPLETERS[ActiveCompleter.HISTORY] = HISTORY_COMPLETER

                case ActiveCompleter.PATH:
                    if not _COMPLETERS[ActiveCompleter.PATH]:
                        global PATH_COMPLETER
                        if not PATH_COMPLETER:
                            PATH_COMPLETER = _cast_c(PathCompleter())
                        _COMPLETERS[ActiveCompleter.PATH] = PATH_COMPLETER

        elif c in _COMPLETERS:
            _COMPLETERS[c] = None

    return merge_completers([v for k, v in _COMPLETERS.items() if v])


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
                    display_meta="history",
                )
            else:
                for line in history:
                    yield Completion(
                        text=line,
                        start_position=start_position,
                        display=self._display(match, console_width),
                        display_meta="history",
                    )

    def _display(self, text, console_width) -> str:
        half_console_width = int(console_width / 2)
        return (
            f"{text[:half_console_width]}…" if len(text) > half_console_width else text
        )
