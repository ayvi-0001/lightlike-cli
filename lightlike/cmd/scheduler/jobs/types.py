import typing as t

if t.TYPE_CHECKING:
    from datetime import datetime

    from apscheduler.triggers.interval import BaseTrigger

__all__: t.Sequence[str] = ("JobKwargs",)


class JobKwargs(t.TypedDict):
    """kwargs to pass to scheduler.add_job(...)"""

    func: t.Callable[..., t.Any]
    jobstore: str
    trigger: "BaseTrigger | str"
    id: t.NotRequired[str]
    name: t.NotRequired[str]
    args: t.NotRequired[tuple[t.Any] | list[t.Any]]
    kwargs: t.NotRequired[dict[str, t.Any]]
    coalesce: t.NotRequired[bool]
    executor: t.NotRequired[str]
    misfire_grace_time: t.NotRequired[int]
    max_instances: t.NotRequired[int]
    next_run_time: t.NotRequired["datetime"]
    replace_existing: t.NotRequired[bool]
    run_date: t.NotRequired["str | datetime"]
    weeks: t.NotRequired[int]
    days: t.NotRequired[int]
    hours: t.NotRequired[int]
    minutes: t.NotRequired[int]
    seconds: t.NotRequired[int]
    year: t.NotRequired[int]
    month: t.NotRequired[int]
    week: t.NotRequired[int]
    day: t.NotRequired[int]
    day_of_week: t.NotRequired[str]
    hour: t.NotRequired[int]
    minute: t.NotRequired[int]
    second: t.NotRequired[int]
    start_date: t.NotRequired["str | datetime"]
    end_date: t.NotRequired["str | datetime"]
