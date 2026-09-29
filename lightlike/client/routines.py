from __future__ import annotations

import re
import typing as t
from datetime import date, datetime, time
from inspect import classify_class_attrs
from time import sleep
from zoneinfo import ZoneInfo

import click
import sqlalchemy as sq
from google.cloud.bigquery import QueryJob
from more_itertools import filter_map
from rich.text import Text

from lightlike.app.config import AppConfig
from lightlike.client.bigquery import get_client
from lightlike.internal import markup

if t.TYPE_CHECKING:
    from decimal import Decimal

    from google.cloud.bigquery import Client, QueryJobConfig
    from google.cloud.bigquery.job import QueryJob

__all__: t.Sequence[str] = ("CliQueryRoutines",)


P = t.ParamSpec("P")

_MAPPING: dict[str, str] = AppConfig()["bigquery"]

type Rows = t.Sequence[sq.Row[t.Any]]


class CliQueryRoutines:
    dataset: str = _MAPPING["dataset"]
    table_timesheet: str = _MAPPING["timesheet"]
    table_projects: str = _MAPPING["projects"]
    timesheet_id: str = f"{dataset}.{table_timesheet}"
    projects_id: str = f"{dataset}.{table_projects}"

    client: t.Callable[..., Client] = get_client

    engine = sq.create_engine(
        url=f"bigquery://{client().project}?use_query_cache=false",
        connect_args={"client": client()},
    )

    _table_timesheet = sq.Table(
        table_timesheet,
        sq.MetaData(),
        sq.Column("id", sq.String()),
        sq.Column("date", sq.DATE()),
        sq.Column("project", sq.String()),
        sq.Column("note", sq.String()),
        sq.Column("timestamp_start", sq.types.TIMESTAMP(timezone=False)),
        sq.Column("start", sq.types.DateTime(timezone=False)),
        sq.Column("timestamp_end", sq.types.TIMESTAMP(timezone=False)),
        sq.Column("end", sq.types.DateTime(timezone=False)),
        sq.Column("active", sq.Boolean()),
        sq.Column("billable", sq.Boolean()),
        sq.Column("archived", sq.Boolean()),
        sq.Column("paused", sq.Boolean()),
        sq.Column("timestamp_paused", sq.types.TIMESTAMP(timezone=False)),
        sq.Column("paused_counter", sq.Integer()),
        sq.Column("paused_hours", sq.Numeric(precision=4)),
        sq.Column("hours", sq.Numeric(precision=4)),
        schema=dataset,
        autoload_with=engine,
    )
    _table_projects = sq.Table(
        table_projects,
        sq.MetaData(),
        schema=dataset,
        autoload_with=engine,
    )

    def _query_and_wait(self, query: str, job_config: QueryJobConfig | None = None) -> QueryJob:
        query_is_active = 1

        def _completed(*args: P.args, **kwargs: P.kwargs) -> None:
            """
            Function is added as a callback to the query job so we have a non-blocking thread
            to wait for the query results without having to use consecutive GET requests.
            """
            nonlocal query_is_active
            query_is_active = 0

        query_job = self.client().query(query, job_config=job_config)
        query_job.add_done_callback(_completed)  # type: ignore[no-untyped-call]

        while query_is_active:
            sleep(0.01)

        return query_job

    def _query(
        self,
        target: str,
        job_config: QueryJobConfig | None = None,
        wait: bool | None = False,
        suppress: bool | None = False,
    ) -> QueryJob:
        if wait:
            query_job = self._query_and_wait(
                target,
                job_config=job_config,
            )
            if query_job._exception and not suppress:
                raise click.ClickException(
                    message=self._format_error_message(query_job, target),
                )

            return query_job

        query_job: QueryJob = self.client().query(target, job_config=job_config)
        if query_job._exception and suppress is False:
            raise click.ClickException(
                message=self._format_error_message(query_job, target),
            )

        return query_job

    def _start_time_entry(
        self,
        time_entry_id: str,
        project: str,
        note: str,
        start_time: datetime,
        billable: bool,
    ) -> Rows:
        executable: sq.Executable = self._table_timesheet.insert().values(
            id=time_entry_id,
            date=sq.cast(start_time.date(), sq.DATE()),
            project=project,
            note=None if note == "None" else note,
            timestamp_start=sq.cast(start_time.astimezone(None), sq.TIMESTAMP()),
            start=sq.text(
                f"datetime(timestamp('{start_time}'), '{AppConfig().tzname}')",
            ),
            active=sq.cast(True, sq.BOOLEAN()),
            billable=sq.cast(billable, sq.BOOLEAN()),
            archived=sq.cast(False, sq.BOOLEAN()),
            paused=sq.cast(False, sq.BOOLEAN()),
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _add_time_entry(
        self,
        id: str,
        project: str,
        note: str,
        start_time: datetime,
        end_time: datetime,
        hours: Decimal,
        billable: bool,
    ) -> Rows:
        executable: sq.Executable = self._table_timesheet.insert().values(
            id=id,
            date=sq.cast(start_time.date(), sq.Date()),
            project=project,
            note=note if note != "None" else None,
            timestamp_start=start_time.astimezone(ZoneInfo("UTC")),
            start=sq.cast(start_time.replace(tzinfo=None), sq.DateTime(timezone=True)),
            timestamp_end=end_time.astimezone(ZoneInfo("UTC")),
            end=sq.cast(end_time.replace(tzinfo=None), sq.DateTime(timezone=True)),
            active=False,
            billable=billable,
            archived=False,
            paused=False,
            hours=hours,
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _delete_time_entries(self, ids: list[str]) -> Rows:
        executable: sq.Executable = self._table_timesheet.delete().where(
            self._table_timesheet.c.id.in_(ids),
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _archive_project(self, name: str) -> Rows:
        executable: sq.Executable = (
            self._table_projects
            .update()
            .values(archived=datetime.now(tz=AppConfig().tzinfo))
            .where(self._table_projects.c.name == name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _archive_time_entries(self, name: str) -> Rows:
        executable: sq.Executable = (
            self._table_timesheet
            .update()
            .values(archived=True)
            .where(self._table_timesheet.c.project == name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _create_project(
        self,
        name: str,
        description: str,
        default_billable: bool,
    ) -> Rows:
        executable: sq.Executable = self._table_projects.insert().values(
            name=name,
            description=description or None,
            default_billable=default_billable,
            created=datetime.now(tz=AppConfig().tzinfo),
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _delete_project(self, name: str) -> Rows:
        executable: sq.Executable = self._table_projects.delete().where(
            self._table_projects.c.name == name,
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _delete_time_entries_by_project(self, project: str) -> QueryJob:
        executable: sq.Executable = self._table_timesheet.delete().where(
            self._table_timesheet.c.project == project,
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _update_time_entries(
        self,
        ids: t.Sequence[str],
        project: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        date: date | None = None,
    ) -> Rows:
        timesheet = self._table_timesheet
        second = sq.literal_column("SECOND")
        tzname: str = AppConfig().tzname

        values: dict[str, t.Any] = {}
        if project is not None:
            values["project"] = project
        if note is not None:
            values["note"] = note
        if billable is not None:
            values["billable"] = billable
        if date is not None:
            values["date"] = date

        date_param = sq.literal(date, sq.Date()) if date is not None else None

        start: sq.ColumnElement[t.Any] = timesheet.c.start
        if date is not None or start_time is not None:
            start = sq.func.datetime(
                date_param if date_param is not None else sq.func.date(timesheet.c.start),
                sq.literal(start_time, sq.Time())
                if start_time is not None
                else sq.func.time(timesheet.c.start),
            )
            values["start"] = sq.func.datetime_trunc(start, second)
            values["timestamp_start"] = sq.func.timestamp_trunc(
                sq.func.timestamp(start, tzname),
                second,
            )

        end: sq.ColumnElement[t.Any] = timesheet.c.end
        if date is not None or end_time is not None:
            end = sq.func.datetime(
                date_param if date_param is not None else sq.func.date(timesheet.c.end),
                sq.literal(end_time, sq.Time())
                if end_time is not None
                else sq.func.time(timesheet.c.end),
            )
            values["end"] = sq.func.datetime_trunc(end, second)
            values["timestamp_end"] = sq.func.timestamp_trunc(
                sq.func.timestamp(end, tzname),
                second,
            )

        if "start" in values or "end" in values:
            values["hours"] = sq.func.round(
                sq.cast(
                    sq.func.safe_divide(
                        sq.func.datetime_diff(end, start, second),
                        sq.literal_column("3600"),
                    )
                    - sq.func.coalesce(timesheet.c.paused_hours, sq.literal_column("0")),
                    sq.Numeric(),
                ),
                sq.literal_column("4"),
            )

        if not values:
            return []

        executable: sq.Executable = (
            timesheet.update().values(**values).where(timesheet.c.id.in_([*ids]))
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _stop_time_entry(self, id: str, end: datetime) -> Rows:
        timesheet = self._table_timesheet
        second = sq.literal_column("SECOND")
        timestamp_end = sq.bindparam(
            "timestamp_end_param",
            end.replace(microsecond=0),
            type_=sq.TIMESTAMP(timezone=True),
        )

        paused_hours = sq.cast(
            sq.case(
                (
                    timesheet.c.paused == True,  # ruff: ignore[true-false-comparison]
                    sq.func.safe_divide(
                        sq.func.timestamp_diff(
                            timestamp_end,
                            timesheet.c.timestamp_paused,
                            second,
                        ),
                        sq.literal_column("3600"),
                    ),
                ),
                else_=sq.literal_column("0"),
            )
            + sq.func.coalesce(timesheet.c.paused_hours, sq.literal_column("0")),
            sq.Numeric(),
        )
        hours = (
            sq.cast(
                sq.func.safe_divide(
                    sq.func.timestamp_diff(
                        timestamp_end,
                        timesheet.c.timestamp_start,
                        second,
                    ),
                    sq.literal_column("3600"),
                ),
                sq.Numeric(),
            )
            - paused_hours
        )

        executable: sq.Executable = (
            timesheet
            .update()
            .values(
                timestamp_end=timestamp_end,
                end=end.astimezone(AppConfig().tzinfo).replace(
                    tzinfo=None,
                    microsecond=0,
                ),
                hours=sq.func.round(hours, sq.literal_column("4")),
                paused_hours=sq.func.round(paused_hours, sq.literal_column("4")),
                active=False,
                paused=False,
                timestamp_paused=None,
            )
            .where(timesheet.c.id == id)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _get_time_entries(self, ids: list[str]) -> Rows:
        executable: sq.Executable = self._table_timesheet.select().where(
            self._table_timesheet.c.id.in_(ids),
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _resume_time_entry(self, id: str, time_resume: datetime) -> Rows:
        timesheet = self._table_timesheet
        second = sq.literal_column("SECOND")
        time_resume_param = sq.bindparam(
            "time_resume",
            time_resume,
            type_=sq.TIMESTAMP(timezone=True),
        )

        paused_hours = sq.cast(
            sq.func.safe_divide(
                sq.func.timestamp_diff(
                    time_resume_param,
                    timesheet.c.timestamp_paused,
                    second,
                ),
                sq.literal_column("3600"),
            )
            + sq.func.coalesce(timesheet.c.paused_hours, sq.literal_column("0")),
            sq.Numeric(),
        )

        executable: sq.Executable = (
            timesheet
            .update()
            .values(
                paused=False,
                active=True,
                paused_hours=sq.func.round(paused_hours, sq.literal_column("4")),
                timestamp_paused=None,
            )
            .where(timesheet.c.id == id)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _unarchive_project(self, name: str) -> Rows:
        executable: sq.Executable = (
            self._table_projects
            .update()
            .values(archived=None)
            .where(self._table_projects.c.name == name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _unarchive_time_entries(self, name: str) -> Rows:
        executable: sq.Executable = (
            self._table_timesheet
            .update()
            .values(archived=False)
            .where(self._table_timesheet.c.name == name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _update_project_default_billable(
        self,
        name: str,
        default_billable: bool,
    ) -> Rows:
        executable: sq.Executable = (
            self._table_projects
            .update()
            .values(default_billable=default_billable)
            .where(self._table_projects.c.name == name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _update_project_description(self, name: str, description: str) -> Rows:
        executable: sq.Executable = (
            self._table_projects
            .update()
            .values(description=description)
            .where(self._table_projects.c.name == name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _update_project_name(self, old_name: str, new_name: str) -> Rows:
        executable: sq.Executable = (
            self._table_projects
            .update()
            .values(name=new_name)
            .where(self._table_projects.c.name == old_name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _update_time_entry_projects(self, old_name: str, new_name: str) -> Rows:
        executable: sq.Executable = (
            self._table_timesheet
            .update()
            .values(project=new_name)
            .where(self._table_timesheet.c.project == old_name)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _pause_time_entry(self, id: str, timestamp_paused: datetime) -> Rows:
        executable: sq.Executable = (
            self._table_timesheet
            .update()
            .values(
                paused=True,
                active=False,
                timestamp_paused=sq.cast(
                    timestamp_paused.replace(microsecond=0),
                    sq.TIMESTAMP(timezone=False),
                ),
                paused_counter=sq.func.coalesce(
                    self._table_timesheet.c.paused_counter,
                    0,
                )
                + 1,
            )
            .where(self._table_timesheet.c.id == id)
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def _list_timesheet(
        self,
        date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        include: t.Sequence[str] | None = None,
        exclude: t.Sequence[str] | None = None,
        match_project: t.Sequence[str] | None = None,
        match_note: t.Sequence[str] | None = None,
        modifiers: t.Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        where: str | None = None,
    ) -> Rows:
        timesheet = self._table_timesheet
        row = (
            sq.func
            .row_number()
            .over(
                order_by=[
                    timesheet.c.timestamp_start,
                    timesheet.c.timestamp_end,
                    timesheet.c.paused,
                    timesheet.c.timestamp_paused,
                    timesheet.c.paused_counter,
                    timesheet.c.paused_hours,
                ],
            )
            .label("row")
        )
        total = (
            sq.func
            .sum(timesheet.c.hours)
            .over(
                order_by=[
                    timesheet.c.timestamp_start,
                    timesheet.c.timestamp_end,
                    timesheet.c.paused,
                    timesheet.c.timestamp_paused,
                    timesheet.c.paused_counter,
                    timesheet.c.paused_hours,
                ],
            )
            .label("total")
        )
        columns = [
            row,
            timesheet.c.id,
            timesheet.c.date,
            timesheet.c.project,
            timesheet.c.note,
            timesheet.c.timestamp_start,
            timesheet.c.start,
            timesheet.c.timestamp_end,
            timesheet.c.end,
            timesheet.c.active,
            timesheet.c.billable,
            timesheet.c.archived,
            timesheet.c.paused,
            timesheet.c.timestamp_paused,
            timesheet.c.paused_counter,
            timesheet.c.paused_hours,
            timesheet.c.hours,
            total,
        ]

        executable = sq.select(*columns)

        if date:
            executable = executable.where(timesheet.c.date == date)
        if start_date and end_date:
            executable = executable.where(
                timesheet.c.date.between(start_date, end_date),
            )
        if where:
            executable = executable.where(sq.text(where))

        case_insensitive_regexp_match: bool = False
        if modifiers and "I" in modifiers:
            case_insensitive_regexp_match = True

        # https://docs.sqlalchemy.org/en/14/core/sqlelement.html#sqlalchemy.sql.expression.ColumnOperators.regexp_match
        if include:
            include_clauses = []
            for pattern in include:
                if not pattern:
                    continue
                if not case_insensitive_regexp_match:
                    include_clauses.append(
                        sq.or_(
                            timesheet.c.project.regexp_match(pattern),
                            timesheet.c.note.regexp_match(pattern),
                        ),
                    )
                else:
                    include_clauses.append(
                        sq.or_(
                            sq.func.lower(timesheet.c.project).regexp_match(
                                pattern.lower(),
                            ),
                            sq.func.lower(timesheet.c.note).regexp_match(
                                pattern.lower(),
                            ),
                        ),
                    )

            executable = executable.where(sq.or_(*include_clauses))
        if exclude:
            exclude_clauses = []
            for pattern in exclude:
                if not pattern:
                    continue
                exclude_clauses.append(
                    sq.or_(
                        sq.and_(
                            sq.not_(timesheet.c.project.regexp_match(pattern)),
                            sq.not_(timesheet.c.note.regexp_match(pattern)),
                        ),
                        # TODO add to other exclude/include filters
                        sq.and_(
                            sq.not_(timesheet.c.project.regexp_match(pattern)),
                            timesheet.c.note == None,  # ruff: ignore[none-comparison]
                        ),
                    ),
                )
            executable = executable.where(sq.and_(*exclude_clauses))
        if match_project:
            match_project_clauses = []
            for pattern in match_project:
                if not pattern:
                    continue
                match_project_clauses.append(
                    timesheet.c.project.regexp_match(pattern),
                )
            executable = executable.where(sq.or_(*match_project_clauses))
        if match_note:
            match_note_clauses = []
            for pattern in match_note:
                if not pattern:
                    continue
                match_note_clauses.append(
                    timesheet.c.note.regexp_match(pattern),
                )
            executable = executable.where(sq.or_(*match_note_clauses))

        if limit:
            executable = executable.limit(limit)
        if offset:
            executable = executable.offset(offset)

        executable = executable.order_by(
            timesheet.c.timestamp_start,
            timesheet.c.timestamp_end,
        )

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as error:
            msg = f"{error}"
            raise click.get_current_context().fail(msg)

        return rows

    def summary(  # ruff: ignore[complex-structure, too-many-branches, too-many-statements]
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        where: str | None = None,
        round_: str | None = None,
        match_project: t.Sequence[str] | None = None,
        match_note: t.Sequence[str] | None = None,
        exclude: t.Sequence[str] | None = None,
        include: t.Sequence[str] | None = None,
        modifiers: t.Sequence[str] | None = None,
        regex_engine: t.Literal["ECMAScript", "re2"] = "ECMAScript",
        order_by: t.Literal["date", "project"] = "date",
        *,
        show_null_values: bool = True,
        is_file: bool | None = False,
    ) -> Rows:
        timesheet = self._table_timesheet

        round_factor: int
        match round_:
            case ".05":
                round_factor = 5
            case ".1":
                round_factor = 10
            case ".25":
                round_factor = 25
            case ".5":
                round_factor = 50
            case "1":
                round_factor = 100
            case _:
                round_factor = 1

        hours: sq.ColumnElement[t.Any] = sq.func.sum(timesheet.c.hours)
        if round_:
            hours = sq.func.round(
                hours / sq.literal_column(str(round_factor)),
                sq.literal_column("2"),
            ) * sq.literal_column(str(round_factor))

        grouped = (
            sq
            .select(
                timesheet.c.date,
                timesheet.c.project,
                timesheet.c.billable,
                timesheet.c.note,
                hours.label("hours"),
            )
            .where(
                timesheet.c.archived == False,  # ruff: ignore[true-false-comparison]
                timesheet.c.paused == False,  # ruff: ignore[true-false-comparison]
            )
            .group_by(
                timesheet.c.project,
                timesheet.c.date,
                timesheet.c.billable,
                timesheet.c.note,
            )
        )

        if start_date and end_date:
            grouped = grouped.where(timesheet.c.date.between(start_date, end_date))

        def _regexp(
            column: sq.ColumnElement[t.Any],
            patterns: t.Sequence[str],
        ) -> sq.ColumnElement[t.Any]:
            return self._regexp_contains(
                column=column,
                pattern="|".join(filter(None, patterns)),
                modifiers=modifiers,
                regex_engine=regex_engine,
            )

        if match_project:
            grouped = grouped.where(_regexp(timesheet.c.project, match_project))
        if match_note:
            grouped = grouped.where(_regexp(timesheet.c.note, match_note))
        if exclude:
            grouped = grouped.where(
                sq.or_(
                    sq.not_(
                        sq.or_(
                            _regexp(timesheet.c.project, exclude),
                            _regexp(timesheet.c.note, exclude),
                        ),
                    ),
                    sq.and_(
                        sq.not_(_regexp(timesheet.c.project, exclude)),
                        timesheet.c.note == None,  # ruff: ignore[none-comparison]
                    ),
                ),
            )
        if include:
            grouped = grouped.where(
                sq.or_(
                    _regexp(timesheet.c.project, include),
                    _regexp(timesheet.c.note, include),
                ),
            )
        if where:
            grouped = grouped.where(sq.text(where))

        if show_null_values:
            grouped = grouped.having(hours != sq.literal_column("0"))

        grouped_cte = grouped.cte("grouped")

        window_order: list[sq.ColumnElement[t.Any]]
        if order_by == "project":
            window_order = [
                grouped_cte.c.project,
                grouped_cte.c.date,
                grouped_cte.c.billable,
            ]
        else:
            window_order = [
                grouped_cte.c.date,
                grouped_cte.c.project,
                grouped_cte.c.billable,
            ]

        sum_hours = sq.func.sum(grouped_cte.c.hours)
        precision = sq.literal_column("4")

        windowed = sq.select(
            sq.func.round(sum_hours.over(order_by=window_order), precision).label(
                "total_summary",
            ),
            sq.func.round(
                sum_hours.over(partition_by=grouped_cte.c.project, order_by=window_order),
                precision,
            ).label("total_project"),
            sq.func.round(
                sum_hours.over(partition_by=grouped_cte.c.date, order_by=window_order),
                precision,
            ).label("total_day"),
            grouped_cte.c.date,
            grouped_cte.c.project,
            grouped_cte.c.billable,
            sq.func.round(sum_hours.over(partition_by=window_order), precision).label(
                "hours",
            ),
            sq.func
            .string_agg(
                sq.func.concat(grouped_cte.c.note, " - ", grouped_cte.c.hours),
                ", " if is_file else "\n",
            )
            .over(partition_by=window_order)
            .label("notes"),
        ).cte("windowed")

        executable = sq.select(windowed).distinct()

        if show_null_values:
            executable = executable.where(windowed.c.total_day != sq.literal_column("0"))

        if order_by == "project":
            executable = executable.order_by(windowed.c.project, windowed.c.date)
        else:
            executable = executable.order_by(windowed.c.date, windowed.c.project)

        try:
            with self.engine.begin() as conn:
                result = conn.execute(executable)
                rows = result.fetchall()
        except Exception as exc:
            msg = f"{exc}"
            raise click.UsageError(msg, click.get_current_context()) from exc

        return rows

    def _regexp_contains(
        self,
        column: sq.ColumnElement[t.Any],
        pattern: str,
        modifiers: t.Sequence[str] | None = None,
        regex_engine: t.Literal["ECMAScript", "re2"] | None = "ECMAScript",
    ) -> sq.ColumnElement[t.Any]:
        match regex_engine:
            case "ECMAScript":
                js_regex_contains = getattr(sq.func, self.dataset).js_regex_contains
                if modifiers:
                    modifiers = "".join(map(str.lower, modifiers))
                return js_regex_contains(column, pattern, modifiers or "")
            case "re2":
                return column.regexp_match(pattern)
            case _:
                msg = f"Unknown regex engine: {regex_engine}"
                raise ValueError(msg)

    def _select(
        self,
        resource: str,
        fields: t.Sequence[str] = ["*"],
        where: t.Sequence[str] | None = None,
        order: t.Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        distinct: bool | None = False,
        wait: bool | None = False,
    ) -> QueryJob:
        query = "".join(
            [
                f"SELECT {'DISTINCT ' if distinct else ''}",
                f"{','.join(fields)} ",
                f"FROM {resource} ",
                f"WHERE {' AND '.join(where)} " if where else "",
                f"ORDER BY {','.join(order)} " if order else "",
                f"LIMIT {limit} " if limit else "",
                f"OFFSET {offset} " if offset else "",
                ";",
            ],
        )
        return self._query(target=query, wait=wait)

    def _format_regular_expression(
        self,
        fields: str | list[str],
        expr: str,
        modifiers: str | None = None,
        and_: bool = False,
        not_: bool = False,
        regex_engine: t.Literal["ECMAScript", "re2"] | str = "ECMAScript",
    ) -> str:
        expression = ""
        and_op = "AND " if and_ else ""
        not_op = "NOT " if not_ else ""
        conditionals = f"{and_op}{not_op}"

        if regex_engine == "ECMAScript":
            fn = f"{self.dataset}.js_regex_contains"

            if isinstance(fields, list):
                filter_clauses = [f'{fn}({field},r"{expr}","{modifiers}")' for field in fields]
                expression = f"{conditionals}({' OR '.join(filter_clauses)})"
            else:
                expression = f'{conditionals}{fn}({fields}, r"{expr}", "{modifiers}")'

        elif regex_engine == "re2":
            fn = "REGEXP_CONTAINS"

            if isinstance(fields, list):
                filter_clauses = []
                for field in fields:
                    filter_clauses.append(f'{fn}({field}, r"{expr}")')
                expression = f"{conditionals}({' OR '.join(filter_clauses)})"
            else:
                expression = f'{conditionals}{fn}({fields}, r"{expr}")'

        else:
            msg = f"Unknown regex engine: {regex_engine}"
            raise ValueError(msg)

        return expression

    @property
    def _all_routines_ids(self) -> list[str]:
        functions = [
            "current_datetime",
            "current_timestamp",
            "js_regex_contains",
        ]
        procedures = list(
            filter_map(
                lambda a: a.name if a.kind == "method" and not a.name.startswith("_") else None,
                classify_class_attrs(type(self)),
            ),
        )
        return procedures + functions

    def _format_error_message(
        self,
        query_job: QueryJob,
        target: str | None = None,
    ) -> str:
        pattern = re.compile(r"\d{3}\s.+?(?=:)")
        error = pattern.findall(f"{query_job._exception}")
        query_string = f"QUERY: {target}" + "\n\n" if target else ""
        if error:
            message = pattern.sub("", f"{query_job._exception}")
            return Text.assemble(query_string, markup.br(error[0]), message).markup
        return Text.assemble(query_string, markup.br(query_job._exception)).markup
