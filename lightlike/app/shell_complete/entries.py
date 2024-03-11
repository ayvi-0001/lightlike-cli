from typing import TYPE_CHECKING, Sequence

from click.shell_completion import CompletionItem

from lightlike.app.cache import EntryIdList, TomlCache
from lightlike.app.config import AppConfig
from lightlike.internal.utils import _match_str

if TYPE_CHECKING:
    import rich_click as click

__all__: Sequence[str] = ("paused", "all_ids")


def paused(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    cache = TomlCache()
    completions = []
    now = AppConfig().now

    if cache.paused_entries:
        paused_entries = cache.get_updated_paused_entries(now)
        for entry in paused_entries:
            help = cache._to_meta(entry, now, truncate_note=True)
            if _match_str(incomplete, help) or _match_str(incomplete, entry["id"]):
                completions.append(CompletionItem(value=entry["id"][:7], help=help))

        return completions

    return []


def all_ids(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    return [
        CompletionItem(value=_id)
        for _id in EntryIdList().ids
        if _match_str(incomplete, _id)
    ]
