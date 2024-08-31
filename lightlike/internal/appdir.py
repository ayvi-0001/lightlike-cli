import logging
import sys
import typing as t
from datetime import datetime
from inspect import cleandoc
from pathlib import Path

import rtoml
from packaging.version import Version
from prompt_toolkit.history import FileHistory, ThreadedHistory
from rich import get_console
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from lightlike import _console, _fasteners
from lightlike.__about__ import (
    __appdir__,
    __appname__,
    __appname_sc__,
    __config__,
    __lock__,
    __repo__,
    __version__,
)
from lightlike.internal import constant, enums, markup, utils

__all__: t.Sequence[str] = (
    "CACHE",
    "CACHE_LOCK",
    "ENTRY_APPDATA",
    "SQL_HISTORY",
    "SQL_FILE_HISTORY",
    "REPL_HISTORY",
    "REPL_FILE_HISTORY",
    "QUERIES",
    "TIMER_LIST_CACHE",
    "LOGS",
    "SCHEDULER_CONFIG",
    "rmtree",
    "log",
    "console_log_error",
)


# fmt: off
__appdir__.mkdir(exist_ok=True)

CACHE: t.Final[Path] = __appdir__ / ".local_entries"
CACHE.touch(exist_ok=True)
CACHE_LOCK: t.Final[Path] = __appdir__ / "cache.lock"
CACHE_LOCK.touch(exist_ok=True)
ENTRY_APPDATA: t.Final[Path] = __appdir__ / ".entry_appdata"
ENTRY_APPDATA.touch(exist_ok=True)
SQL_HISTORY: t.Final[Path] = __appdir__ / ".sql_history"
SQL_HISTORY.touch(exist_ok=True)
SQL_FILE_HISTORY: t.Final[t.Callable[[], ThreadedHistory]] = lambda: ThreadedHistory(FileHistory(f"{SQL_HISTORY}"))
REPL_HISTORY: t.Final[Path] = __appdir__ / ".repl_history"
REPL_HISTORY.touch(exist_ok=True)
REPL_FILE_HISTORY: t.Final[t.Callable[[], ThreadedHistory]] = lambda: ThreadedHistory(FileHistory(f"{REPL_HISTORY}"))
QUERIES: t.Final[Path] = __appdir__ / "queries"
TIMER_LIST_CACHE: t.Final[Path] = __appdir__ / ".tl_ids_latest.json"
LOGS: t.Final[Path] = __appdir__ / "logs"
LOGS.mkdir(exist_ok=True)
SCHEDULER_CONFIG: t.Final[Path] = __appdir__ / "scheduler.toml"
APSCHEDULER_DB: t.Final[Path] = __appdir__ / "apscheduler.db"
APSCHEDULER_DB.touch(exist_ok=True)
# fmt: on


_TODAY: datetime = datetime.today()
_DAILY_LOG_DIR: Path = LOGS / _TODAY.strftime("%Y.%m.%d")
_DAILY_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    filename=(_DAILY_LOG_DIR / _TODAY.strftime("%H.%M.%S.%f")).with_suffix(".log"),
    filemode="a",
    format="[%(asctime)s] %(pathname)s:%(lineno)d\n%(levelname)s: %(message)s",
    datefmt="%m-%d %H:%M:%S",
)


def log() -> logging.Logger:
    return logging.getLogger(__appname_sc__)


def rmtree(appdata: Path = __appdir__) -> t.NoReturn:
    import logging
    import shutil

    logging.shutdown()
    shutil.rmtree(appdata, ignore_errors=True)
    sys.exit(1)


CONFIG_UPDATE_PATHS: list[str] = [
    "app.name",
    "bigquery.dataset",
    "bigquery.projects",
    "bigquery.resources_provisioned",
    "bigquery.timesheet",
    "bigquery",
    "client.credentials_source",
    "completers.default",
    "keys.completers.commands",
    "keys.completers.exec",
    "keys.completers.history",
    "keys.completers.path",
    "keys.completers",
    "keys.exit",
    "keys.system-command",
    "scheduler",
    "settings.complete_style",
    "settings.dateparser.additional_date_formats",
    "settings.dateparser.prefer_dates_from",
    "settings.dateparser.prefer_day_of_month",
    "settings.dateparser.prefer_locale_date_order",
    "settings.dateparser.prefer_month_of_year",
    "settings.editor",
    "settings.note_history.days",
    "settings.quiet_start",
    "settings.reserve_space_for_menu",
    "settings.timer_add_min",
    "settings.week_start",
    "settings.update-terminal-title",
    "user.host",
    "user.name",
    "user.stay_logged_in",
]
CONFIG_FORCE_UPDATE_PATHS: list[str] = [
    "app.version",
]


@_fasteners.interprocess_locked(__appdir__ / "config.lock", logger=log())
def validate(__version__: str, __config__: Path, /) -> None | t.NoReturn:
    console = get_console()
    _console.if_not_quiet_start(console.log)("Validating app directory")

    if utils.file_empty_or_not_exists(__config__):
        console.log(f"{__config__} not found")
        console.log("Initializing app directory")
        return _initial_build()
    else:
        local_config: dict[str, t.Any] = rtoml.load(__config__)

        v_local: Version = Version(local_config["app"]["version"])
        v_package: Version = Version(__version__)

        if v_local < v_package:
            console.log(
                "Updating version:", f"[repr.number]{v_local}[/]",
                "->", f"[repr.number]{v_package}[/]",  # fmt: skip
            )

        local_config = utils.merge_default_dict_into_current_dict(
            local_config,
            rtoml.load(constant.DEFAULT_CONFIG),
            update_paths=CONFIG_UPDATE_PATHS,
            force_update_paths=CONFIG_FORCE_UPDATE_PATHS,
        )

        __config__.write_text(utils.format_toml(local_config))

    return None


def console_log_error(error: Exception, notify: bool, patch_stdout: bool) -> None:
    error_logs: Path = LOGS / "errors"
    error_logs.mkdir(exist_ok=True)
    timestamp: str = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
    file_name: str = f"{error.__class__.__name__}_{timestamp}.log"
    error_log: Path = error_logs / file_name

    with Console(record=True, width=200) as console:
        console.begin_capture()
        console.print_exception(show_locals=True, width=console.width)
        console.save_text(f"{error_log!s}", clear=True)
        console.end_capture()

    if notify:
        notice: str = (
            f"\n[b][red]Encountered an unexpected error:[/] {error!r}."
            "\nIf you'd like to create an issue for this, you can submit @ "
            "[repr.url]https://github.com/ayvi-0001/lightlike-cli/issues/new[/repr.url]."
            "\nPlease include any relevant info in the traceback found at:"
            f"\n[repr.url]{error_log.as_uri()}[/repr.url]\n"
        )
        if patch_stdout:
            from prompt_toolkit.patch_stdout import patch_stdout as _patch_stdout

            with _patch_stdout(raw=True):
                rprint(notice)
        else:
            rprint(notice)


def _initial_build() -> None | t.NoReturn:
    try:
        import getpass
        import os
        import socket

        from prompt_toolkit.validation import Validator
        from pytz import all_timezones
        from rich.console import NewLine
        from rich.padding import Padding

        from lightlike.app import _questionary
        from lightlike.app.config import AppConfig

        console = get_console()
        default_config = rtoml.load(constant.DEFAULT_CONFIG)

        console.rule(style="#9146ff")
        _console.reconfigure(height=17)
        console.print(Padding(_get_license(), (0, 0, 1, 1)))
        _console.reconfigure(height=None)
        _questionary.press_any_key_to_continue(message="Press any key to continue.")

        console.print(NewLine())
        console.log("Writing config")
        console.log(
            markup.repr_attrib_name("appname"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(__appname_sc__),
            sep="",
        )
        console.log(
            markup.repr_attrib_name("version"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(__version__),
            sep="",
        )

        term = os.getenv("TERM", "unknown")
        console.log(
            markup.repr_attrib_name("term"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(term),
            sep="",
        )

        default_config["app"].update(
            name=__appname_sc__, version=__version__, term=term
        )

        user = getpass.getuser()
        console.log(
            markup.repr_attrib_name("user"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(user),
            sep="",
        )
        host = socket.gethostname()
        console.log(
            markup.repr_attrib_name("host"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(host),
            sep="",
        )

        default_config["user"].update(name=user, host=host)

        console.log("Determining timezone from env")

        default_timezone = utils.get_local_timezone_string()
        if default_timezone is None:
            console.log(markup.log_error("Could not determine timezone"))
            default_timezone = "UTC"

        console.print(NewLine())
        timezone = _questionary.autocomplete(
            message="Enter timezone $",
            choices=all_timezones,
            default=default_timezone,
            validate=Validator.from_callable(
                lambda d: d in all_timezones,
                error_message="Invalid timezone.",
            ),
        )

        console.print(NewLine())
        console.log(
            markup.repr_attrib_name("timezone"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(timezone),
            sep="",
        )
        default_config["settings"].update(timezone=timezone)

        console.print(
            Padding(
                cleandoc(
                    """
                    [u]Select method for authenticating client.[/u]

                    Methods:
                        ▸ [b][u]from-environment[/b][/u]
                          Let the client determine credentials from the current environment.
                          This will likely use Application Default Credentials.
                          If you have the Google Cloud SDK installed, try [code]gcloud init[/code] or [code]gcloud auth application-default login[/code].
                        
                        ▸ [b][u]from-service-account-key[/b][/u]
                          Copy and paste a service-account key.
                          You will be prompted to provide a password, which will be used to encrypt the json file.
                    """
                ),
                (1, 1, 0, 1),
            )
        )

        console.print(NewLine())
        client_credential_source = _questionary.select(
            message="Select authorization",
            choices=[
                enums.CredentialsSource.from_service_account_key,
                enums.CredentialsSource.from_environment,
            ],
        )

        console.print(
            Padding(
                Text.assemble(
                    "App will create the dataset ",
                    markup.code(__appname_sc__),
                    " in BigQuery.",
                ),
                (1, 0, 1, 1),
            )
        )

        if _questionary.confirm(message="Do you want to rename this?", auto_enter=True):
            from lightlike.internal.bq_resources.resource import ResourceName

            console.print(
                Padding(
                    Text.assemble("Enter ", markup.code("${NAME}")),
                    (1, 0, 1, 1),
                )
            )
            dataset_name = _questionary.text(message="$", validate=ResourceName())
        else:
            dataset_name = __appname_sc__

        console.print(NewLine())
        console.log(
            markup.repr_attrib_name("dataset"),
            markup.repr_attrib_equal(),
            markup.repr_attrib_value(dataset_name),
            sep="",
        )

        default_config["bigquery"].update(dataset=dataset_name)
        default_config["client"].update(
            credentials_source=repr(client_credential_source)
        )

        default_config["cli"].update(add_to_path=[__appdir__.as_posix()])

        console.log("Building app directory")
        console.log("Saving config")
        __config__.write_text(utils.format_toml(default_config))
        __config__.touch(exist_ok=True)
        console.log(f"Writing {__config__}")
        console.log(f"Writing {REPL_HISTORY}")
        console.log(f"Writing {SQL_HISTORY}")
        console.log(f"Writing {CACHE}")
        console.log(f"Writing {SCHEDULER_CONFIG}")
        SCHEDULER_CONFIG.touch(exist_ok=True)
        SCHEDULER_CONFIG.write_text(
            constant.DEFAULT_SCHEDULER_TOML
            % (
                timezone,
                "sqlite:///" + __appdir__.joinpath("apscheduler.db").as_posix(),
            )
        )
        console.log(f"Writing {ENTRY_APPDATA}")
        ENTRY_APPDATA.write_text(
            cleandoc(
                """
                [active.no-project]
                name = "no-project"
                description = "default"
                default_billable = false
                notes = []
                """
            )
        )
        console.log("Directory build complete")

        return None
    except (KeyboardInterrupt, EOFError):
        sys.exit(1)
    except Exception as error:
        rprint(markup.failure("Failed build:"), error)
        rprint(markup.failure("Deleting app directory."))
        rmtree()


def _get_license() -> Markdown:
    return Markdown(
        markup=cleandoc(
            """
            MIT License

            Copyright (c) 2024 ayvi-0001

            Permission is hereby granted, free of charge, to any person obtaining a copy
            of this software and associated documentation files (the "Software"), to deal
            in the Software without restriction, including without limitation the rights
            to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
            copies of the Software, and to permit persons to whom the Software is
            furnished to do so, subject to the following conditions:

            The above copyright notice and this permission notice shall be included in all
            copies or substantial portions of the Software.

            THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
            IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
            FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
            AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
            LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
            OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
            SOFTWARE.
                """
        ),
        justify="left",
    )
