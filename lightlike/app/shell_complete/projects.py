import typing as t
from pathlib import Path

import click
import rtoml
from click.shell_completion import CompletionItem
from fuzzyfinder import fuzzyfinder
from prompt_toolkit.completion import Completer, Completion

from lightlike.internal import appdir
from lightlike.internal.utils import match_str, print_message_and_clear_buffer

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: t.Sequence[str] = (
    "Active",
    "Archived",
    "from_argument",
    "from_option",
    "from_chained_cmd",
    "ActiveProject",
    "ArchivedProject",
    "AnyProject",
)


ActiveProject = t.NewType("ActiveProject", str)
ArchivedProject = t.NewType("ArchivedProject", str)
AnyProject = t.NewType("AnyProject", str)


class Projects(Completer):
    path: Path = appdir.ENTRY_APPDATA

    def __init__(self, list_: t.Literal["active", "archived"] | str = "") -> None:
        self.list_ = list_.lower()

    @property
    def names(self) -> list[str]:
        return sorted(list(self.projects.keys()))

    @property
    def projects(self) -> dict[str, t.Any]:
        return t.cast(dict[str, t.Any], self.data.get(self.list_, {}))

    @property
    def data(self) -> dict[str, t.Any]:
        return rtoml.load(self.path)

    @property
    def completion_items(self) -> list[CompletionItem]:
        completion_items: list[CompletionItem] = []
        for project in self.projects.values():
            completion_items.append(
                CompletionItem(
                    value=project.get("name"),
                    help=project.get("meta"),
                    created=project.get("created"),
                )
            )
        return completion_items

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterator[Completion]:

        matches: list[str] = fuzzyfinder(
            document.text,
            self.names,
            sort_results=False,
        )
        for match in matches:
            yield Completion(
                text=match,
                start_position=-len(document.text_before_cursor),
                display=match,
                display_meta=self.projects[match].get("meta"),
            )


class Active(Projects):
    def __init__(self) -> None:
        super().__init__(list_="active")


class Archived(Projects):
    def __init__(self) -> None:
        super().__init__(list_="archived")


def _matches_name_or_help(incomplete: str, item: CompletionItem) -> bool:
    match_value = match_str(incomplete, item.value, strip_quotes=True)
    match_help = match_str(incomplete, item.help, strip_quotes=True)
    return match_value or match_help


def _item_not_in_parent_args(
    item: CompletionItem,
    ctx: click.Context,
    param: click.Parameter,
    exclude_default: bool = False,
) -> bool:
    assert ctx.parent
    exclude = ctx.parent.args
    if exclude_default:
        exclude += ["no-project"] if param.type.name != "AnyProject" else []
    return item.value not in exclude


def _sorted_by_created(completions: list[CompletionItem]) -> list[CompletionItem]:
    return sorted(
        completions,
        key=lambda c: getattr(c, "created"),
        reverse=True,
    )


def from_argument(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    assert isinstance(param, click.Argument)
    assert ctx.parent

    completions: list[CompletionItem] = []

    if param.type.name == "ActiveProject":
        completer: Projects = Projects(list_="ACTIVE")
        completion_items = completer.completion_items
    elif param.type.name == "ArchivedProject":
        completer = Projects(list_="ARCHIVED")
        completion_items = completer.completion_items
    else:
        completion_items = (
            Projects(list_="ACTIVE").completion_items
            + Projects(list_="ARCHIVED").completion_items
        )

    if not completion_items:
        print_message_and_clear_buffer(
            f"{completer.list_} projects list is empty.",
        )
        return completions

    if param.nargs == -1:
        for item in completion_items:
            if not _matches_name_or_help(incomplete, item):
                continue
            if _item_not_in_parent_args(item, ctx, param, True):
                completions.append(item)
        return _sorted_by_created(completions)

    elif not ctx.params.get("project") and not ctx.params.get("projects"):
        for item in completion_items:
            if not _matches_name_or_help(incomplete, item):
                continue
            if _item_not_in_parent_args(item, ctx, param, True):
                completions.append(item)

        return _sorted_by_created(completions)

    return completions


def from_option(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    assert isinstance(param, click.Option)

    completions: list[CompletionItem] = []

    if param.type.name == "ActiveProject":
        completer: Projects = Projects(list_="ACTIVE")
        completion_items = Projects(list_="ACTIVE").completion_items
    elif param.type.name == "ArchivedProject":
        completer = Projects(list_="ARCHIVED")
        completion_items = Projects(list_="ARCHIVED").completion_items
    else:
        completion_items = (
            Projects(list_="ACTIVE").completion_items
            + Projects(list_="ARCHIVED").completion_items
        )

    if not completion_items:
        print_message_and_clear_buffer(
            f"{completer.list_} projects list is empty.",
        )
        return []

    for item in completion_items:
        if not _matches_name_or_help(incomplete, item):
            continue
        if _item_not_in_parent_args(item, ctx, param, True):
            completions.append(item)

    return _sorted_by_created(completions)


def from_chained_cmd(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    completions: list[CompletionItem] = []

    for item in Active().completion_items:
        if not _matches_name_or_help(incomplete, item):
            continue
        if _item_not_in_parent_args(item, ctx, param, True):
            completions.append(item)

    return _sorted_by_created(completions)
