from pathlib import Path
from typing import Any, Sequence, cast

import rich_click as click
from pytz import all_timezones

from lightlike.app.cache import TomlCache
from lightlike.internal import utils
from lightlike.lib.third_party import _questionary

__all__: Sequence[str] = ("timezone", "edit_params", "weekstart", "report_path")


def timezone(ctx: click.Context, param: click.Parameter, value: str) -> str:
    if value not in all_timezones:
        raise click.BadArgumentUsage(
            message="Unrecognized timezone.", ctx=click.get_current_context()
        )
    return value


def edit_params(locals: dict[str, Any]) -> bool:
    id_sequence = cast(list[str], locals.get("id_sequence"))
    ctx = cast(click.Context, locals.get("ctx"))
    cache = cast(TomlCache, locals.get("cache"))
    editors = cast(Sequence[dict[str, Any]], locals.get("editors"))

    if not id_sequence:
        raise click.UsageError(message="No ID provided.", ctx=ctx)

    elif not editors:
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    if cache._if_any_entries(cache.running_entries, id_sequence):
        raise click.UsageError(
            message="This entry is currently active. Use the command "
            "[code.command]timer[/code.command]:[code.command]update[/code.command] instead.",
            ctx=ctx,
        )
    if cache._if_any_entries(cache.paused_entries, id_sequence):
        raise click.UsageError(
            message="This entry is paused. "
            "Either use commands "
            "[code.command]timer[/code.command]:[code.command]resume[/code.command] -> "
            "[code.command]timer[/code.command]:[code.command]update[/code.command], or "
            "[code.command]timer[/code.command]:[code.command]resume[/code.command] -> "
            "[code.command]timer[/code.command]:[code.command]stop[/code.command] -> "
            "[code.command]timer[/code.command]:[code.command]edit[/code.command].",
            ctx=ctx,
        )

    return True


def report_path(ctx: click.Context, param: click.Parameter, value: str) -> Path | None:
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
        if _questionary.confirm(
            message="This file already exists. Overwrite?",
            auto_enter=True,
        ):
            return path.with_suffix(suffix)
        else:
            raise utils.click_exit
    else:
        if not path.suffix:
            return path.with_suffix(suffix)
        else:
            return path


def weekstart(ctx: click.Context, param: click.Parameter, value: str) -> int:
    match value:
        case "Sunday":
            isoweekday = 0
        case "Monday":
            isoweekday = 1
        case _:
            raise click.BadArgumentUsage(
                message="Invalid week-start date.",
                ctx=click.get_current_context(),
            )

    return isoweekday
