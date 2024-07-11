from __future__ import annotations

import typing as t
from contextlib import suppress
from functools import cached_property
from os import getenv

from prompt_toolkit.completion import (
    Completer,
    Completion,
    ThreadedCompleter,
    merge_completers,
)
from prompt_toolkit.document import Document

from lightlike.app import _get
from lightlike.app.client import get_client
from lightlike.cmd.query.words import KEYWORD_META, SQL_KEYWORDS
from lightlike.internal.utils import _alter_str

if t.TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent

__all__: t.Sequence[str] = ("query_repl_completer",)


def query_repl_completer() -> ThreadedCompleter:
    completers = [
        ResourceCompleter(),
        LoopNestedCompleter.from_nested_dict(SQL_KEYWORDS, KEYWORD_META),
    ]
    return ThreadedCompleter(merge_completers(completers, deduplicate=True))


class LoopNestedCompleter(Completer):
    __slots__ = ()
    original_keywords: dict[str, t.Any] = SQL_KEYWORDS

    class _LastNestedWordCompleter(Completer):
        __slots__ = ()

        def __init__(self, words: list[str], meta: dict[str, str] = {}) -> None:
            self.words = words
            self.meta = meta

        def get_completions(
            self, document: Document, complete_event: "CompleteEvent"
        ) -> t.Iterable[Completion]:
            words = list(map(str.upper, self.words))
            word_before_cursor = document.get_word_before_cursor(WORD=True).upper()

            for word in words:
                if word.startswith(word_before_cursor):
                    yield Completion(
                        text=f"{word}",
                        start_position=-len(word_before_cursor),
                        display_meta=f"{self.meta.get(word, '')}",
                    )

    def __init__(
        self,
        keywords: dict[str, Completer | None],
        keyword_meta: dict[str, str] = {},
    ) -> None:
        self.current_keywords = keywords
        self.keyword_meta = keyword_meta

    @classmethod
    def from_nested_dict(
        cls,
        data: dict[str, t.Any | t.Set[str] | None | Completer],
        meta: dict[str, str] = {},
    ) -> LoopNestedCompleter:
        keywords: dict[str, Completer | None] = {}
        for key, value in data.items():
            if isinstance(value, Completer):
                keywords[key] = value
            elif isinstance(value, dict):
                keywords[key] = cls.from_nested_dict(value, meta)
            elif isinstance(value, set):
                keywords[key] = cls.from_nested_dict(
                    {item: None for item in value}, meta
                )
            else:
                assert value is None
                keywords[key] = None

        return cls(keywords, meta)

    def get_completions(
        self, document: Document, complete_event: "CompleteEvent"
    ) -> t.Iterable[Completion]:
        text = document.text_before_cursor.lstrip().upper()
        stripped_len = len(document.text_before_cursor) - len(text)

        if " " in text:
            first_term = text.split()[0]
            completer = self.current_keywords.get(first_term.upper())

            if completer is not None:
                remaining_text = text[len(first_term) :].lstrip()
                move_cursor = len(text) - len(remaining_text) + stripped_len
                new_document = Document(
                    text=remaining_text,
                    cursor_position=document.cursor_position - move_cursor,
                )
                yield from completer.get_completions(new_document, complete_event)
            else:
                yield from self._LastNestedWordCompleter(
                    words=list(self.original_keywords.keys()), meta=self.keyword_meta
                ).get_completions(document, complete_event)
        else:
            yield from self._LastNestedWordCompleter(
                words=list(self.current_keywords.keys()), meta=self.keyword_meta
            ).get_completions(document, complete_event)


class ResourceCompleter(Completer):
    def __init__(self) -> None:
        self.project: str = get_client().project
        if getenv("LIGHTLIKE_CLI_DEV"):
            self.schemas = ["lightlike_cli"]
        else:
            self.schemas = list(
                map(_get.dataset_id, get_client().list_datasets(self.project))
            )

    @cached_property
    def schemas(self) -> list[str]:
        return []

    @cached_property
    def typed_schemas(self) -> list[str]:
        return []

    @cached_property
    def tables(self) -> dict[str, list[str]]:
        return {}

    @cached_property
    def routines(self) -> dict[str, list[str]]:
        return {}

    @cached_property
    def fields(self) -> dict[str, list[str]]:
        return {}

    def get_completions(
        self, document: Document, complete_event: "CompleteEvent"
    ) -> t.Iterable[Completion]:
        word_before_cursor = document.get_word_before_cursor()
        args = document.text.split(" ")

        if any(map(lambda d: d in document.text, self.typed_schemas)):
            yield from self._from_typed_schemas(document, word_before_cursor)

        for schema in self.schemas:
            if schema.startswith(word_before_cursor):
                yield from self._schema_completion(word_before_cursor, schema)

        if document.char_before_cursor == ".":
            yield from self._save_and_yield_schema(args, word_before_cursor)

    def _load_tables(self, schema: str) -> None:
        _tables = get_client().list_tables(schema)
        self.tables[schema] = list(map(_get.table_id, _tables))

    def _load_fields(self, schema: str, table: str) -> None:
        _schema = get_client().get_table(f"{self.project}.{schema}.{table}").schema
        self.fields[table] = list(map(_get.name, _schema))

    def _load_routines(self, schema: str) -> None:
        _routines = get_client().list_routines(schema)
        self.routines[schema] = list(map(_get.routine_id, _routines))

    def _from_typed_schemas(
        self, document: Document, word_before_cursor: str
    ) -> t.Iterable[Completion]:
        for schema in self.typed_schemas:
            if schema in document.text:
                for table in self.tables[schema]:
                    if table.startswith(word_before_cursor):
                        yield from self._table_completion(
                            word_before_cursor, schema, table
                        )
                    if table in self.fields:
                        stripped_word_before_cur: str = _alter_str(
                            word_before_cursor, strip_parenthesis=True
                        )
                        for field in self.fields[table]:
                            if field.startswith(stripped_word_before_cur):
                                yield from self._field_completion(
                                    stripped_word_before_cur, schema, table, field
                                )

                for routine in self.routines[schema]:
                    if routine.startswith(word_before_cursor):
                        yield from self._routine_completion(
                            word_before_cursor, schema, routine
                        )

    def _save_and_yield_schema(
        self, list_text: list[str], word_before_cursor: str
    ) -> t.Iterable[Completion]:
        with suppress(IndexError):
            last_word = list_text[-1]
            schema = last_word.split(".")[0]
            resource = last_word.split(".")[1]

            if schema in self.schemas:
                if schema not in self.typed_schemas:
                    self.typed_schemas.append(schema)
                if schema not in self.tables:
                    self._load_tables(schema)
                if schema not in self.routines:
                    self._load_routines(schema)

                for table in self.tables[schema]:
                    if resource in table:
                        yield from self._table_completion(
                            word_before_cursor, schema, table
                        )
                for routine in self.routines[schema]:
                    if resource in routine:
                        yield from self._routine_completion(
                            word_before_cursor, schema, routine
                        )
            for schema in self.typed_schemas:
                if schema in self.tables:
                    for table in self.tables[schema]:
                        if table not in self.fields:
                            self._load_fields(schema, table)

    def _schema_completion(
        self, word_before_cursor: str, schema: str
    ) -> t.Iterable[Completion]:
        yield Completion(
            text=schema,
            start_position=-len(word_before_cursor),
            display_meta="DATASET",
            style="fg:#f3aa61",
            selected_style="reverse",
        )

    def _table_completion(
        self, word_before_cursor: str, schema: str, table: str
    ) -> t.Iterable[Completion]:
        start_position = (
            -len(word_before_cursor) + 1
            if word_before_cursor == "."
            else -len(word_before_cursor)
        )
        yield Completion(
            text=table,
            start_position=start_position,
            display_meta=f"TABLE:{schema}",
            style="fg:#ceaafb",
            selected_style="reverse",
        )

    def _routine_completion(
        self, word_before_cursor: str, schema: str, routine: str
    ) -> t.Iterable[Completion]:
        start_position = (
            -len(word_before_cursor) + 1
            if word_before_cursor == "."
            else -len(word_before_cursor)
        )
        yield Completion(
            text=routine,
            start_position=start_position,
            display_meta=f"ROUTINE:{schema}",
            style="fg:#f08375",
            selected_style="reverse",
        )

    def _field_completion(
        self, word_before_cursor: str, schema: str, table: str, field: str
    ) -> t.Iterable[Completion]:
        start_position = (
            -len(word_before_cursor) + 1
            if word_before_cursor == "."
            else -len(word_before_cursor)
        )
        yield Completion(
            text=field,
            start_position=start_position,
            display_meta=f"FIELD:{schema}.{table}",
            selected_style="reverse",
        )
