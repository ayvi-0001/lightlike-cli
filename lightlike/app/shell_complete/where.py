import re
import typing as t

from prompt_toolkit.completion import (
    Completion,
    ThreadedCompleter,
    WordCompleter,
    merge_completers,
)
from prompt_toolkit.document import Document

from lightlike.app import shell_complete
from lightlike.app.client import get_client
from lightlike.internal import utils

if t.TYPE_CHECKING:
    from google.cloud.bigquery import Client
    from prompt_toolkit.completion import CompleteEvent
    from rich.console import Console

    from lightlike.app.routines import CliQueryRoutines

__all__: t.Sequence[str] = ("completer", "_bottom_toolbar", "_parse_click_options")


def completer(schema: str, table: str) -> ThreadedCompleter:
    from lightlike.cmd.query.completers import LoopNestedCompleter
    from lightlike.cmd.query.words import KEYWORD_META, SQL_KEYWORDS

    completers = [
        WhereClauseCompleter(schema=schema, table=table),
        LoopNestedCompleter.from_nested_dict(SQL_KEYWORDS, KEYWORD_META),
    ]

    return ThreadedCompleter(merge_completers(completers, deduplicate=True))


class WhereClauseCompleter(WordCompleter):
    __slots__ = ()
    client: t.Callable[..., "Client"] = get_client
    fields: list[str] = [
        "id",
        "date",
        "project",
        "note",
        "timestamp_start",
        "start",
        "timestamp_end",
        "end",
        "active",
        "billable",
        "archived",
        "paused",
        "timestamp_paused",
        "paused_counter",
        "paused_hours",
        "hours",
    ]

    def __init__(self, schema: str, table: str) -> None:
        super().__init__([], WORD=True)
        self.resource_id = f"{self.client().project}.{schema}.{table}"
        self.projects = shell_complete.projects.Active().names
        self.notes = shell_complete.notes.Notes().get_all()

    def get_completions(
        self, document: Document, complete_event: "CompleteEvent"
    ) -> t.Iterable[Completion]:
        word_before_cursor: str = utils._alter_str(
            document.get_word_before_cursor(self.WORD),
            strip_parenthesis=True,
            strip_quotes=True,
        )

        if "project" in document.text:
            yield from self._project_items(document, word_before_cursor)

        for field in self.fields:
            if field.startswith(word_before_cursor):
                yield Completion(
                    text=field,
                    start_position=-len(word_before_cursor),
                    display_meta=f"FIELD:{self.resource_id}",
                    selected_style="reverse",
                )

    def _project_items(
        self, document: "Document", word_before_cursor: str
    ) -> t.Iterable[Completion]:
        for project in self.projects:
            if utils._match_str(
                word_before_cursor,
                project,
                case_sensitive=False,
                strip_parenthesis=True,
                strip_quotes=True,
            ):
                yield Completion(
                    text=f"{project}",
                    start_position=-len(word_before_cursor),
                    display_meta=f"PROJECT:{project}",
                    style="#239551",
                    selected_style="reverse",
                )

            if "note" in document.text and project in document.text:
                yield from self._note_items(project, word_before_cursor)

    def _note_items(
        self, project: str, word_before_cursor: str
    ) -> t.Iterable[Completion]:
        for note in self.notes[project]:
            if note.startswith(word_before_cursor):
                yield Completion(
                    text=f"{note}",
                    display=f"{note[:45]}…" if len(note) > 45 else f"{note}",
                    start_position=-len(word_before_cursor),
                    display_meta=f"NOTE:{project}",
                    style="#239551",
                    selected_style="reverse",
                )


def _bottom_toolbar(console: "Console") -> t.Callable[..., list[tuple[str, str]]]:
    bt_line1 = (
        "Press esc + enter to submit. Press up for history. Press ctrl + Q to exit."
    )
    bt_line2 = (
        "If project field appears in document, "
        "project values from timesheets will add to autocomplete."
    )
    bt_line3 = (
        "If a project field value, and the note field appear in document, "
        "note values from timesheets for that project will add to autocomplete."
    )

    text = [
        ("#000000", f"{' ' * (console.width - 2)}|\n"),
        ("#000000", f"{' ' * (console.width - 2)}|\n"),
        ("", f"{bt_line1}{' ' * (console.width - len(bt_line1) - 2)}|\n"),
        ("", f"{bt_line2}{' ' * (console.width - len(bt_line2) - 2)}|\n"),
        ("", f"{bt_line3}{' ' * (console.width - len(bt_line3) - 2)}|"),
    ]

    return lambda: text


WHERE_CLAUSE: t.Final[re.Pattern[str]] = re.compile(
    r"^(?:'|\"|)(?:.?where\s+|)(.*)(?:'|\"|)$", re.IGNORECASE
)


def _parse_click_options(
    flag: bool,
    args: t.Sequence[str] | None,
    console: "Console",
    routine: "CliQueryRoutines",
) -> str:
    if not args:
        if flag:
            from lightlike.cmd.query import _build_query_session

            session = _build_query_session(
                completer=shell_complete.where.completer(
                    routine.dataset, routine.table_timesheet
                ),
            )
            where_clause = session.prompt(
                default="WHERE ",
                pre_run=utils._prerun_autocomplete,
                bottom_toolbar=shell_complete.where._bottom_toolbar(console),
            )
        else:
            where_clause = ""
    else:
        where_clause = " ".join(args)

    if where_clause:
        capture_groups = WHERE_CLAUSE.match(where_clause)
        if capture_groups:
            where_clause = capture_groups.group(1)
        else:
            where_clause = ""

    return t.cast(str, where_clause)
