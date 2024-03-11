import operator
import re
import typing as t
from math import copysign

if t.TYPE_CHECKING:
    from google.cloud.bigquery.client import Project

__all__: t.Sequence[str] = (
    "id",
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
    "project_display",
    "where_clause",
)

T = t.TypeVar("T")


id = operator.itemgetter("id")
project = operator.itemgetter("project")
note = operator.itemgetter("note")
name = operator.attrgetter("name")
description = operator.attrgetter("description")
table_name = operator.attrgetter("table_name")
table_id = operator.attrgetter("table_id")
routine_id = operator.attrgetter("routine_id")
dataset_id = operator.attrgetter("dataset_id")
projects_list = operator.attrgetter("projects_list")
count_entries = operator.attrgetter("count_entries")

sign = lambda x: copysign(1, x)

project_display: t.Callable[["Project"], str] = lambda p: "%s | %s | %s" % (
    p.friendly_name,
    p.project_id,
    p.numeric_id,
)

where_clause: t.Final[re.Pattern[str]] = re.compile(
    r"^(?:'|\"|)(?:.?where\s+|)(.*)(?:'|\"|)$", re.IGNORECASE
)
