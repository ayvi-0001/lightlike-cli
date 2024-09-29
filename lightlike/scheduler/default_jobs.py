import importlib
import typing as t
from pathlib import Path
from types import ModuleType

import rtoml
from apscheduler.schedulers.background import BackgroundScheduler

from lightlike.internal import appdir, utils

# from importlib._bootstrap import _DeadlockError


__all__: t.Sequence[str] = ("create_or_replace_default_jobs",)


def create_or_replace_default_jobs(
    jobs: dict[str, str] | None = None,
    path_to_jobs: Path | None = None,
    keys: t.Sequence[str] | None = None,
) -> None:
    from lightlike.scheduler import get_scheduler

    job_config: dict[str, str] = {}

    if path_to_jobs and keys:
        if path_to_jobs.exists():
            jobs_toml = rtoml.load(path_to_jobs)
            job_config = utils.reduce_keys(*keys or [], sequence=jobs_toml)
    elif jobs:
        job_config = jobs

    scheduler: BackgroundScheduler = get_scheduler()

    for job_object_name, import_path in job_config.items():
        try:
            modname, job_object_name = import_path.rsplit(":", 1)
            mod: ModuleType | None = importlib.import_module(modname)
            job_kwargs: t.Callable[..., dict[str, t.Any]] = getattr(
                mod, job_object_name
            )

            scheduler.add_job(**job_kwargs())

        except Exception as error:
            appdir.log().error(
                f"Failed to load default job: {job_object_name}: {error}"
            )
