import typing as t
from functools import wraps
from types import FunctionType

import click
from rich import get_console

from lightlike.app.cache import TimeEntryAppData, TimeEntryCache, TimeEntryIdList
from lightlike.app.config import AppConfig
from lightlike.app.dates import now as datetime_now
from lightlike.client import CliQueryRoutines, get_client

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
)

AnyCallable: t.TypeAlias = t.Callable[..., t.Any]

P = t.ParamSpec("P")

routine: AnyCallable = click.make_pass_decorator(CliQueryRoutines, ensure=True)
config: AnyCallable = click.make_pass_decorator(AppConfig, ensure=False)
cache: AnyCallable = click.make_pass_decorator(TimeEntryCache, ensure=True)
appdata: AnyCallable = click.make_pass_decorator(TimeEntryAppData, ensure=True)
id_list: AnyCallable = click.make_pass_decorator(TimeEntryIdList, ensure=True)


def client(fn: AnyCallable) -> AnyCallable:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        return fn(get_client(), *args, **kwargs)

    return inner


def console(fn: AnyCallable) -> AnyCallable:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        return fn(get_console(), *args, **kwargs)

    return inner


def now(fn: AnyCallable) -> AnyCallable:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        return fn(datetime_now(AppConfig().tzinfo), *args, **kwargs)

    return inner


def ctx_group(parents: int) -> t.Callable[..., AnyCallable]:
    def decorator(fn: FunctionType) -> AnyCallable:
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
