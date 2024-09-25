import json
import sys
import typing as t
from functools import partial

import google.auth
import google.auth.credentials
from google.cloud import bigquery
from google.oauth2 import service_account
from rich import get_console, print
from rich.console import Console, NewLine

from lightlike.app import _questionary
from lightlike.app.config import AppConfig
from lightlike.client.auth import AuthPromptSession, _Auth
from lightlike.internal import markup
from lightlike.internal.enums import CredentialsSource

if t.TYPE_CHECKING:
    from google.cloud.bigquery.client import Project


__all__: t.Sequence[str] = (
    "_get_credentials_from_config",
    "service_account_key_flow",
)


def _get_credentials_from_config(
    appconfig: AppConfig,
    prompt_for_project: bool = True,
) -> google.auth.credentials.Credentials:
    credentials: google.auth.credentials.Credentials
    credentials_source: str = appconfig.get(
        "client",
        "credentials_source",
        default=CredentialsSource.not_set,
    )

    match credentials_source:
        case CredentialsSource.from_service_account_key:

            encrypted_key, salt = service_account_key_flow(appconfig)

            service_account_info: dict[str, t.Any] = json.loads(
                AuthPromptSession().decrypt_key(
                    salt=salt,
                    encrypted_key=encrypted_key,
                    saved_password=appconfig.saved_password,
                    stay_logged_in=appconfig.stay_logged_in,
                    saved_credentials_failed=partial(
                        appconfig._update_user_credentials,
                        password="null",
                        stay_logged_in=False,
                    ),
                )
            )

            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )

        case CredentialsSource.from_environment:
            quota_project_id: str | None
            quota_project_id = appconfig.get("client", "active_project")

            if quota_project_id == "null":
                quota_project_id = None

            if quota_project_id is not None:
                credentials, project_id = google.auth.default(
                    quota_project_id=quota_project_id
                )
            else:
                credentials, project_id = google.auth.default()
                if prompt_for_project:
                    if not _questionary.confirm(
                        message=f"Continue with project: {project_id}?",
                        auto_enter=True,
                    ):
                        project_id = _select_project(credentials=credentials)

            credentials = credentials.with_quota_project(project_id)

        case _:
            print("credentials configuration not found")

            with appconfig.rw() as config:
                config["client"].update(
                    credentials_source=_select_credential_source(
                        current_setting=appconfig.get(
                            "client",
                            "credentials_source",
                            default=CredentialsSource.not_set,
                        )
                    )
                )

            return _get_credentials_from_config(appconfig, prompt_for_project)

    return credentials


def service_account_key_flow(appconfig: AppConfig) -> tuple[bytes, bytes]:
    console: Console = get_console()

    encrypted_key: bytes | None = None
    salt: bytes | None = None

    encrypted_key_from_config: bytearray | None = appconfig.get(
        "client",
        "service_account_key",
    )
    salt_from_config: bytearray | None = appconfig.get(
        "user",
        "salt",
    )

    if not (encrypted_key_from_config and salt_from_config):
        console.log("Initializing new service-account config")

        print(NewLine())
        print(
            "Create a password. "
            "This will be used to encrypt your service-account key.\n"
            "Type password (will not be echoed) and press [code]enter[/] to continue."
        )

        password, salt = AuthPromptSession().prompt_new_password()
        key_derivation: bytes = _Auth()._generate_key(password.hexdigest(), salt)

        print(NewLine())
        if _questionary.confirm(message="Stay logged in?"):
            appconfig._update_user_credentials(
                password=password.hexdigest(),
                stay_logged_in=True,
            )

        print(
            NewLine(),
            "Copy and paste service-account key.",
            "Press",
            markup.code("esc enter"),
            "to continue.",
            "Press",
            markup.code("ctrl t"),
            "to toggle hidden input.",
        )
        service_account: str = prompt_service_account_key()
        encrypted_key = _Auth().encrypt(key_derivation, service_account)

        appconfig._update_user_credentials(salt=salt)
        with appconfig.rw() as config:
            config["client"].update(service_account_key=encrypted_key)

        del password
        del key_derivation

        return encrypted_key, salt
    else:
        return bytes(encrypted_key_from_config), bytes(salt_from_config)


def prompt_service_account_key() -> str:
    service_account_key: str | None = None

    try:
        while not service_account_key:
            response: str = AuthPromptSession().prompt_secret(
                message="(service-account-key) $ "
            )
            try:
                key = json.loads(response)
            except json.JSONDecodeError:
                print(markup.br("Invalid json."))
                continue
            else:
                if "client_email" not in key.keys():
                    print(
                        "Invalid service-account json. Missing required key",
                        markup.code("client_email"),
                    )
                    continue
                if "token_uri" not in key.keys():
                    print(
                        "Invalid service-account json. Missing required key",
                        markup.code("token_uri"),
                    )
                    continue
                service_account_key = response
    except (KeyboardInterrupt, EOFError):
        print("[b][red]Aborted")
        sys.exit(2)

    return service_account_key


def _select_credential_source(
    current_setting: CredentialsSource | str,
) -> str | None | t.NoReturn:
    choices = [
        CredentialsSource.from_environment,
        CredentialsSource.from_service_account_key,
    ]

    try:
        new_setting: str = _questionary.select(
            message="Select source for credentials.",
            choices=choices,
            default=current_setting if current_setting in choices else None,
        )
        if new_setting == current_setting:
            print(markup.dimmed("Selected current source, nothing happened."))
            return None
        else:
            return new_setting
    except (KeyboardInterrupt, EOFError):
        sys.exit(1)


def _select_project(credentials: google.auth.credentials.Credentials) -> str:
    projects: t.Sequence["Project"] = list(
        bigquery.Client(credentials=credentials).list_projects()
    )

    project_display: t.Callable[["Project"], str] = lambda p: " | ".join(
        [
            p.friendly_name,
            p.project_id,
            p.numeric_id,
        ]
    )

    select = _questionary.select(
        message="Select GCP project.",
        choices=list(map(project_display, projects)),
        instruction="",
        use_indicator=True,
    )

    project_id: str = select.split("|")[1].strip()
    return project_id
