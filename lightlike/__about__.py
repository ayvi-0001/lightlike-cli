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

import sys
from os import getenv
from pathlib import Path
from typing import Final, Sequence

from click import get_app_dir
from rich import print

__all__: Sequence[str] = (
    "__appdir__",
    "__appname__",
    "__appname_sc__",
    "__cli_help__",
    "__config__",
    "__configdir__",
    "__lock__",
    "__repo__",
    "__version__",
)

__version__: Final[str] = "v0.12.0"


LIGHTLIKE_ENV: str | None = getenv("LIGHTLIKE_ENV")
LIGHTLIKE_APP_DIR: Path = Path(
    getenv(
        "LIGHTLIKE_APP_DIR",
        default=get_app_dir("lightlike-cli", force_posix=True),
    )
)
LIGHTLIKE_CONFIG_DIR: Path = Path(
    getenv(
        "LIGHTLIKE_CONFIG_DIR",
        default=f'{Path.home().joinpath(".config").joinpath("lightlike-cli")}',
    )
)

# #################################################################################################
# ENVIRONMENT VARIABLES:
# LIGHTLIKE_ENV:                  If set, $LIGHTLIKE_ENV appended to appdir/config, and
#                                 dataset/tables in BigQuery. This is essentially a new environment
#                                 for the cli, and will run independently of other environments.
# LIGHTLIKE_CONFIG_DIR:           Directory for config. Must be absolute path.
# LIGHTLIKE_APP_DIR:              Directory for app data. Must be absolute path.
# LIGHTLIKE_CLI_DEV:              Enables dev features.
# LIGHTLIKE_CLI_DEV_EXPORT_HELP:  Output of help commands are saved to an svg in the current directory.
#                                 svg's are saved as the name of the command.
# #################################################################################################


def get_appdir_path(env: str | None = None) -> Path:
    global LIGHTLIKE_APP_DIR
    appdir: Path = LIGHTLIKE_APP_DIR.resolve()

    if appdir.exists() and not appdir.is_dir():
        print(
            "[b][red]EnvironmentVariableError[/]: "
            "[code]LIGHTLIKE_APP_DIR[/] must point to a directory: "
            f"{LIGHTLIKE_APP_DIR}"
        )
        sys.exit(2)

    if env is not None:
        appdir = appdir.parent / f"{appdir.name}-{env.lower()}"

    return appdir


def get_config_dir(env: str | None = None) -> Path:
    global LIGHTLIKE_CONFIG_DIR
    config_dir: Path = LIGHTLIKE_CONFIG_DIR.resolve()

    if config_dir.exists() and not config_dir.is_dir():
        print(
            "[b][red]EnvironmentVariableError[/]: "
            "[code]LIGHTLIKE_CONFIG_DIR[/] must point to a directory: "
            f"{LIGHTLIKE_CONFIG_DIR}"
        )
        sys.exit(2)

    if env is not None:
        config_dir = config_dir.parent / f"{config_dir.name}-{env.lower()}"

    config_dir.mkdir(exist_ok=True, parents=True)

    return config_dir


# fmt: off
# appname redefined from line 45, env appended
__appdir__: Final[Path] = get_appdir_path(LIGHTLIKE_ENV)
__appname__: Final[str] = "lightlike-cli%s" % (f"-{LIGHTLIKE_ENV}" if LIGHTLIKE_ENV else "")
__appname_sc__: Final[str] = "".join(c if c.isalnum() else "_" for c in __appname__.lower())
__configdir__: Final[Path] = get_config_dir(LIGHTLIKE_ENV)
__config__: Final[Path] = __configdir__ / "lightlike.toml"
__lock__: Final[Path] = __appdir__ / "cli.lock"
__repo__: Final[str] = "https://github.com/ayvi-0001/lightlike-cli"
# fmt: on


__cli_help__: str = f"""\
[b]Completion[/b]:
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

[b]Commands[/b]:
    commands are aliased, use the shortest unique string of the command path.
    add/remove commands in the config file -> cli.commands.
    commands not recognized by the available top-level commands paths are passed to the shell.
    [yellow]see[/] app:config:set:general:shell --help / -h to configure what shell is used.

[b]Time entry ids[/b]:
    time entry ids are the sha1 hash of the project, note, and start timestamp.
    if any fields are later edited, the id will not change.
    for commands using an id, supply the first several characters,
    as long as it is unique, a matching id will be found.

[b]Date/time fields[/b]:
    arguments/options for date/time use the dateparser module to parse the input.
    if it's unable too parse the string, an error will raise.
    unless explicitly stated in the string or customized in the config,
    dates are relative to today and prefer the past.
    [yellow]see[/] app:parse-date to see examples of strings to pass to parser.

[b]Help[/b]: add --help / -h to command/group.

[b]Exit[/b]: type [code]exit[/code] | press [code]:q[/code] | press [code]ctrl q[/code]

[b]Repo[/b]: [repr.url][link={__repo__}]{__repo__}[/link][/]

{'LIGHTLIKE_ENV: %s' % LIGHTLIKE_ENV if LIGHTLIKE_ENV else ''}
VERSION = {__version__}
LIGHTLIKE_APP_DIR = {LIGHTLIKE_APP_DIR.as_posix()}
LIGHTLIKE_CONFIG_DIR = {LIGHTLIKE_CONFIG_DIR.as_posix()}
"""
