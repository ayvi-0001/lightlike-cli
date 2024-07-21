import typing as t

__all__: t.Sequence[str] = (
    "DEFAULT_CONFIG",
    "DEFAULT_SCHEDULER_TOML",
    "CONSOLE",
    "PROMPT_STYLE",
    "_CONSOLE_SVG_FORMAT",
)


DEFAULT_CONFIG: str = """\
[app]
name = ""
version = ""
term = ""
last_checked_release = ""

[user]
name = "null"
host = "null"
stay_logged_in = false
password = ""
salt = []

[updates]
"v0.9.3" = false

[settings]
complete_style = "COLUMN"
editor = ""
note_required = "not-implemented"
quiet_start = false
reserve_space_for_menu = 12
timer_add_min = -6
timezone = "null"
week_start = 1

[settings.dateparser]
additional_date_formats = ["%I%p", "%I:%M%p", "%H:%M:%S"]
cache_size_limit = 0
date_order = "MDY"
default_languages = ["en"]
language_detection_confidence_threshold = 0.5
normalize = true
prefer_dates_from = "current_period"
prefer_day_of_month = "current"
prefer_locale_date_order = true
prefer_month_of_year = "current"
strict_parsing = false

[settings.note_history]
days = 90

[settings.query]
hide_table_render = false
mouse_support = false
save_query_info = false
save_svg = false
save_txt = false

[bigquery]
dataset = "null"
timesheet = "timesheet"
projects = "projects"
resources_provisioned = false

[client]
active_project = "null"
credentials_source = "not-set"
service_account_key = []

[cli.commands]
calendar = "lightlike.cmd.app.other:calendar"
eval = "lightlike.cmd.app.other:eval_"
help = "lightlike.cmd.app.default:help_"
cd = "lightlike.cmd.app.default:cd_"
exit = "lightlike.cmd.app.default:exit_"
app = "lightlike.cmd.app:app"
bq = "lightlike.cmd.bq:bq"
project = "lightlike.cmd.project:project"
summary = "lightlike.cmd.summary:summary"
timer = "lightlike.cmd.timer:timer"

[cli.append_path]
paths = []

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
"rprompt.entries" = "fg:#000000 bg:#f0f0ff"
cursor = "fg:#f0f0ff"

[system-command]
shell = []

[keybinds.exit]
1 = [":", "q"]
2 = ["c-q"]

[keybinds.completers]
commands = [":", "c", "1"]
history = [":", "c", "2"]
path = [":", "c", "3"]

[git]
branch = ""
path = ""

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


CONSOLE: str = """
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
"status.message" = "#32ccfe"
"status.spinner" = "#32ccfe"
"table.caption" = "dim"
"table.cell.empty" = "#888888"
"table.cell" = "#f0f0ff"
"table.footer" = "dim"
"table.header" = "bold #f0f0ff"
"table.title" = "bold #f0f0ff"
"tree.line" = "bold magenta"
"""


PROMPT_STYLE: str = """
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

rprompt = "fg:#f0f0ff"
"rprompt.clock" = "fg:#888888"
"rprompt.entries" = "fg:#000000 bg:#f0f0ff"

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

"completion-menu" = "bg:#0e0e10 fg:#f0f0ff"
"completion-menu.completion" = "bg:#0e0e10 fg:#f0f0ff"
# (Note: for the current completion, we use 'reverse' on top of fg/bg colors.
# This is to have proper rendering with NO_COLOR=1).
"completion-menu.completion.current" = "bold bg:#f0f0ff fg:#9146ff reverse"
"completion-menu.meta.completion" = "bg:#f0f0ff fg:#000000"
"completion-menu.meta.completion.current" = "bold bg:#f0f0ff fg:#9146ff"
"completion-menu.multi-column-meta" = "bg:#f0f0ff fg:#000000"

"scrollbar.arrow" = "noinherit bold"
"scrollbar.background" = "bg:#f0f0ff"
"scrollbar.button" = "bg:#9146ff"

"control-character" = 'bold ansired'
"validation-toolbar" = "bg:#550000 #ffffff"
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
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}

    .{unique_id}-title {{
        font-size: 18px;
        font-weight: bold;
        font-family: arial;
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
