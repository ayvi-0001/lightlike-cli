# mypy: disable-error-code="func-returns-value"

import typing as t

import rich_click as click
from more_itertools import first
from prompt_toolkit.patch_stdout import patch_stdout
from rich import print as rprint
from rich.text import Text

from lightlike.__about__ import __appname_sc__
from lightlike.app import _get, _pass, render, shell_complete, threads, validate
from lightlike.app.core import AliasedRichGroup, FmtRichCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _help
from lightlike.internal import markup, utils
from lightlike.lib.third_party import _questionary

if t.TYPE_CHECKING:
    from rich.console import Console

    from lightlike.app.cache import TimeEntryAppData, TimeEntryCache
    from lightlike.app.routines import CliQueryRoutines

__all__: t.Sequence[str] = (
    "archive",
    "create",
    "delete",
    "list_",
    "set_",
    "set_name",
    "set_description",
    "set_default_billable",
    "unarchive",
)


@click.command(
    cls=FmtRichCommand,
    name="archive",
    no_args_is_help=True,
    help=_help.project_archive,
    short_help="Archive projects and related time entries.",
    syntax=_help.project_archive_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not archive projects.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    cache: "TimeEntryCache",
    projects: t.Sequence[str],
    yes: bool,
) -> None:
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
                console.print(
                    render.map_sequence_to_rich_table(
                        mappings=matching_entries,
                        string_ctype=["id", "project", "note"],
                        bool_ctype=["billable", "paused"],
                        num_ctype=[
                            "total_summary",
                            "total_project",
                            "total_day",
                            "hours",
                        ],
                        datetime_ctype=["timestamp_paused"],
                        time_ctype=["start"],
                    )
                )
                status.start()
                continue

            query_job = routine._select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=[f'project = "{project}"'],
            )
            routine.archive_project(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=Text.assemble(
                    markup.status_message("Archiving project "),
                    markup.code(project),
                ),
            )
            routine.archive_time_entries(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=Text.assemble(
                    markup.status_message("Archiving "),
                    markup.code(project),
                    markup.status_message(" time entries"),
                ),
            )

            threads.spawn(ctx, appdata.sync, dict(debug=debug))
            count_archived: int = _get.count_entries(first(query_job))

            all_count_entries.append(count_archived)

            console.print(
                "Archived project",
                markup.code(project),
                "and",
                count_archived,
                "related time" "entry" if count_archived == 1 else "entries",
            )

            status.update("")

        if all_count_entries and max(all_count_entries) > 0:
            console.print(
                "Any related entries will not appear in results until you unarchive",
                "this project." if len(projects) == 1 else "these projects.",
            )


@click.command(
    cls=FmtRichCommand,
    name="create",
    help=_help.project_create,
    short_help="Create a new project.",
    syntax=_help.project_create_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not create project.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    name: str,
    description: str,
    default_billable: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not name:
        name = PromptFactory.prompt_project(new=True)

        # Only prompt for description and default billable if command was called with no flags.
        # Otherwise assume user ignored options.
        if not description and _questionary.confirm(
            message="Description?", auto_enter=True, default=False
        ):
            description = PromptFactory._prompt("(description)")

        if default_billable is False and _questionary.confirm(
            message="Default billable?", auto_enter=True, default=False
        ):
            default_billable = True

    debug and patch_stdout(raw=True)(console.log)(
        "[DEBUG]:", "project default billable set to", default_billable
    )

    routine.create_project(
        name=name,
        description=description or "",
        default_billable=default_billable,
        wait=True,
        render=True,
        status_renderable=markup.status_message("Creating project"),
    )
    threads.spawn(ctx, appdata.sync, dict(debug=debug))
    console.print("Created new project:", markup.code(name))


@click.command(
    cls=FmtRichCommand,
    name="delete",
    no_args_is_help=True,
    help=_help.project_delete,
    short_help="Deletes projects and related time entries.",
    syntax=_help.project_delete_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not delete projects.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    cache: "TimeEntryCache",
    projects: t.Sequence[str],
    yes: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    if not yes:
        if not _questionary.confirm(
            message=(
                "This will permanently delete %s and all related time entries. Continue? "
                % ("this project" if len(projects) == 1 else "these projects")
            ),
            default=False,
        ):
            return

    with console.status(markup.status_message("Getting project info")) as status:
        for project in projects:
            count_query_job = routine._select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=[f'project = "{project}"'],
            )
            routine.delete_project(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=Text.assemble(
                    markup.status_message("Deleting "),
                    markup.code(project),
                    markup.status_message(" from projects"),
                ),
            )
            threads.spawn(ctx, appdata.sync, dict(debug=debug))
            routine.delete_time_entries(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=Text.assemble(
                    markup.status_message("Deleting "),
                    markup.code(project),
                    markup.status_message(" time entries"),
                ),
            )

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
                cache._clear_active()
                console.set_window_title(__appname_sc__)

            cache.remove(
                entries=[cache.running_entries, cache.paused_entries],
                key="project",
                sequence=[project],
            )

            status.update("")


@click.command(
    cls=FmtRichCommand,
    name="list",
    help=_help.project_list,
    short_help="List projects.",
    syntax=_help.project_list_syntax,
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
    "-Rn",
    "--match-name",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Expression to match project name.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@click.option(
    "-Rd",
    "--match-description",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Expression to match project description.",
    required=False,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.console
def list_(
    console: "Console",
    routine: "CliQueryRoutines",
    all_: bool,
    match_name: str,
    match_description: str,
) -> None:
    fields: list[str] = [
        "name",
        "description",
        "default_billable",
        "date(created) as created",
    ]
    if all_:
        fields.append("date(archived) as archived")

    where: list[str] = []
    if not all_:
        where.append("archived is null")
    if match_name:
        where.append(
            f'{routine.dataset_main}.js_regex_contains(name, r"{match_name}")',
        )
    if match_description:
        where.append(
            f'{routine.dataset_main}.js_regex_contains(description, r"{match_description}")',
        )

    order: list[str] = ["created desc"]

    query_job = routine._select(
        resource=routine.projects_id,
        fields=fields,
        where=where,
        order=order,
    )

    table = render.map_sequence_to_rich_table(
        mappings=list(map(lambda r: dict(r.items()), query_job)),
        string_ctype=["name", "description"],
        bool_ctype=["default_billable"],
        date_ctype=["created", "archived"],
    )

    console.print(table)


@click.group(
    cls=AliasedRichGroup,
    name="set",
    help=_help.project_set,
    short_help="Update a project's name/description/default_billable.",
    syntax=_help.project_set_syntax,
)
def set_() -> None: ...


@set_.command(
    cls=FmtRichCommand,
    name="name",
    help=_help.project_set_name,
    syntax=_help.project_set_name_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not update project.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    cache: "TimeEntryCache",
    project: str,
    name: str,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    new_name = name or PromptFactory.prompt_project(new=True)

    if project == new_name:
        console.print(markup.dimmed("Current name, nothing happened."))
        raise utils.click_exit

    with console.status(markup.status_message("Updating project")) as status:
        routine.update_project_name(
            name=project,
            new_name=new_name,
            wait=True,
            render=True,
            status=status,
            status_renderable=markup.status_message("Updating project name"),
        )
        threads.spawn(ctx, appdata.sync, dict(debug=debug))
        routine.update_time_entry_projects(
            name=project,
            new_name=new_name,
            wait=True,
            render=True,
            status=status,
            status_renderable=markup.status_message("Updating related time entries"),
        )
        cache.sync()
        console.print(
            "Renamed project",
            markup.code(project),
            "to",
            markup.code(new_name),
        )


@set_.command(
    cls=FmtRichCommand,
    name="description",
    help=_help.project_set_description,
    syntax=_help.project_set_description_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not update project.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    project: str,
    desc: str,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    from lightlike.app.autosuggest import threaded_autosuggest

    active_projects: dict[str, t.Any]
    try:
        active_projects = appdata.load()["active"]
    except KeyError:
        appdata.sync()
        active_projects = appdata.load()["active"]

    project_appdata: dict[str, t.Any] = active_projects[project]
    current_desc = (
        project_appdata["description"]
        if project_appdata["description"] != "null"
        else None
    )

    new_desc = desc or PromptFactory._prompt(
        message="(description)",
        default=current_desc or "",
        auto_suggest=threaded_autosuggest([current_desc or ""]),
        bottom_toolbar=lambda: f"Enter new description for project: {project}.",
    )

    if not new_desc:
        raise utils.click_exit

    if current_desc == new_desc:
        console.print(markup.dimmed("Current description, nothing happened."))
        return

    routine.update_project_description(
        project,
        new_desc,
        wait=True,
        render=True,
        status_renderable=markup.status_message("Updating project"),
    )
    threads.spawn(ctx, appdata.sync, dict(debug=debug))
    console.print("Set description to", markup.repr_str(new_desc))


@set_.command(
    cls=FmtRichCommand,
    name="default_billable",
    help=_help.project_set_default_billable,
    syntax=_help.project_set_default_billable_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not update project.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    project: str,
    billable: bool,
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    routine.update_project_default_billable(
        project,
        billable,
        wait=True,
        render=True,
        status_renderable=markup.status_message("Updating project"),
    )
    threads.spawn(ctx, appdata.sync, dict(debug=debug))
    console.print("Set project default billable to", billable)


@click.command(
    cls=FmtRichCommand,
    name="unarchive",
    help=_help.project_unarchive,
    no_args_is_help=True,
    short_help="Unarchive projects and all hidden time entries.",
    syntax=_help.project_unarchive_syntax,
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not unarchive project.")),
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
    ctx_group: t.Sequence[click.RichContext],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "TimeEntryAppData",
    projects: t.Sequence[str],
) -> None:
    ctx, parent = ctx_group
    debug: bool = parent.params.get("debug", False)

    with console.status(markup.status_message("Getting project info")) as status:
        all_count_entries = []

        for project in projects:
            query_job = routine._select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=[f'project = "{project}"'],
            )
            routine.unarchive_project(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=Text.assemble(
                    markup.status_message("Unarchiving project "),
                    markup.code(project),
                ),
            )
            threads.spawn(ctx, appdata.sync, dict(debug=debug))
            routine.unarchive_time_entries(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=Text.assemble(
                    markup.status_message("Unarchiving "),
                    markup.code(project),
                    markup.status_message(" time entries"),
                ),
            )
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
