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
from pathlib import Path
from typing import Final, Sequence

__all__: Sequence[str] = (
    "__appdir__",
    "__appname__",
    "__appname_sc__",
    "__config__",
    "__lock__",
    "__repo__",
    "__version__",
)


def get_app_dir(app_name: str, roaming: bool = True, force_posix: bool = True) -> str:
    # Copy of function from click.
    # Import from click in this file was causing errors with hatch build,
    # temporarily copying this function here until that issue is resolved.
    import sys

    def _posixify(name: str) -> str:
        return "-".join(name.split()).lower()

    if sys.platform.startswith("win"):
        key = "APPDATA" if roaming else "LOCALAPPDATA"
        folder = os.environ.get(key)
        if folder is None:
            folder = os.path.expanduser("~")
        return os.path.join(folder, app_name)
    if force_posix:
        return os.path.join(os.path.expanduser(f"~/.{_posixify(app_name)}"))
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"), app_name
        )
    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        _posixify(app_name),
    )


def _appdir_filename() -> str:
    env: str | None = os.getenv("LIGHTLIKE_CLI")
    return f"Lightlike CLI%s" % (f" {env}" if env else "")


def _config_filename() -> str:
    env: str | None = os.getenv("LIGHTLIKE_CLI")
    return f".lightlike{('_' + env.lower()) if env else ''}.toml"


__version__: Final[str] = "v0.10.0b2"

__appname__: Final[str] = _appdir_filename()
__appname_sc__: Final[str] = "".join(c if c.isalnum() else "_" for c in __appname__.lower())  # fmt: skip
__config__: Final[Path] = Path.home() / _config_filename()
__repo__: Final[str] = "https://github.com/ayvi-0001/lightlike-cli"
__appdir__: Final[Path] = Path(get_app_dir(__appname__, roaming=True))
__lock__: Final[Path] = __appdir__ / "cli.lock"


# fmt: off


LIGHTLIKE_CLI_DEV_USERNAME = os.getenv("LIGHTLIKE_CLI_DEV_USERNAME")


__cli_help__: str = f"""
[repr_attrib_name]__appname__[/][b red]=[/][repr_attrib_value]{
        (
            "lightlike_cli"
            if LIGHTLIKE_CLI_DEV_USERNAME
            else __appname_sc__
        )
    }[/repr_attrib_value]
[repr_attrib_name]__version__[/][b red]=[/][repr_number]{__version__}[/repr_number]
[repr_attrib_name]__config__[/][b red]=[/][repr_path]{
        (
            "/%s/.lightlike.toml" % LIGHTLIKE_CLI_DEV_USERNAME
            if LIGHTLIKE_CLI_DEV_USERNAME
            else __config__.as_posix()
        )
    }[/repr_path]
[repr_attrib_name]__appdir__[/][b red]=[/][repr_path]{
        (
            "/%s/.lightlike-cli" % LIGHTLIKE_CLI_DEV_USERNAME
            if LIGHTLIKE_CLI_DEV_USERNAME
            else __appdir__.as_posix()
        )
    }[/repr_path]

github: [repr.url]{__repo__}[/]

GENERAL:
    [code]ctrl space[/code] or [code]tab[/code] to display commands/autocomplete.
    commands are aliased, use the shortest unique string of the current command path.
    [code]:q[/code] or [code]ctrl q[/code] or type exit to exit repl.
    [code]:c{{1 | 2 | 3}}[/code] to add/remove completions from the global completer. [code]1[/code]=commands, [code]2[/code]=history, [code]3[/code]=path

HELP:
    add help option to command/group --help / -h.

SYSTEM COMMANDS:
    any command that's not recognized by the top-level parent commands, will be passed to the shell.
    system commands can also be invoked by:
        - typing command and pressing [code]:[/code][code]![/code]
        - typing command and pressing [code]escape[/code] [code]enter[/code]
        - pressing [code]meta[/code] [code]shift[/code] [code]1[/code] to enable system prompt
    
    see app:config:set:general:shell --help / -h to configure shell..
    path autocompletion is automatic for [code]cd[/code].

TIME ENTRY IDS:
    time entry ids are the sha1 hash of the project, note, and start timestamp.
    if any fields are later edited, the id will not change.
    for commands requiring an id, supply the first several characters.
    the command will find the matching id, as long as it is unique.

DATE/TIME FIELDS:
    datetime arguments/options use dateparser on the string input. an error will raise if it's unable to parse.
    unless explicitly stated in the string, dates are relative to today.
"""
