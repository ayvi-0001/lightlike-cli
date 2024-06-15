from os import getenv

from rich.syntax import Syntax

# isort: off
# fmt: off
from lightlike.__about__ import (
    __appdir__,
    __appname_sc__,
    __config__,
    __version__
)
# isort: on
# fmt: on


if LIGHTLIKE_CLI_DEV_USERNAME := getenv("LIGHTLIKE_CLI_DEV_USERNAME"):
    cli_info = f"""\
[repr_attrib_name]__appname__[/][b red]=[/][repr_attrib_value]lightlike_cli[/repr_attrib_value]
[repr_attrib_name]__version__[/][b red]=[/][repr_number]{__version__}[/repr_number]
[repr_attrib_name]__config__[/][b red]=[/][repr_path]/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike.toml[/repr_path]
[repr_attrib_name]__appdir__[/][b red]=[/][repr_path]/{LIGHTLIKE_CLI_DEV_USERNAME}/.lightlike-cli[/repr_path]\
"""
else:
    cli_info = f"""\
[repr_attrib_name]__appname__[/][b red]=[/][repr_attrib_value]{__appname_sc__}[/repr_attrib_value]
[repr_attrib_name]__version__[/][b red]=[/][repr_number]{__version__}[/repr_number]
[repr_attrib_name]__config__[/][b red]=[/][repr_path]{__config__}[/repr_path]
[repr_attrib_name]__appdir__[/][b red]=[/][repr_path]{__appdir__}[/repr_path]\
"""


def general() -> str:
    return f"""\
{cli_info}

GENERAL:
    [code]ctrl space[/code] or [code]tab[/code] to display commands/autocomplete.
    [code]:q[/code] or [code]ctrl q[/code] or type exit to exit repl.
    [code]:c{{1 | 2 | 3}}[/code] to add/remove completions from the global completer. [code]1[/code]=commands, [code]2[/code]=history, [code]3[/code]=path

HELP:
    add help option to command/group --help / -h.

SYSTEM COMMANDS:
    any command that's not recognized by top parent commands, will be passed to the shell.
    system commands can also be invoked by:
        - typing command and pressing [code]:[/code][code]![/code]
        - typing command and pressing [code]escape[/code] [code]enter[/code]
        - pressing [code]meta[/code] [code]shift[/code] [code]1[/code] to enable system prompt
    
    see app:config:set:general:shell --help / -h to configure what shell is used.
    path autocompletion is automatic for [code]cd[/code].

TIME ENTRY IDS:
    time entry ids are the sha1 hash of the project, note, and the start timestamp.
    if 2 entries were created with the same project, note, and start-time, they'd have the same id.
    if any fields are later edited, the id will not change.
    there is currently no way to remove duplicate ids other than directly dropping from the table in BigQuery.
    for commands requiring an id, supply the first several characters.
    the command will find the matching id, as long as it is unique.
    if more than 1 id matches the string provided, use more characters until it is unique.

DATE/TIME FIELDS:
    arguments/options asking for datetime will attempt to parse the string provided.
    error will raise if unable to parse.
    dates are relative to today, unless explicitly stated in the string.\
"""


def timer_add():
    return """\
Insert a new time entry.

--project / -p:
    set the project for the time entry to this.
    projects can be searched for by name or description.
    projects are ordered in created time desc.
    defaults to [code]no-project[/code].

--note / -n:
    set the note for the time entry to this.
    if --project / -p is used, then autocomplete will include notes for the selected project.

--start / -s:
    set the entry to start at this time.
    defaults to -6 minutes (1/10th of an hour).
    update the default value using app:config:set:general:timer_add_min.

--end / -e:
    set the entry to end at this time.
    defaults to [code]now[/code].

--billable / -b:
    set the entry as billable or not.
    if not provided, the default setting for the project is used.
    set project default billable value when first creating a project
    with project:create, using --default-billable / -b,
    or update an existing project's with project:set:default_billable.\
"""


def timer_add_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer add --project lightlike-cli
        $ t a -plightlike-cli
        
        $ timer add # defaults to adding an entry under `no-project`, that started 6 minutes ago, ending now.
        $ t a       # this can be later updated using timer:update

        $ timer add --project lightlike-cli --start jan1@9am --end jan1@1pm --note "…" --billable true
        $ t a -plightlike-cli -sjan1@9am -ejan1@1pm -n"…" -b1\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_delete() -> str:
    return """\
Delete time entries.

--id / -i:
    ids for entries to edit.
    repeat flag for multiple entries.

--yank / -y:
    pull an id from the latest timer:list results.
    option must be an integer within the range of the cached list.
    the id of the corresponding row will be passed to the command.
    this option can be repeated and combined with --id / -i.
    e.g.

    ```
        $ timer list --current-week

    | row | id      |   …
    |-----|---------|   …
    |   1 | a6c8e8e |   …
    |   2 | e01812e |   …
    ```

    --yank 2 [d](or -y2)[/d] would be the same as typing --id e01812e
    
--use-list-timer-list / -u:
    pass all id's from the most recent timer:list result to this command
    this option can be repeated and combined with --id / -i or --yank / -y.
"""


def timer_delete_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer delete --id b95eb89 --id 22b0140 --id b5b8e24
        $ t d -ib95eb89 -i22b0140 -ib5b8e24
        
        $ timer delete --yank 1
        $ t d -y1
        
        $ timer delete --use-last-timer-list
        $ t d -u\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_edit() -> str:
    return """\
Edit completed time entries.

--id / -i:
    ids for entries to edit.
    repeat flag for multiple entries.

--yank / -y:
    pull an id from the latest timer:list results.
    option must be an integer within the range of the cached list.
    the id of the corresponding row will be passed to the command.
    this option can be repeated and combined with --id / -i.
    e.g.

    ```
        $ timer list --current-week

    | row | id      |   …
    |-----|---------|   …
    |   1 | a6c8e8e |   …
    |   2 | e01812e |   …
    ```

    --yank 2 [d](or -y2)[/d] would be the same as typing --id e01812e
    
--use-list-timer-list / -u:
    pass all id's from the most recent timer:list result to this command
    this option can be repeated and combined with --id / -i or --yank / -y.

--project / -p:
    set the project for all selected entries to this.
    projects can be searched for by name or description.
    projects are ordered in created time desc.

--note / -n:
    set the note for all selected entries to this.
    if --project / -p is used, then autocomplete will include notes for the selected project.

--billable / -b:
    set the entry as billable or not.

--start-time / -s / --end-time / -e:
    set the start/end time for all selected entries to this.
    only the time value of the parsed datetime will be used.
    if only one of the 2 are selected, each selected time entry will update 
    that respective value, and recalculate the total duration,
    taking any existing paused hours into account.

--date / -d:
    set the date for all selected entries to this.
    only the date value of the parsed datetime will be used.
    the existing start/end times will remain,
    unless this option is combined with --start-time / -s / --end-time / -e.\
"""


def timer_edit_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer edit --id b95eb89 --id 36c9fe5 --start 3pm --note "…"
        $ t e -ib95eb89 -i36c9fe5 -s3pm -n"…"

        $ timer edit --use-last-timer-list --note "rewrite task"
        $ t e -u -n"rewrite task"

        $ timer edit --yank 1 --yank 2 --end now
        $ t e -y1 -y2 -enow
        
        $ timer edit --yank 1 --yank 2 --id 36c9fe5 --date -2d # set 3 entries to 2 days ago
        $ t e -y1 -y2 -i36c9fe5 -d-2d\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_get_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer get 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        
        $ timer get 36c9fe5
        
        $ t g 36c9fe5\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_list() -> str:
    return """\
List time entries.

DATE/TIME FIELDS:
    arguments/options asking for datetime will attempt to parse the string provided.
    error will raise if unable to parse.
    dates are relative to today, unless explicitly stated in the string.

    Example values to pass to the date parser:
    | type             | examples                                                  |
    |-----------------:|-----------------------------------------------------------|
    | datetime         | jan1@2pm [d](January 1st current year at 2:00 PM)[/d]            |
    | date (relative)  | today/now, yesterday, monday, 2 days ago, -2d | "\-2d"    |
    | time (relative)  | -15m [d](15 minutes ago)[/d], 1.25 hrs ago, -1.25hr | "\-1.25hr" |
    | date             | jan1, 01/01, 2024-01-01                                   |
    | time             | 2pm, 14:30:00, 2:30pm                                     |

    [b]Note:[/b] If the date is an argument, the minus operator needs to be escaped.
    e.g.
    ```
    $ command --option -2d
    $ c -o-2d
    $ command \-2d # argument
    $ c \-2d # argument
    ```

--current-week / -cw:
--current-month / -cm:
--current-year / -cy:
    flags are processed before other date options.
    configure week start dates with app:config:set:general:week_start

--match-project / -Rp:
    match a regular expression against project names.

--match-note / -Rn:
    match a regular expression against entry notes.
    
--prompt-where / -w:
    filter results with a where clause.
    interactive prompt that launches after command runs.
    prompt includes autocompletions for projects and notes.
    note autocompletions will only populate for a project if that project name appears in the string.

[bold #34e2e2]WHERE[/]:
    where clause can also be written as the last argument to this command.
    it can be a single string, or individual words separated by a space,
    as long as characters are properly escaped if necessary.
    it must either begin with the word "WHERE" (case-insensitive),
    or it must be the string immediately proceeding the word "WHERE".

[b]See[/]:
    test a string against the parser with app:test:date-parse.
"""


def timer_list_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer list --date jan1
        $ t l -djan1

        $ timer list --all active is true # where clause as arguments
        $ t l -a active is true
        
        $ timer list --today
        $ t l -t
        
        $ timer list --yesterday --prompt-where # interactive prompt for where clause
        $ t l -yw

        $ timer list --current-week billable is false
        $ t l -cw billable is false
        
        $ timer list --date -2d --match-note (?i)task.* # case insensitive regex match
        $ t l -d-2d -Rn (?i)task.*

        $ t l -t -Rp ^(?!demo) # exclude projects containing word "demo"
        
        $ timer list --current-month "project = 'lightlike-cli' and note like any ('something%', 'else%')"
        
        $ timer list --all time(start) >= \\"18:29:09\\"
        $ t l -a time(start) >= \\"18:29:09\\"\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_notes_update() -> str:
    return """\
Interactively update notes.

Select which notes to replace with [code]space[/code]. Press [code]enter[/code] to continue with the selection.
Enter a new note, and all selected notes will be replaced.
There is a lookback window so old notes do not clutter the autocompletions.
Update how many days to look back with app:config:set:general:note_history.\
"""


def timer_notes_update_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer notes update lightlike-cli # interactive
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_pause() -> str:
    return """\
Pause the [b]active[/b] entry.

[b]See[/]:
    timer:run --help / -h\
"""


def timer_pause_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer pause\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_resume() -> str:
    return """\
Continue a paused entry.

A resumed time entry becomes the [b]active[/b] entry.

[b]See[/]:
    timer:run --help / -h\
"""


def timer_resume_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer resume 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        $ t re 36c9fe5
    
        $ timer resume 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46 --force
        $ t re 36c9fe5 -f\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_run() -> str:
    return """\
Start a new time entry.

When a new entry is started, a stopwatch displaying the duration & project appears in the prompt and in the tab title.
This is the [b]active[/b] entry. Multiple timers may run at once. Only 1 will be displayed in the cursor.
If a timer runs and there's an [b]active[/b] entry running, the latest becomes the new [b]active[/b] entry.

--project / -p:
    project to log time entry under.
    defaults to [code]no-project[/code].
    create new projects with project:create.
    projects can be searched for by name or description.
    projects are ordered in created time desc.

--note / -n:
    note to attach to time entry.
    if --project / -p is used, then autocomplete will include notes for the selected project.

--billable / -b:
    set the entry as billable or not.
    if not provided, the default setting for the project is used.
    set project default billable value when first creating a project
    with project:create, using --default-billable / -b,
    or update an existing project with project:set:default_billable.

--start / -s:
    start the entry at an earlier time.
    if not provided, the entry starts now.

[b]See[/]:
    timer:stop - stop the [b]active[/b] entry.
    timer:pause - pause the [b]active[/b] entry.
    timer:resume - continue a paused entry, this paused entry becomes the [b]active[/b] entry.
    timer:switch - pause and switch the [b]active[/b] entry.\
"""


def timer_run_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer run
        $ t ru

        $ timer run --project lightlike-cli --note readme --start -1hr --billable False
        $ t ru -plightlike-cli -nreadme -s-1hr -b0\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_show() -> str:
    return """\
Show tables of all local running and paused time entries.
If there is an active entry, it will be in bold, in the first row.
Other running entries will be in the following rows.
If there are paused entries, they will be dimmed, and in the last row(s).
"""


def timer_show_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer show
        $ t sh\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_stop() -> str:
    return """\
Stop the [b]active[/b] entry.

[b]See[/]:
    timer:run --help / -h\
"""


def timer_stop_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer stop
        $ t st
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_switch() -> str:
    return """\
Switch the active time entry.

    --force / -u:
        do not pause the active entry during switch.

    [b]See[/]:
        timer:run --help / -h\
"""


def timer_switch_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer switch
        $ t s # interactive

        $ timer switch 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46
        $ t s 36c9fe
    
        $ timer switch 36c9fe5ebbea4e4bcbbec2ad3a25c03a7e655a46 --force
        $ t s 36c9fe -f\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def timer_update() -> str:
    return """\
Update the [b]active[/b] time entry.

[b]See[/]:
    timer:edit for making changes to entries that have already stopped.\
"""


def timer_update_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ timer update --project lightlike-cli --start -30m
    
        $ timer update --billable true --note "redefine task"
        $ t u -b1 -n"redefine task"\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_archive() -> str:
    return """\
Archive projects.

When a project is archived, all related time entries are also archived
and will not appear in results for timer:list or summary commands.

    --yes / -y:
        accept all prompts.\
"""


def project_archive_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project archive example-project
        $ p a example-project
    
        # archive multiple
        $ project archive example-project1 example-project2 example-project3\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_create() -> str:
    return """\
Create a new project.

For interactive prompt, pass no options.
The name [code]no-project[/code] is reserved for the default setting.

--name / -n:
    must match regex [code]^\[a-zA-Z0-9-\\_]{3,20}$[/code].\
"""


def project_create_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project create
    
        $ project create --name lightlike-cli
        $ p c -nlightlike-cli

        $ project create --name lightlike-cli --description "time-tracking repl" --default-billable true
        $ p c -nlightlike-cli -d"time-tracking repl" -bt # -b for default-billable flag\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_delete() -> str:
    return """\
Delete projects and all related time entries.

When a project is deleted, all related time entries are also deleted.

--yes / -y:
    accept all prompts.\
"""


def project_delete_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project delete lightlike-cli
        $ p d lightlike-cli

        # delete multiple
        $ project delete example-project1 example-project2 example-project3\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_list() -> str:
    return """\
List projects.

--all / -a:
    include archived projects.\
"""


def project_list_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project list
        $ p l
    
        $ project list --all
        $ p l -a\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_set() -> str:
    return """\
Set a project's name, description, or default billable setting.\
"""


def project_set_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project set name lightlike-cli …
    
        $ project set description lightlike-cli …

        $ project set default_billable lightlike-cli …\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_set_name() -> str:
    return """\
Update a project's name.

Name must match regex [code]no-project[/code].
The name [code]^\[a-zA-Z0-9-\\_]{3,20}$[/code] is reserved for the default setting.\
"""


def project_set_name_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project set name lightlike-cli # interactive
        $ p s n lightlike-cli

        $ project set name lightlike-cli new-name
        $ p s n lightlike-cli new-name\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_set_default_billable() -> str:
    return """\
Update a project's default billable setting.\
"""


def project_set_default_billable_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project set default_billable lightlike-cli true
        $ p s def lightlike-cli true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_set_description() -> str:
    return """\
Add/overwrite project description.\
"""


def project_set_description_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project set description lightlike-cli # interactive

        $ project set description lightlike-cli "time-tracking repl"
        $ p s desc lightlike-cli "time-tracking repl"\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def project_unarchive() -> str:
    return """\
Unarchive projects.

When a project is unarchived, all related time entries are also unarchived
and will appear in results for timer:list or summary commands.\
"""


def project_unarchive_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ project unarchive lightlike-cli
        $ p u lightlike-cli

        # unarchive multiple
        $ project unarchive example-project1 example-project2 example-project3\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def summary_csv() -> str:
    return """\
Create a summary and save to a csv file, or print to terminal.

[yellow][b][u]Note: running & paused entries are not included in summaries.[/b][/u][/yellow]

[b]Fields[/]:
  - total_summary: The total sum of hours over the entire summary.
  - total_project: The total sum of hours over the entire summary, partitioned by project.
  - total_day: The total sum of hours on each day, partitioned by day.
  - date: Date.
  - project: Project.
  - billable: Billable.
  - timer: The total sum of hours for a project on that day.
  - notes: String aggregate of all notes on that day. Sum of hours appened to the end.

--print / -p:
    print output to terminal.
    either this, or --output / -d must be provided.

--output / -d:
    save the output of the command to this path.
    either this, or --print / -p must be provided.

--output / -d:
    save the output of this command to this path.
    if the path does not have any suffix, then the expected suffix will be appended.
    if the path with the correct suffix already exists, a prompt will ask whether to overwrite or not.
    if the path ends in any suffix other than what's expected, an error will raise.

--round / -r:
    round totals to the nearest 0.25.

--current-week / -cw:
--current-month / -cm:
--current-year / -cy:
    flags are processed before other date options.
    configure week start dates with app:config:set:general:week_start.

--match-project / -Rp:
    match a regular expression against project names.

--match-note / -Rn:
    match a regular expression against entry notes.

--prompt-where / -w:
    filter results with a where clause.
    interactive prompt that launches after command runs.
    prompt includes autocompletions for projects and notes.
    note autocompletions will only populate for a project if that project name appears in the string.

[bold #34e2e2]WHERE[/]:
    where clause can also be written as the last argument to this command.
    it can be a single string, or individual words separated by a space,
    as long as characters are properly escaped if necessary.
    it must either begin with the word "WHERE" (case-insensitive),
    or it must be the string immediately proceeding the word "WHERE".\
"""


def summary_csv_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ summary csv --start jan1 --end jan31 --round --print
        $ s c -s jan1 -e jan31 -r -p
    
        $ summary csv --current-week --output path/to/file.csv where billable is false
        $ s c -cw -o path/to/file.csv where billable is false\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def summary_json() -> str:
    return """\
Create a summary and save to a json file, or print to terminal.

[yellow][b][u]Note: running & paused entries are not included in summaries.[/b][/u][/yellow]

[b]Fields[/]:
  - total_summary: The total sum of hours over the entire summary.
  - total_project: The total sum of hours over the entire summary, partitioned by project.
  - total_day: The total sum of hours on each day, partitioned by day.
  - date: Date.
  - project: Project.
  - billable: Billable.
  - timer: The total sum of hours for a project on that day.
  - notes: String aggregate of all notes on that day. Sum of hours appened to the end.

--print / -p:
    print output to terminal.
    either this, or --output / -d must be provided.

--output / -d:
    save the output of the command to this path.
    either this, or --print / -p must be provided.

--output / -d:
    save the output of this command to this path.
    if the path does not have any suffix, then the expected suffix will be appended.
    if the path with the correct suffix already exists, a prompt will ask whether to overwrite or not.
    if the path ends in any suffix other than what's expected, an error will raise.

--round / -r:
    round totals to the nearest 0.25.

--current-week / -cw:
--current-month / -cm:
--current-year / -cy:
    flags are processed before other date options.
    configure week start dates with app:config:set:general:week_start.

--orient / -o:
    default is [code]records[/code].
    available choices are; columns, index, records, split, table, values.
        split = dict like {"index" -> [index], "columns" -> [columns], "data" -> [values]}
        records = list like [{column -> value}, … , {column -> value}]
        index = dict like {index -> {column -> value}}
        columns = dict like {column -> {index -> value}}
        values = just the values array
        table = dict like {"schema": {schema}, "data": {data}}

--match-project / -Rp:
    match a regular expression against project names.

--match-note / -Rn:
    match a regular expression against entry notes.

--prompt-where / -w:
    filter results with a where clause.
    interactive prompt that launches after command runs.
    prompt includes autocompletions for projects and notes.
    note autocompletions will only populate for a project if that project name appears in the string.

[bold #34e2e2]WHERE[/]:
    where clause can also be written as the last argument to this command.
    it can be a single string, or individual words separated by a space,
    as long as characters are properly escaped if necessary.
    it must either begin with the word "WHERE" (case-insensitive),
    or it must be the string immediately proceeding the word "WHERE".\
"""


def summary_json_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ summary json --start "6 days ago" --end today --print
        $ s j -s -6d -e now -p
    
        $ summary json --current-week --orient index where billable is false
        $ s j -cw -o index -w\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def summary_table() -> str:
    return """\
Create a summary and render a table in terminal. Optional svg download.

[yellow][b][u]Note: running & paused entries are not included in summaries.[/b][/u][/yellow]

[b]Fields[/]:
  - total_summary: The total sum of hours over the entire summary.
  - total_project: The total sum of hours over the entire summary, partitioned by project.
  - total_day: The total sum of hours on each day, partitioned by day.
  - date: Date.
  - project: Project.
  - billable: Billable.
  - timer: The total sum of hours for a project on that day.
  - notes: String aggregate of all notes on that day. Sum of hours appened to the end.

--output / -d:
    save the output of this command to this path.
    if the path does not have any suffix, then the expected suffix will be appended.
    if the path with the correct suffix already exists, a prompt will ask whether to overwrite or not.
    if the path ends in any suffix other than what's expected, an error will raise.

--round / -r:
    round totals to the nearest 0.25.

--current-week / -cw:
--current-month / -cm:
--current-year / -cy:
    flags are processed before other date options.
    configure week start dates with app:config:set:general:week_start.

--match-project / -Rp:
    match a regular expression against project names.

--match-note / -Rn:
    match a regular expression against entry notes.

--prompt-where / -w:
    filter results with a where clause.
    interactive prompt that launches after command runs.
    prompt includes autocompletions for projects and notes.
    note autocompletions will only populate for a project if that project name appears in the string.

[bold #34e2e2]WHERE[/]:
    where clause can also be written as the last argument to this command.
    it can be a single string, or individual words separated by a space,
    as long as characters are properly escaped if necessary.
    it must either begin with the word "WHERE" (case-insensitive),
    or it must be the string immediately proceeding the word "WHERE".\
"""


def summary_table_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ summary table --current-month --round where project = \"lightlike-cli\"
        $ s t -cm -r where project = \"lightlike-cli\"
    
        $ summary table --current-year --output path/to/file.svg regexp_contains(note, r\\"(?i).*keyword\\")
        $ s t -cy -o path/to/file.svg regexp_contains(note, r\\"(?i).*keyword\\")

        $ summary table --start -15d --end monday
        $ s t -s -15d -e mon\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_dir() -> str:
    return """\
Open cli directory.

    --start / -s:
        default option.
        open app directory with the system command [code]start[/code].

    --editor / -e:
        open the app directory using the configured text-editor.
        configure text-editor with app:config:set:general:editor.\
"""


def app_dir_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app dir
    
        $ app dir --editor\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_run_bq() -> str:
    return """\
Run BigQuery scripts.

Executes all necessary scripts in BigQuery for this cli to run. Table's are only built if they do not exist.\
"""


def app_run_bq_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app run-bq\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config() -> str:
    return """\
View/Update cli configuration settings.

app:config:open:
    open the config file located in the users home directory using the default text editor.

app:config:show:
    view in config file in terminal.
    this list does not include everything, only the keys that can be updated through the cli.

app:config:set:
    [b]general settings[/b]:
        configure time entry functions
        login (if auth through a service-account)
        misc. behaviour (e.g. default text-editor).
    [b]query settings[/b]:
        configure behaviour for bq:query.\
"""


def app_config_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config open
        $ a c o
    
        $ app config show
        $ a c s
    
        $ app config set
        $ a c u\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_editor() -> str:
    return """\
Editor should be the full path to the executable, but the regular operating system search path is used for finding the executable.\
"""


def app_config_editor_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set general editor code
    
        $ app config set general editor vim\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_note_history() -> str:
    return """\
Days to store note history.

This settings affects how many days to store notes used by option --note / -n for autocompletions.
e.g. If days = 30, any notes older than 30 days won't appear in autocompletions.
Default is set to 90 days.\
"""


def app_config_note_history_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set general note-history 365\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_show() -> str:
    return """\
Show config file in terminal.

[b]general settings[/b] affect timer functions/options, logging in (if using a service-account-key), and behaviour of other commands such as the default text-editor to launch.
[b]query settings[/b] affect the behaviour of the bq:query.\
"""


def app_config_show_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config show
        $ a c s
    
        $ app config show --json
        $ a c s -j\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_stay_logged_in() -> str:
    return """\
Save login password.

This setting is only visible if the client is authenticated using a service-account key.
It's not recommended to leave this setting on, as the password and encryped key are stored in the same place.\
"""


def app_config_stay_logged_in_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set general stay_logged_in true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_system_command_shell():
    return """\
Shell to use when running external commands.

e.g.
unix: ["sh", "-c"] / ["bash", "-c"]
windows: ["cmd", "/C"]

When setting value, enclose list in single quotes, and use double quotes for string values.
"""


def app_config_system_command_shell_syntax() -> Syntax:
    return Syntax(
        code="""\
        # if setting was set to ["bash", "-c"]
        # and the command is `ls`
        # then it will be executed as
        $ bash -c "ls"

        # example setting config key
        $ app config set general shell '["bash", "-c"]'
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_timezone() -> str:
    return """\
Timezone used for all date/time conversions.

If this value is updated, run app:run-bq to rebuild procedures in BigQuery using the new timezone.\
"""


def app_config_timezone_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set general timezone UTC\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_week_start() -> str:
    return """\
Update week start for option --current-week / -cw.\
"""


def app_config_week_start_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set week_start Sunday\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_hide_table_render() -> str:
    return """\
If save_text or save_svg is enabled, enable/disable table render in console.

If save_text or save_svg is disabled, this option does not have any affect.\
"""


def app_config_hide_table_render_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set query hide_table_render true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_mouse_support() -> str:
    return """\
Controls mouse support in bq:query.\
"""


def app_config_mouse_support_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set query mouse_support true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_save_query_info() -> str:
    return """\
Include query info when saving to file.

Query info:
    - query string
    - resource url
    - elapsed time
    - cache hit/output
    - statement type
    - slot millis
    - bytes processed/billed
    - row count
    - dml stats\
"""


def app_config_save_query_info_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set query save_query_info true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_save_svg() -> str:
    return """\
Queries using bq:query will save the rendered result to an [code].svg[/code] file in the app directory.\
"""


def app_config_save_svg_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set query save_svg true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_config_save_txt() -> str:
    return """\
Queries using bq:query will save the rendered result to a [code].txt[/code] file in the app directory.\
"""


def app_config_save_txt_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app config set query save_txt true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_sync() -> str:
    return """\
Syncs local files for time entry data, projects, and cache.

These can be found in the app directory using the app:dir.

These tables should only ever be altered through the procedures in this cli.
If the local files are out of sync with BigQuery, or if logging in from a new location, can use this command to re-sync them.\
"""


def app_sync_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app sync --appdata
        $ a s -a

        $ app sync --cache
        $ a s -c

        $ app sync --appdata --cache
        $ a s -ac\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )


def app_test_dateparser() -> str:
    return """\
Test the dateparser function.

DATE/TIME FIELDS:
    arguments/options asking for datetime will attempt to parse the string provided.
    error will raise if unable to parse.
    dates are relative to today, unless explicitly stated in the string.

    Example values to pass to the date parser:
    | type             | examples                                                  |
    |-----------------:|-----------------------------------------------------------|
    | datetime         | jan1@2pm [d](January 1st current year at 2:00 PM)[/d]            |
    | date (relative)  | today/now, yesterday, monday, 2 days ago, -2d | "\-2d"    |
    | time (relative)  | -15m [d](15 minutes ago)[/d], 1.25 hrs ago, -1.25hr | "\-1.25hr" |
    | date             | jan1, 01/01, 2024-01-01                                   |
    | time             | 2pm, 14:30:00, 2:30pm                                     |

    [b]Note:[/b] If the date is an argument, the minus operator needs to be escaped.
    e.g.
    ```
    $ command --option -2d
    $ c -o-2d
    $ command \-2d # argument
    $ c \-2d # argument
    ```
"""


def app_test_dateparser_syntax() -> Syntax:
    return Syntax(
        code="""\
        $ app test date-parse --date -1.35hr\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    )
