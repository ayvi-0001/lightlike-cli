import contextlib
import functools
import logging
import re
import typing as t
from contextlib import suppress
from datetime import date, time, timedelta
from decimal import Decimal
from functools import reduce
from types import FunctionType

import rtoml
from prompt_toolkit.application import get_app, in_terminal
from rich import get_console
from rich import print as rprint
from rich.console import NewLine

from lightlike.__about__ import __appdir__, __appname_sc__
from lightlike.internal import appdir

if t.TYPE_CHECKING:
    from logging import Logger


__all__: t.Sequence[str] = (
    "_log",
    "_handle_keyboard_interrupt",
    "_identical_vectors",
    "pretty_print_exception",
    "_prerun_autocomplete",
    "_regexp_replace",
    "_nl",
    "_nl_async",
    "_nl_start",
    "_format_toml",
    "_alter_str",
    "_split_and_alter_str",
    "_match_str",
    "timer",
    "update_dict",
    "_sec_to_time_parts",
    "ifbool",
    "print_updated_val",
)


P = t.ParamSpec("P")


logging.basicConfig(
    level=logging.DEBUG,
    filename=appdir.LOG.as_posix(),
    filemode="a",
    format=(
        "[%(asctime)s] "
        "fn(%(funcName)s) "
        "{%(pathname)s:%(lineno)d} "
        "%(levelname)s - %(message)s"
    ),
    datefmt="%m-%d %H:%M:%S",
)


def _log() -> "Logger":
    return logging.getLogger(__appname_sc__)


def _handle_keyboard_interrupt(
    callback: t.Callable[..., t.Any] | None = None
) -> t.Callable[..., t.Callable[..., t.Any]]:
    def decorator(fn: FunctionType) -> t.Callable[..., t.Any]:
        @functools.wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            try:
                return fn(*args, **kwargs)
            except (KeyboardInterrupt, EOFError):
                if callback and callable(callback):
                    callback()
                else:
                    rprint("[d]Canceled prompt.")
                return

        return inner

    return decorator


_nl: t.Callable[..., None] = lambda: rprint(NewLine())


async def _nl_async() -> None:
    with suppress(Exception):
        async with in_terminal():
            _nl()


def _nl_start(
    after: bool = False, before: bool = False
) -> t.Callable[..., t.Callable[..., t.Any]]:
    def decorator(fn: FunctionType) -> t.Callable[..., t.Any]:
        @functools.wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            _nl() if before else ...
            r = fn(*args, **kwargs)
            _nl() if after else ...
            return r

        return inner

    return decorator


def _identical_vectors(l1: list[t.Any], l2: list[t.Any]) -> bool:
    return reduce(
        lambda b1, b2: b1 and b2,
        map(lambda e1, e2: e1 == e2, l1, l2),
        True,
    )


def pretty_print_exception(fn) -> t.Callable[..., t.Any]:
    @functools.wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            return fn(*args, **kwargs)
        except Exception:
            with get_console() as console:
                console.print_exception(
                    show_locals=True,
                    width=console.width,
                )

    return inner


def _prerun_autocomplete() -> None:
    app = get_app()
    b = app.current_buffer
    if b.complete_state:
        b.complete_next()
    else:
        b.start_completion(select_first=False)


def _regexp_replace(patterns: t.Mapping[str, str], text: str) -> str:
    mapped: dict[str, str] = dict((re.escape(k), v) for k, v in patterns.items())
    pattern: re.Pattern = re.compile("|".join(mapped.keys()))
    escape: t.Callable[..., str] = lambda m: mapped[re.escape(m.group(0))]
    return pattern.sub(escape, text)


def _format_toml(toml_obj: t.MutableMapping[str, t.Any]) -> str:
    toml_patterns = {
        '"\n[': '"\n\n[',
        "true\n[": "true\n\n[",
        "false\n[": "false\n\n[",
        "]\n[": "]\n\n[",
        "\"'": '"',
        "'\"": '"',
    }
    return _regexp_replace(toml_patterns, rtoml.dumps(toml_obj))


def _alter_str(
    string: t.Any,
    strip: bool = False,
    lower: bool = False,
    strip_quotes: bool = False,
    strip_parenthesis: bool = False,
    add_quotes: bool = False,
) -> str:
    if not isinstance(string, str):
        string = f"{string}"

    if lower:
        string = string.lower()
    if strip_quotes:
        string = re.compile(r"(\"|')").sub("", string)
    if strip_parenthesis:
        string = re.compile(r"(\(|\))").sub("", string)
    if strip:
        string = string.strip()
    if add_quotes:
        string = f'"{string}"'

    return string


def _split_and_alter_str(
    string: str,
    delimeter: str = " ",
    strip: bool = False,
    lower: bool = False,
    strip_quotes: bool = True,
    filter_null_strings: bool = True,
    filter_fns: t.Sequence[t.Callable[..., t.Any]] | None = None,
    map_fns: t.Sequence[t.Callable[..., t.Any]] | None = None,
) -> list[str]:
    string_args: list[str] = string.split(delimeter)

    iter_map_fn: list[t.Callable[..., t.Any]] = []

    if strip:
        iter_map_fn.append(str.strip)
    if lower:
        iter_map_fn.append(str.lower)
    if strip_quotes:
        iter_map_fn.append(lambda s: re.compile(r"(\"|')").sub("", s))
    if map_fns:
        for fn in map_fns:
            iter_map_fn.append(fn)

    mapped_args = reduce(lambda s, fn: [*map(fn, s)], iter_map_fn, string_args)

    if filter_fns:
        iter_filter_fn: list[t.Callable[..., t.Any]] = []
        if filter_null_strings:
            iter_filter_fn.append(lambda s: s != "")
        if filter_fns:
            for fn in filter_fns:
                iter_filter_fn.append(fn)

        filtered_args = reduce(lambda x, y: [*map(y, x)], filter_fns, mapped_args)

        return filtered_args

    else:
        return mapped_args


def _match_str(
    string_to_check: t.Any,
    string_to_match: t.Any,
    strip_quotes: bool = False,
    strip_parenthesis: bool = False,
    strip: bool = False,
    case_sensitive: bool = False,
    method: t.Literal["in", "startswith", "endswith"] = "in",
    replace_patterns: t.Mapping[str, str] | None = None,
) -> bool:
    if not isinstance(string_to_check, str):
        string_to_check = f"{string_to_check}"
    if not isinstance(string_to_match, str):
        string_to_match = f"{string_to_match}"

    if not case_sensitive:
        string_to_check = string_to_check.lower()
        string_to_match = string_to_match.lower()
    if strip_quotes:
        string_to_check = re.compile(r"(\"|')").sub("", string_to_check)
        string_to_match = re.compile(r"(\"|')").sub("", string_to_match)
    if strip_parenthesis:
        string_to_check = re.compile(r"(\(|\))").sub("", string_to_check)
        string_to_match = re.compile(r"(\(|\))").sub("", string_to_match)
    if strip:
        string_to_check = string_to_check.strip()
        string_to_match = string_to_match.strip()
    if replace_patterns:
        if not isinstance(replace_patterns, t.Mapping):
            raise TypeError("Patterns must be a mapping.")

        string_to_check = _regexp_replace(
            patterns=replace_patterns, text=string_to_check
        )
        string_to_match = _regexp_replace(
            patterns=replace_patterns, text=string_to_match
        )

    match method:
        case "in":
            return string_to_check in string_to_match
        case "startswith":
            return string_to_match.startswith(string_to_check)
        case "endswith":
            return string_to_match.endswith(string_to_check)
        case _:
            raise ValueError("Invalid method for string match.")


@contextlib.contextmanager
def timer(subject: str = "time") -> t.Generator[None, None, None]:
    from time import time

    start = time()
    yield
    elapsed = time() - start
    elapsed_ms = elapsed * 1000
    print(f"{subject} elapsed {elapsed_ms:.1f}ms")


def update_dict(
    original: t.MutableMapping[str, t.Any],
    updates: t.MutableMapping[str, t.Any],
    ignore: t.Sequence[str] | None = None,
) -> t.MutableMapping[str, t.Any]:
    for __key, __val in updates.items():
        if ignore and __key in ignore:
            original[__key] = __val
        if __key not in original:
            continue
        if isinstance(__val, t.MutableMapping):
            original[__key] = update_dict(original.get(__key, {}), __val)
        else:
            original[__key] = __val
    return original


def _sec_to_time_parts(seconds: Decimal) -> tuple[int, int, int]:
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return int(hours), int(minutes), int(seconds)


def print_updated_val(
    key: str, val: t.Any, prefix: str | None = "[#00ff00]Saved[/#00ff00]."
) -> None:
    markup: str = ""
    if isinstance(val, bool) or val in (1, 0):
        markup = "repr.bool_true" if bool(val) else "repr.bool_false"
    elif isinstance(val, date):
        markup = "iso8601.date"
    elif isinstance(val, (time, timedelta)):
        markup = "iso8601.time"
    elif isinstance(val, str):
        markup = "repr.str"
    elif not val or val in ("null", "None"):
        markup = "italic #888888"
    elif isinstance(val, int):
        markup = "repr.number"
    else:
        markup = "code"

    message = "".join(
        [
            f"{prefix} " if prefix else "",
            "Setting ",
            f"[scope.key]{key}[/scope.key] ",
            "to ",
            f"[{markup}]{val}[/{markup}].",
        ]
    )

    rprint(message)
