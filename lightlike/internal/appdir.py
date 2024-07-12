import logging
import sys
import typing as t
from datetime import datetime
from pathlib import Path

import rtoml
from fasteners import interprocess_locked
from prompt_toolkit.history import FileHistory, ThreadedHistory
from rich import get_console
from rich import print as rprint
from rich.console import Console
from rich.text import Text

from lightlike import _console
from lightlike.__about__ import (
    __appdir__,
    __appname__,
    __appname_sc__,
    __config__,
    __latest_release__,
    __lock__,
    __repo__,
    __version__,
)
from lightlike.internal import constant, markup, update, utils

__all__: t.Sequence[str] = (
    "CACHE",
    "ENTRY_APPDATA",
    "SQL_HISTORY",
    "SQL_FILE_HISTORY",
    "REPL_HISTORY",
    "REPL_FILE_HISTORY",
    "QUERIES",
    "TIMER_LIST_CACHE",
    "LOGS",
    "rmtree",
    "_log",
    "console_log_error",
)


# fmt: off
__appdir__.mkdir(exist_ok=True)

CACHE: t.Final[Path] = __appdir__ / "cache.toml"
CACHE.touch(exist_ok=True)
ENTRY_APPDATA: t.Final[Path] = __appdir__ / "entry_appdata.toml"
ENTRY_APPDATA.touch(exist_ok=True)
SQL_HISTORY: t.Final[Path] = __appdir__ / ".sql_history"
SQL_HISTORY.touch(exist_ok=True)
SQL_FILE_HISTORY: t.Final[t.Callable[..., ThreadedHistory]] = lambda: ThreadedHistory(FileHistory(f"{SQL_HISTORY}"))
REPL_HISTORY: t.Final[Path] = __appdir__ / ".repl_history"
REPL_HISTORY.touch(exist_ok=True)
REPL_FILE_HISTORY: t.Final[t.Callable[..., ThreadedHistory]] = lambda: ThreadedHistory(FileHistory(f"{REPL_HISTORY}"))
QUERIES: t.Final[Path] = __appdir__ / "queries"
TIMER_LIST_CACHE: t.Final[Path] = __appdir__ / "timer_list_cache.json"
LOGS: t.Final[Path] = __appdir__ / "logs"
LOGS.mkdir(exist_ok=True)
# fmt: on


logging.basicConfig(
    level=logging.DEBUG,
    filename=LOGS / "cli.log",
    filemode="a",
    format="[%(asctime)s] %(pathname)s:%(lineno)d\n%(levelname)s: %(message)s",
    datefmt="%m-%d %H:%M:%S",
)


def _log() -> logging.Logger:
    return logging.getLogger(__appname_sc__)


def rmtree(appdata: Path = __appdir__) -> t.NoReturn:
    import logging
    import shutil

    logging.shutdown()
    shutil.rmtree(appdata, ignore_errors=True)
    sys.exit(1)


_interprocess_locked: t.Callable[..., t.Any] = interprocess_locked

VersionTuple: t.TypeAlias = tuple[int, int, int]


@_interprocess_locked(__appdir__ / "config.lock")  # type:ignore[misc]
def validate(__version__: str, __config__: Path, /) -> None | t.NoReturn:
    console = get_console()

    _console.if_not_quiet_start(console.log)("Validating app directory")

    update._patch_appdir_lt_v_0_9_0(__appdir__, __config__)

    if not __config__.exists():
        console.log(f"{__config__} not found")
        console.log("Initializing app directory")
        return _initial_build()
    else:
        v_package: VersionTuple = update.extract_version(__version__)
        local_config: dict[str, t.Any] = rtoml.load(__config__)

        last_checked_release: datetime | None = local_config["app"].get(
            "last_checked_release"
        )

        if not last_checked_release or (
            last_checked_release
            and last_checked_release.date() < datetime.today().date()
        ):
            _console.if_not_quiet_start(console.log)("Checking latest release")
            update.check_latest_release(v_package, __repo__, __latest_release__)
            last_checked_release = datetime.now()

        _console.if_not_quiet_start(console.log)("Checking config")

        v_local: VersionTuple = update.extract_version(local_config["app"]["version"])

        if v_local < v_package:
            console.log(
                "Updating version: v",
                markup.repr_number(".".join(map(str, v_package))),
                sep="",
            )
            v_local < (0, 9, 0) and update._patch_cache_lt_v_0_9_0(__appdir__)

            updated_config = utils.update_dict(
                rtoml.load(constant.DEFAULT_CONFIG), local_config
            )
            updated_config["app"].update(version=__version__)
            local_config = updated_config

        local_config["app"].update(last_checked_release=last_checked_release)
        __config__.write_text(utils._format_toml(local_config))

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
        _console.reconfigure()
        console = get_console()

        import getpass
        import os
        import socket
        from inspect import cleandoc

        from prompt_toolkit.validation import Validator
        from pytz import all_timezones
        from rich.markdown import Markdown
        from rich.padding import Padding

        from lightlike.app import _questionary
        from lightlike.internal.enums import CredentialsSource

        default_config = rtoml.load(constant.DEFAULT_CONFIG)

        license = Markdown(
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

        console.rule(style="#9146ff")
        _console.reconfigure(height=17)
        console.print(Padding(license, (0, 0, 1, 1)))
        _console.reconfigure(height=None)
        _questionary.press_any_key_to_continue(message="Press any key to continue.")

        utils._nl()
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
        console.set_window_title(__appname_sc__)

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

        default_timezone = utils._get_local_timezone_string()
        if default_timezone is None:
            console.log(markup.log_error("Could not determine timezone"))
            default_timezone = "UTC"

        utils._nl()
        timezone = _questionary.autocomplete(
            message="Enter timezone $",
            choices=all_timezones,
            default=default_timezone,
            validate=Validator.from_callable(
                lambda d: d in all_timezones,
                error_message="Invalid timezone.",
            ),
        )

        utils._nl()
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

        utils._nl()
        client_credential_source = _questionary.select(
            message="Select authorization",
            choices=[
                CredentialsSource.from_service_account_key,
                CredentialsSource.from_environment,
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

        utils._nl()
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
        console.log("Saving config")

        __config__.write_text(utils._format_toml(default_config))
        console.log("Building app directory")
        __config__.touch(exist_ok=True)
        console.log(f"Writing {__config__}")
        console.log(f"Writing {REPL_HISTORY}")
        console.log(f"Writing {SQL_HISTORY}")
        console.log(f"Writing {CACHE}")
        console.log("Directory build complete")

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
        return None

    except (KeyboardInterrupt, EOFError):
        sys.exit(1)

    except Exception as error:
        rprint(markup.failure("Failed build:"), error)
        rprint(markup.failure("Deleting app directory."))
        rmtree()
