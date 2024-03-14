# mypy: disable-error-code="arg-type"

from inspect import cleandoc

import rich_click as click
from rich.syntax import Syntax
from rich.text import Text

from lightlike.__about__ import __appdir__, __appname_sc__, __lock__, __version__


def _reformat_help_text(help_text: str) -> str:
    """
    Cancels out some of the formatting done by click/rich_click's help string formatters.
    The result of this should appear in the help text almost exactly as it's written here.
    """
    assert click.rich_click.USE_RICH_MARKUP is True
    assert click.rich_click.USE_MARKDOWN is False
    first_line = help_text.split("\n\n")[0]
    remaining_paragraphs = help_text.split("\n\n")[1:]
    _remaining_paragraphs = list(
        map(lambda t: t.replace("\n", "\n\n"), remaining_paragraphs)
    )
    help_text = "".join(
        [
            "\b\n",
            first_line + "%s" % "\n" * 4,
            "<rem-split>".join(_remaining_paragraphs),
        ],
    )
    return cleandoc(help_text.replace("<rem-split>", "\b" + "\n" * 4))


def code(text: str) -> str:
    return Text(text, style="bold #f08375").markup


def code_command(text: str) -> str:
    commands = text.split(":")
    code_command = lambda t: Text(t, style="bold #3465a4").markup
    list(map(code_command, commands))
    return ":".join(list(map(code_command, commands)))


class flag:
    project = "--project / -p"
    note = "--note / -n"
    start = "--start / -s"
    end = "--end / -e"
    billable = "--billable / -b"
    where = "--where / -w"
    current_week = "--current-week / -cw"
    destination = "--destination / -d"
    json = "--json / -j"
    id = "--id / -i"
    all = "--all / -a"
    round = "--round / -r"
    print = "--print / -p"
    orient = "--orient / -o"
    editor = "--editor / -e"
    confirm = "--confirm / -c"
    yes = "--yes / -y"


_where_clause_help = f"""\
If the {flag.where} flag is used, command will prompt for input. This prompt will include autocompletions.
If you want this to run on a single command without prompts, You can instead ignore the {flag.where} flag and write out the where clause after the date.
If a where clause is provided as the last arg, it must either begin with "WHERE" (case-insensitive), or it must be the string that will immediately proceed the word "WHERE".\
"""

_current_week_flag_help = f"""\
Use the {flag.current_week} flag to use week start and end dates.
Use command {code_command('app:settings:update:general:week-start')} to select whether to use a Monday or Sunday week start.\
"""

_destination_flag_help = f"""\
If {flag.destination} is provided, then %s will save to that path.
If the path provided does not end in expected suffix, then the suffix will be appended.
If the path already exists, you will be asked to overwrite it or not.
If the provided path ends in any suffix other than what's expected, an error will raise.\
"""

_report_fields = f"""\
Fields:
- total_report: The total sum of duration over the entire report.
- total_project: The total sum of duration over the entire report, partitioned by project.
- total_day: The total sum of duration on each day, partitioned by day.
- date: Date.
- project: Project.
- billable: Billable.
- timer: The total sum of duration for a project on that day.
- notes: String aggregate of all the notes for a project on that day. \
The sum of hours for that note is appended on the end of each note.\
"""

_date_parser_examples = f"""\
Example values to pass to the date parser:
[d][b]Note:[/b] to use the minus operator, it must be escaped to avoid mistaking it for a flag[/d]

| format                     | examples                                                                     |
|----------------------------|------------------------------------------------------------------------------|
| relative  date             | "today"/"now" [d](same result)[/d], "yesterday", "monday", "2 days ago", "\-2 days" |
| relative time              | "1 hour 15 min ago", "1.25 hrs ago", "\-1.25hr"                              |
| time                       | "14:30:00", "2:30 PM"                                                        |
| date [d](assumes this year)[/d]   | "jan1", "01/01", "01-01"                                                     |
| full date                  | "2024-01-01"                                                                 |

Use command {code_command('app:test:date-parse')} to test a string against the parser.\
"""

_confirm_flags = f"""\
Use flag {flag.confirm} or {flag.yes} to accept all prompts.\
"""

SYNTAX_KWARGS = dict(
    lexer="fishshell",
    line_numbers=True,
    dedent=True,
    background_color="#131310",
)


general = _reformat_help_text(
    f"""\b
[repr.attrib_name]__appname__[/repr.attrib_name][bold red]=[/bold red][repr.attrib_value]{__appname_sc__}[/repr.attrib_value]
[repr.attrib_name]__version__[/repr.attrib_name][bold red]=[/bold red][repr.attrib_value]{__version__}[/repr.attrib_value]
[repr.attrib_name]__appdir__[/repr.attrib_name][bold red]=[/bold red][repr.attrib_value]{__appdir__.as_posix()}[/repr.attrib_value]
[repr.attrib_name]__lock__[/repr.attrib_name][bold red]=[/bold red][repr.attrib_value]{__lock__.as_posix()}[/repr.attrib_value]
\b\n\
GENERAL:
    ▸ {code('ctrl')} + {code('space')} [b]|[/b] {code('tab')} to display commands/autocomplete.
    ▸ {code('ctrl')} + {code('Q')} [b]|[/b] cmd {code_command('app:exit')} to exit.
    ▸ [ {code('ctrl')} + ]{'{'} {" [b]|[/b] ".join(
                [
                    '%s' % code('F1'),
                    '%s' % code('F2'),
                    '%s' % code('F3'),
                    '%s' % code('F5'),
                ]
            )
        } {'}'} to cycle between autocompleters. ( {" [b]|[/b] ".join(
                [
                    '%s = Commands' % code('F1'),
                    '%s = History' % code('F2'),
                    '%s = Path' % code('F3'),
                    '%s = None' % code('F5'),
                ]
            )
        } )
\b\n\
HELP:
    ▸ Add help flag to command/group \[[code.lflag]--help[/code.lflag], [code.sflag]-h[/code.sflag]].
\b\n\
SYSTEM COMMANDS:
    ▸ Type cmd and press {code('escape')} + {code('enter')}.
    ▸ To enable system prompt, press {code('meta')} + {code('shift')} + {code('1')} and enter cmd.
    ▸ Built-in system commands: {" [b]|[/b] ".join(
            [
                code_command('cd'),
                code_command('ls'),
                code_command('tree'),
            ]
        )
    }
\b\n\
TIMER IDS:
    Timer ID's are the sha1 hash of the project, note, and the start timestamp.
    If you created 2 entries of the same project, note, and start-time, they would have the same ID.
    If you later edit the project, note, or start fields for a time entry, the ID will not change.
    
    For any commands that require an ID, you can supply the first 7+ characters and the command will find a matching ID.
    If more than 1 ID matches the string provided, the command will ask you to provide a longer string.
\b\n\
DATE/TIME FIELDS:
    Any argument or option that asks for a date or time value will attempt to parse the string provided.
    If it's unable to parse the string, an error will raise.
    All dates are relative to today unless explicitly stated in the string.
    See the help for command {code_command('timer:list:date')} for more details about what kinds of strings work best.
"""
)


timer_add = _reformat_help_text(
    f"""
Retroactively add a time entry.

The same 4 flags when using {code_command('timer:run')} are available, with an additional flag {flag.end} to supply the time the entry ends.

If {flag.end} is not provided, it will default to {code('now')}.

If any of {flag.project} | {flag.start} are not provided, a prompt will call for these values.

If any of {flag.note} | {flag.billable} are not provided, they will be ignored [d](uses default billable set in config)[/d].
"""
)


timer_add_syntax = Syntax(
    code="""\
    $ timer add --project no-project --start "mon 9am" --end "mon 12pm" --note "..." --billable true
    
    $ timer add --project lightlike-cli --start "01-15 12PM" --end "01-15 3PM"
    """,
    **SYNTAX_KWARGS,
)


timer_delete = _reformat_help_text(
    f"""
Delete time entries by passing one or more timer ID's as args to this command.
"""
)


timer_delete_syntax = Syntax(
    code="""\
    $ timer delete b95eb89 22b0140 b5b8e24
    """,
    **SYNTAX_KWARGS,
)


timer_edit_entry = _reformat_help_text(
    f"""
Edit entries that have already been stopped.

Use the {flag.id} flag to specify which entries you want to edit.

Use the sub commands {code_command('billable')} | {code_command('date')} | {code_command('end')} | {code_command('note')} | {code_command('project')} | {code_command('start')} to select which fields you want to edit.

For {code_command('start')} & {code_command('end')}, only the [b]time value[/b] of the parsed date will be used.
For {code_command('date')}, only the [b]date value[/b] of the parsed date will be used.

If the subcommand {code_command('project')} is provided, the subcommand {code_command('note')} will autocomplete relevant values for that project.
"""
)


timer_edit_entry_syntax = Syntax(
    code="""\
    $ timer edit entry --id b95eb89 billable false end now
    
    $ timer edit entry --id b95eb89 project lightlike-cli start 10am
    
    $ t e e -i b95eb89 date "2 days ago" start 11am end 2pm
    """,
    **SYNTAX_KWARGS,
)


timer_get = _reformat_help_text(
    f"""
Retrives the row for a given time entry ID.
"""
)


timer_get_syntax = Syntax(
    code="""\
    $ timer get 36c9fe5
    
    $ timer get 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
    """,
    **SYNTAX_KWARGS,
)


timer_list_date = _reformat_help_text(
    f"""
List time entries on a given date.

{_date_parser_examples}

{_where_clause_help}
"""
)


timer_list_date_syntax = Syntax(
    code="""\
    $ timer list date today
    
    $ t l d today
    
    $ timer l d yesterday -w   # will prompt for where clause
    
    $ timer list date "2 days ago" "where is_billable is false"
    
    $ timer list date monday project = "lightlike_cli" and note like any ("something%", "else%")
    """,
    **SYNTAX_KWARGS,
)


timer_list_range = _reformat_help_text(
    f"""
List time entries on a given date.

{_date_parser_examples}

{_where_clause_help}

{_current_week_flag_help}
"""
)


timer_list_range_syntax = Syntax(
    code="""\
    $ timer list range jan1 jan31 "where project not in (\\"test\\", \\"demo\\")"
    
    $ timer list range --current-week --where   # will prompt for where clause
    
    $ t l r -cw
    """,
    **SYNTAX_KWARGS,
)


timer_notes_update = _reformat_help_text(
    f"""
Bulk update notes for a project.

Select which notes to replace with {code('space')}. Press {code('enter')} to continue with the selection.

Enter a new note, and all selected notes will be replaced.

There is a lookback window so old notes do not clutter the autocompletions.
Update how many days to look back with command {code_command('app:settings:update:general:note-history')}.
"""
)


timer_notes_update_syntax = Syntax(
    code="""\
    $ timer notes update lightlike-cli
    """,
    **SYNTAX_KWARGS,
)


timer_pause = _reformat_help_text(
    f"""
Pause the [b][u]active[/b][/u] entry.

Also see: command {code_command('timer:run:help')}.
"""
)


timer_pause_syntax = Syntax(
    code="""\
    $ timer pause
    """,
    **SYNTAX_KWARGS,
)


timer_resume = _reformat_help_text(
    f"""
Continue a previously paused entry, this paused entry becomes the [b][u]active[/b][/u] entry.

Also see: command {code_command('timer:run:help')}.
"""
)


timer_resume_syntax = Syntax(
    code="""\
    $ timer resume 36c9fe5
    
    $ timer resume 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
    """,
    **SYNTAX_KWARGS,
)


timer_run = _reformat_help_text(
    f"""
Start a new time entry.

If the {flag.project} flag is not provided, the project will default to {code('no-project')}.

Create projects with command {code_command('project:create')}.

If the {flag.project} is provided, the {flag.note} flag will autocomplete past notes used for that project.

Use the {flag.billable} flag to flag the entry as billable or not. If not provided, app default is used.

Update the default setting for billable with command {code_command('app:settings:update:general:billable')}.

Use the {flag.start} flag to start the entry at an earlier time. If not provided, the entry starts {code('${now}')}.

When you start a new time entry, a stopwatch displaying the duration appears on the right-hand side of the cursor.

You can have multiple timers running at once, but only 1 will be displayed in the cursor - This is the [b]active[/b] entry.

When you start a new time entry and already have an [b][u]active[/b][/u] entry running, the latest will be displayed in the cursor and becomes the new [b][u]active[/b][/u] one.

Use command {code_command('timer:stop')} to end the [b][u]active[/b][/u] entry. [d](can also use alias {code_command('end')})[/d]

Use command {code_command('timer:pause')} to pause the [b][u]active[/b][/u] entry.

Use command {code_command('timer:resume')} to continue a previously paused entry, this paused entry becomes the [b][u]active[/b][/u] entry.

Use command {code_command('timer:switch')} to rotate through which entry, of all that are currently running, is [b][u]active[/b][/u].
"""
)


timer_run_syntax = Syntax(
    code="""\
    $ timer run --project lightlike-cli --note "readme" --start "1 hour ago" --billable False
    
    $ t ru -p lightlike-cli -n "command guide"
    """,
    **SYNTAX_KWARGS,
)


timer_show = _reformat_help_text(
    f"""
Show a table of all running and paused time entries.

Any running time entries appear in the top section. The [b][u]active[/b][/u] time entry - if there is one - will always be the first row.

If there are any paused entries, they will be appear in the bottom section, and are dimmed out.

If there are no running or paused entries, a row of null values will appear under active.
"""
)


timer_show_syntax = Syntax(
    code="""\
    $ timer show
    
    $ timer show -j
    """,
    **SYNTAX_KWARGS,
)


timer_stop = _reformat_help_text(
    f"""
End the [b][u]active[/b][/u] entry. [d](can also use alias {code_command('end')})[/d]

Also see: command {code_command('timer:run:help')}.
"""
)


timer_stop_syntax = Syntax(
    code="""\
    $ timer stop
    """,
    **SYNTAX_KWARGS,
)


timer_switch = _reformat_help_text(
    f"""
Rotate through which entry, of all that are currently running, is the [b][u]active[/b][/u] entry.

Also see: command {code_command('timer:run:help')}.
"""
)


timer_switch_syntax = Syntax(
    code="""\
    $ timer switch
    """,
    **SYNTAX_KWARGS,
)


timer_update = _reformat_help_text(
    f"""
Make updates to the [b][u]active[/b][/u] time entry.

Note: See command {code_command('timer:edit')} for making changes to entries that have already stopped.

The same 4 flags when using {code_command('timer:run')} are available, and will update the selected values for the [b][u]active[/b][/u] entry.
"""
)


timer_update_syntax = Syntax(
    code="""\
    $ timer update --project lightlike-cli --start "15 min ago"
    
    $ t u -b f -n "redefine task"
    """,
    **SYNTAX_KWARGS,
)


project_archive = _reformat_help_text(
    f"""
Archive a project.

When you archive a project, all related time entries are also archived, and will not appear in results for {code_command('timer:list')} or {code_command('report')} commands.

{_confirm_flags}
"""
)


project_archive_syntax = Syntax(
    code="""\
    $ project archive lightlike-cli
    
    $ project archive lightlike-cli -c
    """,
    **SYNTAX_KWARGS,
)


project_create = _reformat_help_text(
    f"""
Create a new project.

If the name and description args are not provided, command will prompt you for input.

Name must match regex %s.

The name %s is reserved for the default setting.
"""
    % (code("^[a-zA-Z0-9-\_]{3,20}$"), code("no-project"))
)


project_create_syntax = Syntax(
    code="""\
    $ project create
    
    $ project create lightlike-cli "time-tracking repl"
    
    $ project create lightlike-cli -nd
    """,
    **SYNTAX_KWARGS,
)


project_delete = _reformat_help_text(
    f"""
Delete a project and all time entries under this project.

{_confirm_flags}
"""
)


project_delete_syntax = Syntax(
    code="""\
    $ project delete lightlike-cli
    
    $ project delete lightlike-cli -c
    """,
    **SYNTAX_KWARGS,
)


project_list = _reformat_help_text(
    f"""
List projects.

Use flag {flag.all} to include archived projects.
"""
)


project_list_syntax = Syntax(
    code="""\
    $ project list
    
    $ project list --all
    """,
    **SYNTAX_KWARGS,
)


project_unarchive = _reformat_help_text(
    f"""
Unarchive a project.

When you unarchive a project, all related time entries are also unarchived, and will appear in results for {code_command('timer:list')} or {code_command('report')} commands.
"""
)


project_unarchive_syntax = Syntax(
    code="""\
    $ project unarchive lightlike-cli
    """,
    **SYNTAX_KWARGS,
)


project_update_name = _reformat_help_text(
    f"""
Update a projects name.

Name must match regex %s.

The name %s is reserved for the default setting.
"""
    % (code("^[a-zA-Z0-9-\_]{3,20}$"), code("no-project"))
)


project_update_name_syntax = Syntax(
    code="""\
    $ project update lightlike-cli name
    """,
    **SYNTAX_KWARGS,
)


project_update_description = _reformat_help_text(
    f"""
Update a projects description.
"""
)


project_update_description_syntax = Syntax(
    code="""\
    $ project update lightlike-cli description
    """,
    **SYNTAX_KWARGS,
)


report_csv = _reformat_help_text(
    f"""
Creates a report as a CSV.
This can be saved to a file, or printed to the terminal.

[b][u]At least 1 of the {flag.print} [u]or[/u] {flag.destination} flag must be provided.[/b][/u]

[yellow][b][u]Note: running & paused entries are not included in reports.[/b][/u][/yellow]

{_report_fields}

{_date_parser_examples}

{_destination_flag_help % 'the csv'}

{_where_clause_help}

If the {flag.round} flag is set, totals will round to the nearest 0.25.

{_current_week_flag_help}
"""
)


report_csv_syntax = Syntax(
    code="""\
    $ report csv --start 01/01 --end 01/31 --round --print
    
    $ report c -s monday -e today --round --print "where is_billable is false"
    
    $ r c -cw -p
    """,
    **SYNTAX_KWARGS,
)


report_json = _reformat_help_text(
    f"""
Creates a report as a JSON.
This can be saved to a file, or printed to the terminal.

[b][u]At least 1 of the {flag.print} [u]or[/u] {flag.destination} flag must be provided.[/b][/u]

[yellow][b][u]Note: running & paused entries are not included in reports.[/b][/u][/yellow]

{_report_fields}

{_date_parser_examples}

{_destination_flag_help % 'the json'}

{_where_clause_help}

If the {flag.round} flag is set, totals will round to the nearest 0.25.

{_current_week_flag_help}

The default value for the {flag.orient} flag is {code('records')}. Available options are; columns, index, records, split, table, values.
"""
)


report_json_syntax = Syntax(
    code="""\
    $ report json --start "6 days ago" --end today --print
    
    $ report j -cw -p -d Path/to/save/file.json --orient records -r
    
    $ r j -s jan15 -e jan31 -r -p -o index 'where is_billable is false'
    """,
    **SYNTAX_KWARGS,
)


report_table = _reformat_help_text(
    f"""
Creates a report and renders a table in terminal. Optional svg download.

[yellow][b][u]Note: running & paused entries are not included in reports.[/b][/u][/yellow]

{_report_fields}

{_date_parser_examples}

{_destination_flag_help % 'an svg of the rendered table'}

{_where_clause_help}

If the {flag.round} flag is set, totals will round to the nearest 0.25.

{_current_week_flag_help}
"""
)


report_table_syntax = Syntax(
    code="""\
    $ report table --start jan1 --end jan14 --round
    
    $ report t --current-week --destination Path/to/save/file.svg --round "where project = 'lightlike_cli'"
    
    $ r t -cw -r
    """,
    **SYNTAX_KWARGS,
)


app_dir = _reformat_help_text(
    f"""
Launch CLI directory.

Default flag is {flag.start}. This launches the app directory with cmd {code("start")}.

{flag.editor} launches the app directory using the configured editor.
This can be set with the command {code_command('app:settings:update:general:editor')}.
"""
)


app_dir_syntax = Syntax(
    code="""\
    $ app dev dir
    
    $ app dev dir --editor
    """,
    **SYNTAX_KWARGS,
)


app_run_bq = _reformat_help_text(
    f"""
Run BigQuery scripts.

Executes all necessary scripts in BigQuery for this CLI to run. Table's are only built if they do not exist.
"""
)


app_run_bq_syntax = Syntax(
    code="""\
    $ app dev run-bq
    """,
    **SYNTAX_KWARGS,
)


app_settings = _reformat_help_text(
    f"""
View/Update CLI configuration settings.

Command {code_command('app:settings:show')} displays settings in a table. The flag {flag.json} can be used to view as a json instead.

For command {code_command('app:settings:update')};
[b]general settings[/b] affect timer functions/flags, logging in (if using a service-account-key), and behaviour of other commands such as the default text-editor to launch.
[b]query settings[/b] affect the behaviour of the command {code_command('bq:query')}.
"""
)


app_settings_syntax = Syntax(
    code="""\
    $ app settings show
    
    $ app settings show --json
    
    $ app settings update 
    """,
    **SYNTAX_KWARGS,
)


app_settings_editor = _reformat_help_text(
    f"""
Editor should be the full path to the executable, but the regular operating system search path is used for finding the executable.
"""
)


app_settings_editor_syntax = Syntax(
    code="""\
    $ app settings update general editor code
    
    $ app settings update general editor vim
    """,
    **SYNTAX_KWARGS,
)


app_settings_is_billable = _reformat_help_text(
    f"""
Default billable flag used for {code_command('timer')} commands.
"""
)


app_settings_is_billable_syntax = Syntax(
    code="""\
    $ app settings update general is_billable false
    """,
    **SYNTAX_KWARGS,
)


app_settings_note_history = _reformat_help_text(
    f"""
Days to store note history.

This settings affects how many days to store notes used by {flag.note} flags for autocompletions.

E.g. If days = 30, any notes older than 30 days won't appear in autocompletions.

Default is set to 90 days.
"""
)


app_settings_note_history_syntax = Syntax(
    code="""\
    $ app settings update general note-history 365
    """,
    **SYNTAX_KWARGS,
)


app_settings_stay_logged_in = _reformat_help_text(
    f"""
Save login password.

This setting is only visible if the client is authenticated using a service-account key.

It's not recommended to leave this setting on, as the password and encryped key are stored in the same place.
"""
)


app_settings_stay_logged_in_syntax = Syntax(
    code="""\
    $ app settings update general stay_logged_in true
    """,
    **SYNTAX_KWARGS,
)


app_settings_timezone = _reformat_help_text(
    f"""
Timezone used for all date/time conversions.

If you change this value, run command {code_command('app:dev:run-bq')} to recreate procedures in BigQuery using the new timezone.
"""
)


app_settings_timezone_syntax = Syntax(
    code="""\
    $ app settings update general timezone UTC
    """,
    **SYNTAX_KWARGS,
)


app_settings_week_start = _reformat_help_text(
    f"""
Update week start for {flag.current_week} flags.
"""
)


app_settings_week_start_syntax = Syntax(
    code="""\
    $ app settings update week_start Sunday
    """,
    **SYNTAX_KWARGS,
)


app_settings_hide_table_render = _reformat_help_text(
    f"""
If {code_command('save_text')} or {code_command('save_svg')} are enabled, enable/disable table render in console.

If {code_command('save_text')} or {code_command('save_svg')} are disabled, this option does not have any affect.
"""
)


app_settings_hide_table_render_syntax = Syntax(
    code="""\
    $ app settings update query hide_table_render true
    """,
    **SYNTAX_KWARGS,
)


app_settings_mouse_support = _reformat_help_text(
    f"""
Controls mouse support in command {code_command('bq:query')}.
"""
)


app_settings_mouse_support_syntax = Syntax(
    code="""\
    $ app settings update query mouse_support true
    """,
    **SYNTAX_KWARGS,
)


app_settings_save_query_info = _reformat_help_text(
    f"""
Include query info when saving to file.

This includes:
- query string
- resource url
- elapsed time
- cache hit/destination
- statement type
- slot millis
- bytes processed/billed
- row count
- dml stats
"""
)


app_settings_save_query_info_syntax = Syntax(
    code="""\
    $ app settings update query save_query_info true
    """,
    **SYNTAX_KWARGS,
)


app_settings_save_svg = _reformat_help_text(
    f"""
Queries using command {code_command("bq:query")} will save the rendered result to an {code('.svg')} file in the app directory.
"""
)


app_settings_save_svg_syntax = Syntax(
    code="""\
    $ app settings update query save_svg true
    """,
    **SYNTAX_KWARGS,
)
app_settings_save_txt = _reformat_help_text(
    f"""
Queries using command {code_command("bq:query")} will save the rendered result to a {code('.txt')} file in the app directory.
"""
)


app_settings_save_txt_syntax = Syntax(
    code="""\
    $ app settings update query save_txt true
    """,
    **SYNTAX_KWARGS,
)


app_sync = _reformat_help_text(
    f"""
Syncs local files for time entry data, projects, and cache.

These can be found in the app directory using the command {code_command('app:dev:dir')}.

These tables should only ever be altered through the procedures in this CLI.
If the local files are ever out of sync with BigQuery, or you log in from a new location, you can use this command to re-sync them.
"""
)


app_sync_syntax = Syntax(
    code="""\
    $ app sync appdata

    $ app sync cache

    $ app sync appdata cache
    """,
    **SYNTAX_KWARGS,
)


app_test_dateparser = _reformat_help_text(
    f"""
Test the dateparser function.

{_date_parser_examples}
"""
)


app_test_dateparser_syntax = Syntax(
    code="""\
    $ app test date-parse "\-1.35hr"
    """,
    **SYNTAX_KWARGS,
)
