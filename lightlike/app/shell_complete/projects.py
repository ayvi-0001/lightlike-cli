from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Literal, NewType, Sequence

import rtoml
from click.shell_completion import CompletionItem
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.patch_stdout import patch_stdout
from rich import print as rprint

from lightlike.internal import appdir
from lightlike.internal.utils import _match_str

if TYPE_CHECKING:
    import rich_click as click
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: Sequence[str] = (
    "Active",
    "Archived",
    "from_argument",
    "from_option",
    "from_chained_cmd",
    "ActiveProject",
    "ArchivedProject",
)


ActiveProject = NewType("ActiveProject", str)
ArchivedProject = NewType("ArchivedProject", str)


class Projects(Completer):
    path: ClassVar[Path] = appdir.ENTRY_APPDATA

    def __init__(self, list_: Literal["active", "archived"] | str = "") -> None:
        self.list_ = list_.lower()

    @property
    def names(self) -> list[str]:
        return sorted(list(self.projects.keys()))

    @property
    def projects(self) -> dict[str, Any]:
        return rtoml.load(self.path).get(self.list_, {})

    @property
    def completion_items(self) -> list[CompletionItem]:
        project_list = self.projects

        return [
            CompletionItem(
                value=project_list[project].get("name"),
                help=project_list[project].get("meta"),
            )
            for project in project_list
        ]

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> Iterator[Completion]:
        matches = list(
            filter(
                lambda n: _match_str(document.text, n, case_sensitive=True),
                self.names,
            )
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


def from_argument(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem] | None:
    assert param.param_type_name == "argument"
    assert param.metavar
    assert ctx.parent

    project_type = "ACTIVE" if "ACTIVE" in param.metavar else "ARCHIVED"
    completer = Projects(list_=project_type)
    completion_items = completer.completion_items

    if not completer.completion_items:
        _clear_and_return(f"{completer.list_} projects list is empty")
        return []

    if param.nargs == -1:
        return sorted(
            [
                item
                for item in completion_items
                if _match_str(incomplete, item.value)
                and item.value not in ctx.parent.args + ["no-project"]
            ],
            key=lambda c: getattr(c, "value"),
        )

    elif not ctx.parent.args:
        return sorted(
            [
                item
                for item in completion_items
                if _match_str(incomplete, item.value)
                and item.value not in ctx.parent.args + ["no-project"]
            ],
            key=lambda c: getattr(c, "value"),
        )

    return []


def from_option(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem] | None:
    assert param.param_type_name == "option"

    if param.type.name == "ActiveProject":
        project_type = "ACTIVE"
    else:
        project_type = "ARCHIVED"

    completer = Projects(list_=project_type)

    if not completer.completion_items:
        _clear_and_return(f"{completer.list_} projects list is empty")
        return []

    items = list(
        filter(
            lambda c: _match_str(incomplete, c.value),
            completer.completion_items,
        )
    )

    return sorted(items, key=lambda c: getattr(c, "value", ""))


def from_chained_cmd(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    parent = ctx.parent
    assert parent is not None
    get_project_param = lambda c: (
        _match_str(incomplete, c.value) and c.value not in parent.args
    )
    projects = filter(get_project_param, Active().completion_items)

    return sorted(list(projects), key=lambda c: getattr(c, "value"))


def _clear_and_return(message: str) -> None:
    with patch_stdout(raw=True):
        rprint(f"[d]{message}.\n")
        get_app().current_buffer.text = ""
