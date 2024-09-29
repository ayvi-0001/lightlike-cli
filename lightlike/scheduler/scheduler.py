import logging
import typing as t

import rtoml
from apscheduler.schedulers.background import BackgroundScheduler

from lightlike.internal import appdir

__all__: t.Sequence[str] = ("SCHEDULER", "get_scheduler")


logging.getLogger("apscheduler").setLevel(logging.DEBUG)


SCHEDULER: BackgroundScheduler | None = None


P = t.ParamSpec("P")


def get_scheduler(*args: P.args, **kwargs: P.kwargs) -> BackgroundScheduler:
    global SCHEDULER
    if SCHEDULER is None:
        SCHEDULER = _build_scheduler()
    return SCHEDULER


def _build_scheduler() -> BackgroundScheduler:
    scheduler_config: dict[str, t.Any] = {}

    if appdir.SCHEDULER_CONFIG.exists():
        config = rtoml.load(appdir.SCHEDULER_CONFIG)
        scheduler_config = config.get("scheduler", {})

    SCHEDULER = BackgroundScheduler(scheduler_config)

    return SCHEDULER
