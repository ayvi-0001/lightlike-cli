import typing as t
from math import copysign
from operator import attrgetter, itemgetter

__all__: t.Sequence[str] = (
    "_id",
    "project",
    "note",
    "name",
    "description",
    "table_name",
    "table_id",
    "routine_id",
    "dataset_id",
    "projects_list",
    "count_entries",
    "sign",
)

t_itemgetter: t.TypeAlias = itemgetter
t_attrgetter: t.TypeAlias = attrgetter

_id: t_itemgetter = itemgetter("id")
project: t_itemgetter = itemgetter("project")
note: t_itemgetter = itemgetter("note")
name: t_attrgetter = attrgetter("name")
description: t_attrgetter = attrgetter("description")
table_name: t_attrgetter = attrgetter("table_name")
table_id: t_attrgetter = attrgetter("table_id")
routine_id: t_attrgetter = attrgetter("routine_id")
dataset_id: t_attrgetter = attrgetter("dataset_id")
projects_list: t_attrgetter = attrgetter("projects_list")
count_entries: t_attrgetter = attrgetter("count_entries")

sign: t.Callable[[t.SupportsFloat | t.SupportsIndex], float] = lambda x: copysign(1, x)
