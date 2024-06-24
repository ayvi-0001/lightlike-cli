from __future__ import annotations

import re
import typing as t
from inspect import classify_class_attrs, cleandoc
from os import getenv
from time import perf_counter_ns, sleep, time

import rich_click as click
from google.cloud.bigquery import QueryJob, QueryJobConfig
from google.cloud.bigquery.query import (
    ArrayQueryParameter,
    ScalarQueryParameter,
    SqlParameterScalarTypes,
)
from more_itertools import filter_map
from rich import get_console
from rich.text import Text

from lightlike.app.client import get_client
from lightlike.app.config import AppConfig
from lightlike.internal import markup

if t.TYPE_CHECKING:
    from datetime import date, datetime

    from google.cloud.bigquery import Client
    from google.cloud.bigquery.job import QueryJob
    from rich.console import RenderableType
    from rich.status import Status

__all__: t.Sequence[str] = ("CliQueryRoutines",)


P = t.ParamSpec("P")


class _Singleton(type):
    _instances: t.ClassVar[dict[object, _Singleton]] = {}

    def __call__(cls, *args: P.args, **kwargs: P.kwargs) -> _Singleton:
        if cls not in cls._instances:
            cls._instances[cls] = super(type(cls), cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class CliQueryRoutines(metaclass=_Singleton):
    _client: t.ClassVar[t.Callable[..., "Client"]] = get_client
    dataset: t.ClassVar[str] = AppConfig().get("bigquery", "dataset")
    table_timesheet: t.ClassVar[str] = AppConfig().get("bigquery", "timesheet")
    table_projects: t.ClassVar[str] = AppConfig().get("bigquery", "projects")
    timesheet_id: t.ClassVar[str] = f"{dataset}.{table_timesheet}"
    projects_id: t.ClassVar[str] = f"{dataset}.{table_projects}"

    def _query_and_wait(
        self,
        query: str,
        job_config: QueryJobConfig | None = None,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        query_is_active = 1

        def _completed(*args: P.args, **kwargs: P.kwargs) -> None:
            """
            function is added as a callback to the query job so we have a non-blocking thread
            to wait for the query results without having to use consecutive GET requests.
            """
            nonlocal query_is_active
            query_is_active = 0

        if render:
            console = get_console()
            status_message = status_renderable or markup.status_message("Running query")
            start = perf_counter_ns()
            query_job = self._client().query(query, job_config=job_config)
            query_job.add_done_callback(_completed)

            if status:
                try:
                    while query_is_active:
                        self._update_elapsed_time(
                            query_job, status, status_message, start
                        )
                except (KeyboardInterrupt, EOFError):
                    self._cancel_job(query_job)
            else:
                with console.status(status_message) as status:
                    try:
                        while query_is_active:
                            self._update_elapsed_time(
                                query_job, status, status_message, start
                            )
                    except (KeyboardInterrupt, EOFError):
                        self._cancel_job(query_job)

            return query_job

        else:
            query_job = self._client().query(query, job_config=job_config)
            query_job.add_done_callback(_completed)

            while query_is_active:
                sleep(0.0001)

            return query_job

    def _query(
        self,
        target: str,
        job_config: QueryJobConfig | None = None,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
        suppress: bool | None = False,
    ) -> "QueryJob":
        if wait or render:
            query_job = self._query_and_wait(
                target,
                job_config=job_config,
                render=render,
                status=status,
                status_renderable=status_renderable,
            )
            if query_job._exception and not suppress:
                raise click.ClickException(
                    message=self._format_error_message(query_job, target)
                )

            return query_job

        else:
            query_job = self._client().query(target, job_config=job_config)
            if query_job._exception and suppress is False:
                raise click.ClickException(
                    message=self._format_error_message(query_job, target)
                )

            return query_job

    def start_time_entry(
        self,
        id: str,
        project: str,
        note: str,
        start_time,
        billable: bool,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            # fmt:off
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
                ScalarQueryParameter("note", SqlParameterScalarTypes.STRING, note),
                ScalarQueryParameter("start_time", SqlParameterScalarTypes.TIMESTAMP, start_time),
                ScalarQueryParameter("billable", SqlParameterScalarTypes.BOOL, billable),
            ],
            # fmt:on
        )

        return self._query(
            target=f"CALL {self.dataset}.start_time_entry(@id, @project, @note, @start_time, @billable);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def add_time_entry(
        self,
        id: str,
        project: str,
        note: str,
        start_time: "datetime",
        end_time: "datetime",
        billable: bool,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
                ScalarQueryParameter("note", SqlParameterScalarTypes.STRING, note),
                ScalarQueryParameter("start_time", SqlParameterScalarTypes.TIMESTAMP, start_time),
                ScalarQueryParameter("end_time", SqlParameterScalarTypes.TIMESTAMP, end_time),
                ScalarQueryParameter("billable", SqlParameterScalarTypes.BOOL, billable),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset}.add_time_entry(@id, @project, @note, @start_time, @end_time, @billable);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _delete_time_entry(
        self,
        ids: list[str],
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ArrayQueryParameter(
                    "ids", SqlParameterScalarTypes.STRING, [i for i in ids]
                ),
            ],
        )

        return self._query(
            target=f"DELETE FROM {self.timesheet_id} WHERE id IN UNNEST(@ids)",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def archive_project(
        self,
        name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.archive_project(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def archive_time_entries(
        self,
        name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.archive_time_entries(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def create_project(
        self,
        name: str,
        description: str,
        default_billable: bool,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("description", SqlParameterScalarTypes.STRING, description),
                ScalarQueryParameter("default_billable", SqlParameterScalarTypes.BOOL, default_billable),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset}.create_project(@name, @description, @default_billable);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def delete_project(
        self,
        name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.delete_project(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def delete_time_entries(
        self,
        project: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter(
                    "project", SqlParameterScalarTypes.STRING, project
                ),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.delete_time_entries(@project);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_time_entries(
        self,
        ids: t.Sequence[str],
        project: str | None = None,
        note: str | None = None,
        billable: bool | None = None,
        start: t.Optional["datetime"] = None,
        end: t.Optional["datetime"] = None,
        date: t.Optional["date"] = None,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                # fmt: off
                ArrayQueryParameter("ids", SqlParameterScalarTypes.STRING, [*ids]),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
                ScalarQueryParameter("note", SqlParameterScalarTypes.STRING, note),
                ScalarQueryParameter("billable", SqlParameterScalarTypes.BOOL, billable),
                ScalarQueryParameter("start", SqlParameterScalarTypes.TIME, start),
                ScalarQueryParameter("end", SqlParameterScalarTypes.TIME, end),
                ScalarQueryParameter("date", SqlParameterScalarTypes.DATE, date),
                # fmt: on
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.update_time_entries(@ids, @project, @note, @billable, @start, @end, @date);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def stop_time_entry(
        self,
        id: str,
        end: datetime,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("end", SqlParameterScalarTypes.TIMESTAMP, end),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.stop_time_entry(@id, @end);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _get_time_entries(
        self,
        ids: list[str],
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ArrayQueryParameter(
                    "ids", SqlParameterScalarTypes.STRING, [i for i in ids]
                ),
            ],
        )

        return self._query(
            target=f"SELECT * FROM {self.timesheet_id} WHERE id IN UNNEST(@ids)",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _create_snapshot(
        self,
        name: str,
        expiration_timestamp: t.Union["datetime", None] = None,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter(
                    "expiration_timestamp",
                    SqlParameterScalarTypes.TIMESTAMP,
                    expiration_timestamp,
                ),
            ],
        )

        query = cleandoc(
            f"""
        CREATE SNAPSHOT TABLE
          {self.dataset}.`{name}`
        CLONE
          {self.timesheet_id}
        """
        )

        if expiration_timestamp:
            query += (
                f"\nOPTIONS(expiration_timestamp=TIMESTAMP('{expiration_timestamp}'))"
            )

        return self._query(
            target=query,
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _restore_snapshot(
        self,
        snapshot_table: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter(
                    "snapshot_table", SqlParameterScalarTypes.STRING, snapshot_table
                ),
            ],
        )

        query = cleandoc(
            f"""
        DECLARE query, version STRING;
        
        SET version = (
          WITH
            table_options AS (
              SELECT
                ARRAY(
                  SELECT AS STRUCT
                    arr[SAFE_OFFSET(0)] AS `key`,
                    arr[SAFE_OFFSET(1)] AS value
                  FROM
                    UNNEST(REGEXP_EXTRACT_ALL(option_value, r'STRUCT\(("[^"]+", "[^"]+")\)')) AS kv,
                    UNNEST([STRUCT(SPLIT(REPLACE(kv, '"', ''), ', ') AS arr)])
                ) AS labels,
              FROM
                {self.dataset}.INFORMATION_SCHEMA.TABLE_OPTIONS
              WHERE
                table_name = "{snapshot_table}"
                AND option_name = "labels"
            )
        
          SELECT
            labels.value,
          FROM
            table_options
          CROSS JOIN
            UNNEST(labels) AS labels
          WHERE
            `key` = "version"
        );
        
        IF version IS NULL
        THEN
          RAISE USING message = "Snapshot is from an old version and is incompatible with the current timesheet table.";
        ELSE
          CREATE OR REPLACE TABLE
            `{self.timesheet_id}`
          CLONE
            `{self.dataset}.{snapshot_table}`;
        END IF;
        """
        )

        return self._query(
            target=query,
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _list_snapshots(
        self,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
        )

        target: str = cleandoc(
            f"""
            SELECT
              table_name,
              TIMESTAMP_TRUNC(creation_time, second) AS creation_time,
              TIMESTAMP_TRUNC(snapshot_time_ms, second) AS snapshot_time_ms,
              expiration_timestamp,
            FROM
              {self.dataset}.INFORMATION_SCHEMA.TABLES
            LEFT JOIN
              (
                SELECT
                  table_name,
                  TIMESTAMP(REGEXP_EXTRACT(option_value, r'TIMESTAMP\s\"(.*)\"')) AS expiration_timestamp
                FROM
                    {self.dataset}.INFORMATION_SCHEMA.TABLE_OPTIONS
                WHERE
                  option_name = "expiration_timestamp"
                  AND option_value NOT IN ('""', "[]")
              )
            USING
              (table_name)
            WHERE
              snapshot_time_ms IS NOT NULL
            ORDER BY
              creation_time;
            """
        )

        return self._query(
            target=target,
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    @property
    def _resume_time_entry(self) -> str:
        return f"CALL {self.dataset}.resume_time_entry(@id, @time_resume);"

    def resume_time_entry(
        self,
        id: str,
        time_resume: "datetime",
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter(
                    "time_resume", SqlParameterScalarTypes.TIMESTAMP, time_resume
                ),
            ],
        )

        return self._query(
            target=self._resume_time_entry,
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def unarchive_project(
        self,
        name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.unarchive_project(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def unarchive_time_entries(
        self,
        name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.unarchive_time_entries(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_notes(
        self,
        new_note: str,
        old_note: str,
        project: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("new_note", SqlParameterScalarTypes.STRING, new_note),
                ScalarQueryParameter("old_note", SqlParameterScalarTypes.STRING, old_note),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset}.update_notes(@new_note, @old_note, @project);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_project_default_billable(
        self,
        project: str,
        value: bool,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                # fmt:off
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
                ScalarQueryParameter("value", SqlParameterScalarTypes.BOOL, value),
                # fmt:on
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.update_project_default_billable(@project, @value);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_project_description(
        self,
        name: str,
        desc: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("desc", SqlParameterScalarTypes.STRING, desc),
            ],
        )

        return self._query(
            target=f"CALL {self.dataset}.update_project_description(@name, @desc);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_project_name(
        self,
        name: str,
        new_name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("new_name", SqlParameterScalarTypes.STRING, new_name),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset}.update_project_name(@name, @new_name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_time_entry_projects(
        self,
        name: str,
        new_name: str,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("new_name", SqlParameterScalarTypes.STRING, new_name),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset}.update_time_entry_projects(@name, @new_name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def pause_time_entry(
        self,
        id: str,
        timestamp_paused: "datetime",
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("timestamp_paused", SqlParameterScalarTypes.TIMESTAMP, timestamp_paused),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset}.pause_time_entry(@id, @timestamp_paused);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _list_timesheet(
        self,
        date: t.Optional["date"] = None,
        start_date: t.Optional["date"] = None,
        end_date: t.Optional["date"] = None,
        where: str | None = None,
        match_project: str | None = None,
        match_note: str | None = None,
        modifiers: str | None = None,
        regex_engine: t.Literal["ECMAScript", "re2"] | str | None = "ECMAScript",
        limit: int | None = None,
        offset: int | None = None,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                # fmt: off
                ScalarQueryParameter("date", SqlParameterScalarTypes.DATE, date),
                ScalarQueryParameter("start_date", SqlParameterScalarTypes.DATE, start_date),
                ScalarQueryParameter("end_date", SqlParameterScalarTypes.DATE, end_date),
                ScalarQueryParameter("where", SqlParameterScalarTypes.STRING, where),
                ScalarQueryParameter("match_project", SqlParameterScalarTypes.STRING, match_project),
                ScalarQueryParameter("match_note", SqlParameterScalarTypes.STRING, match_note),
                ScalarQueryParameter("modifiers", SqlParameterScalarTypes.STRING, modifiers),
                ScalarQueryParameter("limit", SqlParameterScalarTypes.INT64, limit),
                ScalarQueryParameter("offset", SqlParameterScalarTypes.INT64, offset),
                # fmt: on
            ],
        )

        fmt_match_project = self._format_regular_expression(
            field="project",
            expression=match_project,
            modifiers=modifiers,
            regex_engine=regex_engine,
            and_=True,
        )
        fmt_match_note = self._format_regular_expression(
            field="note",
            expression=match_note,
            modifiers=modifiers,
            regex_engine=regex_engine,
            and_=True,
        )

        target = cleandoc(
            f"""
        SELECT
          ROW_NUMBER() OVER(timer) AS `row`,
          LEFT(id, 7) AS id,
          date,
          CAST(FORMAT_DATETIME("%%T", start) AS TIME) AS start,
          CAST(FORMAT_DATETIME("%%T", `end`) AS TIME) AS `end`,
          project,
          note,
          billable,
          active,
          paused,
          ROUND(SAFE_CAST(IF(paused = TRUE, SAFE_DIVIDE(TIMESTAMP_DIFF({self.dataset}.current_timestamp(), timestamp_paused, SECOND), 3600), 0) + IFNULL(paused_hours, 0) AS NUMERIC), 4) AS paused_hours,
          CASE
            WHEN paused THEN ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(timestamp_paused, timestamp_start, SECOND), 3600) AS NUMERIC) - IFNULL(paused_hours, 0), 4)
            WHEN active THEN ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(IFNULL(timestamp_end, lightlike_cli_test.current_timestamp()), timestamp_start, SECOND), 3600) AS NUMERIC) - IFNULL(paused_hours, 0), 4)
            ELSE hours
          END AS hours,
          ROUND(
            SUM(
              CASE
                WHEN paused THEN ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(timestamp_paused, timestamp_start, SECOND), 3600) AS NUMERIC) - IFNULL(paused_hours, 0), 4)
                WHEN active THEN ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(IFNULL(timestamp_end, lightlike_cli_test.current_timestamp()), timestamp_start, SECOND), 3600) AS NUMERIC) - IFNULL(paused_hours, 0), 4)
                ELSE hours
              END
            ) OVER(timer),
            4
          ) AS total,
        FROM
          {self.timesheet_id}
        WHERE
          TRUE
          %s /* date */
          %s /* date between */
          %s /* additional where clause */
          %s /* match project */
          %s /* match note */
        WINDOW
          timer AS (
            ORDER BY
              timestamp_start,
              timestamp_end,
              paused,
              timestamp_paused,
              paused_counter,
              paused_hours
          )
        ORDER BY
          timestamp_start,
          timestamp_end,
          id
        %s
        %s
        """
            % (
                # fmt: off
                f"AND date = \"{date}\"" if date else "",
                f"AND date BETWEEN \"{start_date}\" AND \"{end_date}\"" if start_date and end_date else "",
                f"AND {where}" if where else "",
                fmt_match_project,
                fmt_match_note,
                f"LIMIT {limit}" if limit else "",
                f"OFFSET {offset}" if limit and offset else "",
                # fmt: on
            )
        )

        return self._query(
            target=target,
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _summary(
        self,
        start_date: t.Optional["date"] = None,
        end_date: t.Optional["date"] = None,
        where: str | None = None,
        round_: bool | None = False,
        is_file: bool | None = False,
        match_project: str | None = None,
        match_note: str | None = None,
        modifiers: str | None = None,
        regex_engine: t.Literal["ECMAScript", "re2"] | str | None = "ECMAScript",
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
            query_parameters=[
                # fmt: off
                ScalarQueryParameter("start_date", SqlParameterScalarTypes.DATE, start_date),
                ScalarQueryParameter("end_date", SqlParameterScalarTypes.DATE, end_date),
                ScalarQueryParameter("where", SqlParameterScalarTypes.STRING, where),
                ScalarQueryParameter("match_project", SqlParameterScalarTypes.STRING, match_project),
                ScalarQueryParameter("match_note", SqlParameterScalarTypes.STRING, match_note),
                ScalarQueryParameter("modifiers", SqlParameterScalarTypes.STRING, modifiers),
                ScalarQueryParameter("round_", SqlParameterScalarTypes.BOOL, round_),
                ScalarQueryParameter("is_file", SqlParameterScalarTypes.BOOL, is_file),
                # fmt: on
            ],
        )

        fmt_match_project = self._format_regular_expression(
            field="project",
            expression=match_project,
            modifiers=modifiers,
            regex_engine=regex_engine,
        )
        fmt_match_note = self._format_regular_expression(
            field="note",
            expression=match_note,
            modifiers=modifiers,
            regex_engine=regex_engine,
        )

        target = cleandoc(
            f"""
        SELECT DISTINCT
          ROUND(SUM(hours) OVER(), 4) AS total_summary,
          ROUND(SUM(hours) OVER(PARTITION BY project), 4) AS total_project,
          ROUND(SUM(hours) OVER(PARTITION BY date), 4) AS total_day,
          date,
          project,
          billable,
          ROUND(SUM(hours) OVER(PARTITION BY date, project, billable), 4) AS hours,
          STRING_AGG(note || " - " || hours, "%s") OVER(PARTITION BY date, project, billable) AS notes,
        FROM
          (
            SELECT
              date,
              project,
              billable,
              note,
              CASE %s /* round */
                WHEN TRUE THEN
                  IF(
                    {self.dataset}.rounding_step(SUM(hours) - FLOOR(SUM(hours))) = 1,
                    ROUND(SUM(hours)),
                    FLOOR(SUM(hours)) + {self.dataset}.rounding_step(SUM(hours) - FLOOR(SUM(hours)))
                  )
                ELSE
                  SUM(hours)
              END AS hours,
            FROM
              {self.timesheet_id}
            WHERE
              TRUE
              AND NOT archived
              AND NOT paused
              %s /* date between */
              %s /* match project */
              %s /* match note */
              %s /* additional where clause */
            GROUP BY
              project,
              date,
              billable,
              note
            HAVING
              hours != 0
          )
        QUALIFY
          total_day != 0
        ORDER BY
          date,
          project
        """
            % (
                # fmt: off
                ", " if is_file else "\\n",
                round_ or False,
                f"AND date BETWEEN \"{start_date}\" AND \"{end_date}\"" if start_date and end_date else "",
                fmt_match_project,
                fmt_match_note,
                f"AND {where}" if where else "",
                # fmt: on
            )
        )

        return self._query(
            target=target,
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def _select(
        self,
        resource: str,
        fields: t.Sequence[str] = ["*"],
        where: t.Optional[t.Sequence[str]] = None,
        order: t.Optional[t.Sequence[str]] = None,
        distinct: bool | None = False,
        use_query_cache: bool = True,
        use_legacy_sql: bool | None = False,
        wait: bool | None = False,
        render: bool | None = False,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            use_query_cache=use_query_cache,
            use_legacy_sql=use_legacy_sql,
        )
        query = "".join(
            [
                f"SELECT {'DISTINCT ' if distinct else ''}",
                f"{','.join(fields)} ",
                f"FROM {resource} ",
                f"WHERE {' AND '.join(where)} " if where else " ",
                f"ORDER BY {','.join(order)}" if order else " ",
                ";",
            ]
        )
        return self._query(
            target=query, job_config=job_config, wait=wait, render=render
        )

    def _format_regular_expression(
        self,
        field: str,
        expression: str | None = None,
        modifiers: str | None = None,
        and_: bool = False,
        regex_engine: t.Literal["ECMAScript", "re2"] | str | None = "ECMAScript",
    ) -> str:
        match regex_engine:
            case "ECMAScript":
                return (
                    f'{"AND " if and_ else ""}{self.dataset}.js_regex_contains({field}, r"{expression}", "{modifiers}")'
                    if expression
                    else ""
                )
            case "re2":
                return (
                    f'{"AND " if and_ else ""}REGEXP_CONTAINS({field}, r"{expression}")'
                    if expression
                    else ""
                )
            case _:
                raise ValueError(f"Unknown regex engine: {regex_engine}")

    @property
    def _all_routines_ids(self) -> list[str]:
        functions = [
            "current_datetime",
            "rounding_step",
            "current_timestamp",
            "js_regex_contains",
        ]
        procedures = list(
            filter_map(
                lambda a: (
                    a.name
                    if a.kind == "method" and not a.name.startswith("_")
                    else None
                ),
                classify_class_attrs(type(self)),
            )
        )
        return procedures + functions

    def _elapsed_time(self, query_job: "QueryJob", start: float | None = None) -> str:
        if start:
            ns = (perf_counter_ns() - start) * 1.0e-9
        elif query_job.ended:
            ns = query_job.ended.timestamp() - query_job.started.timestamp()
        else:
            ns = time() - query_job.started.timestamp()

        w, d = str(round(ns, 4)).split(".")
        elapsed = f"{w}.{'0' * (4 - len(d)) + d}"
        return f"{elapsed}"

    def _update_elapsed_time(
        self,
        query_job: "QueryJob",
        status: "Status",
        status_message: t.Optional["RenderableType"],
        start: float | None = None,
    ) -> None:
        elapsed_time = markup.repr_number(self._elapsed_time(query_job, start=start))
        if isinstance(status_message, Text):
            status.update(Text.assemble(status_message, " ", elapsed_time))
        else:
            status.update(f"[status.message]{status_message} {elapsed_time.markup}")

    def _format_error_message(
        self, query_job: QueryJob, target: str | None = None
    ) -> str:
        pattern = re.compile(r"\d{3}\s.+?(?=:)")
        error = pattern.findall(f"{query_job._exception}")
        query_string = f"QUERY: {target}" + "\n\n" if target else ""
        if error:
            message = pattern.sub("", f"{query_job._exception}")
            return Text.assemble(query_string, markup.br(error[0]), message).markup
        else:
            return Text.assemble(query_string, markup.br(query_job._exception)).markup

    def _format_job_cancel_message(self, query_job: QueryJob) -> Text:
        return Text.assemble(
            markup.br("Sent request to cancel job. "),
            "It's not possible to check if a job was canceled in the API. ",
            "To verify if the job was canceled or not, see the ",
            markup.link("job results", self._query_job_url(query_job)),
            " in console.\n",
            markup.repr_url(self._query_job_url(query_job)),
        )

    def _cancel_job(self, query_job: "QueryJob") -> None:
        if query_job.cancel():
            raise click.UsageError(
                message=self._format_job_cancel_message(query_job).markup,
                ctx=click.get_current_context(silent=True),
            )
        else:
            raise click.UsageError(
                message=Text.assemble(
                    markup.br("Failed to request job cancel"),
                    ", see the job results in console.\n",
                    markup.repr_url(self._query_job_url(query_job)),
                ).markup,
                ctx=click.get_current_context(silent=True),
            )

    def _query_job_url(self, query_job: "QueryJob") -> str:
        if LIGHTLIKE_CLI_DEV_GCP_PROJECT := getenv("LIGHTLIKE_CLI_DEV_GCP_PROJECT"):
            from uuid import uuid4

            return "{base_url}project={project_id}&j=bq:{region}:{job_id}&{end_point}".format(
                base_url="https://console.cloud.google.com/bigquery?",
                project_id=LIGHTLIKE_CLI_DEV_GCP_PROJECT,
                region=query_job.location,
                job_id=uuid4(),
                end_point="page=queryresults",
            )

        return (
            "{base_url}project={project_id}&j=bq:{region}:{job_id}&{end_point}".format(
                base_url="https://console.cloud.google.com/bigquery?",
                project_id=query_job.project,
                region=query_job.location,
                job_id=query_job.job_id,
                end_point="page=queryresults",
            )
        )
