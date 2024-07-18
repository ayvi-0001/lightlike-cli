import json
import sys
import typing as t
from functools import partial
from inspect import cleandoc
from pathlib import Path

import rtoml
from google.auth.exceptions import DefaultCredentialsError
from google.cloud.bigquery import Client
from prompt_toolkit import PromptSession
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator
from pytz import timezone
from rich import get_console
from rich import print as rprint
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from lightlike import _console
from lightlike.app import _questionary
from lightlike.app.config import AppConfig
from lightlike.client.auth import AuthPromptSession, _Auth
from lightlike.internal import constant, markup, utils
from lightlike.internal.enums import CredentialsSource

if t.TYPE_CHECKING:
    from google.cloud.bigquery.client import Project


__all__: t.Sequence[str] = (
    "get_client",
    "reconfigure",
    "authorize_client",
    "_select_credential_source",
    "_select_project",
    "service_account_key_flow",
    "_authorize_from_service_account_key",
    "_authorize_from_environment",
    "provision_bigquery_resources",
)


P = t.ParamSpec("P")


CLIENT: Client | None = None


def get_client(*args: P.args, **kwargs: P.kwargs) -> Client:
    global CLIENT
    if CLIENT is None:
        _console.if_not_quiet_start(get_console().log)("Authorizing BigQuery Client")
        CLIENT = authorize_client()
    return CLIENT


def reconfigure(*args: P.args, **kwargs: P.kwargs) -> None:
    NEW_CLIENT = authorize_client()
    global CLIENT
    CLIENT = get_client()
    CLIENT = NEW_CLIENT


def authorize_client() -> Client:
    credentials_source: str = AppConfig().get("client", "credentials_source")

    try:
        match credentials_source:
            case CredentialsSource.from_service_account_key:
                client = _authorize_from_service_account_key()

            case CredentialsSource.from_environment:
                client = _authorize_from_environment()

            case CredentialsSource.not_set:
                _console.if_not_quiet_start(get_console().log)(
                    markup.log_error("Client configuration not found")
                )
                with AppConfig().rw() as config:
                    config["client"].update(
                        credentials_source=_select_credential_source()
                    )

                return authorize_client()

        resources_provisioned = AppConfig().get("bigquery", "resources_provisioned")
        updates = AppConfig().get("updates")

        if not resources_provisioned:
            provision_bigquery_resources(client)
        elif updates and any([updates[k] is False for k in updates]):
            provision_bigquery_resources(client, updates=updates)

        return client

    except KeyboardInterrupt:
        sys.exit(1)
    except DefaultCredentialsError as error:
        rprint(
            # fmt: off
            markup.failure(f"Auth failed: {error}"), "\nProvided either a service account key, ",
            "or double check your application default credentials. ",
            markup.dimmed("(try running "), markup.code("gcloud init"), markup.dimmed(")"),
            # fmt: on
            sep="",
        )
        sys.exit(2)

    except Exception as error:
        if "cannot access local variable 'service_account_key'" in f"{error}":
            rprint(markup.failure(f"Auth Failed. Incorrect Pass."))
        else:
            rprint(markup.failure(f"Auth failed: {error}"))
            if credentials_source == CredentialsSource.from_service_account_key:
                AppConfig()._update_user_credentials(
                    password="null", stay_logged_in=False
                )

        return authorize_client()


def _select_credential_source() -> str | None | t.NoReturn:
    try:
        choices = [
            CredentialsSource.from_environment,
            CredentialsSource.from_service_account_key,
        ]

        current_setting = AppConfig().get("client", "credentials_source")

        source: str = _questionary.select(
            message="Select GCP project.",
            choices=choices,
            style=Style.from_dict(
                utils.update_dict(
                    rtoml.load(constant.PROMPT_STYLE),
                    AppConfig().get("prompt", "style", default={}),
                )
            ),
            cursor=CursorShape.BLOCK,
            default=current_setting if current_setting in choices else None,
        )

        if source == current_setting:
            rprint(markup.dimmed("Selected current source, nothing happened."))
            return None
        else:
            return source

    except (KeyboardInterrupt, EOFError):
        sys.exit(1)


def _select_project(client: Client) -> str:
    projects: t.Sequence["Project"] = list(client.list_projects())

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
        style=Style.from_dict(
            utils.update_dict(
                rtoml.load(constant.PROMPT_STYLE),
                AppConfig().get("prompt", "style", default={}),
            )
        ),
        cursor=CursorShape.BLOCK,
        instruction="",
        use_indicator=True,
    )

    project_id: str = select.split("|")[1].strip()
    return project_id


def service_account_key_flow() -> tuple[bytes, bytes]:
    encrypted_key: bytes | None = AppConfig().get("client", "service_account_key")
    salt: bytes | None = AppConfig().get("user", "salt")

    if not (encrypted_key and salt):
        _console.if_not_quiet_start(get_console().log)(
            "Initializing new service-account config"
        )

        auth: _Auth = _Auth()

        panel: Panel = Panel.fit(
            Text.assemble(
                "Create a password. ",
                "This will be used to encrypt your service-account key.\n",
                "You will need it again to load this cli. ",
                "Type password (will not be echoed) and press ",
                markup.code("enter"),
                " to continue.",
            )
        )
        rprint(Padding(panel, (1, 0, 0, 1)))

        hashed_password, salt = AuthPromptSession().prompt_new_password()
        key_derivation: bytes = auth._generate_key(hashed_password.hexdigest(), salt)

        utils._nl()
        if _questionary.confirm(message="Stay logged in?"):
            AppConfig()._update_user_credentials(
                password=hashed_password.hexdigest(),
                stay_logged_in=True,
            )

        service_account: str = prompt_service_account_key()
        encrypted_key = auth.encrypt(key_derivation, service_account)

        AppConfig()._update_user_credentials(salt=salt)
        with AppConfig().rw() as config:
            config["client"].update(service_account_key=encrypted_key)

        del hashed_password
        del key_derivation

    return encrypted_key, salt


def _authorize_from_service_account_key() -> Client:
    console = get_console()
    _console.if_not_quiet_start(console.log)(
        "Getting credentials from service-account-key"
    )

    encrypted_key, salt = service_account_key_flow()

    client: Client = Client.from_service_account_info(
        AuthPromptSession().authenticate(
            salt=salt,
            encrypted_key=encrypted_key,
            saved_password=AppConfig().saved_password,
            stay_logged_in=AppConfig().stay_logged_in,
            saved_credentials_failed=partial(
                AppConfig()._update_user_credentials,
                password="null",
                stay_logged_in=False,
            ),
        )
    )

    with AppConfig().rw() as config:
        config["client"].update(
            credentials_source=CredentialsSource.from_service_account_key,
            active_project=client.project,
        )

    import lightlike.app.cursor

    lightlike.app.cursor.GCP_PROJECT = client.project

    _console.if_not_quiet_start(console.log)("Client authenticated")
    return client


def _authorize_from_environment() -> Client:
    import google.auth

    console = get_console()

    _console.if_not_quiet_start(console.log)("Getting credentials from environment")
    active_project: str = AppConfig().get("client", "active_project")

    if active_project != "null" and active_project is not None:
        credentials, project_id = google.auth.default(quota_project_id=active_project)

        client = Client(project=active_project, credentials=credentials)

        with AppConfig().rw() as config:
            config["client"].update(active_project=active_project)

        import lightlike.app.cursor

        lightlike.app.cursor.GCP_PROJECT = active_project

        _console.if_not_quiet_start(console.log)("Client authenticated")
        _console.if_not_quiet_start(console.log)(
            "Current project:", markup.code(active_project)
        )
        return client

    else:
        credentials, project_id = google.auth.default()

        _console.if_not_quiet_start(console.log)(
            "Default project:", markup.code(project_id)
        )

        if not _questionary.confirm(
            message=f"Continue with project: {project_id}?", auto_enter=True
        ):
            project_id = _select_project(Client(credentials=credentials))

        _console.if_not_quiet_start(console.log)(
            "Current project:", markup.code(project_id)
        )

        credentials = credentials.with_quota_project(project_id)

        client = Client(project=project_id, credentials=credentials)

        with AppConfig().rw() as config:
            config["client"].update(
                credentials_source=CredentialsSource.from_environment,
                active_project=client.project,
            )

        import lightlike.app.cursor

        lightlike.app.cursor.GCP_PROJECT = client.project

        _console.if_not_quiet_start(console.log)("Client authenticated")
        return client


def prompt_service_account_key() -> str:
    auth_keybinds: KeyBindings = KeyBindings()
    hidden: list[bool] = [True]

    @auth_keybinds.add(Keys.ControlT, eager=True)
    def _(event: KeyPressEvent) -> None:
        hidden[0] = not hidden[0]

    panel = Panel.fit(
        Text.assemble(
            "Copy and paste service-account key. Press ",
            markup.code("esc enter"),
            " to continue.",
        )
    )
    rprint(Padding(panel, (1, 0, 1, 1)))

    session: PromptSession[str] = PromptSession(
        message="(service-account-key) $ ",
        style=Style.from_dict(
            utils.update_dict(
                rtoml.load(constant.PROMPT_STYLE),
                AppConfig().get("prompt", "style", default={}),
            )
        ),
        cursor=CursorShape.BLOCK,
        multiline=True,
        refresh_interval=1,
        erase_when_done=True,
        key_bindings=auth_keybinds,
        is_password=Condition(lambda: hidden[0]),
        validator=Validator.from_callable(
            lambda d: False if not d else True,
            error_message="Input cannot be None.",
        ),
    )

    service_account_key = None

    try:
        while not service_account_key:
            key_input = session.prompt()
            try:
                key = json.loads(key_input)
            except json.JSONDecodeError:
                rprint(markup.br("Invalid json."))
                continue
            else:
                if "client_email" not in key.keys():
                    rprint(
                        "Invalid service-account json. Missing required key",
                        markup.code("client_email"),
                    )
                    continue
                if "token_uri" not in key.keys():
                    rprint(
                        "Invalid service-account json. Missing required key",
                        markup.code("token_uri"),
                    )
                    continue
                service_account_key = key_input
    except (KeyboardInterrupt, EOFError):
        rprint(markup.br("Aborted"))
        sys.exit(2)

    return service_account_key


def provision_bigquery_resources(
    client: Client,
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

    mapping: dict[str, t.Any] = AppConfig().get("bigquery")
    bq_patterns = {
        "${DATASET.NAME}": mapping["dataset"],
        "${TABLES.TIMESHEET}": mapping["timesheet"],
        "${TABLES.PROJECTS}": mapping["projects"],
        "${TIMEZONE}": f"{timezone(AppConfig().get('settings', 'timezone'))}",
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


def update_routine_diff(client: Client) -> None:
    try:
        from more_itertools import flatten, interleave_longest

        from lightlike.app import _get
        from lightlike.client.routines import CliQueryRoutines

        console = get_console()
        routine = CliQueryRoutines()

        dataset = AppConfig().get("bigquery", "dataset")
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
                mapping: dict[str, t.Any] = AppConfig().get("bigquery")
                bq_patterns = {
                    "${DATASET.NAME}": mapping["dataset"],
                    "${TABLES.TIMESHEET}": mapping["timesheet"],
                    "${TABLES.PROJECTS}": mapping["projects"],
                    "${TIMEZONE}": f"{timezone(AppConfig().get('settings', 'timezone'))}",
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
                        script = utils._regexp_replace(
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
