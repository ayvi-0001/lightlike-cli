import typing as t
from operator import attrgetter, itemgetter

__all__: t.Sequence[str] = (
    "count_entries",
    "dataset_id",
    "id_",
    "name",
    "note",
    "routine_id",
    "table_id",
)

id_ = itemgetter("id")
count_entries = attrgetter("count_entries")
dataset_id = attrgetter("dataset_id")
note = itemgetter("note")
name = attrgetter("name")
routine_id = attrgetter("routine_id")
table_id = attrgetter("table_id")
