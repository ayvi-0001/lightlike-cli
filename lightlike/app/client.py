# mypy: disable-error-code="import-untyped"

from typing import TYPE_CHECKING, NoReturn, ParamSpec, Sequence

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.cloud.bigquery import Client
from rich import get_console
from rich import print as rprint
from rich.padding import Padding
from rich.panel import Panel

from lightlike.app import _get
from lightlike.app.auth import _AuthSession
from lightlike.app.config import AppConfig
from lightlike.internal import utils
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

get_console().log("[log.main]Authorizing BigQuery Client")


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
                get_console().log("[log.error]Client configuration not found")

                with AppConfig().update() as config:
                    config["client"].update(
                        credentials_source=_select_credential_source()
                    )

                return authorize_client()

        if not AppConfig().get("bigquery", "resources_provisioned"):
            _provision_bigquery_resources(client)
        return client

    except KeyboardInterrupt:
        exit(1)
    except DefaultCredentialsError as e:
        rprint(
            f"\n[failure]Auth Failed. {e}.[/failure]\n"
            "Provide either a service account key, or double check "
            "your application default credentials. [i](try running [code]gcloud init[/code]).[/i]\n"
        )
        exit(2)

    except Exception as e:
        if "cannot access local variable 'service_account_key'" in f"{e}":
            rprint(f"[failure]Auth Failed. Incorrect Pass.")
        else:
            rprint(f"[failure]Auth Failed. {e}")
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
            rprint("[d]Selected current source. Nothing happened.")
            return None
        else:
            return source

    except (KeyboardInterrupt, EOFError):
        exit(1)


def _select_project(client: Client) -> str:
    projects: Sequence["Project"] = list(client.list_projects())

    select_kwargs = dict(
        message="Select source for BigQuery Client.",
        choices=list(map(_get.project_display, projects)),
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
        get_console().log("[log.main]Initializing new service-account config")

        auth = _AuthSession()

        rprint(
            Padding(
                Panel.fit(
                    "Create a password. "
                    "This will be used to encrypt your service-account key.\n"
                    "You will need it again to load this CLI.\n"
                    "Type password and press [code]enter[/code] to continue."
                ),
                (1, 0, 0, 1),
            )
        )

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
    get_console().log("[log.main]Getting credentials from service-account-key")

    encrypted_key, salt = service_account_key_flow()

    client = Client.from_service_account_info(
        _AuthSession().authenticate(salt=salt, encrypted_key=encrypted_key)
    )

    with AppConfig().update() as config:
        config["client"].update(
            credentials_source=CredentialsSource.from_service_account_key,
            active_project=client.project,
        )

    get_console().log("[log.main]Client authenticated")
    return client


def _authorize_from_environment() -> Client:
    console = get_console()
    console.log("[log.main]Getting credentials from environment")
    active_project: str = AppConfig().get("client", "active_project")

    if active_project != "null" and active_project is not None:
        credentials, project_id = google.auth.default(quota_project_id=active_project)

        client = Client(project=active_project, credentials=credentials)

        with AppConfig().update() as config:
            config["client"].update(active_project=active_project)

        console.log("[log.main]Client authenticated")
        console.log(
            f"[log.main]Client loaded with project: [code]{active_project}[/code]"
        )
        return client

    else:
        credentials, project_id = google.auth.default()

        console.log(f"[log.main]Default project: [code]{project_id}[/code]")

        if not _questionary.confirm(
            message=f"Continue with project: {project_id}?", auto_enter=False
        ):
            project_id = _select_project(Client(credentials=credentials))

        console.log(f"[log.main]Using project: [code]{project_id}[/code]")

        credentials = credentials.with_quota_project(project_id)

        client = Client(project=project_id, credentials=credentials)

        with AppConfig().update() as config:
            config["client"].update(
                credentials_source=CredentialsSource.from_environment,
                active_project=client.project,
            )

        console.log("[log.main]Client authenticated")
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
                auto_enter=True,
            ):
                build_state = False
