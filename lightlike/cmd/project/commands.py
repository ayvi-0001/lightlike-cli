import typing as t

import click
import rich
from more_itertools import first
from rich.syntax import Syntax

from lightlike.app import _get, _questionary, render, shell_complete, threads, validate
from lightlike.app.autosuggest import threaded_autosuggest
from lightlike.app.core import AliasedGroup, FormattedCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _pass
from lightlike.internal import markup, utils

if t.TYPE_CHECKING:
    from rich.console import Console
    from rich.table import Table

    from lightlike.app.cache import TimeEntryAppData, TimeEntryCache
    from lightlike.client import CliQueryRoutines

__all__: t.Sequence[str] = (
    "archive",
    "create",
    "delete",
    "list_",
    "set_",
    "set_project_default_billable",
    "set_project_description",
    "set_project_name",
    "unarchive",
)


@click.command(
    cls=FormattedCommand,
    name="archive",
    no_args_is_help=True,
    short_help="Archive projects and related time entries.",
    syntax=Syntax(
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
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not archive projects.")),
)
@click.argument(
    "projects",
    type=shell_complete.projects.ActiveProject,
    required=True,
    default=None,
    callback=validate.active_project_list,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.projects.from_argument,
)
@click.option(
    "-y",
    "--yes",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Accept all prompts",
    required=False,
    hidden=True,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.cache
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def archive(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    cache: TimeEntryCache,
    projects: t.Sequence[str],
    yes: bool,
) -> None:
    """
    Archive projects.

    When a project is archived, all related time entries are also archived
    and will not appear in results for timer:list or summary commands.

        --yes / -y:
            accept all prompts.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not yes:
        if not _questionary.confirm(
            message="This will hide all related time entries from timer:list and summary commands. Continue? ",
            auto_enter=True,
        ):
            return

    with console.status(markup.status_message("Getting project info")) as status:
        all_count_entries = []

        for project in projects:
            matching_entries = cache.get(
                cache.running_entries + cache.paused_entries,
                key="project",
                sequence=[project],
            )

            if matching_entries:
                status.stop()
                console.print(
                    markup.code(project),
                    "has one or more of running/paused entries.",
                    "End these entries before trying to archive this project.",
                    "\nMatching entries:",
                )
                table: Table = render.map_sequence_to_rich_table(matching_entries)
                console.print(table)
                status.start()
                continue

            query_job = routine.select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=[f'project = "{project}"'],
            )
            routine.archive_project(project)
            routine.archive_time_entries(project)

            threads.spawn(ctx, appdata.sync, {"debug": debug})
            count_archived: int = _get.count_entries(first(query_job))

            all_count_entries.append(count_archived)

            console.print(
                "Archived project",
                markup.code(project),
                "and",
                count_archived,
                "related time {}".format("entry" if count_archived == 1 else "entries"),
            )

        if all_count_entries and max(all_count_entries) > 0:
            console.print(
                "Any related entries will not appear in results until you unarchive",
                "this project." if len(projects) == 1 else "these projects.",
            )


@click.command(
    cls=FormattedCommand,
    name="create",
    short_help="Create a new project.",
    syntax=Syntax(
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
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not create project.")),
)
@click.option(
    "-n",
    "--name",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Project name.",
    required=False,
    default=None,
    callback=validate.new_project,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-d",
    "--description",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Project description.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-b",
    "--default-billable",
    show_default=True,
    multiple=False,
    type=click.BOOL,
    help="Default billable flag for new time entries.",
    required=False,
    default=False,
    callback=None,
    metavar=None,
    shell_complete=shell_complete.Param("value").bool,
)
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def create(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    name: str,
    description: str,
    default_billable: bool,
) -> None:
    r"""
    Create a new project.

    For interactive prompt, pass no options.
    The name [code]no-project[/code] is reserved for the default setting.

    --name / -n:
        must match regex [code]^\[a-zA-Z0-9-\_\.]{3,30}$[/code].
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not name:
        name = PromptFactory.prompt_project(new=True)

        # Only prompt for description and default billable if command was called with no flags.
        # Otherwise assume user ignored options.
        if not description and _questionary.confirm(
            message="Description?",
            auto_enter=True,
            default=False,
        ):
            description = PromptFactory._prompt("(description)")

        if default_billable is False and _questionary.confirm(
            message="Default billable?",
            auto_enter=True,
            default=False,
        ):
            default_billable = True

    debug and console.log(
        "[DEBUG]",
        "project default billable set to",
        default_billable,
    )

    routine.create_project(
        name=name,
        description=description,
        default_billable=default_billable,
    )

    threads.spawn(ctx, appdata.sync, {"debug": debug})
    console.print("Created new project:", markup.code(name))


@click.command(
    cls=FormattedCommand,
    name="delete",
    no_args_is_help=True,
    short_help="Deletes projects and related time entries.",
    syntax=Syntax(
        code="""\
        $ project delete lightlike-cli
        $ p d lightlike-cli

        # delete multiple
        $ project delete example-project1 example-project2 example-project3
        $ p d example-project1 example-project2 example-project3\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not delete projects.")),
)
@click.argument(
    "projects",
    type=shell_complete.projects.ActiveProject,
    required=True,
    default=None,
    callback=validate.active_project_list,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.projects.from_argument,
)
@click.option(
    "-y",
    "--yes",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Accept all prompts",
    required=False,
    hidden=True,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.cache
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def delete(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    cache: TimeEntryCache,
    projects: t.Sequence[str],
    yes: bool,
) -> None:
    """
    Delete projects and all related time entries.

    When a project is deleted, all related time entries are also deleted.

    --yes / -y:
        accept all prompts.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not yes and not _questionary.confirm(
        message=(
            "This will permanently delete %s and all related time entries. Continue? "
            % ("this project" if len(projects) == 1 else "these projects")
        ),
        default=False,
    ):
        return

    with console.status(markup.status_message("Getting project info")):
        for project in projects:
            count_query_job = routine.select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=[f'project = "{project}"'],
            )
            routine.delete_project(project)
            threads.spawn(ctx, appdata.sync, {"debug": debug})
            routine.delete_time_entries_by_project(project)

            count_deleted: int = _get.count_entries(first(count_query_job))
            console.print(
                "Deleted project",
                markup.code(project),
                "and",
                count_deleted,
                "related time",
                "entry" if count_deleted == 1 else "entries",
            )

            if cache and cache.project == project:
                cache.clear_active()

            cache.remove(key="project", sequence=[project])


@click.command(
    cls=FormattedCommand,
    name="list",
    short_help="List projects.",
    syntax=Syntax(
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
    ),
)
@click.option(
    "-a",
    "--all",
    "all_",
    show_default=True,
    is_flag=True,
    flag_value=True,
    multiple=False,
    type=click.BOOL,
    help="Include archived projects.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-E",
    "--exclude",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Exclude pattern matched against project name and/or note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-I",
    "--include",
    show_default=True,
    multiple=True,
    type=click.STRING,
    help="Include pattern matched against project name and/or note.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-M",
    "--modifiers",
    show_default=False,
    multiple=False,
    type=click.STRING,
    help="Modifiers to pass to RegExp. (ECMAScript only)",
    required=False,
    default="",
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-O",
    "--order-by",
    show_default=True,
    multiple=False,
    type=click.Choice(
        ["created:asc", "created:desc", "name:asc", "name:desc"],
        case_sensitive=False,
    ),
    help="Order table.",
    required=False,
    default="created:desc",
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-re",
    "--regex-engine",
    show_default=True,
    multiple=False,
    type=click.Choice(["ECMAScript", "re2"]),
    help="Regex engine to use.",
    required=False,
    default="ECMAScript",
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.console
def list_(
    console: Console,
    routine: CliQueryRoutines,
    all_: bool,
    exclude: t.Sequence[str],
    include: t.Sequence[str],
    modifiers: str,
    order_by: str,
    regex_engine: str,
) -> None:
    """
    List projects.

    --all / -a:
        include archived projects.

    --exclude / -E:
        exclude pattern matched against project name and/or note.
        this option can be repeated, with each pattern being separated by `|`.

    --include / -I:
        include pattern matched against project name and/or note.
        this option can be repeated, with each pattern being separated by `|`.

    --modifiers / -M:
        modifiers to pass to RegExp. (ECMAScript only)

    --regex-engine / -re:
        which regex engine to use.
        re2 = google's regular expression library used by all bigquery regex functions.
        ECMAScript = javascript regex syntax.

    Example:
        re2 does not allow perl operator's such as negative lookaheads, while ECMAScript does.
        to run a case-insensitive regex match in re2, use the inline modifier [repr.str]"(?i)"[/repr.str],
        for ECMAScript, use the --modifiers / -M option with [repr.str]"i"[/repr.str]

    """
    fields: list[str] = [
        "name",
        "description",
        "default_billable",
        "created",
    ]
    if all_:
        fields.append("archived")

    where: list[str] = []

    if not all_:
        where.append("archived is null")

    fmt_exclude_expression: str = ""
    if exclude:
        exclude_expressions: list[str] = []
        for pattern in exclude:
            exclude_expressions.append(pattern)

        exclude_expression: str = "|".join(exclude_expressions)
        fmt_exclude_expression = routine.format_regular_expression(
            fields=["name", "description"],
            expr=exclude_expression,
            modifiers=modifiers,
            regex_engine=regex_engine,
            not_=True,
        )

        where.append(fmt_exclude_expression)

    fmt_include_expression: str = ""
    if include:
        include_expressions: list[str] = []
        for pattern in include:
            include_expressions.append(pattern)

        include_expression: str = "|".join(include_expressions)
        fmt_include_expression = routine.format_regular_expression(
            fields=["name", "description"],
            expr=include_expression,
            modifiers=modifiers,
            regex_engine=regex_engine,
            not_=False,
        )

        where.append(fmt_include_expression)

    query_job = routine.select(
        resource=routine.projects_id,
        fields=fields,
        where=where,
        order=[order_by.replace(":", " ")],
    )

    table: Table = render.map_sequence_to_rich_table(
        mappings=[dict(r.items()) for r in query_job],
    )
    if not table.row_count:
        rich.print(markup.dimmed("No results"))
        raise click.exceptions.Exit

    console.print(table)


@click.group(
    cls=AliasedGroup,
    name="set",
    short_help="Update a project's name/description/default-billable.",
    syntax=Syntax(
        code="""\
        $ project set name lightlike-cli ...

        $ project set description lightlike-cli ...

        $ project set default-billable lightlike-cli ...\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
def set_() -> None:
    """Set a project's name, description, or default billable setting."""


@set_.command(
    cls=FormattedCommand,
    name="name",
    short_help="Update a project's name.",
    syntax=Syntax(
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
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not update project.")),
)
@click.argument(
    "project",
    type=shell_complete.projects.ActiveProject,
    required=True,
    default=None,
    callback=validate.active_project,
    nargs=1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.projects.from_argument,
)
@click.argument(
    "name",
    type=click.STRING,
    required=False,
    default=None,
    callback=None,
    nargs=1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=None,
)
@_pass.cache
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def set_project_name(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    cache: TimeEntryCache,
    project: str,
    name: str,
) -> None:
    r"""
    Update a project's name.

    Name must match regex [code]^\\[a-zA-Z0-9-\\_\\.]{3,30}$[/code].
    The name [code]no-project[/code] is reserved for the default setting.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    new_name = name or PromptFactory.prompt_project(new=True)

    if project == new_name:
        console.print(markup.dimmed("Current name, nothing happened."))
        raise click.exceptions.Exit

    with console.status(markup.status_message("Updating project")):
        routine.update_project_name(old_name=project, new_name=new_name)
        routine.update_time_entry_projects(old_name=project, new_name=new_name)
        cache.sync()
        console.print(
            "Renamed project",
            markup.code(project),
            "to",
            markup.code(new_name),
        )

    threads.spawn(ctx, appdata.sync, {"debug": debug})


@set_.command(
    cls=FormattedCommand,
    name="description",
    syntax=Syntax(
        code="""\
        $ project set description lightlike-cli # interactive

        $ project set description lightlike-cli "time-tracking repl"
        $ p s desc lightlike-cli "time-tracking repl"\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not update project.")),
)
@click.argument(
    "project",
    type=shell_complete.projects.ActiveProject,
    required=True,
    default=None,
    callback=validate.active_project,
    nargs=1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.projects.from_argument,
)
@click.argument(
    "desc",
    type=click.STRING,
    required=False,
    default=None,
    callback=None,
    nargs=1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=None,
)
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def set_project_description(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    project: str,
    desc: str,
) -> None:
    """Add/overwrite project description."""
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    active_projects: dict[str, t.Any]
    try:
        active_projects = appdata.load()["active"]
    except KeyError:
        appdata.sync(debug=debug)
        active_projects = appdata.load()["active"]

    project_appdata: dict[str, t.Any] = active_projects[project]
    current_desc = (
        project_appdata["description"] if project_appdata["description"] != "null" else None
    )

    default: str = current_desc or ""

    new_desc = desc or PromptFactory._prompt(
        message="(description)",
        default=default,
        auto_suggest=threaded_autosuggest([default]),
    )

    if not new_desc:
        raise click.exceptions.Exit

    if current_desc == new_desc:
        console.print(markup.dimmed("Current description, nothing happened."))
        return

    routine.update_project_description(project, new_desc)
    threads.spawn(ctx, appdata.sync, {"debug": debug})
    console.print("Set description to", markup.repr_str(new_desc))


@set_.command(
    cls=FormattedCommand,
    name="default-billable",
    syntax=Syntax(
        code="""\
        $ project set default-billable lightlike-cli true
        $ p s def lightlike-cli true\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not update project.")),
)
@click.argument(
    "project",
    type=shell_complete.projects.ActiveProject,
    required=True,
    default=None,
    callback=validate.active_project,
    nargs=1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.projects.from_argument,
)
@click.argument(
    "billable",
    type=click.BOOL,
    required=True,
    default=None,
    callback=None,
    nargs=1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.Param("value").bool,
)
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def set_project_default_billable(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    project: str,
    billable: bool,
) -> None:
    """Update a project's default billable setting."""
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)
    routine.update_project_default_billable(project, default_billable=billable)
    threads.spawn(ctx, appdata.sync, {"debug": debug})
    console.print("Set project default billable to", billable)


@click.command(
    cls=FormattedCommand,
    name="unarchive",
    no_args_is_help=True,
    short_help="Unarchive projects and all hidden time entries.",
    syntax=Syntax(
        code="""\
        $ project unarchive lightlike-cli
        $ p u lightlike-cli

        # unarchive multiple
        $ project unarchive example-project1 example-project2 example-project3
        $ p u example-project1 example-project2 example-project3\
        """,
        lexer="fishshell",
        dedent=True,
        line_numbers=True,
        background_color="#131310",
    ),
)
@utils.handle_keyboard_interrupt(
    callback=lambda: rich.print(markup.dimmed("Did not unarchive project.")),
)
@click.argument(
    "projects",
    type=shell_complete.projects.ArchivedProject,
    required=True,
    default=None,
    callback=validate.archived_project_list,
    nargs=-1,
    metavar=None,
    expose_value=True,
    is_eager=False,
    shell_complete=shell_complete.projects.from_argument,
)
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def unarchive(
    ctx_group: t.Sequence[click.Context],
    console: Console,
    routine: CliQueryRoutines,
    appdata: TimeEntryAppData,
    projects: t.Sequence[str],
) -> None:
    """
    Unarchive projects.

    When a project is unarchived, all related time entries are also unarchived
    and will appear in results for timer:list or summary commands.
    """
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    with console.status(markup.status_message("Unarchiving project..")):
        all_count_entries = []

        for project in projects:
            query_job = routine.select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=[f'project = "{project}"'],
            )
            routine.unarchive_project(project)
            threads.spawn(ctx, appdata.sync, {"debug": debug})
            routine.unarchive_time_entries(project)
            count_unarchived: int = _get.count_entries(first(query_job))
            all_count_entries.append(count_unarchived)
            console.print(
                "Unarchived project",
                markup.code(project),
                "and",
                count_unarchived,
                "related time",
                "entry" if count_unarchived == 1 else "entries",
            )

        if all_count_entries and max(all_count_entries) > 0:
            console.print("Any related entries will now appear in results again.")
