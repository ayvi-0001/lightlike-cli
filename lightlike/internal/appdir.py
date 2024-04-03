import logging
import shutil
import sys
from contextlib import suppress
from pathlib import Path
from typing import Final, NoReturn, Sequence

import rtoml
from prompt_toolkit.history import FileHistory, ThreadedHistory
from rich.text import Text

from lightlike import _console
from lightlike.__about__ import __appdir__, __appname__
from lightlike.internal import markup

__all__: Sequence[str] = (
    "CONFIG",
    "CACHE",
    "ENTRY_APPDATA",
    "SQL_HISTORY",
    "SQL_FILE_HISTORY",
    "REPL_HISTORY",
    "REPL_FILE_HISTORY",
    "QUERIES",
    "LOG",
    "rmtree",
)


# fmt: off
__appdir__.mkdir(exist_ok=True)

CONFIG: Final[Path] = __appdir__ / "config.toml"
CACHE: Final[Path] = __appdir__ / "cache.toml"
CACHE.touch(exist_ok=True)
ENTRY_APPDATA: Final[Path] = __appdir__ / "entry_appdata.toml"
ENTRY_APPDATA.touch(exist_ok=True)
SQL_HISTORY: Final[Path] = __appdir__ / ".sql_history"
SQL_HISTORY.touch(exist_ok=True)
SQL_FILE_HISTORY: Final[ThreadedHistory] = ThreadedHistory(FileHistory(f"{SQL_HISTORY}"))
REPL_HISTORY: Final[Path] = __appdir__ / ".repl_history"
REPL_HISTORY.touch(exist_ok=True)
REPL_FILE_HISTORY: Final[ThreadedHistory] = ThreadedHistory(FileHistory(f"{REPL_HISTORY}"))
QUERIES: Final[Path] = __appdir__ / "queries"
LOG: Final[Path] = __appdir__ / "cli.log"
# SQLITE_DB: Final[Path] = __appdir__ / "lightlike_cli.db"
# fmt: on


def rmtree(appdata: Path = __appdir__) -> NoReturn:
    logging.shutdown()
    shutil.rmtree(appdata, ignore_errors=True)
    sys.exit(1)


from lightlike.internal.update import DEFAULT_CONFIG
from lightlike.internal.utils import _identical_vectors


def validate(__version__: str, /) -> None | NoReturn:
    console = _console.get_console()
    if not _console.QUIET_START:
        console.log("Verifying app directory")

    if not CONFIG.exists():
        console.log("config.toml not found")
        console.log("Initializing new directory")
        return _initial_build()

    else:
        if not _console.QUIET_START:
            console.log("Checking for updates")

        config = rtoml.load(CONFIG)

        if not (
            _identical_vectors(
                list(rtoml.load(DEFAULT_CONFIG).keys()), list(config.keys())
            )
        ):
            console.log(
                markup.log_error("App config is either corrupt or missing keys")
            )
            console.log("Initializing new directory")
            return _initial_build()

        with suppress(Exception):
            from lightlike.__about__ import __latest_release__, __repo__
            from lightlike.internal.update import compare_version

            compare_version(__version__, __repo__, __latest_release__)

        from lightlike.internal.update import extract_version, update_cli, update_config

        if config["app"]["version"] != __version__:
            console.log(
                Text.assemble(
                    "Updating version: v",
                    markup.repr_number(
                        ".".join(map(str, extract_version(__version__)))
                    ),
                )
            )
            update_cli(CONFIG, __version__)

        update_config(CONFIG, __version__)

    return None


def _initial_build(__version__: str | None = None, /) -> None | NoReturn:
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

        from lightlike.__about__ import __appname_sc__, __version__
        from lightlike.internal import utils
        from lightlike.internal.enums import CredentialsSource
        from lightlike.internal.update import DEFAULT_CONFIG
        from lightlike.lib.third_party import _questionary

        _DEFAULT_CONFIG = rtoml.load(DEFAULT_CONFIG)

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
            Text.assemble(
                markup.repr_attrib_name("appname"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(__appname_sc__),
            )
        )
        console.log(
            Text.assemble(
                markup.repr_attrib_name("version"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(__version__),
            )
        )
        console.set_window_title(__appname_sc__)

        term = os.getenv("TERM", "unknown")
        console.log(
            Text.assemble(
                markup.repr_attrib_name("term"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(term),
            )
        )

        _DEFAULT_CONFIG["app"].update(
            name=__appname_sc__, version=__version__, term=term
        )

        user = getpass.getuser()
        console.log(
            Text.assemble(
                markup.repr_attrib_name("user"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(user),
            )
        )
        host = socket.gethostname()
        console.log(
            Text.assemble(
                markup.repr_attrib_name("host"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(host),
            )
        )

        _DEFAULT_CONFIG["user"].update(name=user, host=host)

        console.log("Determining timezone from env..")

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
            Text.assemble(
                markup.repr_attrib_name("timezone"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(timezone),
            )
        )
        _DEFAULT_CONFIG["settings"].update(timezone=timezone)

        console.print(
            Padding(
                cleandoc(
                    """
                    [u]Select method for authenticating client.[/u]

                    Methods;
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
                CredentialsSource.from_environment,
                CredentialsSource.from_service_account_key,
            ],
        )

        console.print(
            Padding(
                Text.assemble(
                    "App will create the dataset ",
                    markup.code(__appname_sc__), " in BigQuery.",  # fmt: skip
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
            Text.assemble(
                markup.repr_attrib_name("dataset"),
                markup.repr_attrib_equal(),
                markup.repr_attrib_value(dataset_name),
            )
        )

        _DEFAULT_CONFIG["bigquery"].update(dataset=dataset_name)
        _DEFAULT_CONFIG["client"].update(
            credentials_source=repr(client_credential_source)
        )
        console.log("Saving config")
        CONFIG.write_text(utils._format_toml(_DEFAULT_CONFIG))
        console.log("Building app directory")
        CONFIG.touch(exist_ok=True)
        console.log(f"Writing {CONFIG}")
        REPL_HISTORY.touch(exist_ok=True)
        console.log(f"Writing {REPL_HISTORY}")
        SQL_HISTORY.touch(exist_ok=True)
        console.log(f"Writing {SQL_HISTORY}")
        CACHE.touch(exist_ok=True)
        console.log(f"Writing {CACHE}")
        console.log("Directory build complete")

        ENTRY_APPDATA.write_text(
            '[active.no-project]\nname = "no-project"'
            '\ndescription = "default"\nnotes=[]'
        )
        return None

    except (KeyboardInterrupt, EOFError):
        sys.exit(1)

    except Exception as error:
        _console.get_console().print(
            Text.assemble(
                markup.failure(f"Failed to build app directory {error}.\n"),
                "Deleting app directory.",
            )
        )
        rmtree()
