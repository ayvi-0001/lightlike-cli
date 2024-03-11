from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Iterator, Sequence

import rtoml
from click.shell_completion import CompletionItem
from more_itertools import first, nth
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, Completion

from lightlike.app.cache import TomlCache
from lightlike.internal import appdir
from lightlike.internal.utils import _alter_str, _match_str

if TYPE_CHECKING:
    import rich_click as click
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: Sequence[str] = ("Notes", "from_param", "from_cache", "from_chained_cmd")


class Notes(Completer):
    path: ClassVar[Path] = appdir.ENTRY_APPDATA

    def __init__(self, project: str | None = None) -> None:
        self.project = project

    def get(self, project: str | None = None) -> list[str]:
        notes = []
        active_projects = rtoml.load(self.path)["active"]
        project_notes = active_projects.get(project or self.project)
        if project_notes and "notes" in project_notes:
            notes = project_notes.get("notes", [])
        return notes

    def get_all(self) -> dict[str, list[str]]:
        active_projects = rtoml.load(self.path)["active"]
        notes = {}
        for project in active_projects.keys():
            notes[project] = active_projects[project]["notes"]
        return notes

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> Iterator[Completion]:
        if self.project:
            matches = filter(
                lambda o: _match_str(document.text, o),
                self.get(self.project),
            )
            completions = [
                Completion(text=match, start_position=-len(document.text_before_cursor))
                for match in matches
            ]
            yield from completions


def from_param(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    completer = Notes()
    completions: list[CompletionItem] = []

    if projects := ctx.params.get("projects"):
        for project in projects:
            notes = filter(
                lambda n: _match_str(incomplete, n, strip_quotes=True),
                completer.get(project),
            )
            completions.extend(
                [
                    CompletionItem(
                        value=_alter_str(note, add_quotes=True),
                        help=f"project: {project}",
                    )
                    for note in notes
                ]
            )
    elif project := ctx.params.get("project"):
        notes = filter(
            lambda n: _match_str(incomplete, n, strip_quotes=True),
            completer.get(project),
        )
        completions.extend(
            [
                CompletionItem(
                    value=_alter_str(note, add_quotes=True),
                    help=f"project: {project}",
                )
                for note in notes
            ]
        )
    return completions


def from_cache(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    completer = Notes()
    completions: list[CompletionItem] = []

    if cache := TomlCache():
        notes = completer.get(cache.project)
        if notes:
            completions.extend(
                [
                    CompletionItem(
                        value=_alter_str(note, add_quotes=True),
                        help=f"project: {cache.project}",
                    )
                    for note in filter(
                        lambda n: _match_str(incomplete, n, strip_quotes=True),
                        notes,
                    )
                ]
            )

    return completions


def from_chained_cmd(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    document = get_app().current_buffer.document
    completions = []
    project_location = first(document.find_all("project"), default=None)

    if project_location and (
        project := nth(document.text[project_location:].split(" "), 1)
    ):
        notes = filter(
            lambda n: _match_str(incomplete, n, strip_quotes=True),
            Notes().get(project),
        )
        completions.extend(
            [
                CompletionItem(
                    value=_alter_str(note, add_quotes=True),
                    help=f"project: {project}",
                )
                for note in notes
            ]
        )

    return completions
