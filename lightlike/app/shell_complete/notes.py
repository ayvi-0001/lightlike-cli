import typing as t
from pathlib import Path

import click
import rtoml
from click.shell_completion import CompletionItem
from more_itertools import first
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, Completion

from lightlike.app.cache import TimeEntryCache
from lightlike.internal import appdir
from lightlike.internal.utils import alter_str, match_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: t.Sequence[str] = (
    "Notes",
    "from_param",
    "from_cache",
    "from_chained_cmd",
)


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
        notes = {}
        for project in active_projects.keys():
            notes[project] = active_projects[project]["notes"]
        return notes

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterator[Completion]:
        if self.project:
            matches = filter(
                lambda o: match_str(document.text, o),
                self.get(self.project),
            )
            completions = [
                Completion(text=match, start_position=-len(document.text_before_cursor))
                for match in matches
            ]
            yield from completions


def from_param(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completer = Notes()
    completions: list[CompletionItem] = []

    if projects := ctx.params.get("projects"):
        for project in projects:
            notes = filter(
                lambda n: match_str(incomplete, n, strip_quotes=True),
                completer.get(project),
            )
            completions.extend(
                [
                    CompletionItem(
                        value=alter_str(note, add_quotes=True),
                        help=f"project: {project}",
                    )
                    for note in notes
                ]
            )
    elif project := ctx.params.get("project"):
        notes = filter(
            lambda n: match_str(incomplete, n, strip_quotes=True),
            completer.get(project),
        )
        completions.extend(
            [
                CompletionItem(
                    value=alter_str(note, add_quotes=True),
                    help=f"project: {project}",
                )
                for note in notes
            ]
        )
    elif any([option in ctx.protected_args for option in ("-p", "--project")]):
        opt_idx = 0
        for idx, opt in enumerate(ctx.protected_args):
            if opt in ("-p", "--project"):
                opt_idx = idx

        project = ctx.protected_args[opt_idx + 1]
        notes = filter(
            lambda n: match_str(incomplete, n, strip_quotes=True),
            completer.get(project),
        )
        completions.extend(
            [
                CompletionItem(
                    value=alter_str(note, add_quotes=True),
                    help=f"project: {project}",
                )
                for note in notes
            ]
        )

    if not completions:
        if "-p" not in get_app().current_buffer.document.text:
            return from_cache(ctx, param, incomplete)
    return completions


def from_cache(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    completer = Notes()
    completions: list[CompletionItem] = []

    if cache := TimeEntryCache():
        notes = completer.get(cache.project)
        if notes:
            completions.extend(
                [
                    CompletionItem(
                        value=alter_str(note, add_quotes=True),
                        help=f"project: {cache.project}",
                    )
                    for note in filter(
                        lambda n: match_str(incomplete, n, strip_quotes=True),
                        notes,
                    )
                ]
            )

    return completions


def from_chained_cmd(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    document = get_app().current_buffer.document
    completions = []
    project_location = first(document.find_all("project"), default=None)

    if project_location and (
        project := first(document.text[project_location:].split(" "))
    ):
        notes = filter(
            lambda n: match_str(incomplete, n, strip_quotes=True),
            Notes().get(project),
        )
        completions.extend(
            [
                CompletionItem(
                    value=alter_str(note, add_quotes=True),
                    help=f"project: {project}",
                )
                for note in notes
            ]
        )

    return completions
