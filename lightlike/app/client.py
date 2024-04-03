# mypy: disable-error-code="import-untyped"

import sys
from typing import TYPE_CHECKING, Callable, NoReturn, ParamSpec, Sequence

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.cloud.bigquery import Client
from rich import get_console
from rich import print as rprint
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from lightlike import _console
from lightlike.app.auth import _AuthSession
from lightlike.app.config import AppConfig
from lightlike.internal import markup
from lightlike.internal.enums import CredentialsSource
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from google.cloud.bigquery.client import Project

__all__: Sequence[str] = (
    "get_client",
    "reconfigure",
    "authorize_client",
    "_select_credential_source",
    "_select_project",
    "service_account_key_flow",
    "_authorize_from_service_account_key",
    "_authorize_from_environment",
    "_provision_bigquery_resources",
)


def global_console_log(message: Text | str) -> None:
    if not _console.QUIET_START:
        get_console().log(message)


global_console_log("Authorizing BigQuery Client")


P = ParamSpec("P")


CLIENT: Client | None = None


def get_client(*args: P.args, **kwargs: P.kwargs) -> Client:
    global CLIENT
    if CLIENT is None:
        CLIENT = authorize_client()
    return CLIENT


def reconfigure(*args: P.args, **kwargs: P.kwargs) -> None:
    NEW_CLIENT = authorize_client()
    global CLIENT
    CLIENT = get_client()
    CLIENT = NEW_CLIENT


def authorize_client() -> Client | NoReturn:
    credentials_source: str = AppConfig().get("client", "credentials_source")

    try:
        match credentials_source:
            case CredentialsSource.from_service_account_key:
                client = _authorize_from_service_account_key()

            case CredentialsSource.from_environment:
                client = _authorize_from_environment()

            case CredentialsSource.not_set:
                global_console_log(markup.log_error("Client configuration not found"))

                with AppConfig().update() as config:
                    config["client"].update(
                        credentials_source=_select_credential_source()
                    )

                return authorize_client()

        if not AppConfig().get("bigquery", "resources_provisioned"):
            _provision_bigquery_resources(client)
        return client

    except KeyboardInterrupt:
        sys.exit(1)
    except DefaultCredentialsError as error:
        rprint(
            Text.assemble(
                markup.failure(f"Auth failed: {error}"),
                "\nProvided either a service account key, ",
                "or double check your application default credentials. ",
                markup.dim(f"(try running "),
                markup.code("gcloud init"),
                markup.dim(f")"),
            )
        )
        sys.exit(2)

    except Exception as error:
        if "cannot access local variable 'service_account_key'" in f"{error}":
            rprint(markup.failure(f"Auth Failed. Incorrect Pass."))
        else:
            rprint(markup.failure(f"Auth failed: {error}"))
            if credentials_source == CredentialsSource.from_service_account_key:
                _AuthSession()._update_user_credentials(
                    password="null", stay_logged_in=False
                )

        return authorize_client()


def _select_credential_source() -> str | None | NoReturn:
    try:
        choices = [
            CredentialsSource.from_environment,
            CredentialsSource.from_service_account_key,
        ]

        select_kwargs = dict(
            message="Select source for BigQuery Client.",
            choices=choices,
            style=AppConfig().prompt_style,
            cursor=AppConfig().cursor_shape,
        )

        current_setting = AppConfig().credentials_source

        if current_setting in choices:
            select_kwargs.update(
                default=current_setting,
                instruction="(current setting highlighted)",
            )

        source = _questionary.select(**select_kwargs)

        if source == current_setting:
            rprint(markup.dim("Selected current source, nothing happened."))
            return None
        else:
            return source

    except (KeyboardInterrupt, EOFError):
        sys.exit(1)


def _select_project(client: Client) -> str:
    projects: Sequence["Project"] = list(client.list_projects())

    project_display: Callable[["Project"], str] = lambda p: " | ".join(
        [
            p.friendly_name,
            p.project_id,
            p.numeric_id,
        ]
    )

    select_kwargs = dict(
        message="Select source for BigQuery Client.",
        choices=list(map(project_display, projects)),
        style=AppConfig().prompt_style,
        cursor=AppConfig().cursor_shape,
        instruction="",
        use_indicator=True,
    )

    select = _questionary.select(**select_kwargs)
    project_id = select.split("|")[1].strip()
    return project_id


def service_account_key_flow() -> tuple[bytearray, bytes]:
    encrypted_key = AppConfig().get("client", "service_account_key")
    salt = AppConfig().get("user", "salt")

    if not (encrypted_key and salt):
        global_console_log("Initializing new service-account config")

        auth = _AuthSession()

        panel = Panel.fit(
            Text.assemble(
                "Create a password.",
                "This will be used to encrypt your service-account key.\n",
                "You will need it again to load this CLI.\n",
                "Type password and press ",
                markup.code("enter"),
                " to continue.",
            )
        )
        rprint(Padding(panel, (1, 0, 0, 1)))

        hashed_password, salt = auth.prompt_new_password()
        key_derivation = auth._generate_key(hashed_password.hexdigest(), salt)

        save_password = _questionary.confirm(message="Stay logged in?")

        if save_password:
            auth._update_user_credentials(
                password=hashed_password,
                stay_logged_in=True,
            )

        service_account = auth.prompt_service_account_key()
        encrypted_key = auth.encrypt(key_derivation, service_account)

        auth._update_user_credentials(salt=salt)

        with AppConfig().update() as config:
            config["client"].update(service_account_key=encrypted_key)

        del hashed_password
        del key_derivation

        return encrypted_key, salt

    return encrypted_key, salt


def _authorize_from_service_account_key() -> Client:
    global_console_log("Getting credentials from service-account-key")

    encrypted_key, salt = service_account_key_flow()

    client = Client.from_service_account_info(
        _AuthSession().authenticate(salt=salt, encrypted_key=encrypted_key)
    )

    with AppConfig().update() as config:
        config["client"].update(
            credentials_source=CredentialsSource.from_service_account_key,
            active_project=client.project,
        )

    global_console_log("Client authenticated")
    return client


def _authorize_from_environment() -> Client:
    global_console_log("Getting credentials from environment")
    active_project: str = AppConfig().get("client", "active_project")

    if active_project != "null" and active_project is not None:
        credentials, project_id = google.auth.default(quota_project_id=active_project)

        client = Client(project=active_project, credentials=credentials)

        with AppConfig().update() as config:
            config["client"].update(active_project=active_project)

        global_console_log("Client authenticated")
        global_console_log(
            Text.assemble("Client loaded with project: ", markup.code(active_project))
        )
        return client

    else:
        credentials, project_id = google.auth.default()

        global_console_log(Text.assemble("Default project: ", markup.code(project_id)))

        if not _questionary.confirm(
            message=f"Continue with project: {project_id}?", auto_enter=False
        ):
            project_id = _select_project(Client(credentials=credentials))

        global_console_log(Text.assemble("Using project: ", markup.code(project_id)))

        credentials = credentials.with_quota_project(project_id)

        client = Client(project=project_id, credentials=credentials)

        with AppConfig().update() as config:
            config["client"].update(
                credentials_source=CredentialsSource.from_environment,
                active_project=client.project,
            )

        global_console_log("Client authenticated")
        return client


def _provision_bigquery_resources(client: Client) -> None:
    from lightlike.internal.bq_resources import build

    mapping = AppConfig().get("bigquery")
    bq_patterns = {
        "${DATASET.NAME}": mapping["dataset"],
        "${TABLES.TIMESHEET}": mapping["timesheet"],
        "${TABLES.PROJECTS}": mapping["projects"],
        "${TIMEZONE}": f"{AppConfig().tz}",
    }

    build_state = True
    while build_state:
        build_status = build.run(client=client, patterns=bq_patterns)

        if build_status:
            with AppConfig().update() as config:
                config["bigquery"].update(resources_provisioned=True)

            build_state = False

        if not build_status:
            if _questionary.confirm(
                message="This CLI will not work if the required tables/procedures do not exist. "
                "Are you sure you want to continue?",
            ):
                build_state = False
