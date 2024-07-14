import logging
import typing as t
from pathlib import Path

import rtoml

from lightlike.__about__ import __appdir__


def _appdir_lt_v_0_9_0(appdir: Path, config: Path, /) -> None:
    try:
        if (deprecated_config := appdir / "config.toml").exists():
            config.touch(exist_ok=True)
            config.write_text(deprecated_config.read_text())
            deprecated_config.unlink()
    except Exception as error:
        logging.error(f"{error}")


def _config_lt_v_0_10_0(appdir: Path, local_config: dict[str, t.Any], /) -> None:
    try:
        local_config["cli"].update(
            commands=local_config["cli"].pop("lazy_subcommands", {})
        )
        appdir.joinpath("timer_list_cache.json").unlink(missing_ok=True)
    except Exception as error:
        logging.error(f"{error}")


def _cache_lt_v_0_9_0(appdir: Path, /) -> None:
    try:
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
    except Exception as error:
        logging.error(f"{error}")
