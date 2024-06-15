import typing as t
from functools import wraps
from types import FunctionType

import rich_click as click
from rich import get_console
from rich import print as rprint
from rich_click import make_pass_decorator

from lightlike.app.cache import TimeEntryAppData, TimeEntryCache, TimeEntryIdList
from lightlike.app.client import get_client, get_console
from lightlike.app.config import AppConfig
from lightlike.app.dates import now as datetime_now
from lightlike.app.routines import CliQueryRoutines
from lightlike.internal import markup

__all__: t.Sequence[str] = (
    "routine",
    "config",
    "cache",
    "appdata",
    "id_list",
    "client",
    "console",
    "now",
    "ctx_group",
    "active_time_entry",
)


P = t.ParamSpec("P")

routine = make_pass_decorator(CliQueryRoutines, ensure=True)
config = make_pass_decorator(AppConfig, ensure=False)
cache = make_pass_decorator(TimeEntryCache, ensure=True)
appdata = make_pass_decorator(TimeEntryAppData, ensure=True)
id_list = make_pass_decorator(TimeEntryIdList, ensure=True)


def client(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        return fn(get_client(), *args, **kwargs)

    return inner


def console(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        return fn(get_console(), *args, **kwargs)

    return inner


def now(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        return fn(datetime_now(AppConfig().tz), *args, **kwargs)

    return inner


def ctx_group(parents: int) -> t.Callable[..., t.Callable[..., t.Any]]:
    def decorator(fn: FunctionType) -> t.Callable[..., t.Any]:
        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            ctx = click.get_current_context()
            ctx_group = [ctx]
            count = parents

            def _get_parent(ctx: click.Context) -> click.Context | None:
                nonlocal count
                if ctx.parent and count != 0:
                    count -= 1
                    return ctx.parent
                return None

            while count:
                parent = _get_parent(ctx)
                if parent:
                    ctx_group.append(parent)
                    ctx = parent

            fn(ctx_group, *args, **kwargs)

        return inner

    return decorator


def active_time_entry(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @cache
    @wraps(fn)
    def inner(cache: TimeEntryCache, *args: P.args, **kwargs: P.kwargs) -> t.Any:
        if not cache:
            rprint(markup.dimmed("There is no active time entry."))
            return None
        else:
            return fn(cache, *args, **kwargs)

    return inner
