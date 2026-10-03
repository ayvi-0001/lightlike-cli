import typing as t
from functools import wraps

import click
from rich import get_console

from lightlike.app.cache import TimeEntryAppData, TimeEntryCache, TimeEntryIdList
from lightlike.app.config import AppConfig
from lightlike.app.dates import now as datetime_now
from lightlike.client import CliQueryRoutines, get_client

if t.TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from types import FunctionType

    from google.cloud.bigquery import Client
    from rich.console import Console

__all__: t.Sequence[str] = (
    "appdata",
    "cache",
    "client",
    "config",
    "console",
    "ctx_group",
    "id_list",
    "now",
    "routine",
)

type AnyCallable = t.Callable[..., t.Any]


routine: AnyCallable = click.make_pass_decorator(CliQueryRoutines, ensure=True)
config: AnyCallable = click.make_pass_decorator(AppConfig, ensure=False)
cache: AnyCallable = click.make_pass_decorator(TimeEntryCache, ensure=True)
appdata: AnyCallable = click.make_pass_decorator(TimeEntryAppData, ensure=True)
id_list: AnyCallable = click.make_pass_decorator(TimeEntryIdList, ensure=True)


def client[**P, R](fn: Callable[t.Concatenate[Client, P], R]) -> Callable[P, R]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(get_client(), *args, **kwargs)

    return inner


def console[**P, R](fn: Callable[t.Concatenate[Console, P], R]) -> Callable[P, R]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(get_console(), *args, **kwargs)

    return inner


def now[**P, R](fn: Callable[t.Concatenate[datetime, P], R]) -> Callable[P, R]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(datetime_now(AppConfig().tzinfo), *args, **kwargs)

    return inner


def ctx_group[**P, R](parents: int) -> t.Callable[[FunctionType], Callable[P, R | None]]:
    def decorator(fn: FunctionType) -> Callable[P, R | None]:
        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> R | None:
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
