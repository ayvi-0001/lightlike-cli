import re
import typing as t
from datetime import datetime, timedelta

import httpx
from apscheduler.triggers.date import DateTrigger
from packaging.version import Version
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console

from lightlike.__about__ import __repo__, __version__
from lightlike.app.config import AppConfig
from lightlike.cmd.scheduler.jobs.types import JobKwargs
from lightlike.internal import appdir, markup

__all__: t.Sequence[str] = ("check_latest_release", "default_job_check_latest_release")


PATTERN_SEMVER: t.Final[t.Pattern[str]] = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:(-|\.)"
    r"(?P<prerelease_alphanumeric>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))(?:\.)"
    r"(?P<prerelease_numeric>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def get_version_from_release(repo: str) -> Version:
    headers = {
        "accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = httpx.get(url=f"{repo}/releases/latest", headers=headers)
    next_request: httpx.Request | None = response.next_request
    assert next_request
    version = next_request.url.path.removeprefix(
        "/ayvi-0001/lightlike-cli/releases/tag/"
    )
    return Version(version)


def check_latest_release(v_package: str, repo: str) -> None:
    try:
        last_checked_release: datetime | None = None
        last_checked_release = AppConfig().get("app", "last_checked_release")

        if not last_checked_release or (
            last_checked_release
            and last_checked_release.date() < datetime.today().date()
        ):
            console = get_console()
            latest_version: Version = get_version_from_release(repo)

            with AppConfig().rw() as config:
                config["app"].update(last_checked_release=datetime.now())

            if Version(v_package) < latest_version:
                with patch_stdout(raw=True):
                    console.log(
                        markup.bg("New Release available:"),
                        markup.repr_number(f"v{latest_version}"),
                    )
                    console.log(
                        "Install update with command: ",
                        markup.code(
                            f'$ pip install -U "lightlike @ git+{repo}@v{latest_version}"'
                        ),
                    )
    except Exception as error:
        appdir._log().error(f"Failed to retrieve latest release: {error}")


def default_job_check_latest_release() -> JobKwargs:
    job_kwargs = JobKwargs(
        func=check_latest_release,
        id="check_latest_release",
        name="check_latest_release",
        kwargs=dict(v_package=__version__, repo=__repo__),
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=2)),
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        jobstore="sqlalchemy",
        executor="sqlalchemy",
        misfire_grace_time=10,
    )
    return job_kwargs
