# mypy: disable-error-code="func-returns-value"

import sys
import typing as t

from lightlike import _console
from lightlike.__about__ import __appdir__
from lightlike.app.config import AppConfig
from lightlike.cmd.app import app
from lightlike.cmd.bq import bq
from lightlike.cmd.project import project
from lightlike.cmd.summary import summary
from lightlike.cmd.timer import timer
from lightlike.internal import appdir

lazy_subcommands: dict[str, str] = AppConfig().get(
    "cli", "lazy_subcommands", default={}
) | {
    "help": "lightlike.cmd.app.default.help_",
    "cd": "lightlike.cmd.app.default.cd_",
    "exit": "lightlike.cmd.app.default.exit_",
}


try:
    paths: dict[str, str] | None = AppConfig().get("cli", "append_path", "paths")
    if paths:
        for path in paths:
            not _console.QUIET_START and (
                _console.get_console().log(f"{path} added to path")
            )
            sys.path.append(path)
except Exception as error:
    appdir._log().error(error)


__all__: t.Sequence[str] = (
    "app",
    "bq",
    "project",
    "summary",
    "timer",
    "lazy_subcommands",
)
