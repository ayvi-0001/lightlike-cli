import typing as t

import click
from click.shell_completion import CompletionItem

from lightlike.app import dates
from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.internal.utils import match_str

if t.TYPE_CHECKING:
    from datetime import datetime


__all__: t.Sequence[str] = ("paused", "all_")


def paused(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    now: "datetime" = dates.now(AppConfig().tzinfo)
    cache = TimeEntryCache()
    completions = []

    if not ctx.params.get(param.name or ""):
        if cache.paused_entries:
            paused_entries = cache.get_updated_paused_entries(now)
            for entry in paused_entries:
                help = cache._to_meta(entry, now)
                if match_str(incomplete, help) or match_str(incomplete, entry["id"]):
                    completions.append(CompletionItem(value=entry["id"], help=help))

    return completions


def all_(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    now: "datetime" = dates.now(AppConfig().tzinfo)
    cache = TimeEntryCache()
    completions = []

    if not ctx.params.get(param.name or ""):
        if cache.paused_entries:
            paused_entries = cache.get_updated_paused_entries(now)
            for entry in paused_entries:
                help = cache._to_meta(entry, now)
                if match_str(incomplete, help) or match_str(incomplete, entry["id"]):
                    completions.append(CompletionItem(value=entry["id"], help=help))

        if cache.running_entries:
            for entry in cache.running_entries:
                if entry["id"] in (cache.id, "null"):
                    continue
                help = cache._to_meta(entry, now)
                if match_str(incomplete, help) or match_str(incomplete, entry["id"]):
                    completions.append(CompletionItem(value=entry["id"], help=help))

    return completions
