import logging
import typing as t

import rtoml

# from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, SchedulerEvent
from apscheduler.schedulers.background import BackgroundScheduler

from lightlike.internal import appdir
from lightlike.scheduler.default_jobs import create_or_replace_default_jobs

__all__: t.Sequence[str] = (
    "SCHEDULER",
    "get_scheduler",
    "create_or_replace_default_jobs",
)

logging.getLogger("apscheduler").setLevel(logging.DEBUG)


SCHEDULER: BackgroundScheduler | None = None


P = t.ParamSpec("P")


def get_scheduler(*args: P.args, **kwargs: P.kwargs) -> BackgroundScheduler:
    global SCHEDULER
    if SCHEDULER is None:

        scheduler_config: dict[str, t.Any] = {}

        if appdir.SCHEDULER_CONFIG.exists():
            config = rtoml.load(appdir.SCHEDULER_CONFIG)
            scheduler_config = config.get("scheduler", {})

        SCHEDULER = BackgroundScheduler(scheduler_config)

        # SCHEDULER.add_listener(listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    return SCHEDULER


# def listener(event: SchedulerEvent) -> None:
#     if event.exception:
#         ...
#     else:
#         ...
