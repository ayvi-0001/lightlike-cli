import re
import typing as t
from pathlib import Path

import httpx
import rtoml
from packaging.version import Version
from rich import get_console

from lightlike.__about__ import __appdir__
from lightlike.internal import appdir, markup

__all__: t.Sequence[str] = ("check_latest_release",)


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


def check_latest_release(v_package: Version, repo: str) -> None:
    try:
        latest_version: Version = get_version_from_release(repo)

        if v_package < latest_version:
            console = get_console()
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


def _patch_appdir_lt_v_0_9_0(appdir: Path, config: Path, /) -> None:
    if (deprecated_config := appdir / "config.toml").exists():
        config.touch(exist_ok=True)
        config.write_text(deprecated_config.read_text())
        deprecated_config.unlink()


def _patch_cache_lt_v_0_9_0(appdir: Path, /) -> None:
    cache = rtoml.load(appdir / "cache.toml")
    if not cache:
        return

    running = []
    for e in cache["running"]["entries"]:
        remapped: dict[str, t.Any] = {}
        remapped["id"] = e["id"]
        remapped["start"] = e["start"]
        remapped["timestamp_paused"] = e["time_paused"]
        remapped["project"] = e["project"]
        remapped["note"] = e["note"]
        remapped["billable"] = e["is_billable"]
        remapped["paused"] = e["is_paused"]
        remapped["paused_hours"] = e["paused_hrs"]
        running.append(remapped)
    paused = []
    for e in cache["paused"]["entries"]:
        remapped = {}
        remapped["id"] = e["id"]
        remapped["start"] = e["start"]
        remapped["timestamp_paused"] = e["time_paused"]
        remapped["project"] = e["project"]
        remapped["note"] = e["note"]
        remapped["billable"] = e["is_billable"]
        remapped["paused"] = e["is_paused"]
        remapped["paused_hours"] = e["paused_hrs"]
        paused.append(remapped)

    cache["running"].update(entries=running)
    cache["paused"].update(entries=paused)
    rtoml.dump(cache, appdir / "cache.toml")

    if (deprecated_log := appdir / "cli.log").exists():
        deprecated_log.unlink()
