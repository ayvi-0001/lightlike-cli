from typing import TYPE_CHECKING, Optional, Sequence, TypeVar, cast

import rich_click as click
from prompt_toolkit.completion import (
    Completer,
    DummyCompleter,
    DynamicCompleter,
    ThreadedCompleter,
)

from lightlike._console import global_completer
from lightlike.app.group import AliasedRichGroup
from lightlike.app.shell_complete.history import HistoryCompleter
from lightlike.app.shell_complete.path import PathCompleter
from lightlike.internal.enums import ActiveCompleter

if TYPE_CHECKING:
    from lightlike.lib.third_party.click_repl import ClickCompleter

__all__: Sequence[str] = ("_dynamic_completer", "_click_completer")


RG = TypeVar("RG", bound=AliasedRichGroup)
RC = TypeVar("RC", bound=click.RichContext)


def _dynamic_completer(
    default_completer: Optional["ClickCompleter[RG, RC]"] = None,
) -> ThreadedCompleter:
    return ThreadedCompleter(
        DynamicCompleter(lambda: _get_completer(default_completer))
    )


def _click_completer(cli: RG, ctx: RC) -> "ClickCompleter[RG, RC]":
    from lightlike.lib.third_party.click_repl._completer import ClickCompleter

    return ClickCompleter(cli, ctx)


def _get_completer(
    default_completer: Optional["ClickCompleter[RG, RC]"] = None,
) -> ThreadedCompleter:
    match global_completer():
        case ActiveCompleter.HISTORY:
            completer = cast(Completer, HistoryCompleter())
        case ActiveCompleter.PATH:
            completer = cast(Completer, PathCompleter())
        case ActiveCompleter.NONE:
            completer = cast(Completer, DummyCompleter())
        case _:
            completer = cast(Completer, default_completer or DummyCompleter())

    return ThreadedCompleter(completer)
