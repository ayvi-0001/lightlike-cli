import sys
import typing as t
from inspect import cleandoc
from pathlib import Path

import google.auth
import google.auth.credentials
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery
from more_itertools import flatten, interleave_longest
from pytz import timezone
from rich import get_console
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel

from lightlike import _console
from lightlike.app import _get, _questionary
from lightlike.app.config import AppConfig
from lightlike.client._credentials import _get_credentials_from_config
from lightlike.internal import markup, utils

__all__: t.Sequence[str] = (
    "get_client",
    "reconfigure",
    "authorize_bigquery_client",
    "provision_bigquery_resources",
)


P = t.ParamSpec("P")


BIGQUERY_CLIENT: bigquery.Client | None = None


def get_client(*args: P.args, **kwargs: P.kwargs) -> bigquery.Client:
    global BIGQUERY_CLIENT
    if BIGQUERY_CLIENT is None:
        _console.if_not_quiet_start(get_console().log)("Authorizing bigquery.Client")
        BIGQUERY_CLIENT = authorize_bigquery_client()
    return BIGQUERY_CLIENT


def reconfigure(*args: P.args, **kwargs: P.kwargs) -> None:
    NEW_CLIENT = authorize_bigquery_client()
    global BIGQUERY_CLIENT
    BIGQUERY_CLIENT = get_client()
    BIGQUERY_CLIENT = NEW_CLIENT


def authorize_bigquery_client() -> bigquery.Client:
    console: Console = get_console()
    client: bigquery.Client | None = None
    credentials: google.auth.credentials.Credentials | None = None
    appconfig = AppConfig()

    try:
        credentials = _get_credentials_from_config(appconfig)

        client = bigquery.Client(
            project=credentials.quota_project_id, credentials=credentials
        )

        with appconfig.rw() as config:
            config["client"].update(
                active_project=getattr(credentials, "quota_project_id", None)
                or getattr(credentials, "project_id", None),
            )

        _console.if_not_quiet_start(console.log)("bigquery.Client authenticated")

        resources_provisioned = appconfig.get("bigquery", "resources_provisioned")
        updates = appconfig.get("updates")

        if not resources_provisioned:
            provision_bigquery_resources(client)
        elif updates and any([updates[k] is False for k in updates]):
            provision_bigquery_resources(client, updates=updates)

        _update_cursor_global_project(locals())
        return client

    except KeyboardInterrupt:
        sys.exit(1)
    except DefaultCredentialsError as error:
        rprint(markup.failure(f"Auth failed: {error}"))
        sys.exit(2)

    except Exception as error:
        if "cannot access local variable 'service_account_key'" in f"{error}":
            rprint(markup.failure(f"Auth Failed. Incorrect Pass."))
        else:
            rprint(markup.failure(f"Auth failed: {error}"))
            AppConfig()._update_user_credentials(password=None, stay_logged_in=False)

        return authorize_bigquery_client()


def _update_cursor_global_project(l: dict[str, t.Any]) -> None:
    client: bigquery.Client | None = l.get("client")
    if client and isinstance(client, bigquery.Client):
        import lightlike.app.cursor

        lightlike.app.cursor.GCP_PROJECT = client.project


def provision_bigquery_resources(
    client: bigquery.Client,
    force: bool = False,
    updates: dict[str, bool] | None = None,
    yes: bool = False,
) -> None:
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
                """
            ),
            border_style="bold green",
            title="Updates in BigQuery",
            title_align="center",
            subtitle_align="center",
            padding=(1, 1),
        )
        rprint(Padding(update_panel, (1, 0, 1, 1)))

    link = markup.link(escape(build.SCRIPTS.as_posix()), build.SCRIPTS.as_uri())
    confirm_panel = Panel.fit(
        f"Press {markup.code('y').markup} to run scripts in BigQuery.\n"
        f"View scripts in {link.markup}"
    )

    if not (force or yes):
        rprint(Padding(confirm_panel, (1, 0, 1, 1)))

    def update_config() -> None:
        updates = AppConfig().get("updates")

        with AppConfig().rw() as config:
            config["bigquery"].update(resources_provisioned=True)

            if updates and any([updates[k] is False for k in updates]):
                for k in updates:
                    config["updates"][k] = True

    mapping: dict[str, t.Any] = AppConfig().get("bigquery", default={})
    bq_patterns = {
        "${DATASET.NAME}": mapping["dataset"],
        "${TABLES.TIMESHEET}": mapping["timesheet"],
        "${TABLES.PROJECTS}": mapping["projects"],
        "${TIMEZONE}": AppConfig().tzname,
    }

    if force:
        if not yes:
            if not _questionary.confirm(message="Run SQL scripts?", default=False):
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
                    rprint(
                        "[b][red]![/] [b]"
                        "This cli will not work as expected if tables or procedures are not up to date."
                    )
                else:
                    rprint(
                        "[b][red]![/] [b]"
                        "This cli will not work if the required tables/procedures do not exist."
                    )
                if _questionary.confirm(
                    message="Are you sure you want to continue without running?",
                    default=False,
                ):
                    build_state = False


def update_routine_diff(client: bigquery.Client) -> None:
    try:
        from lightlike.client.routines import CliQueryRoutines

        console = get_console()
        routine = CliQueryRoutines()

        mapping: dict[str, str] = AppConfig().get("bigquery", default={})
        dataset: str = mapping["dataset"]
        list_routines = client.list_routines(dataset=dataset)
        existing_routines = list(map(_get.routine_id, list_routines))
        removed = set(existing_routines).difference(list(routine._all_routines_ids))
        missing = set(routine._all_routines_ids).difference(existing_routines)

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
                bq_patterns = {
                    "${DATASET.NAME}": mapping["dataset"],
                    "${TABLES.TIMESHEET}": mapping["timesheet"],
                    "${TABLES.PROJECTS}": mapping["projects"],
                    "${TIMEZONE}": AppConfig().tzname,
                }
                console.log("Creating missing procedures")

                bq_resources = Path(
                    f"{__file__}/../../internal/bq_resources/sql"
                ).resolve()

                for path in flatten(
                    interleave_longest(
                        list(map(lambda b: b.iterdir(), bq_resources.iterdir()))
                    )
                ):
                    if path.stem in missing:
                        script = utils.regexp_replace(
                            text=path.read_text(), patterns=bq_patterns
                        )
                        script = script.replace("${__name__}", path.stem)
                        client.query(script)
                        console.log(markup.bg("Created routine:"), path.stem)

    except Exception:
        console.log(
            markup.br("Failed to update BigQuery scripts."),
            markup.br("Try running command app:run-bq"),
            markup.br("or some functions may not work properly."),
        )
