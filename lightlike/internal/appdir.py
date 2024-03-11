import logging
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Final, NoReturn, Sequence

import rtoml
from prompt_toolkit.history import FileHistory, ThreadedHistory

from lightlike import _console
from lightlike.__about__ import __appdir__, __appname__

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

CONFIG: Final[Path] = __appdir__.joinpath("config.toml")
CACHE: Final[Path] = __appdir__.joinpath("cache.toml")
CACHE.touch(exist_ok=True)
ENTRY_APPDATA: Final[Path] = __appdir__.joinpath("entry_appdata.toml")
ENTRY_APPDATA.touch(exist_ok=True)
SQL_HISTORY: Final[Path] = __appdir__.joinpath(".sql_history")
SQL_HISTORY.touch(exist_ok=True)
SQL_FILE_HISTORY: Final[ThreadedHistory] = ThreadedHistory(FileHistory(f"{SQL_HISTORY}"))
REPL_HISTORY: Final[Path] = __appdir__.joinpath(".repl_history")
REPL_HISTORY.touch(exist_ok=True)
REPL_FILE_HISTORY: Final[ThreadedHistory] = ThreadedHistory(FileHistory(f"{REPL_HISTORY}"))
QUERIES: Final[Path] = __appdir__.joinpath("queries")
LOG: Final[Path] = __appdir__.joinpath("cli.log")
# SQLITE_DB: Final[Path] = __appdir__.joinpath("lightlike_cli.db")
# fmt: on


def rmtree(appdata: Path = __appdir__) -> NoReturn:
    logging.shutdown()
    shutil.rmtree(appdata)
    exit(1)


def validate(__version__: str, /) -> None | NoReturn:
    console = _console.get_console()
    console.log("[log.main]Verifying app directory")

    if not CONFIG.exists():
        console.log("[log.error]App config not found")
        console.log("[log.main]Initializing new directory")
        return _initial_build()

    elif CONFIG.exists():
        console.log("[log.main]Checking for updates")
        with suppress(Exception):
            from lightlike.__about__ import __latest_release__, __repo__
            from lightlike.internal.update import compare_version

            compare_version(__version__, __repo__, __latest_release__)

        from lightlike.internal.update import _update_config, update_cli

        _update_config(CONFIG, __version__)

        if rtoml.load(CONFIG)["app"]["version"] != __version__:
            console.log("[log.main]Updating version")
            update_cli(CONFIG, __version__)

    return None


def _initial_build(__version__: str | None = None, /) -> None | NoReturn:
    try:
        _console.reconfigure()
        console = _console.get_console()

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
        console.log("[log.main]Writing config")
        console.log(
            f"[repr.attrib_name]appname[/repr.attrib_name]"
            f"[repr.attrib_equal]=[/repr.attrib_equal][repr.attrib_value]{__appname_sc__}"
        )
        console.log(
            f"[repr.attrib_name]version[/repr.attrib_name]"
            f"[repr.attrib_equal]=[/repr.attrib_equal][repr.attrib_value]{__version__}"
        )
        console.set_window_title(__appname_sc__)

        term = os.getenv("TERM", "unknown")
        console.log(
            f"[repr.attrib_name]term[/repr.attrib_name]"
            f"[repr.attrib_equal]=[/repr.attrib_equal][repr.attrib_value]{term}"
        )

        _DEFAULT_CONFIG["app"].update(
            name=__appname_sc__, version=__version__, term=term
        )

        user = os.getlogin()
        console.log(
            "[repr.attrib_name]user[/repr.attrib_name]"
            "[repr.attrib_equal]=[/repr.attrib_equal]"
            f"[repr.attrib_value]{user}"
        )
        host = socket.gethostname()
        console.log(
            "[repr.attrib_name]host[/repr.attrib_name]"
            "[repr.attrib_equal]=[/repr.attrib_equal]"
            f"[repr.attrib_value]{host}"
        )

        _DEFAULT_CONFIG["user"].update(name=user, host=host)

        console.log("[log.main]Determining timezone from env..")

        from pytz import all_timezones

        if os.name == "nt":
            from tzlocal import get_localzone_name

            default_timezone = get_localzone_name()
        else:
            from tzlocal.unix import _get_localzone_name

            default_timezone = _get_localzone_name()

        if default_timezone is None:
            console.log("[log.error]Could not determine timezone")
            default_timezone = "UTC"

        utils._nl()
        timezone = _questionary.autocomplete(
            message="Enter timezone $",
            choices=all_timezones,
            default=default_timezone,
            validate=Validator.from_callable(
                lambda d: False if d not in all_timezones else True,
                error_message="Invalid timezone.",
            ),
        )

        utils._nl()
        console.log(
            "[repr.attrib_name]timezone[/repr.attrib_name]"
            "[repr.attrib_equal]=[/repr.attrib_equal]"
            f"[repr.attrib_value]{timezone}"
        )
        _DEFAULT_CONFIG["settings"].update(timezone=timezone)

        console.print(
            Padding(
                cleandoc(
                    f"""
                    [i][u]Select method for authenticating client.[/i][/u]

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
                f"App will create the dataset [code]{__appname_sc__}[/code] in BigQuery.",
                (1, 0, 1, 1),
            )
        )

        if _questionary.confirm(message="Do you want to rename this?", auto_enter=True):
            from lightlike.internal.bq_resources.resource import ResourceName

            console.print(Padding("[b]Enter [code]${NAME}[/code].", (1, 0, 1, 1)))
            dataset_name = _questionary.text(message="$", validate=ResourceName())
        else:
            dataset_name = __appname_sc__

        utils._nl()
        console.log(
            "[repr.attrib_name]dataset[/repr.attrib_name]"
            "[repr.attrib_equal]=[/repr.attrib_equal]"
            f"[repr.attrib_value]{dataset_name}"
        )

        _DEFAULT_CONFIG["bigquery"].update(dataset=dataset_name)
        _DEFAULT_CONFIG["client"].update(
            credentials_source=repr(client_credential_source)
        )
        console.log("[log.main]Saving config")
        CONFIG.write_text(utils._format_toml(_DEFAULT_CONFIG))
        console.log("[log.main]Building app directory")
        CONFIG.touch(exist_ok=True)
        console.log(f"[log.main]Writing {CONFIG}")
        REPL_HISTORY.touch(exist_ok=True)
        console.log(f"[log.main]Writing {REPL_HISTORY}")
        SQL_HISTORY.touch(exist_ok=True)
        console.log(f"[log.main]Writing {SQL_HISTORY}")
        CACHE.touch(exist_ok=True)
        console.log(f"[log.main]Writing {CACHE}")
        console.log("[log.main]Directory build complete")

        ENTRY_APPDATA.write_text(
            '[active.no-project]\nname = "no-project"'
            '\ndescription = "default"\nnotes=[]'
        )
        return None

    except (KeyboardInterrupt, EOFError):
        rmtree()

    except Exception as err:
        _console.get_console().print(
            "{markup}{message}{error}\n{notice}".format(
                markup="[failure]",
                message="Failed to build app directory",
                error=f": {err}" if err else "",
                notice="Deleting app directory.",
            )
        )
        rmtree()
