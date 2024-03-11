from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

import rich_click as click

from lightlike.app.config import AppConfig
from lightlike.app.prompt import PromptFactory

__all__: Sequence[str] = ("_parse_date_range_flags", "_get_current_week_range")


@dataclass
class DateParams:
    start: datetime
    end: datetime


def _parse_date_range_flags(
    start: str | None = None, end: str | None = None
) -> DateParams:
    if not start:
        start_local = PromptFactory.prompt_for_date("(start-date)")
    else:
        start_local = PromptFactory._parse_date(start)

    if not end:
        end_local = PromptFactory.prompt_for_date("(end-date)")
    else:
        end_local = PromptFactory._parse_date(end)

    if end_local < start_local:
        raise click.BadParameter(
            message=(
                "Invalid value for args [[args]START[/args]] | "
                "[[args]END[/args]]: End date cannot be before start date. "
            ),
            ctx=click.get_current_context(),
        )

    return DateParams(start=start_local, end=end_local)


def _get_current_week_range() -> DateParams:
    today = datetime.combine(AppConfig().now, datetime.min.time())

    match AppConfig().get("settings", "week_start"):
        case 0:
            delta = timedelta(days=(today.weekday() + 1) % 7)
        case 1:
            delta = timedelta(days=today.weekday() % 7)

    week_start = today - delta
    week_end = week_start + timedelta(days=6)
    date_range = DateParams(start=week_start, end=week_end)

    return date_range
