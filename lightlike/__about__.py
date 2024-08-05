# MIT License

# Copyright (c) 2024 ayvi-0001

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
from pathlib import Path
from typing import Final, Sequence

from click import get_app_dir
from rich import print

__all__: Sequence[str] = (
    "__appdir__",
    "__appname__",
    "__appname_sc__",
    "__config__",
    "__lock__",
    "__repo__",
    "__version__",
    "__cli_help__",
)

__version__: Final[str] = "v0.11.0b0"

_ENV: str | None = os.getenv("LIGHTLIKE_CLI_ENV")
LIGHTLIKE_CLI_APPDIR_PATH = os.getenv("LIGHTLIKE_CLI_APPDIR_PATH")
LIGHTLIKE_CLI_APPDIR_FORCE_POSIX = bool(
    os.getenv("LIGHTLIKE_CLI_APPDIR_FORCE_POSIX", False)
)
LIGHTLIKE_CLI_CONFIG = os.getenv("LIGHTLIKE_CLI_CONFIG")
LIGHTLIKE_CLI_DEV_USERNAME = os.getenv("LIGHTLIKE_CLI_DEV_USERNAME")

# #################################################################################################
# ENVIRONMENT VARIABLES:
# LIGHTLIKE_CLI_APPDIR_FORCE_POSIX: From click.get_app_dir - if this is set to True then on any
#                                   POSIX system the folder will be stored in the home folder with
#                                   a leading dot instead of the XDG config home or darwin's
#                                   application support folder.
# LIGHTLIKE_CLI_APPDIR_PATH:        Path to application directory.
# LIGHTLIKE_CLI_CONFIG:             Path to application config.
# LIGHTLIKE_CLI_DEV:                Enables dev features.
# LIGHTLIKE_CLI_DEV_EXPORT_HELP:    Help commands printed to an svg in the current directory.
# LIGHTLIKE_CLI_DEV_GCP_PROJECT:    Overrides the displayed gcp project in the cursor,
#                                   does _not_ override the actual project used.
# LIGHTLIKE_CLI_DEV_HOSTNAME:       Overrides the hostname in the cursor (for demos/videos).
# LIGHTLIKE_CLI_DEV_USERNAME:       Overrides the username in the cursor (for demos/videos).
# LIGHTLIKE_CLI_ENV:                If set, $LIGHTLIKE_CLI_ENV appended to the appdir and config.
# #################################################################################################


def appdir_path(appname: str) -> Path:
    if LIGHTLIKE_CLI_APPDIR_PATH:
        path_to_appdir = Path(LIGHTLIKE_CLI_APPDIR_PATH).resolve()
        if path_to_appdir.exists() and not path_to_appdir.is_dir():
            print(
                "[b][red]EnvironmentVariableError[/]: "
                "[code]LIGHTLIKE_CLI_APPDIR_PATH[/] must point to a directory.\n"
                f"{path_to_appdir} pointing to a non-directory file."
            )
            sys.exit(2)
    else:
        path_to_appdir = Path(get_app_dir(appname))

    return path_to_appdir


def config_path(env: str | None = None) -> Path:
    if LIGHTLIKE_CLI_CONFIG:
        path_to_config = Path(LIGHTLIKE_CLI_CONFIG).resolve()
        if path_to_config.exists() and not path_to_config.is_file():
            print(
                "[b][red]EnvironmentVariableError[/]: "
                "[code]LIGHTLIKE_CLI_CONFIG[/] must point to a file.\n"
                f"{path_to_config} not pointing to file."
            )
            sys.exit(2)
    else:
        _user_config = Path.home() / ".config"
        _user_config.mkdir(exist_ok=True)
        if env is not None:
            _config_dir = _user_config / f"lightlike-cli-{env.lower()}"
        else:
            _config_dir = _user_config / f"lightlike-cli"
        _config_dir.mkdir(exist_ok=True)
        path_to_config = _config_dir / "config.toml"

    # Do not touch path. Check for whether path exists in lightlike/internal/appdir.py
    return path_to_config


# fmt: off
__appname__: Final[str] = f"Lightlike CLI%s" % (f" {_ENV}" if _ENV else "")
__appdir__: Final[Path] = appdir_path(__appname__)
__appname_sc__: Final[str] = "".join(c if c.isalnum() else "_" for c in __appname__.lower())
__config__: Final[Path] = config_path(_ENV)
__repo__: Final[str] = "https://github.com/ayvi-0001/lightlike-cli"
__lock__: Final[Path] = __appdir__ / "cli.lock"
# fmt: on


__cli_help__: str = f"""\
[repr.attrib_name]__appname__[/][b][red]=[/red][repr.str]{
        (
            "lightlike_cli"
            if LIGHTLIKE_CLI_DEV_USERNAME
            else __appname_sc__
        )
    }[/b][/repr.str]
[repr.attrib_name]__version__[/][b][red]=[/red][repr.number]{__version__}[/b][/repr.number]
[repr.attrib_name]__config__[/][b][red]=[/red][repr.path]{
        (
            "/%s/.lightlike-cli/config.toml" % LIGHTLIKE_CLI_DEV_USERNAME
            if LIGHTLIKE_CLI_DEV_USERNAME
            else __config__.as_posix()
        )
    }[/b][/repr.path]
[repr.attrib_name]__appdir__[/][b][red]=[/red][repr.path]{
        (
            "/%s/.lightlike-cli" % LIGHTLIKE_CLI_DEV_USERNAME
            if LIGHTLIKE_CLI_DEV_USERNAME
            else __appdir__.as_posix()
        )
    }[/b][/repr.path]

github: [repr.url]{__repo__}[/]

HELP:
    add --help / -h to command/group.

EXIT:
    type [code]exit[/code] | press [code]:q[/code] | press [code]ctrl q[/code]

COMPLETION:
    press [code]ctrl space[/code] or [code]tab[/code] to display.
    [code]:c{{1 | 2 | 3 | 4}}[/code] to add/remove completions from the global completer.
    {", ".join(
        [
            "[code]1[/code] = commands",
            "[code]2[/code] = history",
            "[code]3[/code] = path",
            "[code]4[/code] = executables",
        ]
    )}
    path autocompletion is automatic for [code]cd[/code].

COMMANDS:
    commands are aliased, use the shortest unique string of the command path.
    add/remove commands in the config file -> cli.commands.
    commands not recognized by the available top-level commands paths are passed to the shell.
    [yellow]see[/] app:config:set:general:shell --help / -h to configure what shell is used.

TIME ENTRY IDS:
    time entry ids are the sha1 hash of the project, note, and start timestamp.
    if any fields are later edited, the id will not change.
    for commands using an id, supply the first several characters,
    as long as it is unique, a matching id will be found.

DATE/TIME FIELDS:
    arguments/options for date/time use the dateparser module to parse the input.
    if it's unable too parse the string, an error will raise.
    unless explicitly stated in the string or customized in the config,
    dates are relative to today and prefer the past.
    [yellow]see[/] app:test:date-parse to test parser.
    [yellow]see[/] timer:list --help / -h for more info.
"""
