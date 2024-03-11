import re
from pathlib import Path
from typing import Final, Pattern, Sequence

import rtoml
from more_itertools import flatten, interleave_longest
from rich import get_console

from lightlike.internal import utils
from lightlike.internal.utils import update_dict

__all__: Sequence[str] = ("update_cli", "_update_config")


def update_cli(config: Path, __version__: str | None = None, /) -> None:
    _update_routines()
    # ...  # TODO


def get_version(__latest_release__) -> str:
    import httpx

    headers = {
        "accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = httpx.get(url=__latest_release__, headers=headers)
    match = re.search(r"^.*tag/(.*)$", response.next_request.url.path)  # type: ignore[union-attr]
    version = match.group(1)  # type: ignore[union-attr]

    return version


def compare_version(__version__: str, __latest_release__: str) -> str:
    pkg_expr: Final[Pattern[str]] = re.compile(r"v(\d).(\d)+.(\d)+", re.I)

    latest_release = get_version(__latest_release__)

    vLocal = pkg_expr.match(__version__)
    vLatest = pkg_expr.match(latest_release)

    local_major, local_minor, local_patch = vLocal.group(1, 2, 3)  # type: ignore[union-attr]
    latest_major, latest_minor, latest_patch = vLatest.group(1, 2, 3)  # type: ignore[union-attr]

    latest_version = (int(local_major), int(local_minor), int(local_patch))
    current_version = (int(latest_major), int(latest_minor), int(latest_patch))

    if current_version < latest_version:
        get_console().log(
            f"[b][i][u]New Release available: {latest_release}. "
            f"Download @ {__latest_release__}"
        )

    return latest_release


DEFAULT_CONFIG = """\
[app]
name = ""
version = ""
term = ""

[settings]
editor = "code"
timezone = "null"
is_billable = false
note_required = false
week_start = 1

[settings.note_history]
days = 90

[settings.query]
mouse_support = true
save_txt = false
save_query_info = false
save_svg = false
hide_table_render = false

[user]
name = "null"
host = "null"
stay_logged_in = false
password = ""
salt = []

[bigquery]
dataset = "null"
timesheet = "timesheet"
projects = "projects"
resources_provisioned = false

[client]
active_project = "null"
credentials_source = "not-set"
service_account_key = []

[git]
branch = ""
path = ""
in_repo = false
"""


def _update_config(config: Path, __version__: str | None = None, /) -> None:
    CURRENT_CONFIG = rtoml.load(config)
    NEW_CONFIG = update_dict(
        original=rtoml.load(DEFAULT_CONFIG),
        updates=CURRENT_CONFIG,
    )
    NEW_CONFIG["app"].update(version=__version__)
    config.write_text(utils._format_toml(NEW_CONFIG))


def _update_routines() -> None:
    from lightlike.app import _get, routines
    from lightlike.app.client import get_client
    from lightlike.app.config import AppConfig

    client = get_client()

    if not client:
        return

    console = get_console()
    cli_routines = routines.CliQueryRoutines()

    mapping = AppConfig().get("bigquery")
    dataset = mapping["dataset"]
    timesheet_table = mapping["timesheet"]
    projects_table = mapping["projects"]

    bq_patterns = {
        "${DATASET.NAME}": dataset,
        "${TABLES.TIMESHEET}": timesheet_table,
        "${TABLES.PROJECTS}": projects_table,
        "${TIMEZONE}": str(AppConfig().tz),
    }

    list_routines = client.list_routines(dataset=dataset)
    existing_routines = list(map(_get.routine_id, list_routines))
    removed = set(existing_routines).difference(list(cli_routines._all_routines_ids))
    missing = set(cli_routines._all_routines_ids).difference(existing_routines)

    if not any([removed, missing]):
        return

    console.log("[log.main]Updating routines in BigQuery")

    with console.status(status="[status.message]Updating routines.."):
        if removed:
            for routine in removed:
                routine_id = f"{client.project}.{dataset}.{routine}"
                client.delete_routine(routine_id)
                console.log(f"[bold green]Deleted routine: {routine_id}")

        if missing:
            bq_resources = Path(f"{__file__}/../../internal/bq_resources/sql").resolve()

            for path in flatten(
                interleave_longest(
                    list(map(lambda b: b.iterdir(), bq_resources.iterdir()))
                )
            ):
                if path.stem in missing:
                    script = utils._regexp_replace(
                        text=path.read_text(),
                        patterns=bq_patterns,
                    )
                    script = script.replace("${__name__}", path.stem)
                    client.query(script)
                    console.log(f"[bold green]Created routine: {path.stem}")
