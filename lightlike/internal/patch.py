import typing as t

import rtoml
from packaging.version import Version

from lightlike.__about__ import __appdir__, __config__
from lightlike.internal import constant, utils


@utils._log_exception
def _run(v_local: Version, local_config: dict[str, t.Any], /) -> None:
    if v_local < Version("0.10.0b0"):
        if v_local < Version("0.9.0"):
            _lt_v_0_9_0()
        _config_lt_v_0_10_0b0(local_config)
        _appdata_lt_v_0_10_0b0(local_config)


@utils._log_exception
def _config_lt_v_0_10_0b0(local_config: dict[str, t.Any], /) -> None:
    # format changed for cli commands, object split on `:` instead of `.`.
    local_config["cli"].pop("lazy_subcommands", None)

    # style key changed.
    local_config["prompt"]["style"].pop("prompt.stopwatch", None)

    # adding appdir to path for quick location to load custom commands
    appdir_str: str = __appdir__.as_posix()
    paths: list[str] = local_config["cli"]["append_path"]["paths"] or []
    if appdir_str not in paths:
        paths.extend([appdir_str])
        local_config["cli"]["append_path"].update(paths=paths)


@utils._log_exception
def _appdata_lt_v_0_10_0b0(local_config: dict[str, t.Any], /) -> None:
    from lightlike.internal.appdir import CACHE, ENTRY_APPDATA, SCHEDULER_CONFIG

    # files renamed
    _old_cache = __appdir__.joinpath("cache.toml")
    if _old_cache.exists():
        CACHE.write_text(_old_cache.read_text())
        _old_cache.unlink()

    _old_entry_appdata = __appdir__.joinpath("entry_appdata.toml")
    if _old_entry_appdata.exists():
        ENTRY_APPDATA.write_text(_old_entry_appdata.read_text())
        _old_entry_appdata.unlink()

    __appdir__.joinpath("timer_list_cache.json").unlink(missing_ok=True)

    # added scheduler
    SCHEDULER_CONFIG.touch(exist_ok=True)
    SCHEDULER_CONFIG.write_text(
        constant.DEFAULT_SCHEDULER_TOML
        % (
            local_config["settings"]["timezone"],
            "sqlite:///" + (__appdir__ / "apscheduler.db").as_posix(),
        )
    )


@utils._log_exception
def _appdir_lt_v_0_9_0() -> None:
    # config location changed from appdir to home.
    if (deprecated_config := __appdir__ / "config.toml").exists():
        __config__.touch(exist_ok=True)
        __config__.write_text(deprecated_config.read_text())
        deprecated_config.unlink()


@utils._log_exception
def _lt_v_0_9_0() -> None:
    # fields changed in bigquery,
    # cache getting updated to new keys so an existing time entries
    # that may have been running/paused at time of update
    # will remain running/paused.
    cache = rtoml.load(__appdir__ / "cache.toml")

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
