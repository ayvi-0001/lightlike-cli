import getpass
import os
import socket
import typing as t

from lightlike.__about__ import __appname_sc__, __version__

__all__: t.Sequence[str] = (
    "_CONSOLE_SVG_FORMAT",
    "BQ_UPDATES_CONFIG",
    "CONSOLE",
    "DEFAULT_CONFIG",
    "DEFAULT_SCHEDULER_TOML",
    "LICENSE",
    "PROMPT_STYLE",
)


DEFAULT_CONFIG: str = f"""\
[app]
name = "{__appname_sc__}"
version = "{__version__}"
term = "{os.getenv("TERM", "unknown")}"

[user]
name = "{getpass.getuser()}"
host = "{socket.gethostname()}"
stay-logged-in = false
password = ""
salt = []

[settings]
complete-style = "COLUMN"
editor = "{os.environ.get("EDITOR")}"
note-required = "not-implemented"
quiet-start = false
reserve-space-for-menu = 12
timer-add-min = -6
timezone = "null"
week-start = 1
update-terminal-title = true
rprompt-date-format = "[%H:%M:%S]"

[settings.dateparser]
additional-date-formats = ["%I%p", "%I:%M%p", "%I%M%p", "%H%M", "%H%M%S", "%H:%M", "%H:%M:%S"]
cache-size-limit = 0
date-order = "MDY"
default-languages = ["en"]
language-detection-confidence-threshold = 0.5
normalize = true
prefer-dates-from = "current_period"
prefer-day-of-month = "current"
prefer-locale-date-order = true
prefer-month-of-year = "current"
strict-parsing = false

[settings.note-history]
days = 90

[settings.query]
hide-table-render = false
mouse-support = false
save-query-info = false
save-svg = false
save-txt = false

[bigquery]
dataset = "{__appname_sc__}"
timesheet = "timesheet"
projects = "projects"
resources-provisioned = false

[client]
active-project = "null"
credentials-source = "not-set"
service-account-key = []

[cli]
add-to-path = []

[cli.commands]
calendar = "lightlike.cmd.app.other:calendar"
eval = "lightlike.cmd.app.other:eval_"
help = "lightlike.cmd.app.default:help_"
cd = "lightlike.cmd.app.default:cd_"
exit = "lightlike.cmd.app.default:exit_"
app = "lightlike.cmd.app:app"
bq = "lightlike.cmd.bq:bq"
project = "lightlike.cmd.project:project"
timer = "lightlike.cmd.timer:timer"
scheduler = "lightlike.cmd.scheduler:scheduler"

[prompt.style]
"prompt.user" = "fg:#bfabff bold"
"prompt.at" = "fg:#f0f0ff"
"prompt.host" = "fg:#bfabff bold"
"prompt.timer" = "fg:#000000 bg:#f0f0ff"
"prompt.path.prefix" = "fg:#f0f0ff bold"
"prompt.path.name" = "fg:#69ffc3 bold"
"prompt.project.name" = "fg:#79c0ff bold"
"prompt.branch.name" = "fg:#fc6675 bold"
"prompt.project.parenthesis" = "fg:#bfabff bold"
"prompt.branch.parenthesis" = "fg:#feee85 bold"
"rprompt.clock" = "fg:#888888"
cursor = "fg:#f0f0ff"

[completers]
default = ["CMD"]

[completers.exec]
ignore-patterns = []

[keys]
exit = [[":", "q"], ["c-q"]]
system-command = [[":", "s", "h"], [":", "!"]]

[keys.completers]
commands = [[":", "c", "1"]]
history = [[":", "c", "2"]]
path = [[":", "c", "3"]]
exec = [[":", "c", "4"]]

[system-command]
shell = []
"""


DEFAULT_SCHEDULER_TOML: str = """\
[scheduler]
"apscheduler.job_defaults.coalesce" = false
"apscheduler.job_defaults.max_instances" = 3
"apscheduler.timezone" = "%s"

[scheduler."apscheduler.jobstores.sqlalchemy"]
type = "sqlalchemy"
url = "%s"

[scheduler."apscheduler.executors.sqlalchemy"]
class = "apscheduler.executors.pool:ThreadPoolExecutor"
max_workers = 20

[scheduler."apscheduler.executors.processpool"]
"type" = "processpool"
max_workers = 5

[jobs.functions]
print_daily_total_hours = "lightlike.cmd.scheduler.jobs:print_daily_total_hours"
load_entry_ids = "lightlike.cmd.scheduler.jobs:load_entry_ids"
sync_cache = "lightlike.cmd.scheduler.jobs:sync_cache"
check_latest_release = "lightlike.cmd.scheduler.jobs:check_latest_release"

[jobs.default]
default_job_print_daily_total_hours = "lightlike.cmd.scheduler.jobs:default_job_print_daily_total_hours"
default_job_load_entry_ids = "lightlike.cmd.scheduler.jobs:default_job_load_entry_ids"
default_job_sync_cache = "lightlike.cmd.scheduler.jobs:default_job_sync_cache"
default_job_check_latest_release = "lightlike.cmd.scheduler.jobs:default_job_check_latest_release"
"""


CONSOLE: str = """\
[style]
color = "#f0f0ff"
bold = false

[theme.styles]
argument = "bold #00ffff" # "not dim bold cyan"
attr = "bold #fafa19"
code = "bold #f08375"
command = "bold #3465a4" # "bold cyan"
default = "#f0f0ff"
dimmed = "#888888"
failure = "#f0f0ff on #ff0000"
metavar = "not dim cyan"
metavar_sep = "not dim cyan"
notice = "#32ccfe"
option = "bold #00ffff" # "bold cyan"
prompt = "#f0f0ff"
switch = "bold #00ff00" # "bold green"
usage = "bold #f0f0ff"

repr_attrib_equal = "bold red"
repr_attrib_name = "not dim #ffff00"
repr_attrib_value = "bold #ad7fa8"
repr_bool_false = "italic bright_red"
repr_bool_true = "italic bright_green"
repr_brace = "bold"
repr_call = "bold magenta"
repr_comma = "bold"
repr_ellipsis = "yellow"
repr_error = "bold red"
repr_eui48 = "bold bright_green"
repr_eui64 = "bold bright_green"
repr_filename = "bright_magenta"
repr_indent = "dim green"
repr_ipv4 = "bold bright_green"
repr_ipv6 = "bold bright_green"
repr_none = "italic magenta"
repr_number = "bold cyan"
repr_number_complex = "bold cyan"
repr_path = "magenta"
repr_str = "#00a500"
repr_tag_contents = "#f0f0ff"
repr_tag_end = "bold"
repr_tag_name = "bold bright_magenta"
repr_tag_start = "bold"
repr_url = "underline not bold bright_blue"
repr_uuid = "not bold bright_yellow"

"log.error" = "#ff0000"
"log.path" = "dim #d2d2e6"
"log.time" = "#888888"
"progress.description" = "#f0f0ff"
"progress.spinner" = "#32ccfe"
"scope.border" = "#0000ff"
"scope.equals" = "bold #ff0000"
"scope.key.special" = "dim #ffff00"
"scope.key" = "not dim #ffff00"
"status.message" = "#f0f0ff"
"status.spinner" = "#f0f0ff"
"table.caption" = "dim"
"table.cell.empty" = "#888888"
"table.cell" = "#f0f0ff"
"table.footer" = "dim"
"table.header" = "bold #f0f0ff"
"table.title" = "bold #f0f0ff"
"tree.line" = "bold magenta"
"""


PROMPT_STYLE: str = """\
"" = "fg:#f0f0ff"
prompt = "fg:#f0f0ff"
"prompt.user" = "fg:#bfabff bold"
"prompt.at" = "fg:#f0f0ff"
"prompt.host" = "fg:#bfabff bold"
"prompt.timer" = "fg:#000000 bg:#f0f0ff"
"prompt.path.prefix" = "fg:#f0f0ff bold"
"prompt.path.name" = "fg:#69ffc3 bold"
"prompt.project.name" = "fg:#79c0ff bold"
"prompt.branch.name" = "fg:#fc6675 bold"
"prompt.project.parenthesis" = "fg:#bfabff bold"
"prompt.branch.parenthesis" = "fg:#feee85 bold"
"rprompt.clock" = "fg:#888888"

cursor = "fg:#f0f0ff"
cursor-column = "bg:#dddddd"
cursor-line = "underline"

"bottom-toolbar" = "noreverse bg:#f0f0ff"
"bottom-toolbar.space" = "bg:default noreverse noitalic nounderline noblink"
"bottom-toolbar.text" = "#000000"

system = "fg:#555753"
selected = "reverse"
color-column = "bg:#ccaacc"

"pygments.comment.multiline" = "#f0404e"
"pygments.comment.single" = "#f0404e"
"pygments.error" = ""
"pygments.escape" = ""
"pygments.generic" = ""
"pygments.keyword" = "#6b90f7"
"pygments.literal.number" = "#d32211"
"pygments.literal.string.single" = "#239551"
"pygments.literal.string.symbol" = "#239551"
"pygments.name.builtin" = "#6b90f7"
"pygments.operator" = "#90c0d6"
"pygments.other" = ""
"pygments.punctuation" = "#ba7dac"
"pygments.text" = ""
"pygments.whitespace" = ""

completion-menu = "fg:#f0f0ff bg:default"
"completion-menu.completion" = "fg:#f0f0ff bg:default"
# (Note: for the current completion, we use 'reverse' on top of fg/bg colors.
# This is to have proper rendering with NO_COLOR=1).
"completion-menu.completion.current" = "bold fg:#9146ff bg:default reverse"
"completion-menu.meta.completion" = "bg:default fg:#f0f0ff"
"completion-menu.meta.completion.current" = "bold fg:#9146ff bg:default"
"completion-menu.multi-column-meta" = "fg:#f0f0ff bg:default"

"scrollbar.arrow" = "noinherit bold"
"scrollbar.background" = "bg:default"
"scrollbar.button" = "bg:#f0f0ff"

"control-character" = 'bold ansired'
"validation-toolbar" = "bg:#550000 #ffffff"
"""


LICENSE: str = """\
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

BQ_UPDATES_CONFIG: str = """\
[versions]
"v0.11.0b13" = false
"""


_CONSOLE_SVG_FORMAT = """\
<svg class="rich-terminal" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <style>

    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Regular"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Regular.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Regular.woff") format("woff");
        font-style: normal;
        font-weight: 400;
    }}
    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Bold"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Bold.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Bold.woff") format("woff");
        font-style: bold;
        font-weight: 700;
    }}

    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
    }}

    .{unique_id}-title {{
        font-size: 18px;
        font-weight: bold;
    }}

    {styles}
    </style>

    <defs>
    <clipPath id="{unique_id}-clip-terminal">
    <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>

    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
</svg>
"""
