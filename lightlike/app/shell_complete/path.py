import os
import re
import typing as t
from contextlib import suppress
from pathlib import Path

import click
from click.shell_completion import CompletionItem
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText
from rich import get_console

from lightlike.app import dates
from lightlike.app.config import AppConfig
from lightlike.internal.enums import ActiveCompleter
from lightlike.internal.utils import alter_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from prompt_toolkit.mouse_events import MouseEvent

    NotImplementedOrNone = object

__all__: t.Sequence[str] = (
    "path",
    "PathCompleter",
    "snapshot",
)


OneStyleAndTextTuple = t.Union[
    tuple[str, str], tuple[str, str, t.Callable[["MouseEvent"], "NotImplementedOrNone"]]
]

StyleAndTextTuples = list[OneStyleAndTextTuple]

TYPED_DIR = re.compile(r"^(.*)(?:\\|\/)", flags=re.IGNORECASE)
TYPED_STEM = re.compile(r"^.*(?:\\|\/)+(.*)$", flags=re.IGNORECASE)

_E = (PermissionError, NotADirectoryError, FileNotFoundError)


def _match_stem(incomplete: str) -> t.Callable[[Path], bool]:
    return lambda p: p.stem.lower().startswith(incomplete.lower())


def _typed_dir_and_stem(
    typed_dir: re.Match[str] | None,
    typed_stem: re.Match[str] | None,
    iterator: t.Callable[..., t.Iterable[Path]],
) -> t.Iterator[Path]:
    if typed_dir and typed_stem:
        target_dir = Path(typed_dir.group(0)).expanduser()
        if target_dir.exists():
            with suppress(*_E):
                target_stem = typed_stem.group(1).lower()
                yield from filter(_match_stem(target_stem), iterator(target_dir))


def _stem_in_current_dir(
    incomplete: str, iterator: t.Callable[..., t.Iterable[Path]]
) -> t.Iterator[Path]:
    yield from filter(_match_stem(incomplete), iterator(Path(".")))


def _paths_from_incomplete(
    incomplete: str, iterator: t.Callable[..., t.Iterable[Path]]
) -> t.Iterator[Path]:
    typed_dir = TYPED_DIR.match(incomplete)
    typed_stem = TYPED_STEM.match(incomplete)
    typed_path = Path(incomplete)

    if not incomplete:
        with suppress(*_E):
            yield from iterator(Path("."))
    elif typed_path.exists():
        if typed_path.is_dir():
            yield from _typed_dir_and_stem(typed_dir, typed_stem, iterator)
    elif typed_dir and typed_stem:
        yield from _typed_dir_and_stem(typed_dir, typed_stem, iterator)
    elif typed_dir:
        target_dir = Path(typed_dir.group(0))
        if target_dir.exists():
            yield from iterator(target_dir)
    else:
        yield from _stem_in_current_dir(incomplete, iterator)


def _yield_paths(incomplete: str, dir_only: bool = False) -> t.Iterator[Path]:
    if not dir_only:
        yield from _paths_from_incomplete(incomplete, lambda p: p.iterdir())
    else:
        yield from _paths_from_incomplete(
            incomplete, lambda p: filter(lambda p: p.is_dir(), p.iterdir())
        )


def _is_link(path: Path) -> bool:
    return path.absolute() != path.resolve()


def _path_str_contents(path: Path) -> FormattedText:
    contents: StyleAndTextTuples = []

    with suppress(*_E):
        if _is_link(path):
            resolved: Path = path.resolve()
            if os.name == "nt":
                drive = f"/{resolved.drive.lower().replace(':', '')}"
                full_path = resolved.as_posix().replace(resolved.drive, drive)
            else:
                full_path = f"{resolved}"

            contents.extend([("#81beb1", f"{path.name} -> {full_path}")])

        if path.is_dir():
            for sub in path.iterdir():
                contents.extend([("#7f9fcf", sub.name), ("bold #000000", " | ")])

    return FormattedText(contents)


def path(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem] | None:
    completions: list[CompletionItem] = []
    if not ctx.resilient_parsing:
        return None

    from lightlike.app.shell_complete.dynamic import global_completers

    # Don't show path completions again if they're already included in
    # the global completer
    if ActiveCompleter.PATH in global_completers():
        return completions

    if isinstance(ctx.obj, dict):
        dir_only = ctx.obj.get("dir_only", False)
    else:
        dir_only = False
    for path in _yield_paths(alter_str(incomplete, strip_quotes=True), dir_only):
        value = path.expanduser().as_posix()
        if " " in value:
            value = f'"{value}'

        completions.append(
            CompletionItem(
                value=value,
                help=t.cast(str, _path_str_contents(path)),
            )
        )

    return completions


class PathCompleter(Completer):
    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterable[Completion]:
        console = get_console()
        console_width = console.width

        try:
            if "\\" in document.text:
                count = len(document.find_all("\\")) + 1
                start_pos = document.find_previous_word_beginning(count, WORD=True)
                current_path = document.text[start_pos:]
                word_before_cursor = '"%s"' % current_path.replace("\\ ", " ")
                start_position = -len(word_before_cursor) + 1
            else:
                word_before_cursor = document.get_word_before_cursor(WORD=True)
                start_position = -len(word_before_cursor)

            if not document.text:
                yield from []

            for path in _yield_paths(alter_str(word_before_cursor, strip_quotes=True)):
                value = path.expanduser().as_posix()
                if " " in value:
                    value = value.replace(" ", r"\ ")

                yield Completion(
                    text=value,
                    start_position=start_position,
                    display=self._display(value, console_width),
                    display_meta=_path_str_contents(path),
                    style="cyan",
                )
        except:
            yield from []

    def _display(self, text: str, console_width: int) -> str:
        half_console_width = int(console_width / 3)
        if len(text) > half_console_width:
            return f"{text[:half_console_width]}…"
        else:
            return text


def snapshot(
    prefix: str, suffix: str = ""
) -> t.Callable[..., t.Sequence[CompletionItem]]:
    completion_items: list[CompletionItem] = []
    date_format: str = "%Y-%m-%dT%H_%M_%S"
    timestamp: str = dates.now(AppConfig().tzinfo).strftime(date_format)
    name = f"{prefix}_{timestamp}{suffix}"
    completion_items.append(CompletionItem(value=name))

    def inner(
        ctx: click.Context,
        param: click.Parameter,
        incomplete: str,
    ) -> t.Sequence[CompletionItem]:
        nonlocal completion_items
        matches: list[CompletionItem] = []

        for item in completion_items:
            if item.value.startswith(incomplete):
                matches.append(item)
        return matches

    return inner
