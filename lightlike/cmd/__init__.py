from typing import Sequence

from lightlike._console import global_console_log

global_console_log("Loading command groups")


from lightlike.cmd import other
from lightlike.cmd.app import app
from lightlike.cmd.bq import bq
from lightlike.cmd.project import project
from lightlike.cmd.report import report
from lightlike.cmd.timer import timer

__all__: Sequence[str] = ("app", "bq", "project", "report", "timer", "other")
