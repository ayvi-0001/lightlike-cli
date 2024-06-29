import re
import typing as t
from pathlib import Path

import httpx
import rtoml
from rich import get_console

from lightlike.__about__ import __appdir__
from lightlike.internal import appdir, markup

__all__: t.Sequence[str] = ("check_latest_release", "extract_version")


PATTERN_PKG: t.Final[t.Pattern[str]] = re.compile(r"(?:v|)(\d+).(\d+).(\d+)", re.I)
PATTERN_TAG: t.Final[t.Pattern[str]] = re.compile(r"^.*tag/(.*)$", re.I)
PATTERN_SEMVER: t.Final[t.Pattern[str]] = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def get_version_from_release(__latest_release__: str) -> tuple[int, int, int]:
    headers = {
        "accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = httpx.get(url=__latest_release__, headers=headers)
    version = PATTERN_TAG.search(response.next_request.url.path).group(1)  # type: ignore[union-attr]
    return extract_version(version)


def extract_version(version_text: str) -> tuple[int, int, int]:
    major, minor, patch = PATTERN_PKG.match(version_text).group(1, 2, 3)  # type: ignore[union-attr]
    return int(major), int(minor), int(patch)


def check_latest_release(
    v_package: tuple[int, int, int], __repo__: str, __latest_release__: str
) -> None:
    try:
        latest_version: tuple[int, int, int] = (
            get_version_from_release(__latest_release__)  # fmt: skip
        )

        if v_package < latest_version:
            console = get_console()
            tag = ".".join(map(str, latest_version))
            console.log(
                markup.bg("New Release available"),
                ": v", markup.repr_number(f"{tag}"),  # fmt: skip
                ". Install update by running command: ",
                sep="",
            )
            console.log(
                markup.code(f'$ pip install -U "lightlike @ git+{__repo__}@v{tag}"')
            )

    except Exception as error:
        appdir._log().error(f"Failed to retrieve latest release: {error}")


def _patch_appdir_lt_v_0_9_0(__appdir__: Path, __config__: Path) -> None:
    if (deprecated_config := __appdir__ / "config.toml").exists():
        __config__.touch(exist_ok=True)
        __config__.write_text(deprecated_config.read_text())
        deprecated_config.unlink()


def _patch_cache_lt_v_0_9_0(__appdir__: Path) -> None:
    cache = rtoml.load(__appdir__ / "cache.toml")
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
    rtoml.dump(cache, __appdir__ / "cache.toml")

    if (deprecated_log := __appdir__ / "cli.log").exists():
        deprecated_log.unlink()
