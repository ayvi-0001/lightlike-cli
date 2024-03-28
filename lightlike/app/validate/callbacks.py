from operator import truth
from pathlib import Path
from typing import Any, Sequence, cast

import rich_click as click
from pytz import all_timezones
from rich.text import Text

from lightlike.app.cache import TomlCache
from lightlike.internal import markup, utils
from lightlike.lib.third_party import _questionary

__all__: Sequence[str] = (
    "timezone",
    "edit_params",
    "raise_if_cached_entry",
    "weekstart",
    "report_path",
)


def timezone(ctx: click.Context, param: click.Parameter, value: str) -> str:
    if value not in all_timezones:
        raise click.BadArgumentUsage(
            message="Unrecognized timezone.", ctx=click.get_current_context()
        )
    return value


def edit_params(ctx: click.Context, cache: TomlCache, params: dict[str, Any]) -> bool:
    id_sequence = cast(list[str], params.get("id_sequence"))

    if not id_sequence:
        raise click.UsageError(message="No ID provided.", ctx=ctx)
    elif not any(
        [
            truth(params.get("project")),
            truth(params.get("note")),
            truth(params.get("billable")),
            truth(params.get("start")),
            truth(params.get("end")),
            truth(params.get("date")),
        ]
    ):
        raise click.UsageError(message="No fields selected.", ctx=ctx)

    raise_if_cached_entry(ctx, cache, id_sequence)
    return True


def raise_if_cached_entry(
    ctx: click.Context, cache: TomlCache, id_sequence: list[str]
) -> None:
    if cache._if_any_entries(cache.running_entries, id_sequence):
        raise click.UsageError(
            message=Text.assemble(
                "This entry is currently active. Use the command ",
                markup.code_command_sequence("timer:update", ":"), " instead.",  # fmt: skip
            ).markup,
            ctx=ctx,
        )
    if cache._if_any_entries(cache.paused_entries, id_sequence):
        raise click.UsageError(
            message=Text.assemble(
                # fmt: off
                "This entry is paused. Either use commands ",
                markup.code_command_sequence("timer:resume", ":"), " -> ",
                markup.code_command_sequence("timer:update", ":"), ", or ",
                markup.code_command_sequence("timer:resume", ":"), " -> ",
                markup.code_command_sequence("timer:stop", ":"), " -> ",
                markup.code_command_sequence("timer:edit", ":"), ".",
                # fmt: on
            ).markup,
            ctx=ctx,
        )


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
