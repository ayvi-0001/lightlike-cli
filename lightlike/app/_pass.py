from __future__ import annotations

import functools
from functools import update_wrapper
from types import FunctionType
from typing import Any, Callable, ParamSpec, Sequence

import rich_click as click
from rich import get_console
from rich import print as rprint
from rich_click import make_pass_decorator

from lightlike.app.cache import EntryAppData, EntryIdList, TomlCache
from lightlike.app.client import get_client, get_console
from lightlike.app.config import AppConfig
from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = (
    "routine",
    "config",
    "cache",
    "appdata",
    "id_list",
    "console",
    "client",
    "ctx_group",
    "active_time_entry",
    "confirm_options",
)


P = ParamSpec("P")

routine = make_pass_decorator(CliQueryRoutines, ensure=True)
config = make_pass_decorator(AppConfig, ensure=False)
cache = make_pass_decorator(TomlCache, ensure=True)
appdata = make_pass_decorator(EntryAppData, ensure=True)
id_list = make_pass_decorator(EntryIdList, ensure=True)


def client(fn: Callable[..., Any]) -> Callable[..., Any]:
    def new_func(*args: P.args, **kwargs: P.kwargs) -> Any:
        return fn(get_client(), *args, **kwargs)

    return update_wrapper(new_func, fn)


def console(fn: Callable[..., Any]) -> Callable[..., Any]:
    def new_func(*args: P.args, **kwargs: P.kwargs) -> Any:
        return fn(get_console(), *args, **kwargs)

    return update_wrapper(new_func, fn)


def ctx_group(parents: int = 1) -> Callable[..., Callable[..., Any]]:
    def decorator(fn: FunctionType) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> Any:
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


def active_time_entry(fn: Callable[..., Any]) -> Callable[..., Any]:
    @cache
    @functools.wraps(fn)
    def inner(cache: TomlCache, *args: P.args, **kwargs: P.kwargs) -> Any:
        if not cache:
            rprint("[d]There is no active time entry.")
            return None
        else:
            return fn(cache, *args, **kwargs)

    return inner


def confirm_options(fn) -> Callable[..., Any]:
    @click.option(
        "-c",
        "--confirm",
        hidden=True,
        is_flag=True,
        help="Accept all prompts",
    )
    @click.option(
        "-y",
        "--yes",
        hidden=True,
        is_flag=True,
        help="Accept all prompts",
    )
    @functools.wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> None:
        fn(*args, **kwargs)

    return inner
