import logging
import os
import re
import typing as t
from contextlib import ContextDecorator, suppress
from functools import partial, reduce, wraps
from operator import getitem, truth
from pathlib import Path
from time import perf_counter_ns
from types import FunctionType

import click
import rtoml
from fuzzyfinder import fuzzyfinder
from prompt_toolkit.application import get_app, in_terminal
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich import print as rprint
from rich.console import NewLine

from lightlike.internal import markup

__all__: t.Sequence[str] = (
    "exit_cmd_on_interrupt",
    "handle_keyboard_interrupt",
    "nl",
    "nl_async",
    "nl_start",
    "get_local_timezone_string",
    "identical_vectors",
    "pretty_print_exception",
    "log_exception",
    "prerun_autocomplete",
    "regexp_replace",
    "format_toml",
    "reduce_keys",
    "alter_str",
    "split_and_alter_str",
    "match_str",
    "ns_time_diff",
    "update_dict",
    "print_message_and_clear_buffer",
    "file_empty_or_not_exists",
    "merge_default_dict_into_current_dict",
)


P = t.ParamSpec("P")


class exit_cmd_on_interrupt(ContextDecorator):
    def __enter__(self) -> t.Self:
        try:
            return self
        except (KeyboardInterrupt, EOFError) as error:
            raise click.exceptions.Exit() from error

    def __exit__(self, *exc: t.Any) -> None: ...


def handle_keyboard_interrupt(
    callback: t.Callable[..., t.Any] | None = None,
) -> t.Callable[..., t.Callable[..., t.Any]]:
    def decorator(fn: FunctionType) -> t.Callable[..., t.Any]:
        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            try:
                return fn(*args, **kwargs)
            except (KeyboardInterrupt, EOFError) as error:
                if callback and callable(callback):
                    return callback()
                else:
                    if isinstance(error, KeyboardInterrupt):
                        rprint(markup.dimmed("Command killed by keyboard interrupt."))
                    elif isinstance(error, EOFError):
                        rprint(markup.dimmed("End of file. No input."))
                    return None

        return inner

    return decorator


nl: t.Callable[..., None] = partial(rprint, NewLine())


async def nl_async() -> None:
    with suppress(Exception):
        async with in_terminal():
            nl()


def nl_start(
    after: bool = False, before: bool = False
) -> t.Callable[..., t.Callable[..., t.Any]]:
    def decorator(fn: FunctionType) -> t.Callable[..., t.Any]:
        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            before and nl()
            r = fn(*args, **kwargs)
            after and nl()
            return r

        return inner

    return decorator


@t.overload
def get_local_timezone_string(default: str) -> str: ...


@t.overload
def get_local_timezone_string(default: None = None) -> str | None: ...


def get_local_timezone_string(default: str | None = None) -> str | None:
    if os.name == "nt":
        from tzlocal import get_localzone_name

        default_timezone = get_localzone_name()
    else:
        from tzlocal.unix import _get_localzone_name

        default_timezone = _get_localzone_name()

    return default_timezone or default


def identical_vectors(l1: list[t.Any], l2: list[t.Any]) -> bool:
    return reduce(
        lambda b1, b2: b1 and b2,
        map(lambda e1, e2: e1 == e2, l1, l2),
        True,
    )


def pretty_print_exception(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        try:
            return fn(*args, **kwargs)
        except Exception:
            get_console().print_exception(
                max_frames=1,
                show_locals=True,
                word_wrap=True,
            )

    return inner


def log_exception(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> t.Any:
        try:
            return fn(*args, **kwargs)
        except Exception as error:
            logging.error(f"{error}")

    return inner


def prerun_autocomplete() -> None:
    app = get_app()
    b = app.current_buffer
    if b.complete_state:
        b.complete_next()
    else:
        b.start_completion(select_first=False)


def regexp_replace(patterns: t.Mapping[str, str | None], text: str) -> str:
    mapped: dict[str, str] = dict((re.escape(k), v or "") for k, v in patterns.items())
    pattern: re.Pattern[str] = re.compile("|".join(mapped.keys()))
    escape: t.Callable[..., str] = lambda m: mapped[re.escape(m.group(0))]
    replaced: str = pattern.sub(escape, text)
    return replaced


def format_toml(toml_obj: t.MutableMapping[str, t.Any]) -> str:
    toml_patterns = {
        '"\n[': '"\n\n[',
        "true\n[": "true\n\n[",
        "false\n[": "false\n\n[",
        "]\n[": "]\n\n[",
        "\"'": '"',
        "'\"": '"',
    }
    return regexp_replace(toml_patterns, rtoml.dumps(toml_obj))


def reduce_keys(
    *keys: t.Sequence[str], sequence: t.Any, default: t.Optional[t.Any] = None
) -> t.Any:
    try:
        return reduce(getitem, [*keys], sequence)
    except KeyError:
        return default


RE_QUOTE: re.Pattern[str] = re.compile(r"(\"|')")
RE_PARENTHESIS: re.Pattern[str] = re.compile(r"(\(|\))")


@t.overload
def alter_str(
    string: t.Any,
    split: str,
    strip: bool = False,
    lower: bool = False,
    strip_quotes: bool = False,
    strip_parenthesis: bool = False,
    add_quotes: bool = False,
) -> list[str]: ...


@t.overload
def alter_str(
    string: t.Any,
    split: None = None,
    strip: bool = False,
    lower: bool = False,
    strip_quotes: bool = False,
    strip_parenthesis: bool = False,
    add_quotes: bool = False,
) -> str: ...


def alter_str(
    string: t.Any,
    split: str | None = None,
    strip: bool = False,
    lower: bool = False,
    strip_quotes: bool = False,
    strip_parenthesis: bool = False,
    add_quotes: bool = False,
) -> str | list[str]:
    if not isinstance(string, str):
        string = f"{string}"

    if t.TYPE_CHECKING:
        assert isinstance(string, str)

    if lower:
        string = string.lower()
    if strip_quotes:
        string = re.sub(RE_QUOTE, "", string)
    if strip_parenthesis:
        string = re.sub(RE_PARENTHESIS, "", string)
    if strip:
        string = string.strip()
    if add_quotes:
        string = f'"{string}"'

    if split:
        return string.split(split)
    else:
        return string


def split_and_alter_str(
    string: str,
    delimeter: str = " ",
    strip: bool = False,
    lower: bool = False,
    strip_quotes: bool = True,
    filter_null_strings: bool = True,
    filter_fns: list[t.Callable[..., t.Any]] = [],
    map_fns: list[t.Callable[..., t.Any]] = [],
) -> list[str]:
    string_args: list[str] = string.split(delimeter)
    iter_map_fn: list[t.Callable[..., t.Any]] = []

    if strip:
        iter_map_fn.append(str.strip)
    if lower:
        iter_map_fn.append(str.lower)
    if strip_quotes:
        iter_map_fn.append(lambda s: RE_QUOTE.sub("", s))
    if map_fns:
        for fn in map_fns:
            iter_map_fn.append(fn)

    mapped_args = reduce(lambda s, fn: [*map(fn, s)], iter_map_fn, string_args)

    if filter_null_strings:
        filter_fns.append(lambda s: s != "")

    if filter_fns:
        filtered_args = reduce(lambda x, y: [*map(y, x)], filter_fns, mapped_args)
        return filtered_args

    else:
        return mapped_args


def match_str(
    string_to_check: t.Any,
    string_to_match: t.Any,
    strip_quotes: bool = False,
    strip_parenthesis: bool = False,
    strip: bool = False,
    case_sensitive: bool = False,
    method: t.Literal["in", "fuzzy", "re", "startswith", "endswith"] = "in",
    replace_patterns: t.Mapping[str, str] | None = None,
) -> bool:
    if not isinstance(string_to_check, str):
        string_to_check = f"{string_to_check}"
    if not isinstance(string_to_match, str):
        string_to_match = f"{string_to_match}"

    if t.TYPE_CHECKING:
        assert isinstance(string_to_check, str)
        assert isinstance(string_to_match, str)

    if not case_sensitive:
        string_to_check = string_to_check.lower()
        string_to_match = string_to_match.lower()
    if strip_quotes:
        string_to_check = re.sub(RE_QUOTE, "", string_to_check)
        string_to_match = re.sub(RE_QUOTE, "", string_to_match)
    if strip_parenthesis:
        string_to_check = re.sub(RE_PARENTHESIS, "", string_to_check)
        string_to_match = re.sub(RE_PARENTHESIS, "", string_to_match)
    if strip:
        string_to_check = string_to_check.strip()
        string_to_match = string_to_match.strip()
    if replace_patterns:
        if not isinstance(replace_patterns, dict):
            raise TypeError("Patterns must be a mapping.")

        string_to_check = regexp_replace(
            patterns=replace_patterns, text=string_to_check
        )
        string_to_match = regexp_replace(
            patterns=replace_patterns, text=string_to_match
        )

    match method:
        case "in":
            return string_to_check in string_to_match
        case "fuzzy":
            return truth(fuzzyfinder(string_to_check, string_to_match))
        case "re":
            return truth(re.match(string_to_check, string_to_match))
        case "startswith":
            return string_to_match.startswith(string_to_check)
        case "endswith":
            return string_to_match.endswith(string_to_check)
        case _:
            raise ValueError("Invalid method for string match.")

    return False


def ns_time_diff(ns: int) -> float:
    return round((perf_counter_ns() - ns) * 1.0e-9, 6)


def update_dict(
    original: dict[str, t.Any], updates: dict[str, t.Any]
) -> dict[str, t.Any]:
    for __key, __val in updates.items():
        if isinstance(__val, dict):
            original[__key] = update_dict(original.get(__key, {}), __val)
        else:
            original[__key] = __val
    return original


def merge_default_dict_into_current_dict(
    current: dict[str, t.Any],
    default: dict[str, t.Any],
    key_path: str | None = None,
    paths: list[str] | None = None,
    update_paths: list[str] | None = None,
    force_update_paths: list[str] | None = None,
) -> dict[str, t.Any]:
    paths = paths or []
    for k, v in default.items():
        current_path = "%s%s" % (f"{key_path}." if key_path else "", k)
        paths.append(current_path)

        if isinstance(v, dict):
            current[k] = merge_default_dict_into_current_dict(
                current.get(k, {}),
                v,
                key_path=current_path,
                paths=paths,
                update_paths=update_paths,
                force_update_paths=force_update_paths,
            )
        else:
            k_in_update_paths = current_path in (update_paths or [])
            k_in_force_update_paths = current_path in (force_update_paths or [])
            if not any([k_in_update_paths, k_in_force_update_paths]):
                continue

            if k_in_force_update_paths:
                current[k] = v
            elif k_in_update_paths:
                if k in current:
                    if any([current[k] is None, current[k] == "null"]):
                        current[k] = v
                else:
                    current[k] = v

    return current


def print_message_and_clear_buffer(message: str) -> None:
    with patch_stdout(raw=True):
        rprint(markup.dimmed(f"{message}."))
        get_app().current_buffer.text = ""


def file_empty_or_not_exists(path: Path) -> bool:
    return not path.exists() ^ (path.exists() and path.read_text().splitlines() == [""])
