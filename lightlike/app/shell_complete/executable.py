import os
import re
import shutil
import stat
import typing as t
from functools import cached_property, partial
from pathlib import Path

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText

from lightlike.app.config import AppConfig
from lightlike.internal.utils import _match_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document


__all__: t.Sequence[str] = ("ExecutableCompleter",)


class ExecutableCompleter(Completer):
    style: str = "#aad565"
    ignore_patterns: list[str] = AppConfig().get(
        "completers",
        "exec",
        "ignore_patterns",
        default=[],
    )

    @cached_property
    def path(self) -> list[Path]:
        return list(map(lambda p: Path(p), os.environ["PATH"].split(os.pathsep)))

    @cached_property
    def executables(self) -> list[Path]:
        executables: list[Path] = []

        for path in self.path:
            try:
                if self.ignore_patterns:
                    expressions: list[re.Pattern[str]] = list(
                        map(partial(re.compile, flags=re.I), self.ignore_patterns)  # type: ignore[arg-type]
                    )
                    matches: t.Callable[[Path], bool] = lambda p: not any(
                        exp.match(p.as_posix()) for exp in expressions
                    )
                    subpaths = list(filter(matches, path.iterdir()))
                else:
                    subpaths = list(path.iterdir())

                for executable in subpaths:
                    resolved = executable.resolve()

                    if os.access(resolved, os.X_OK):
                        if executable not in executables:
                            executables.append(executable)
                        continue
                    if shutil.which(resolved):
                        if executable not in executables:
                            executables.append(executable)
                        continue
                    if executable.stat().st_mode & stat.S_IXUSR:
                        if executable not in executables:
                            executables.append(executable)
                        continue
            except:
                continue
        return executables

    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> t.Iterator[Completion]:
        try:
            start_position = -len(document.text_before_cursor)

            match_word_before_cursor = lambda l: _match_str(
                document.get_word_before_cursor(WORD=True), l.name
            )
            matches = list(filter(match_word_before_cursor, self.executables))

            for path in sorted(matches, key=lambda p: p.name):
                resolved = path.resolve()
                text: str = resolved.name.removesuffix(".exe")
                drive = f"/{resolved.drive.lower().replace(':', '')}"
                display_meta = f"{resolved}".replace(resolved.drive, drive)
                display_meta = display_meta.replace("\\", "/")

                yield Completion(
                    text=text,
                    start_position=start_position,
                    display_meta=FormattedText([(self.style, display_meta)]),
                    style=self.style,
                )
        except:
            yield from []