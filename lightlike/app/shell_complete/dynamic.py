import typing as t

import rich_click as click
from prompt_toolkit.completion import (
    Completer,
    DynamicCompleter,
    ThreadedCompleter,
    merge_completers,
)

from lightlike._console import global_completers
from lightlike.app.shell_complete.history import HistoryCompleter
from lightlike.app.shell_complete.path import PathCompleter
from lightlike.internal.enums import ActiveCompleter

if t.TYPE_CHECKING:
    from lightlike.lib.third_party.click_repl import ReplCompleter

__all__: t.Sequence[str] = ("dynamic_completer", "repl_completer")


CMD_COMPLETER: Completer | None = None
HISTORY_COMPLETER: Completer | None = None
PATH_COMPLETER: Completer | None = None
_COMPLETERS: t.MutableMapping[ActiveCompleter, Completer | None] = {
    ActiveCompleter.CMD: None,
    ActiveCompleter.PATH: None,
    ActiveCompleter.HISTORY: None,
}


def dynamic_completer(
    default_completer: t.Optional["ReplCompleter"] = None,
) -> ThreadedCompleter:
    return ThreadedCompleter(
        DynamicCompleter(lambda: t.cast(Completer, _get_completer(default_completer)))
    )


def repl_completer(
    cli: click.Group,
    ctx: click.Context,
    uncaught_exceptions_callable: t.Callable[[Exception], object] | None = None,
) -> "ReplCompleter":
    from lightlike.lib.third_party.click_repl._completer import ReplCompleter

    return ReplCompleter(cli, ctx, uncaught_exceptions_callable)


def _get_completer(
    default_completer: t.Optional["ReplCompleter"] = None,
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
                            CMD_COMPLETER = t.cast(Completer, default_completer)
                        _COMPLETERS[ActiveCompleter.CMD] = CMD_COMPLETER

                case ActiveCompleter.HISTORY:
                    if not _COMPLETERS[ActiveCompleter.HISTORY]:
                        global HISTORY_COMPLETER
                        if not HISTORY_COMPLETER:
                            HISTORY_COMPLETER = t.cast(Completer, HistoryCompleter())
                        _COMPLETERS[ActiveCompleter.HISTORY] = HISTORY_COMPLETER

                case ActiveCompleter.PATH:
                    if not _COMPLETERS[ActiveCompleter.PATH]:
                        global PATH_COMPLETER
                        if not PATH_COMPLETER:
                            PATH_COMPLETER = t.cast(Completer, PathCompleter())
                        _COMPLETERS[ActiveCompleter.PATH] = PATH_COMPLETER

        elif c in _COMPLETERS:
            _COMPLETERS[c] = None

    return merge_completers([v for k, v in _COMPLETERS.items() if v])
