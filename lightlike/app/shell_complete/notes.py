import typing as t
from pathlib import Path

import click
import rtoml
from click.shell_completion import CompletionItem
from fuzzyfinder import fuzzyfinder
from more_itertools import first
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, Completion

from lightlike.app.cache import TimeEntryCache
from lightlike.internal import appdir
from lightlike.internal.utils import alter_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: t.Sequence[str] = ("from_cache", "from_chained_cmd", "from_param", "Notes")


class Notes(Completer):
    path: Path = appdir.ENTRY_APPDATA

    def __init__(self, project: str | None = None) -> None:
        self.project = project

    def get(self, project: str | None = None) -> list[str]:
        notes = []
        active_projects = self.data["active"]
        project_notes = active_projects.get(project or self.project)
        if project_notes and "notes" in project_notes:
            notes = project_notes.get("notes", [])
        return notes

    @property
    def data(self) -> dict[str, t.Any]:
        return rtoml.load(self.path)

    def get_all(self) -> dict[str, list[str]]:
        active_projects = self.data["active"]
        notes = {
            project: active_projects[project]["notes"]
            for project in active_projects.keys()
        }
        return notes

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterator[Completion]:
        completions: list[Completion] = []

        if not self.project:
            yield from completions

        start_position: int = -len(document.text_before_cursor)

        for match in fuzzyfinder(document.text, self.get(self.project)):
            completions.append(Completion(text=match, start_position=start_position))

        yield from completions


def from_param(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completer = Notes()
    completions: list[CompletionItem] = []

    target_project: str | None = None

    if project := first(ctx.params.get("projects", []), default=None):
        target_project = project
    elif project := ctx.params.get("project"):
        target_project = project
    elif any([option in ctx.protected_args for option in ("-p", "--project")]):
        opt_idx = 0
        for idx, opt in enumerate(ctx.protected_args):
            if opt in ("-p", "--project"):
                opt_idx = idx
        target_project = ctx.protected_args[opt_idx + 1]

    if target_project:
        for note in fuzzyfinder(incomplete, completer.get(target_project)):
            completions.append(
                CompletionItem(
                    value=alter_str(note, add_quotes=True),
                    help=f"project: {project}",
                )
            )

    if not completions:
        buffer: str = get_app().current_buffer.document.text
        if "-p" not in buffer:
            return from_cache(ctx, param, incomplete)

    return completions


def from_cache(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completions: list[CompletionItem] = []

    cache = TimeEntryCache()
    if not cache:
        return completions

    completer = Notes()
    notes: list[str] = completer.get(cache.project)
    if not notes:
        return completions

    for note in fuzzyfinder(incomplete, notes):
        completions.append(
            CompletionItem(
                value=alter_str(note, add_quotes=True),
                help=f"project: {cache.project}",
            )
        )

    return completions


def from_chained_cmd(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    document: "Document" = get_app().current_buffer.document
    completions: list[CompletionItem] = []
    project_location: int | None = first(document.find_all("project"), default=None)
    project: str | None = first(
        document.text[project_location:].split(" "), default=None
    )

    if not (project_location and project):
        return completions

    for note in fuzzyfinder(incomplete, Notes().get(project)):
        completions.append(
            CompletionItem(
                value=alter_str(note, add_quotes=True),
                help=f"project: {project}",
            )
        )

    return completions
