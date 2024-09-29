import typing as t

from prompt_toolkit.completion import (
    Completer,
    DynamicCompleter,
    ThreadedCompleter,
    merge_completers,
)

from lightlike.app.config import AppConfig
from lightlike.internal.enums import ActiveCompleter

__all__: t.Sequence[str] = ("global_completer",)


ACTIVE_COMPLETERS: list[ActiveCompleter] = []


CMD_COMPLETER: Completer | None = None
HISTORY_COMPLETER: Completer | None = None
PATH_COMPLETER: Completer | None = None
EXEC_COMPLETER: Completer | None = None

_COMPLETERS: t.MutableMapping[ActiveCompleter, Completer | None] = {
    ActiveCompleter.CMD: None,
    ActiveCompleter.HISTORY: None,
    ActiveCompleter.PATH: None,
    ActiveCompleter.EXEC: None,
}


def global_completer(
    default_completer: t.Optional[Completer] = None,
) -> ThreadedCompleter:
    return ThreadedCompleter(
        DynamicCompleter(lambda: _get_completer(default_completer))
    )


def global_completers() -> list[ActiveCompleter]:
    global ACTIVE_COMPLETERS
    if not ACTIVE_COMPLETERS:
        default_completers = AppConfig().get("completers", "default", default=["CMD"])
        ACTIVE_COMPLETERS = [getattr(ActiveCompleter, k) for k in default_completers]

    return ACTIVE_COMPLETERS


def _get_completer(
    default_completer: t.Optional[Completer] = None,
) -> Completer:
    global _COMPLETERS
    for c in [
        ActiveCompleter.CMD,
        ActiveCompleter.HISTORY,
        ActiveCompleter.PATH,
        ActiveCompleter.EXEC,
    ]:
        if c in global_completers():
            match c:
                case ActiveCompleter.CMD:
                    assert default_completer
                    if _COMPLETERS[ActiveCompleter.CMD] is None:
                        global CMD_COMPLETER
                        if CMD_COMPLETER is None:
                            CMD_COMPLETER = ThreadedCompleter(default_completer)
                        _COMPLETERS[ActiveCompleter.CMD] = CMD_COMPLETER

                case ActiveCompleter.HISTORY:
                    if _COMPLETERS[ActiveCompleter.HISTORY] is None:
                        global HISTORY_COMPLETER
                        if HISTORY_COMPLETER is None:
                            from .history import HistoryCompleter

                            HISTORY_COMPLETER = t.cast(
                                Completer, ThreadedCompleter(HistoryCompleter())
                            )
                        _COMPLETERS[ActiveCompleter.HISTORY] = HISTORY_COMPLETER

                case ActiveCompleter.PATH:
                    if _COMPLETERS[ActiveCompleter.PATH] is None:
                        global PATH_COMPLETER
                        if PATH_COMPLETER is None:
                            from .path import PathCompleter

                            PATH_COMPLETER = t.cast(
                                Completer, ThreadedCompleter(PathCompleter())
                            )
                        _COMPLETERS[ActiveCompleter.PATH] = PATH_COMPLETER

                case ActiveCompleter.EXEC:
                    if _COMPLETERS[ActiveCompleter.EXEC] is None:
                        global EXEC_COMPLETER
                        if EXEC_COMPLETER is None:
                            from .executable import ExecutableCompleter

                            EXEC_COMPLETER = t.cast(
                                Completer, ThreadedCompleter(ExecutableCompleter())
                            )
                        _COMPLETERS[ActiveCompleter.EXEC] = EXEC_COMPLETER

        elif c in _COMPLETERS:
            _COMPLETERS[c] = None

    return merge_completers([c for c in _COMPLETERS.values() if c])


def reconfigure_completer(completer: ActiveCompleter) -> None:
    global ACTIVE_COMPLETERS
    active_completers = global_completers()

    if completer not in active_completers:
        active_completers.append(completer)
    else:
        active_completers.pop(active_completers.index(completer))

    ACTIVE_COMPLETERS = active_completers
