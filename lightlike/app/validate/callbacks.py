import typing as t
from functools import partial
from inspect import cleandoc
from json import loads
from math import copysign
from operator import getitem, truth
from pathlib import Path

import click
from more_itertools import one
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich.text import Text

from lightlike.app import _questionary
from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.app.dates import parse_date
from lightlike.internal import appdir
from lightlike.internal.appdir import AVAILABLE_TIMEZONES

if t.TYPE_CHECKING:
    from datetime import datetime

__all__: t.Sequence[str] = (
    "current_time_period_flags",
    "datetime_parsed",
    "edit_params",
    "non_running_entry",
    "print_or_output",
    "summary_path",
    "timer_list_cache_idx",
    "timezone",
    "weekstart",
)


def timezone(_ctx: click.Context, _param: click.Parameter, value: str) -> str:
    if value not in AVAILABLE_TIMEZONES:
        raise click.UsageError(
            message="Unrecognized timezone.",
            ctx=click.get_current_context(silent=True),
        )
    return value


def weekstart(_ctx: click.Context, _param: click.Parameter, value: str) -> int:
    match value:
        case "Sunday":
            isoweekday = 0
        case "Monday":
            isoweekday = 1
        case _:
            raise click.UsageError(
                message="Invalid week-start date.",
                ctx=click.get_current_context(silent=True),
            )

    return isoweekday


def datetime_parsed(
    ctx: click.Context,
    _param: click.Parameter,
    value: str,
) -> datetime | None:
    if not value and not ctx.resilient_parsing:
        return None

    if value:
        return parse_date(date=value, tzinfo=AppConfig().tzinfo)

    return None


def edit_params(
    ctx: click.Context,
    params: dict[str, t.Any],
    ids_to_match: list[str],
    *,
    debug: bool,
) -> bool:
    debug and patch_stdout(raw=True)(get_console().log)(
        "[DEBUG]",
        "Edit Params:",
        params,
    )

    if ids_to_match:
        non_running_entry(
            ctx,
            one(filter(lambda p: p.name == "id_options", ctx.command.params)),
            ids_to_match,
        )
    else:
        click.UsageError(message="No ids provided.", ctx=ctx)

    if not any(
        params.get(k) is not None
        for k in ["project", "note", "billable", "start_time", "end_time", "date"]
    ):
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    return True


def non_running_entry(
    ctx: click.Context,
    _param: click.Parameter,
    id_sequence: t.Sequence[str],
) -> t.Sequence[str]:
    cache = TimeEntryCache()
    if cache.exists(cache.running_entries, id_sequence):
        message = Text.assemble(
            "One or more selected entries are running. Instead use command timer:update",
        )
        raise click.UsageError(message=message.markup, ctx=ctx)
    if cache.exists(cache.paused_entries, id_sequence):
        message = Text.assemble(
            cleandoc(
                """
                One or more selected entries are paused.
                Use one of following commands instead:
                    - timer:resume -> timer:update
                    - timer:resume --end / -e -> timer:edit
                    - timer:resume -> timer:stop -> timer:edit
                """,
            ),
        )
        raise click.UsageError(message=message.markup, ctx=ctx)

    return id_sequence


def summary_path(ctx: click.Context, param: click.Parameter, value: str) -> Path | None:
    if not value or ctx.resilient_parsing:
        return None
    if not param.metavar:
        ctx.fail("Cannot determine file type.")

    suffix = f".{param.metavar.lower()}"
    path = Path(value or ".")

    if path.is_dir():
        msg = "Cannot overwrite a directory."
        raise click.BadParameter(msg, ctx=ctx)
    if path.suffix and path.suffix != suffix:
        msg = f"Can only write to {suffix}."
        raise click.BadParameter(msg, ctx=ctx)
    if path.with_suffix(suffix).exists():
        try:
            if _questionary.confirm(
                message="File already exists, overwrite?",
                auto_enter=True,
            ):
                return path.with_suffix(suffix)
            raise click.exceptions.Exit
        except (KeyboardInterrupt, EOFError) as exc:
            raise click.exceptions.Exit from exc
    elif not path.suffix:
        return path.with_suffix(suffix)
    else:
        return path


def print_or_output(
    *,
    output: bool = False,
    print_: bool = False,
    ctx: click.Context | None = None,
) -> bool:
    if not any([output, print_]):
        raise click.UsageError(
            message="At least one of --print / -p or --output / -o must be provided.",
            ctx=ctx,
        )
    return False


def current_time_period_flags(
    *,
    current_week: bool | None,
    current_month: bool | None,
    current_year: bool | None,
    previous_week: bool | None,
    ctx: click.Context | None = None,
) -> bool:
    params = filter(
        truth,
        [current_week, current_month, current_year, previous_week],
    )

    if sum(int(x) for x in params if x is not None) > 1:
        raise click.UsageError(
            message="Provide only one of the following options: "
            "--current-week / -cw | --current-month / -cm | --current-year / -cy",
            ctx=ctx,
        )
    return False


def timer_list_cache_idx(
    ctx: click.Context,
    _param: click.Parameter,
    *,
    value: t.Sequence[int] | bool,
) -> list[str] | None:
    if not value and not ctx.resilient_parsing:
        return None

    if not appdir.TIMER_LIST_CACHE.exists():
        msg = "Timer list cache does not exist."
        raise click.ClickException(msg)

    timer_list_cache = loads(appdir.TIMER_LIST_CACHE.read_text(encoding="utf-8"))

    entry_ids: list[str] = []
    if isinstance(value, bool):
        if value is True:
            entry_ids = list(timer_list_cache.values())
    else:
        keys = list(timer_list_cache.keys())

        idxs = []
        for idx in value:
            adjusted_idx = keys[idx] if copysign(1, idx) == -1 else f"{idx - 1}"
            idxs.append(adjusted_idx)

        entry_ids = list(map(partial(getitem, timer_list_cache), idxs))

    return entry_ids
