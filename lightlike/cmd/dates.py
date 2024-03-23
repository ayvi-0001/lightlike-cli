from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

import rich_click as click
from rich.text import Text

from lightlike.app import _get
from lightlike.app.config import AppConfig
from lightlike.app.prompt import PromptFactory
from lightlike.internal import markup

__all__: Sequence[str] = ("_parse_date_range_flags", "_get_current_week_range")


@dataclass
class DateParams:
    start: datetime
    end: datetime
    duration: timedelta
    total_seconds: int


def _parse_date_range_flags(
    start: datetime | str | None = None, end: datetime | str | None = None
) -> DateParams:
    if not start:
        start_local = PromptFactory.prompt_for_date("(start-date)")
    else:
        start_local = PromptFactory._parse_date(f"{start!s}")

    if not end:
        end_local = PromptFactory.prompt_for_date("(end-date)")
    else:
        end_local = PromptFactory._parse_date(f"{end!s}")

    duration = end_local - start_local
    total_seconds = int(duration.total_seconds())

    if total_seconds < 0 or _get.sign(duration.days) == -1:
        raise click.BadParameter(
            message=Text.assemble(
                # fmt: off
                "Invalid value for args [", markup.args("START"), "] | ",
                markup.args("END"), "]: Cannot set end before start",
                # fmt: on
            ).markup,
            ctx=click.get_current_context(),
        )

    return DateParams(
        start=start_local,
        end=end_local,
        duration=duration,
        total_seconds=total_seconds,
    )


def _get_current_week_range() -> DateParams:
    today = datetime.combine(AppConfig().now, datetime.min.time())

    match AppConfig().get("settings", "week_start"):
        case 0:
            delta = timedelta(days=(today.weekday() + 1) % 7)
        case 1:
            delta = timedelta(days=today.weekday() % 7)

    week_start = today - delta
    week_end = week_start + timedelta(days=6)
    duration = week_end - week_start
    total_seconds = int(duration.total_seconds())

    date_range = DateParams(
        start=week_start,
        end=week_end,
        duration=duration,
        total_seconds=total_seconds,
    )

    return date_range
