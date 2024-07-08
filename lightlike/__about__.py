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
    "__latest_release__",
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


def _appdir_filename(env: str | None) -> str:
    return f"Lightlike CLI%s" % (f" {env}" if env else "")


def _config_filename(env: str | None) -> str:
    return f".lightlike{('_' + env.lower()) if env else ''}.toml"


__version__: Final[str] = "v0.10.0.alpha.4"

env: str | None = os.getenv("LIGHTLIKE_CLI")
__appname__: Final[str] = _appdir_filename(env)
__appname_sc__: Final[str] = "".join(c if c.isalnum() else "_" for c in __appname__.lower())  # fmt: skip
__config__: Final[Path] = Path.home() / _config_filename(env)
__repo__: Final[str] = "https://github.com/ayvi-0001/lightlike-cli"
__latest_release__: Final[str] = f"{__repo__}/releases/latest"
__appdir__: Final[Path] = Path(get_app_dir(__appname__, roaming=True))
__lock__: Final[Path] = __appdir__ / "cli.lock"
