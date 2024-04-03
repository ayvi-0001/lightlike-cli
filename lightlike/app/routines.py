import re
import typing as t
from inspect import cleandoc
from time import perf_counter_ns, sleep, time

import rich_click as click
from google.cloud.bigquery import QueryJob, QueryJobConfig
from google.cloud.bigquery.query import ScalarQueryParameter, SqlParameterScalarTypes
from rich import get_console
from rich.text import Text

from lightlike.app.client import get_client
from lightlike.app.config import AppConfig
from lightlike.internal import markup

if t.TYPE_CHECKING:
    from datetime import datetime

    from google.cloud.bigquery import Client
    from google.cloud.bigquery.job import QueryJob
    from rich.console import RenderableType
    from rich.status import Status

__all__: t.Sequence[str] = ("CliQueryRoutines",)


P = t.ParamSpec("P")


class CliQueryRoutines:
    client: t.ClassVar[t.Callable[..., "Client"]] = get_client
    mapping: t.ClassVar[dict[str, t.Any]] = AppConfig().get("bigquery")
    dataset_main: t.ClassVar[str] = mapping["dataset"]
    table_timesheet: t.ClassVar[str] = mapping["timesheet"]
    table_projects: t.ClassVar[str] = mapping["projects"]
    timesheet_id: t.ClassVar[str] = f"{dataset_main}.{table_timesheet}"
    projects_id: t.ClassVar[str] = f"{dataset_main}.{table_projects}"

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
            status_message = (
                status_renderable.markup
                if isinstance(status_renderable, Text)
                else status_renderable or markup.status_message("Running query")
            )
            start = perf_counter_ns()
            query_job = self.client().query(query, job_config=job_config)
            query_job.add_done_callback(_completed)

            if status:
                try:
                    while query_is_active:
                        self._update_elapsed_time(
                            query_job, status, status_message, start
                        )
                except (KeyboardInterrupt, EOFError):
                    self.cancel_job(query_job)
            else:
                with console.status(status_message) as status:
                    try:
                        while query_is_active:
                            self._update_elapsed_time(
                                query_job, status, status_message, start
                            )
                    except (KeyboardInterrupt, EOFError):
                        self.cancel_job(query_job)

            return query_job

        else:
            query_job = self.client().query(query, job_config=job_config)
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
            query_job = self.client().query(target, job_config=job_config)
            if query_job._exception and not suppress:
                raise click.ClickException(
                    message=self._format_error_message(query_job, target)
                )

            return query_job

    def start_time_entry(
        self,
        id: str,
        project,
        note,
        start_time,
        is_billable: bool,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt:off
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
                ScalarQueryParameter("note", SqlParameterScalarTypes.STRING, note),
                ScalarQueryParameter("start_time", SqlParameterScalarTypes.TIMESTAMP, start_time),
                ScalarQueryParameter("is_billable", SqlParameterScalarTypes.BOOL, is_billable),
            ]
            # fmt:on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.start_time_entry(@id, @project, @note, @start_time, @is_billable);",
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
        is_billable: bool,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
                ScalarQueryParameter("note", SqlParameterScalarTypes.STRING, note),
                ScalarQueryParameter("start_time", SqlParameterScalarTypes.TIMESTAMP, start_time),
                ScalarQueryParameter("end_time", SqlParameterScalarTypes.TIMESTAMP, end_time),
                ScalarQueryParameter("is_billable", SqlParameterScalarTypes.BOOL, is_billable),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.add_time_entry(@id, @project, @note, @start_time, @end_time, @is_billable);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def delete_time_entry(
        self,
        id: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
            ]
        )

        return self._query(
            target=f"DELETE FROM {self.timesheet_id} WHERE id = @id",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def archive_project(
        self,
        name: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.archive_project(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def archive_time_entries(
        self,
        name: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.archive_time_entries(@name);",
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
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("description", SqlParameterScalarTypes.STRING, description),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.create_project(@name, @description);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def delete_project(
        self,
        name: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.delete_project(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def delete_time_entries(
        self,
        project: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter(
                    "project", SqlParameterScalarTypes.STRING, project
                ),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.delete_time_entries(@project);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def edit_time_entry(
        self,
        set_clause: t.Any,
        id: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
            ]
        )

        return self._query(
            target="CALL %s.edit_time_entry(%s, @id);"
            % (self.dataset_main, set_clause),
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def end_time_entry(
        self,
        id: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.end_time_entry(@id);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def get_time_entry(
        self,
        id: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
            ]
        )

        return self._query(
            target=f"SELECT * FROM {self.timesheet_id} WHERE id = @id",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def create_snapshot(
        self,
        name: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.create_snapshot(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def restore_snapshot(
        self,
        snapshot_table: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter(
                    "snapshot_table",
                    SqlParameterScalarTypes.STRING,
                    snapshot_table,
                ),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.restore_snapshot(@snapshot_table);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    @property
    def _resume_time_entry(self) -> str:
        return f"CALL {self.dataset_main}.resume_time_entry(@id, @time_resume);"

    def resume_time_entry(
        self,
        id: str,
        time_resume: "datetime",
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter(
                    "time_resume", SqlParameterScalarTypes.TIMESTAMP, time_resume
                ),
            ]
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
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.unarchive_project(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def unarchive_time_entries(
        self,
        name: str,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.unarchive_time_entries(@name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_notes(
        self,
        new_note,
        old_note,
        project,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("new_note", SqlParameterScalarTypes.STRING, new_note),
                ScalarQueryParameter("old_note", SqlParameterScalarTypes.STRING, old_note),
                ScalarQueryParameter("project", SqlParameterScalarTypes.STRING, project),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.update_notes(@new_note, @old_note, @project);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_project_description(
        self,
        name: str,
        desc,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("desc", SqlParameterScalarTypes.STRING, desc),
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.update_project_description(@name, @desc);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_project_name(
        self,
        name: str,
        new_name,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("new_name", SqlParameterScalarTypes.STRING, new_name),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.update_project_name(@name, @new_name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def update_time_entry_projects(
        self,
        name: str,
        new_name,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("name", SqlParameterScalarTypes.STRING, name),
                ScalarQueryParameter("new_name", SqlParameterScalarTypes.STRING, new_name),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.update_time_entry_projects(@name, @new_name);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def pause_time_entry(
        self,
        id: str,
        time_paused: "datetime",
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            # fmt: off
            query_parameters=[
                ScalarQueryParameter("id", SqlParameterScalarTypes.STRING, id),
                ScalarQueryParameter("time_paused", SqlParameterScalarTypes.TIMESTAMP, time_paused),
            ]
            # fmt: on
        )

        return self._query(
            target=f"CALL {self.dataset_main}.pause_time_entry(@id, @time_paused);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def list_time_entries_range(
        self,
        start_date: "datetime",
        end_date: "datetime",
        where_clause: str | None = None,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                # fmt: off
                ScalarQueryParameter("start_date", SqlParameterScalarTypes.TIMESTAMP, start_date),
                ScalarQueryParameter("end_date", SqlParameterScalarTypes.TIMESTAMP, end_date),
                ScalarQueryParameter("where_clause", SqlParameterScalarTypes.STRING, where_clause),
                # fmt: on
            ]
        )

        target = cleandoc(
            f"""
            SELECT
              LEFT(id, 7) AS id,
              date,
              CAST(FORMAT_DATETIME("%T", start) AS TIME) AS start,
              CAST(FORMAT_DATETIME("%T", `end`) AS TIME) AS `end`,
              project,
              note,
              is_billable AS billable,
              is_active AS active,
              is_paused AS paused,
              ROUND(IFNULL(paused_hrs, {self.dataset_main}.current_paused_hrs(is_paused, time_paused, paused_hrs)), 4) AS paused_hrs,
              ROUND(IFNULL(duration, {self.dataset_main}.duration(timestamp_end, timestamp_start, is_paused, time_paused, paused_hrs)), 4) AS duration,
              ROUND(
                SUM(IFNULL(duration, {self.dataset_main}.duration(timestamp_end, timestamp_start, is_paused, time_paused, paused_hrs))) OVER(timer), 4
              ) AS total,
            FROM
              {self.timesheet_id}
            WHERE
              date BETWEEN DATE(@start_date) AND DATE(@end_date)
              AND is_archived IS FALSE 
              {'AND (' + where_clause + ')' if where_clause else ''}
            WINDOW
              timer AS (
                ORDER BY timestamp_start, timestamp_end
              )
            ORDER BY
              timestamp_start,
              timestamp_end;
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

    def list_time_entries(
        self,
        date: "datetime",
        where_clause: str | None = None,
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                # fmt: off
                ScalarQueryParameter("date", SqlParameterScalarTypes.TIMESTAMP, date),
                ScalarQueryParameter("where_clause", SqlParameterScalarTypes.STRING, where_clause),
                # fmt: on
            ],
        )

        target = cleandoc(
            f"""
            SELECT
              LEFT(id, 7) AS id,
              date,
              CAST(FORMAT_DATETIME("%T", start) AS TIME) AS start,
              CAST(FORMAT_DATETIME("%T", `end`) AS TIME) AS `end`,
              project,
              note,
              is_billable AS billable,
              is_active AS active,
              is_paused AS paused,
              ROUND(IFNULL(paused_hrs, {self.dataset_main}.current_paused_hrs(is_paused, time_paused, paused_hrs)), 4) AS paused_hrs,
              ROUND(IFNULL(duration, {self.dataset_main}.duration(timestamp_end, timestamp_start, is_paused, time_paused, paused_hrs)), 4) AS duration,
              ROUND(
                SUM(IFNULL(duration, {self.dataset_main}.duration(timestamp_end, timestamp_start, is_paused, time_paused, paused_hrs))) OVER(timer), 4
              ) AS total,
            FROM
              {self.timesheet_id}
            WHERE
              date = DATE(@date) AND is_archived IS FALSE 
              {'AND (' + where_clause + ')' if where_clause else ''}
            WINDOW
              timer AS (
                ORDER BY timestamp_start, timestamp_end
              )
            ORDER BY
              timestamp_start,
              timestamp_end;
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

    def report(
        self,
        start_date: t.Optional["datetime"] = None,
        end_date: t.Optional["datetime"] = None,
        where_clause: str | None = None,
        round_: bool | None = None,
        type_: t.Literal["table", "file"] = "table",
        wait: bool = False,
        render: bool = False,
        status: t.Optional["Status"] = None,
        status_renderable: t.Optional["RenderableType"] = None,
    ) -> "QueryJob":
        job_config = QueryJobConfig(
            query_parameters=[
                # fmt: off
                ScalarQueryParameter("start_date", SqlParameterScalarTypes.TIMESTAMP, start_date),
                ScalarQueryParameter("end_date", SqlParameterScalarTypes.TIMESTAMP, end_date),
                ScalarQueryParameter("where_clause", SqlParameterScalarTypes.STRING, where_clause),
                ScalarQueryParameter("round_", SqlParameterScalarTypes.BOOL, round_),
                ScalarQueryParameter("type_", SqlParameterScalarTypes.STRING, type_),
                # fmt: on
            ]
        )

        return self._query(
            target=f"CALL {self.dataset_main}.report(@start_date, @end_date, @where_clause, @round_, @type_);",
            job_config=job_config,
            wait=wait,
            render=render,
            status=status,
            status_renderable=status_renderable,
        )

    def select(
        self,
        resource: str,
        fields: t.Sequence[str] = ["*"],
        where: t.Optional[t.Sequence[str]] = None,
        order: t.Optional[t.Sequence[str]] = None,
        distinct: bool = False,
        wait: bool = False,
        render: bool = False,
    ) -> "QueryJob":
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
        return self._query(target=query, wait=wait, render=render)

    @property
    def _all_routines_ids(self) -> list[str]:
        return [
            "add_time_entry",
            "archive_project",
            "archive_time_entries",
            "create_project",
            "create_snapshot",
            "current_paused_hrs",
            "delete_project",
            "delete_time_entries",
            "duration",
            "edit_time_entry",
            "end_time_entry",
            "now",
            "pause_time_entry",
            "report",
            "restore_snapshot",
            "resume_time_entry",
            "rounding_step",
            "start_time_entry",
            "unarchive_project",
            "unarchive_time_entries",
            "update_notes",
            "update_project_description",
            "update_project_name",
            "update_time_entry_projects",
        ]

    def _elapsed_time(self, query_job: "QueryJob", start: float | None = None) -> str:
        if start:
            ts = round((perf_counter_ns() - start) * 1.0e-9, 4)
            return f"{ts}"
        if query_job.ended:
            ts = round(query_job.ended.timestamp() - query_job.started.timestamp(), 4)
            return f"{ts}"
        if time() > query_job.started.timestamp():
            ts = round(time() - query_job.started.timestamp(), 4)
            return f"{ts}"
        return ""

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
            status.update(f"{status_message} " f"{elapsed_time.markup}")

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

    def cancel_job(self, query_job: "QueryJob") -> None:
        cancel_job = query_job.cancel()

        if cancel_job:
            raise click.UsageError(
                message=self._format_job_cancel_message(query_job).markup,
                ctx=click.get_current_context(),
            )
        else:
            raise click.UsageError(
                message=Text.assemble(
                    markup.br("Failed to request job cancel"),
                    ", see the job results in console.\n",
                    markup.repr_url(self._query_job_url(query_job)),
                ).markup,
                ctx=click.get_current_context(),
            )

    def _query_job_url(self, query_job: "QueryJob") -> str:
        url = (
            "{base_url}project={project_id}&j=bq:{region}:{job_id}&{end_point}".format(
                base_url="https://console.cloud.google.com/bigquery?",
                project_id=query_job.project,
                region=query_job.location,
                job_id=query_job.job_id,
                end_point="page=queryresults",
            )
        )
        return url
