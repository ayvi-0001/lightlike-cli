# mypy: disable-error-code="func-returns-value, import-untyped"

import typing as t
from datetime import datetime
from inspect import cleandoc
from json import loads
from operator import truth
from pathlib import Path

import rich_click as click
from more_itertools import one
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich.text import Text

from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.app.dates import parse_date
from lightlike.internal import appdir, utils
from lightlike.lib.third_party import _questionary

__all__: t.Sequence[str] = (
    "timezone",
    "weekstart",
    "datetime_parsed",
    "edit_params",
    "non_running_entry",
    "summary_path",
    "print_or_output",
    "current_time_period_flags",
    "timer_list_cache_exists",
    "timer_list_cache_idx",
)


def timezone(ctx: click.RichContext, param: click.Parameter, value: str) -> str:
    from pytz import all_timezones

    if value not in all_timezones:
        raise click.UsageError(
            message="Unrecognized timezone.",
            ctx=click.get_current_context(silent=True),
        )
    return value


def weekstart(ctx: click.RichContext, param: click.Parameter, value: str) -> int:
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
    ctx: click.RichContext, param: click.Parameter, value: str
) -> datetime | None:
    if not value and not ctx.resilient_parsing:
        return None

    if value:
        return parse_date(value, tzinfo=AppConfig().tz)

    return None


def edit_params(
    ctx: click.RichContext,
    params: dict[str, t.Any],
    ids_to_match: list[str],
    debug: bool,
) -> bool:
    debug and patch_stdout(raw=True)(get_console().log)(
        "[DEBUG]:", "Edit Params:", params
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
        [
            params.get(k) is not None
            for k in ["project", "note", "billable", "start_time", "end_time", "date"]
        ]
    ):
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    return True


def non_running_entry(
    ctx: click.RichContext, param: click.Parameter, id_sequence: t.Sequence[str]
) -> t.Sequence[str] | t.NoReturn:
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
                """
            )
        )
        raise click.UsageError(message=message.markup, ctx=ctx)

    return id_sequence


def summary_path(
    ctx: click.RichContext, param: click.Parameter, value: str
) -> Path | None:
    if not value or ctx.resilient_parsing:
        return None
    if not param.metavar:
        ctx.fail("Cannot determine file type.")

    suffix = f".{param.metavar.lower()}"
    path = Path(value or ".")

    if path.is_dir():
        raise click.BadParameter("Cannot overwrite a directory.", ctx=ctx)
    elif path.suffix and path.suffix != suffix:
        raise click.BadParameter(f"Can only write to {suffix}.", ctx=ctx)
    elif path.with_suffix(suffix).exists():
        try:
            if _questionary.confirm(
                message="File already exists, overwrite?",
                auto_enter=True,
            ):
                return path.with_suffix(suffix)
            else:
                raise utils.click_exit
        except (KeyboardInterrupt, EOFError):
            raise utils.click_exit
    else:
        if not path.suffix:
            return path.with_suffix(suffix)
        else:
            return path


def print_or_output(
    output: bool = False,
    print_: bool = False,
    ctx: click.RichContext | None = None,
) -> bool:
    if not any([output, print_]):
        raise click.UsageError(
            message="At least one of --print / -p or --output / -o must be provided.",
            ctx=ctx,
        )
    return False


def current_time_period_flags(
    current_week: bool | None,
    current_month: bool | None,
    current_year: bool | None,
    previous_week: bool | None,
    ctx: click.RichContext | None = None,
) -> bool:
    params = filter(
        truth,
        [current_week, current_month, current_year, previous_week],
    )

    if sum(list(params)) > 1:  # type: ignore[arg-type]
        raise click.UsageError(
            message="Provide only one of the following options: "
            "--current-week / -cw | --current-month / -cm | --current-year / -cy",
            ctx=ctx,
        )
    return False


def timer_list_cache_exists(
    ctx: click.RichContext, param: click.Parameter, value: t.Any
) -> t.Any:
    if value:
        if appdir.TIMER_LIST_CACHE.exists():
            timer_list_cache = loads(appdir.TIMER_LIST_CACHE.read_text())
            return list(timer_list_cache.values())
        else:
            raise click.ClickException("Timer list cache does not exist.")


def timer_list_cache_idx(
    ctx: click.RichContext, param: click.Parameter, values: t.Sequence[int]
) -> list[str] | None:
    if not values and not ctx.resilient_parsing:
        return None

    if appdir.TIMER_LIST_CACHE.exists():
        timer_list_cache = loads(appdir.TIMER_LIST_CACHE.read_text())
        return [timer_list_cache.get(f"{idx - 1}") for idx in values]
    else:
        raise click.ClickException("Timer list cache does not exist.")
