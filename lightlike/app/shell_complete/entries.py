import typing as t
from datetime import datetime

import click
from click.shell_completion import CompletionItem

from lightlike.app import dates
from lightlike.app.cache import TimeEntryCache
from lightlike.app.config import AppConfig
from lightlike.internal.utils import match_str

__all__: t.Sequence[str] = ("paused", "all_")


def paused(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    now: datetime = dates.now(AppConfig().tzinfo)
    cache = TimeEntryCache()
    completions: list[CompletionItem] = []

    if ctx.params.get(param.name or ""):
        return completions

    if cache.paused_entries:
        paused_entries = cache.get_updated_paused_entries(now)
        for entry in paused_entries:
            entry_id: str = entry["id"]
            meta: str = cache._to_help_str(entry, now)

            if _match_id_or_meta(incomplete, meta, entry_id):
                completions.append(CompletionItem(value=entry_id[:7], help=meta))

    return completions


def all_(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    now: datetime = dates.now(AppConfig().tzinfo)
    cache = TimeEntryCache()
    completions: list[CompletionItem] = []

    if param.name and ctx.params.get(param.name):
        return completions

    if cache.paused_entries:
        paused_entries = cache.get_updated_paused_entries(now)
        for entry in paused_entries:
            entry_id: str = entry["id"]
            meta: str = cache._to_help_str(entry, now)

            if _match_id_or_meta(incomplete, meta, entry_id):
                completions.append(CompletionItem(value=entry_id[:7], help=meta))
    if cache.running_entries:
        for entry in cache.running_entries:
            entry_id = entry["id"]

            if entry_id in (cache.id, "null"):
                continue

            meta = cache._to_help_str(entry, now)

            if _match_id_or_meta(incomplete, meta, entry_id):
                completions.append(CompletionItem(value=entry_id[:7], help=meta))

    return completions


def _match_id_or_meta(incomplete: str, meta: str, entry_id: str) -> bool:
    if match_str(incomplete, meta) or match_str(incomplete, entry_id):
        return True
    return False
