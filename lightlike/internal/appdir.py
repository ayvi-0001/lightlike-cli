# mypy: disable-error-code="func-returns-value, import-untyped"

import sys
import typing as t
from pathlib import Path

import rtoml
from fasteners import interprocess_locked
from prompt_toolkit.history import FileHistory, ThreadedHistory
from rich import print as rprint
from rich.text import Text

from lightlike import _console
from lightlike.__about__ import (
    __appdir__,
    __appname__,
    __config__,
    __latest_release__,
    __lock__,
    __repo__,
)
from lightlike.internal import markup

__all__: t.Sequence[str] = (
    "CACHE",
    "ENTRY_APPDATA",
    "SQL_HISTORY",
    "SQL_FILE_HISTORY",
    "REPL_HISTORY",
    "REPL_FILE_HISTORY",
    "QUERIES",
    "LOGS",
    "TIMER_LIST_CACHE",
    "rmtree",
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


def rmtree(appdata: Path = __appdir__) -> t.NoReturn:
    import logging
    import shutil

    logging.shutdown()
    shutil.rmtree(appdata, ignore_errors=True)
    sys.exit(1)


from lightlike.internal import utils
from lightlike.internal.toml import DEFAULT_CONFIG
from lightlike.internal.update import (
    _patch_appdir_lt_v_0_9_0,
    _patch_cache_lt_v_0_9_0,
    check_latest_release,
    extract_version,
)


@interprocess_locked(__appdir__ / "config.lock")
def validate(__version__: str, __config__: Path, /) -> None | t.NoReturn:
    console = _console.get_console()

    not _console.QUIET_START and console.log("Validating app directory")

    _patch_appdir_lt_v_0_9_0(__appdir__, __config__)

    if not __config__.exists():
        console.log(f"{__config__} not found")
        console.log("Initializing app directory")
        return _initial_build()
    else:
        not _console.QUIET_START and console.log("Checking for updates")

        v_package: tuple[int, int, int] = extract_version(__version__)

        check_latest_release(v_package, __repo__, __latest_release__)

        local_config = rtoml.load(__config__)

        v_local = extract_version(local_config["app"]["version"])
        v_local < v_package and console.log(
            "Updating version: v",
            markup.repr_number(".".join(map(str, v_package))),
            sep="",
        )
        v_local < (0, 9, 0) and _patch_cache_lt_v_0_9_0(__appdir__)

        updated_config = utils.update_dict(
            original=rtoml.load(DEFAULT_CONFIG),
            updates=local_config,
            ignore=["cli", "lazy_subcommands"],
        )
        updated_config["app"].update(version=__version__)
        __config__.write_text(utils._format_toml(updated_config))

    return None


def _initial_build() -> None | t.NoReturn:
    try:
        _console.reconfigure()
        console = _console.get_console()

        import getpass
        import os
        import socket
        from inspect import cleandoc

        from prompt_toolkit.validation import Validator
        from rich.markdown import Markdown
        from rich.padding import Padding

        from lightlike.__about__ import __appname_sc__, __config__, __version__
        from lightlike.internal.enums import CredentialsSource
        from lightlike.lib.third_party import _questionary

        default_config = rtoml.load(DEFAULT_CONFIG)

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

        from pytz import all_timezones

        if os.name == "nt":
            from tzlocal import get_localzone_name

            default_timezone = get_localzone_name()
        else:
            from tzlocal.unix import _get_localzone_name

            default_timezone = _get_localzone_name()

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
        REPL_HISTORY.touch(exist_ok=True)
        console.log(f"Writing {REPL_HISTORY}")
        SQL_HISTORY.touch(exist_ok=True)
        console.log(f"Writing {SQL_HISTORY}")
        CACHE.touch(exist_ok=True)
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
