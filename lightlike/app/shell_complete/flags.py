from typing import TYPE_CHECKING, Any, Sequence

from click.shell_completion import CompletionItem

from lightlike.app.config import AppConfig
from lightlike.internal import utils

if TYPE_CHECKING:
    import rich_click as click

__all__: Sequence[str] = ("Param", "snapshot_table_name")


class Param:
    def __init__(
        self,
        param_name: str,
        completion_items: Sequence[Any] = [],
    ) -> None:
        self.param_name = param_name
        self.completion_items = completion_items

    def bool(
        self, ctx: "click.Context", param: "click.Parameter", incomplete: str
    ) -> Sequence[CompletionItem | None]:
        if ctx.params.get(self.param_name) is None or param.default is not None:
            return [
                CompletionItem(value=k, help=f"[{', '.join(v)}]")
                for k, v in {
                    "true": ("1", "true", "t", "yes", "y"),
                    "false": ("0", "false", "f", "no", "n"),
                }.items()
                if any(i.startswith(incomplete) for i in v)
            ]
        return []

    def string(
        self, ctx: "click.Context", param: "click.Parameter", incomplete: str
    ) -> Sequence[str | None]:
        if (
            ctx.params.get(self.param_name) is None
            or ctx.params.get(self.param_name) == param.default
        ):
            return [
                item
                for item in self.completion_items
                if utils._match_str(incomplete, item)
            ]

        return []


def snapshot_table_name(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[str]:
    ts = int(AppConfig().now.timestamp())
    default = f"timesheet_{ts}"

    if not incomplete and utils._match_str(incomplete, default, method="startswith"):
        return [default]
    else:
        return []
