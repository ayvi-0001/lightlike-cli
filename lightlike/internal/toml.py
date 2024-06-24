import typing as t

__all__: t.Sequence[str] = (
    "DEFAULT_CONFIG",
    "CONSOLE",
    "PROMPT",
)


DEFAULT_CONFIG: str = """\
[app]
name = ""
version = ""
term = ""

[user]
name = "null"
host = "null"
stay_logged_in = false
password = ""
salt = []

[updates]
"v0.9.1" = false

[settings]
complete_style = "COLUMN"
editor = ""
note_required = "not-implemented"
quiet_start = false
reserve_space_for_menu = 10
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

[cli.lazy_subcommands]
calendar = "lightlike.cmd.app.other.calendar"
cd = "lightlike.cmd.app.default.cd_"
eval = "lightlike.cmd.app.other.eval_"
exit = "lightlike.cmd.app.default.exit_"
help = "lightlike.cmd.app.default.help_"

[cli.append_path]
paths = []

[prompt.style]
"prompt.user" = "fg:#bfabff bold"
"prompt.at" = "fg:#f0f0ff"
"prompt.host" = "fg:#bfabff bold"
"prompt.stopwatch" = "fg:#000000 bg:#f0f0ff"
"prompt.note" = "fg:#f0f0ff"
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

[keybinds.system-command]
1 = [":", "!"]
2 = [":", "s", "h"]
3 = ["escape", "c-m"]

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

"header.bool" = "#ff0000"
"header.dt" = "#ffff00"
"header.num" = "#00ffff"
"header.str" = "#ff0000"
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


PROMPT: str = """
cursor-shape = "BLOCK"

[style]
"" = "fg:#f0f0ff"

prompt = "fg:#f0f0ff"
"prompt.user" = "fg:#bfabff bold"
"prompt.at" = "fg:#f0f0ff"
"prompt.host" = "fg:#bfabff bold"
"prompt.stopwatch" = "fg:#000000 bg:#f0f0ff"
"prompt.note" = ""
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

"bottom-toolbar" = "reverse"
"control-character" = 'bold ansired'
"validation-toolbar" = "bg:#550000 #ffffff"
"""
