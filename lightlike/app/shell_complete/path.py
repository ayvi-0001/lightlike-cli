import re
import typing as t
from contextlib import suppress
from pathlib import Path

import click
from click.shell_completion import CompletionItem
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText

from lightlike.internal.enums import ActiveCompleter
from lightlike.internal.utils import _alter_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: t.Sequence[str] = ("path", "PathCompleter")


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


def _path_str_contents(path: Path) -> FormattedText:
    contents = []
    if path.is_dir():
        with suppress(*_E):
            for sub in path.iterdir():
                contents.extend(
                    [
                        ("ansibrightcyan", sub.name),
                        ("bold #000000", " | "),
                    ]
                )

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
    for path in _yield_paths(_alter_str(incomplete, strip_quotes=True), dir_only):
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

            for path in _yield_paths(_alter_str(word_before_cursor, strip_quotes=True)):
                value = path.expanduser().as_posix()
                if " " in value:
                    value = value.replace(" ", r"\ ")

                yield Completion(
                    text=value,
                    start_position=start_position,
                    display_meta=_path_str_contents(path),
                    style="ansibrightcyan",
                )
        except:
            yield from []
