import logging
import sys
import typing as t
from inspect import cleandoc
from pathlib import Path

import rich
import rtoml
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

from lightlike import _console
from lightlike.__about__ import __version__
from lightlike.app import _get, _questionary
from lightlike.app.config import AppConfig
from lightlike.client._credentials import _get_credentials_from_config
from lightlike.internal import appdir, markup, utils

if t.TYPE_CHECKING:
    from rich.console import Console

__all__: t.Sequence[str] = (
    "authorize_bigquery_client",
    "get_client",
    "provision_bigquery_resources",
    "reconfigure",
)

LOGGER = logging.getLogger(__name__)

BIGQUERY_CLIENT: bigquery.Client | None = None


def get_client(*_args: t.Any, **_kwargs: t.Any) -> bigquery.Client:  # ruff: ignore[any-type]
    global BIGQUERY_CLIENT  # ruff: ignore[global-statement]
    if BIGQUERY_CLIENT is None:
        _console.if_not_quiet_start(rich.get_console().log)("Authorizing bigquery.Client")
        BIGQUERY_CLIENT = authorize_bigquery_client()
    return BIGQUERY_CLIENT


def reconfigure(*_args: t.Any, **_kwargs: t.Any) -> None:  # ruff: ignore[any-type]
    new_client = authorize_bigquery_client()
    global BIGQUERY_CLIENT  # ruff: ignore[global-statement]
    BIGQUERY_CLIENT = get_client()
    BIGQUERY_CLIENT = new_client


def authorize_bigquery_client() -> bigquery.Client:
    console: Console = rich.get_console()
    appconfig = AppConfig()

    try:
        credentials = _get_credentials_from_config(appconfig)

        client = bigquery.Client(
            project=credentials.quota_project_id,
            credentials=credentials,
        )

        with appconfig.rw() as config:
            config["client"].update(
                {
                    "active-project": getattr(credentials, "quota_project_id", None)
                    or getattr(credentials, "project_id", None),
                },
            )

        _console.if_not_quiet_start(console.log)("bigquery.Client authenticated")

        resources_provisioned = appconfig.get("bigquery", "resources-provisioned")

        if not resources_provisioned:
            provision_bigquery_resources(client)
        elif appdir.BQ_UPDATES.exists():
            bq_updates: dict[str, dict[str, bool]] = rtoml.load(appdir.BQ_UPDATES)
            versions: dict[str, bool] = bq_updates["versions"]
            if versions and any(versions[k] is False for k in versions):
                provision_bigquery_resources(client, updates=versions)

        # _update_cursor_global_project(locals())

    except KeyboardInterrupt:
        sys.exit(1)
    except DefaultCredentialsError as exc:
        rich.print(markup.failure(f"Auth failed: {exc}"))
        sys.exit(2)
    except Exception as exc:  # ruff: ignore[blind-except]
        if "cannot access local variable 'service_account_key'" in f"{exc}":
            rich.print(markup.failure("Auth Failed. Incorrect Pass."))
        else:
            rich.print(markup.failure(f"Auth failed: {exc}"))
            AppConfig().update_user_credentials(password=None, stay_logged_in=False)

        return authorize_bigquery_client()
    else:
        return client


# ruff: ignore[commented-out-code]
# def _update_cursor_global_project(local_params: dict[str, t.Any]) -> None:
#     client: bigquery.Client | None = local_params.get("client")
#     if client and isinstance(client, bigquery.Client):
#         import lightlike.app.cursor

#         lightlike.app.cursor.GCP_PROJECT = client.project


def provision_bigquery_resources(
    client: bigquery.Client,
    updates: dict[str, bool] | None = None,
    *,
    force: bool = False,
    yes: bool = False,
) -> None:
    from rich.markup import escape
    from rich.padding import Padding
    from rich.panel import Panel

    from lightlike.internal.bq_resources import build

    if updates:
        update_panel = Panel.fit(
            cleandoc(
                """\
            App detected that this version either:
                ▸ is currently updating to a version with breaking changes, and needs to run scripts in BigQuery.
                ▸ has not ran scripts in BigQuery following an update with breaking changes.

            Please run scripts. This prompt will continue until this version update is marked as confirmed.

            [b][red]![/red] [u]This cli may not work as expected if tables/procedures are not up to date[/u].\
                """,  # ruff: ignore[line-too-long]
            ),
            border_style="bold green",
            title="Updates in BigQuery",
            title_align="center",
            subtitle_align="center",
            padding=(1, 1),
        )
        rich.print(Padding(update_panel, (1, 0, 1, 1)))

    link = markup.link(escape(build.SCRIPTS.as_posix()), build.SCRIPTS.as_uri())
    confirm_panel = Panel.fit(
        f"Press {markup.code('y').markup} to run scripts in BigQuery.\n"
        f"View scripts in {link.markup}",
    )

    if not (force or yes):
        rich.print(Padding(confirm_panel, (1, 0, 1, 1)))

    def update_config() -> None:
        with AppConfig().rw() as config:
            config["bigquery"].update({"resources-provisioned": True})

        if appdir.BQ_UPDATES.exists():
            bq_updates: dict[str, dict[str, bool]] = rtoml.load(appdir.BQ_UPDATES)
            versions: dict[str, bool] = bq_updates["versions"]
            if versions and any(versions[k] is False for k in versions):
                for k in versions:
                    bq_updates["versions"][k] = True
                rtoml.dump(bq_updates, appdir.BQ_UPDATES)

    mapping: dict[str, t.Any] = AppConfig().get("bigquery", default={})
    bq_patterns = {
        "${DATASET.NAME}": mapping["dataset"],
        "${TABLES.PROJECTS}": mapping["projects"],
        "${TABLES.TIMESHEET}": mapping["timesheet"],
        "${TIMEZONE}": AppConfig().tzname,
        "${VERSION}": __version__.replace(".", "-"),
    }

    if force:
        if not yes and not _questionary.confirm(message="Run SQL scripts?", default=False):
            return

        build.run(client=client, patterns=bq_patterns)
        update_routine_diff(client)
        update_config()
    else:
        build_state = True
        while build_state:
            if _questionary.confirm(message="Run SQL scripts?", default=False):
                build.run(client=client, patterns=bq_patterns)
                update_routine_diff(client)
                update_config()
                build_state = False
            else:
                if updates:
                    rich.print(
                        "[b][red]![/] [b]This cli will not work as expected "
                        "if tables or procedures are not up to date.",
                    )
                else:
                    rich.print(
                        "[b][red]![/] [b]"
                        "This cli will not work if the required tables/procedures do not exist.",
                    )
                if _questionary.confirm(
                    message="Are you sure you want to continue without running?",
                    default=False,
                ):
                    build_state = False


def update_routine_diff(client: bigquery.Client) -> None:
    try:
        from lightlike.client.routines import CliQueryRoutines

        console = rich.get_console()
        routine = CliQueryRoutines()

        mapping: dict[str, str] = AppConfig().get("bigquery", default={})
        dataset: str = mapping["dataset"]
        list_routines = client.list_routines(dataset=dataset)
        existing_routines = list(map(_get.routine_id, list_routines))
        removed = set(existing_routines).difference(list(routine.all_routines_ids))
        missing = set(routine.all_routines_ids).difference(existing_routines)

        if not any([removed, missing]):
            return

        with console.status(markup.status_message("Updating routines")):
            if removed:
                console.log("Dropping deprecated/unrecognized procedures")

                for routine in removed:
                    routine_id = f"{client.project}.{dataset}.{routine}"
                    client.delete_routine(routine_id)
                    console.log(markup.bg("Dropped routine:"), routine)

            if missing:
                from more_itertools import flatten, interleave_longest

                bq_patterns = {
                    "${DATASET.NAME}": mapping["dataset"],
                    "${TABLES.PROJECTS}": mapping["projects"],
                    "${TABLES.TIMESHEET}": mapping["timesheet"],
                    "${TIMEZONE}": AppConfig().tzname,
                    "${VERSION}": __version__.replace(".", "-"),
                }
                console.log("Creating missing procedures")

                bq_resources = Path(
                    f"{__file__}/../../internal/bq_resources/sql",
                ).resolve()

                for path in flatten(
                    interleave_longest(
                        [b.iterdir() for b in bq_resources.iterdir()],
                    ),
                ):
                    if path.stem in missing:
                        script = utils.regexp_replace(
                            text=path.read_text(),
                            patterns=bq_patterns,
                        )
                        script = script.replace("${__name__}", path.stem)
                        client.query(script)
                        console.log(markup.bg("Created routine:"), path.stem)

    except Exception:
        msg = (
            "Failed to update BigQuery scripts. "
            "Try running command bq:run-build "
            "or some functions may not work properly."
        )
        console.log(markup.br(msg))
        LOGGER.exception("Error updating BigQuery scripts.")
