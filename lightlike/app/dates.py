import typing as t
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import copysign

import click
import dateparser
import pytz
from rich.text import Text

from lightlike.app.config import AppConfig
from lightlike.internal.utils import _get_local_timezone_string

if t.TYPE_CHECKING:
    from datetime import _TzInfo

    from dateparser import _Settings


__all__: t.Sequence[str] = (
    "now",
    "astimezone",
    "parse_date",
    "parse_date_range_flags",
    "get_relative_week",
    "get_month_to_date",
    "get_year_to_date",
    "combine_new_date_into_start_and_end",
    "combine_new_date_into_start",
    "combine_new_date_into_end",
    "seconds_to_time_parts",
    "calculate_duration",
)


@dataclass
class DateParams:
    start: datetime
    end: datetime
    duration: timedelta
    total_seconds: int


def is_tzaware(dt: datetime) -> bool:
    return not (dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None)


def astimezone(dt: datetime, tzinfo: "_TzInfo | None" = None) -> datetime:
    return dt.astimezone(tzinfo).replace(microsecond=0)


def now(tzinfo: "_TzInfo | None" = None) -> datetime:
    return astimezone(datetime.now(), tzinfo)


with AppConfig().rw() as config:
    dateparser_settings: dict[str, t.Any] = config.get(
        "settings", "dateparser", default={}
    )

DEFAULT_PARSER_SETTINGS: dict[str, t.Any] = {
    # fmt: off
    "CACHE_SIZE_LIMIT": dateparser_settings.get("cache_size_limit"),
    "LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD": dateparser_settings.get("language_detection_confidence_threshold"),
    "NORMALIZE": dateparser_settings.get("normalize"),
    "STRICT_PARSING": dateparser_settings.get("strict_parsing"),
    "PREFER_MONTH_OF_YEAR": dateparser_settings.get("prefer_month_of_year"),
    "PREFER_DAY_OF_MONTH": dateparser_settings.get("prefer_day_of_month"),
    "PREFER_DATES_FROM": dateparser_settings.get("prefer_dates_from"),
    "DATE_ORDER": dateparser_settings.get("date_order"),
    "PREFER_LOCALE_DATE_ORDER": dateparser_settings.get("prefer_locale_date_order"),
    "DEFAULT_LANGUAGES": dateparser_settings.get("default_languages"),
    "REQUIRE_PARTS": [],
    "RETURN_TIME_AS_PERIOD": False,
    "SKIP_TOKENS": ["t"],
    "RETURN_AS_TIMEZONE_AWARE": True,
    "PARSERS": [
        "timestamp",
        "negative-timestamp",
        "relative-time",
        "custom-formats",
        "absolute-time",
    ],
    # fmt: on
}

ADDITIONAL_DATE_FORMATS: list[str] = dateparser_settings.get(
    "ADDITIONAL_DATE_FORMATS", ["%I%p", "%I:%M%p", "%H:%M:%S"]
)

del dateparser_settings


def parse_date(
    date: str,
    relative_base: datetime | None = None,
    tzinfo: "_TzInfo | str | None" = None,
) -> datetime:
    if isinstance(tzinfo, str):
        tzinfo = pytz.timezone(tzinfo)
    elif tzinfo is None:
        tzinfo = pytz.timezone(_get_local_timezone_string(default="UTC"))

    _settings = DEFAULT_PARSER_SETTINGS.copy()
    _settings.update(
        {
            "RELATIVE_BASE": relative_base or now(tzinfo),
            "TO_TIMEZONE": f"{tzinfo}",
            "TIMEZONE": f"{tzinfo}",
        },
    )
    parsed_date = dateparser.parse(
        date,
        settings=t.cast("_Settings", _settings),
        date_formats=ADDITIONAL_DATE_FORMATS,
    )
    if not parsed_date:
        raise click.UsageError(
            message=Text.assemble(f"Failed to parse date: ", date).markup,
            ctx=click.get_current_context(silent=True),
        )
    return astimezone(parsed_date, tzinfo)


def parse_date_range_flags(start: datetime, end: datetime) -> DateParams:
    duration = end - start
    total_seconds = int(duration.total_seconds())

    if total_seconds < 0 or copysign(1, duration.days) == -1:
        raise click.UsageError(
            message="Cannot set --start / -s before --end / -e.",
            ctx=click.get_current_context(silent=True),
        )

    return DateParams(
        start=start,
        end=end,
        duration=duration,
        total_seconds=total_seconds,
    )


def get_relative_week(
    now: datetime,
    setting: int,
    week: t.Literal["current", "previous"] = "current",
) -> DateParams:
    match week:
        case "current":
            start_date = datetime.combine(now, datetime.min.time())
        case "previous":
            start_date = datetime.combine(now, datetime.min.time()) - timedelta(days=7)

    match setting:
        case 0:
            delta = timedelta(days=(start_date.weekday() + 1) % 7)
        case 1:
            delta = timedelta(days=start_date.weekday() % 7)
        case _:
            raise click.BadParameter(
                message="Invalid setting for `week_start`. "
                "Value must be either 1 or 0.",
                ctx=click.get_current_context(silent=True),
            )

    start_range = start_date - delta
    end_range = start_range + timedelta(days=6)
    duration = end_range - start_range
    total_seconds = int(duration.total_seconds())

    return DateParams(
        start=start_range,
        end=end_range,
        duration=duration,
        total_seconds=total_seconds,
    )


def get_month_to_date(now: datetime) -> DateParams:
    start_range = datetime.combine(
        date=date(year=now.year, month=now.month, day=1),
        time=datetime.min.time(),
        tzinfo=now.tzinfo,
    )
    duration = now - start_range
    total_seconds = int(duration.total_seconds())

    return DateParams(
        start=start_range,
        end=now,
        duration=duration,
        total_seconds=total_seconds,
    )


def get_year_to_date(now: datetime) -> DateParams:
    start_range = datetime.combine(
        date=date(year=now.year, month=1, day=1),
        time=datetime.min.time(),
        tzinfo=now.tzinfo,
    )
    duration = now - start_range
    total_seconds = int(duration.total_seconds())

    return DateParams(
        start=start_range,
        end=now,
        duration=duration,
        total_seconds=total_seconds,
    )


def combine_new_date_into_start_and_end(
    in_datetime: datetime, in_start: datetime, in_end: datetime
) -> tuple[date, datetime, datetime]:
    out_date = in_datetime.date()
    out_start = astimezone(datetime.combine(out_date, in_start.time()))
    out_end = astimezone(datetime.combine(out_date, in_end.time()))
    return out_date, out_start, out_end


def combine_new_date_into_start(
    in_datetime: datetime, in_start: datetime, in_end: datetime
) -> tuple[date, datetime, datetime]:
    out_date = in_datetime.date()
    out_start = astimezone(datetime.combine(out_date, in_start.time()))
    out_end = astimezone(in_end)
    return out_date, out_start, out_end


def combine_new_date_into_end(
    in_datetime: datetime, in_start: datetime, in_end: datetime
) -> tuple[date, datetime, datetime]:
    out_date = in_datetime.date()
    out_start = astimezone(in_start)
    out_end = astimezone(datetime.combine(out_date, in_end.time()))
    return out_date, out_start, out_end


def seconds_to_time_parts(seconds: Decimal) -> tuple[int, int, int]:
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds = seconds.to_integral_value()
    seconds %= 60
    return int(hours), int(minutes), int(seconds)


def calculate_duration(
    start_date: datetime,
    end_date: datetime,
    paused_hours: Decimal | float | None = None,
    raise_if_negative: bool = False,
    exception: Exception | None = None,
) -> Decimal:
    duration: timedelta = end_date - start_date

    if paused_hours:
        if isinstance(paused_hours, float):
            paused_hours = Decimal(paused_hours)

        time_parts_paused = seconds_to_time_parts(Decimal(paused_hours) * Decimal(3600))
        paused_hours, paused_minutes, paused_seconds = time_parts_paused
        paused_delta: timedelta = timedelta(
            hours=paused_hours,
            minutes=paused_minutes,
            seconds=paused_seconds,
        )
        duration = duration - paused_delta

    if duration.total_seconds() < 0 or copysign(1, duration.days) == -1:
        if raise_if_negative:
            if exception:
                raise exception
            else:
                raise ValueError(f"Negative duration: {duration.total_seconds()}")

    total_seconds: int = int(duration.total_seconds())
    hours: Decimal = round(Decimal(total_seconds) / Decimal(3600), 4)
    return hours
