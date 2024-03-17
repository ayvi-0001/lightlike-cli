from typing import TYPE_CHECKING, Sequence

import rich_click as click
from more_itertools import first
from rich import print as rprint

from lightlike.__about__ import __appname_sc__
from lightlike.app import _get, _pass, render, shell_complete, threads, validate
from lightlike.app.autosuggest import _threaded_autosuggest
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.app.prompt import PromptFactory
from lightlike.cmd import _help
from lightlike.internal import utils
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from rich.console import Console

    from lightlike.app.cache import EntryAppData, TomlCache
    from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = ("projects",)


@click.group(
    cls=AliasedRichGroup,
    short_help="Create & manage projects.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def project(debug: bool) -> None: ...


@project.command(
    cls=_RichCommand,
    name="create",
    help=_help.project_create,
    short_help="Create a new project.",
    context_settings=dict(
        obj=dict(syntax=_help.project_create_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not create project."),
)
@click.argument(
    "name",
    type=click.STRING,
    is_eager=True,
    expose_value=True,
    required=False,
    callback=validate.new_project,
)
@click.argument(
    "description",
    type=click.STRING,
    required=False,
)
@click.option(
    "-nd",
    "--no-desc",
    is_flag=True,
    hidden=True,
    help="Ignore prompt for a description.",
)
@_pass.appdata
@_pass.routine
@_pass.console
@click.pass_context
def create(
    ctx: click.Context,
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "EntryAppData",
    name: str,
    description: str,
    no_desc: bool,
) -> None:
    if not name:
        name = PromptFactory.prompt_project(new=True)
    if (
        not no_desc
        and not description
        and _questionary.confirm(message="Add a description?", auto_enter=True)
    ):
        description = PromptFactory._prompt("(description)")

    routine.create_project(
        name,
        description or "",
        wait=True,
        render=True,
        status_renderable="Creating project",
    )

    threads.spawn(ctx, appdata.update)
    console.print(f"[saved]Saved[/saved]. Created new project: [code]{name}[/code].")


@project.command(
    cls=_RichCommand,
    name="list",
    help=_help.project_list,
    short_help="List active projects.",
    context_settings=dict(
        obj=dict(syntax=_help.project_list_syntax),
    ),
)
@click.option(
    "-a",
    "--all",
    "all_",
    is_flag=True,
    help="Include archived projects.",
)
@_pass.routine
def list_projects(routine: "CliQueryRoutines", all_: bool) -> None:
    table = render.row_iter_to_rich_table(
        row_iterator=routine.select(
            resource=routine.projects_id,
            fields=(
                ["* REPLACE(DATE(created) as created, DATE(archived) as archived)"]
                if all_
                else ["name", "description", "DATE(created) as created"]
            ),
            where="archived is null" if not all_ else "",
            order="name",
        ).result(),
    )
    render.new_console_print(table)


@project.group(
    cls=AliasedRichGroup,
    name="update",
    short_help="Update a project's name/description.",
)
@click.argument(
    "project",
    nargs=1,
    type=shell_complete.projects.ActiveProject,
    metavar="TEXT",
    required=True,
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_argument,
)
@click.pass_context
def update(ctx: click.Context, project: str) -> None:
    ctx.obj = project


@update.command(
    cls=_RichCommand,
    name="name",
    help=_help.project_update_name,
    short_help="Change projects name.",
    context_settings=dict(
        obj=dict(syntax=_help.project_update_name_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not update project."),
)
@_pass.confirm_options
@_pass.cache
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def update_name(
    ctx_group: Sequence[click.Context],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "EntryAppData",
    cache: "TomlCache",
    confirm: bool,
    yes: bool,
) -> None:
    ctx, parent = ctx_group
    project = parent.obj

    renamed_project = PromptFactory.prompt_project(new=True)

    if project == renamed_project:
        console.print("[d]Current name, nothing happened.")
        return

    if not (confirm or yes):
        if not _questionary.confirm(
            message="This will update all time entries under this project. Continue?",
            auto_enter=True,
        ):
            return

    with console.status("[status.message] Updating project name") as status:
        routine.update_project_name(
            project,
            renamed_project,
            wait=True,
            render=True,
            status=status,
            status_renderable="Updating project name",
        )
        routine.update_time_entry_projects(
            project,
            renamed_project,
            wait=True,
            render=True,
            status=status,
            status_renderable="Updating time entries",
        )

        threads.spawn(ctx, appdata.update)
        cache._sync_cache()
        console.print(
            "[saved]Saved[/saved]. "
            f"Renamed project [repr.str]{project}[/repr.str] to "
            f"[repr.str]{renamed_project}[/repr.str]."
        )


@update.command(
    cls=_RichCommand,
    name="description",
    help=_help.project_update_description,
    short_help="Change projects description.",
    context_settings=dict(
        obj=dict(syntax=_help.project_update_description_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not update project."),
)
@_pass.appdata
@_pass.routine
@_pass.console
@_pass.ctx_group(parents=1)
def update_description(
    ctx_group: Sequence[click.Context],
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "EntryAppData",
) -> None:
    ctx, parent = ctx_group
    project = parent.obj

    query_job = routine.select(
        resource=routine.projects_id,
        fields=["description"],
        where=f'name = "{project}"',
    )

    current_description: str = _get.description(first(query_job))

    description = PromptFactory._prompt(
        message="(description)",
        default=current_description or "",
        auto_suggest=_threaded_autosuggest([current_description or ""]),
        bottom_toolbar=lambda: f"Enter new description for project: {project}.",
    )

    if current_description == description or not description:
        console.print("[d]Current description, nothing happened.")
        return

    routine.update_project_description(project, description, wait=True, render=True)
    threads.spawn(ctx, appdata.update)
    console.print(
        "[saved]Saved[/saved]. Updated project description "
        f"to [repr.str]{description}[/repr.str]."
    )


@project.command(
    cls=_RichCommand,
    name="delete",
    help=_help.project_delete,
    no_args_is_help=True,
    short_help="Delete a project. Remove all related time entries.",
    context_settings=dict(
        obj=dict(syntax=_help.project_delete_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not delete project."),
)
@click.argument(
    "projects",
    nargs=-1,
    type=shell_complete.projects.ActiveProject,
    metavar="TEXT",
    required=True,
    callback=validate.active_project_list,
    shell_complete=shell_complete.projects.from_argument,
)
@_pass.confirm_options
@_pass.cache
@_pass.appdata
@_pass.routine
@_pass.console
@click.pass_context
def delete(
    ctx: click.Context,
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "EntryAppData",
    cache: "TomlCache",
    projects: Sequence[str],
    confirm: bool,
    yes: bool,
) -> None:
    if not (confirm or yes):
        if not _questionary.confirm(
            message="This will permanently delete all time entries "
            f"under {'this project' if len(projects) == 1 else 'these projects'}. "
            "Continue?",
            auto_enter=True,
        ):
            return

        if not _questionary.confirm(message="Are you sure?", auto_enter=True):
            return

    with console.status("[status.message] Matching project") as status:
        for project in projects:
            query_job = routine.select(
                resource=routine.timesheet_id,
                fields=["count(*) as count_entries"],
                where=f'project = "{project}"',
            )
            routine.delete_project(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=f"Deleting [code]{project}[/code] from projects",
            )
            routine.delete_time_entries(
                project,
                wait=True,
                render=True,
                status=status,
                status_renderable=f"Deleting [code]{project}[/code] time entries",
            )

            threads.spawn(ctx, appdata.update)
            count_deleted = _get.count_entries(first(query_job))
            console.print(
                "[saved]Saved[/saved]. "
                f"Deleted project [repr.str]{project}[/repr.str] and "
                f"[repr.number]{count_deleted}[/repr.number] "
                f"related time {'entry' if count_deleted == 1 else 'entries'}.",
            )

            if cache and cache.project == project:
                cache._clear_active()
                console.set_window_title(__appname_sc__)

            cache._remove_entries(
                entries=[cache.running_entries, cache.paused_entries],
                key="project",
                sequence=[project],
            )

            status.update("[status.message]")


@project.command(
    cls=_RichCommand,
    name="archive",
    help=_help.project_archive,
    no_args_is_help=True,
    short_help="Archive a project. Hide all related time entries.",
    context_settings=dict(
        obj=dict(syntax=_help.project_archive_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not archive project."),
)
@click.argument(
    "project",
    nargs=1,
    type=shell_complete.projects.ActiveProject,
    metavar="TEXT",
    required=True,
    callback=validate.active_project,
    shell_complete=shell_complete.projects.from_argument,
)
@_pass.confirm_options
@_pass.cache
@_pass.appdata
@_pass.routine
@_pass.console
@click.pass_context
def archive(
    ctx: click.Context,
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "EntryAppData",
    cache: "TomlCache",
    project: str,
    confirm: bool,
    yes: bool,
) -> None:
    matching_entries = cache._get_any_entries(
        cache.running_entries + cache.paused_entries,
        key="project",
        sequence=[project],
    )

    if matching_entries:
        console.print(
            "One or more of running/paused entries fall under this project.\n"
            "End these entries before trying to archive this project.\n"
            "Matching entries:"
        )
        render.new_console_print(render.mappings_list_to_rich_table(matching_entries))
        return

    if not (confirm or yes):
        if not _questionary.confirm(
            message="This will archive all time entries under this project. Continue?",
            auto_enter=True,
        ):
            return

    query_job = routine.select(
        resource=routine.timesheet_id,
        fields=["count(*) as count_entries"],
        where=f'project = "{project}"',
    )
    routine.archive_project(
        project,
        wait=True,
        render=True,
        status_renderable="Archiving project",
    )
    routine.archive_time_entries(
        project,
        wait=True,
        render=True,
        status_renderable="Archiving time entries",
    )

    threads.spawn(ctx, appdata.update)
    count_archived = _get.count_entries(first(query_job))
    console.print(
        "[saved]Saved[/saved].\n"
        "Archived project [repr.str]%s[/repr.str] and [repr.number]%s[/repr.number] related time %s.%s"
        % (
            project,
            count_archived,
            "entry" if count_archived == 1 else "entries",
            (
                "\nThese entries will not appear in results until you unarchive this project."
                if count_archived > 0
                else ""
            ),
        )
    )


@project.command(
    cls=_RichCommand,
    name="unarchive",
    help=_help.project_unarchive,
    no_args_is_help=True,
    short_help="Unarchive a project. Restore all hidden time entries.",
    context_settings=dict(
        obj=dict(syntax=_help.project_unarchive_syntax),
    ),
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint("[d]Did not unarchive project."),
)
@click.argument(
    "project",
    nargs=1,
    required=True,
    type=shell_complete.projects.ArchivedProject,
    metavar="TEXT",
    callback=validate.archived_project,
    shell_complete=shell_complete.projects.from_argument,
)
@_pass.appdata
@_pass.routine
@_pass.console
@click.pass_context
def unarchive(
    ctx: click.Context,
    console: "Console",
    routine: "CliQueryRoutines",
    appdata: "EntryAppData",
    project: str,
) -> None:
    query_job = routine.select(
        resource=routine.timesheet_id,
        fields=["count(*) as count_entries"],
        where=f'project = "{project}"',
    )
    routine.unarchive_project(
        project,
        wait=True,
        render=True,
        status_renderable="Unarchiving project",
    )
    routine.unarchive_time_entries(
        project,
        wait=True,
        render=True,
        status_renderable="Unarchiving time entries",
    )

    threads.spawn(ctx, appdata.update)
    count_unarchived = _get.count_entries(first(query_job))
    console.print(
        "[saved]Saved[/saved].\n"
        "Unarchived project [repr.str]%s[/repr.str] and [repr.number]%s[/repr.number] related time %s.%s"
        % (
            project,
            count_unarchived,
            "entry" if count_unarchived == 1 else "entries",
            (
                "\nThese entries will now appear in results again."
                if count_unarchived > 0
                else ""
            ),
        )
    )
