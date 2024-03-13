from __future__ import annotations

import re
import threading
import typing as t
from contextlib import contextmanager, suppress
from datetime import datetime
from decimal import Decimal
from functools import cached_property, reduce
from operator import truth

import fasteners  # type: ignore[import-untyped, import-not-found]
import rich_click as click
import rtoml
from more_itertools import first, locate, one, unique_everseen
from rich import box, get_console
from rich.measure import Measurement
from rich.rule import Rule
from rich.table import Table

from lightlike.__about__ import __appname_sc__
from lightlike.app import _get, render
from lightlike.app.config import AppConfig
from lightlike.app.routines import CliQueryRoutines
from lightlike.internal import appdir, utils

if t.TYPE_CHECKING:
    from pathlib import Path

    from fasteners import ReaderWriterLock
    from google.cloud.bigquery import QueryJob
    from google.cloud.bigquery.table import Row
    from rich.console import Console, ConsoleOptions, RenderResult

__all__: t.Sequence[str] = ("TomlCache", "EntryIdList", "EntryAppData")


T = t.TypeVar("T")
P = t.ParamSpec("P")


class TomlCache:
    __slots__: t.ClassVar[t.Sequence[str]] = ("_entries",)
    _path: t.ClassVar[Path] = appdir.CACHE
    _rw_lock: t.ClassVar["ReaderWriterLock"] = fasteners.ReaderWriterLock()

    def __init__(self) -> None:
        with self._rw_lock.read_lock():
            self._entries = rtoml.load(self._path)

    def __bool__(self) -> bool:
        return truth(self.id)

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        now = AppConfig().now

        table_running_entries = Table(
            box=box.MARKDOWN,
            border_style="bold",
            show_header=True,
        )
        reduce(
            lambda n, c: table_running_entries.add_column(
                c[0].removeprefix("is_"), **self._map_s_columns(c)
            ),
            self.running_entries[0].items(),
            None,
        )
        reduce(
            lambda n, r: table_running_entries.add_row(
                *render.map_cell_style(r.values()),
                style=self._map_rstyle(r),
            ),
            self.running_entries,
            None,
        )

        table_paused_entries = Table(
            box=box.MARKDOWN,
            border_style="bold",
            show_header=True,
        )
        reduce(
            lambda n, c: table_paused_entries.add_column(
                c[0].removeprefix("is_"), **self._map_s_columns(c)
            ),
            self.running_entries[0].items(),
            None,
        )

        paused_entries = []
        for entry in self.paused_entries:
            new_paused_hr = self._add_hours(
                now,
                entry.copy()["time_paused"],
                entry.copy()["paused_hrs"],
            )
            entry["paused_hrs"] = str(round(new_paused_hr, 4))
            paused_entries.append(entry)

        reduce(
            lambda n, r: table_paused_entries.add_row(
                *render.map_cell_style(r.values()),
                style=self._map_rstyle(r),
            ),
            paused_entries,
            None,
        )

        table = Table(
            box=box.MARKDOWN,
            border_style="bold",
            show_edge=False,
            show_header=False,
        )
        table.add_row()
        table.add_row(
            Rule(
                title="[b]running",
                characters="- ",
                align="left",
                style="bold",
            ),
        )
        table.add_row(table_running_entries)
        table.add_row(
            Rule(
                title="[b]paused",
                characters="- ",
                align="left",
                style="bold",
            ),
        )
        table.add_row(table_paused_entries)

        yield table

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return Measurement(100, options.max_width)

    @contextmanager
    def update(self) -> t.Generator[TomlCache, t.Any, None]:
        try:
            with self._rw_lock.read_lock():
                yield self
        finally:
            with self._rw_lock.write_lock():
                self._path.write_text(self._to_toml)
            with self._rw_lock.read_lock():
                self._entries = rtoml.load(self._path)

    @property
    def _to_toml(self) -> str:
        return utils._format_toml(self._entries)

    def start_new_active_timer(self) -> None:
        with self.update():
            self.running_entries.insert(
                0,
                {
                    "project": None,
                    "id": None,
                    "start": None,
                    "note": None,
                    "is_billable": None,
                    "is_paused": False,
                    "time_paused": None,
                    "paused_hrs": 0,
                },
            )

    def switch_active_entry(self, _id) -> None:
        with self.update():
            idx = one(self._find_entries(self.running_entries, "id", [_id]))
            self.running_entries.insert(0, self.running_entries.pop(idx))

    def get_updated_paused_entries(self, now: datetime) -> list[dict[str, t.Any]]:
        updated_paused_entries = []

        for entry in self.paused_entries:
            copy = entry.copy()
            copy["paused_hrs"] = str(
                self._add_hours(now, entry["time_paused"], entry["paused_hrs"])
            )
            updated_paused_entries.append(copy)

        return updated_paused_entries

    def resume_paused_time_entry(self, _id: str, now: datetime) -> None:
        with self.update():
            idx = one(self._find_entries(self.paused_entries, "id", [_id]))
            entry = self.paused_entries[idx]
            entry["paused_hrs"] = str(
                self._add_hours(now, entry["time_paused"], entry["paused_hrs"])
            )
            entry["is_paused"] = False
            entry["time_paused"] = None

            if not self:
                self.running_entries.pop(0)

            self.running_entries.insert(0, entry)
            self.paused_entries.pop(idx)

    def put_active_entry_on_pause(self, time_paused: datetime) -> None:
        with self.update():
            self.active["is_paused"] = True
            self.active["time_paused"] = time_paused
            self.running_entries.insert(1, self.default_entry)
            self.paused_entries.append(self.running_entries.pop(0))

    def _clear_active(self) -> None:
        with self.update():
            self.running_entries.insert(1, self.default_entry)
            self.running_entries.pop(0)

    def _find_entries(
        self, entries: list[dict[str, t.Any]], key: str, sequence: t.Sequence[str]
    ) -> t.Iterable[int]:
        predicate = lambda e: (any([e[key].startswith(s) for s in sequence]))
        return list(locate(entries, predicate))

    def _if_any_entries(
        self, entries: list[dict[str, t.Any]], id_sequence: t.Sequence[str]
    ) -> bool:
        if self._find_entries(entries, "id", id_sequence):
            return True
        return False

    def _get_any_entries(
        self, entries: list[dict[str, t.Any]], key: str, sequence: t.Sequence[str]
    ) -> list[dict[str, t.Any]]:
        idxs = self._find_entries(entries, key, sequence)
        matching_entries = (
            list(map(lambda i: entries[i], idxs)) if idxs is not None else []
        )
        return matching_entries

    def _remove_entries(
        self,
        entries: t.Sequence[list[dict[str, t.Any]]],
        key: str,
        sequence: t.Sequence[str],
    ) -> None:
        with self.update():
            for entry_list in entries:
                if idxs := self._find_entries(entry_list, key, sequence):
                    for idx in idxs:
                        entry_list.pop(idx)

    def _add_hours(
        self, now: datetime, time_paused: datetime, paused_hrs: Decimal
    ) -> Decimal:
        diff = now - t.cast(datetime, time_paused)
        prev_paused_sec = Decimal(paused_hrs) * 3600
        new_paused_sec = Decimal(diff.total_seconds()) + prev_paused_sec
        new_paused_hr = Decimal(round((new_paused_sec / 3600), 4))
        return new_paused_hr

    def _to_meta(
        self,
        entry: dict[str, t.Any],
        now: datetime,
        truncate_note: bool = False,
    ) -> str:
        meta = "project={project}".format(project=entry.get("project"))

        meta += ", is_billable={is_billable}".format(
            is_billable=entry.get("is_billable")
        )

        if _note := self._ifnull(entry["note"]):
            if truncate_note:
                note = f"{_note[:30]}..."
            else:
                note = _note
            meta += ", note={note}".format(note=note)

        start = entry.get("start")
        if start and start != "null":
            meta += ", start={start_date}{start_time}".format(
                start_date=f"{start.date()}-" if start.date() != now.date() else "",
                start_time=start.time(),
            )

        time_paused = entry.get("time_paused")
        if time_paused and time_paused != "null":
            meta += ", paused={paused_date}{paused_time}".format(
                paused_date=(
                    f"{time_paused.date()}-" if time_paused.date() != now.date() else ""
                ),
                paused_time=time_paused.time(),
            )
            meta += ", paused_hrs={paused_hrs}".format(
                paused_hrs=entry["paused_hrs"],
            )

        return f"[{meta}]"

    def _validate_toml_cache(self) -> None:
        try:
            self._path.touch(exist_ok=True)
            if not utils._identical_vectors(
                list(self.active.keys()),
                list(self.default_entry.keys()),
            ):
                with self.update():
                    self._entries = self.default
        except Exception:
            with self.update():
                self._entries = self.default

    def _sync_cache(self) -> None:
        from lightlike.app.routines import CliQueryRoutines

        routine = CliQueryRoutines()
        running_entries_to_cache = routine.select(
            resource=routine.timesheet_id,
            fields=["*"],
            where="is_active IS TRUE",
            order="timestamp_start",
        )
        paused_entries_to_cache = routine.select(
            resource=routine.timesheet_id,
            fields=["*"],
            where="is_paused IS TRUE",
            order="timestamp_start",
        )

        running_entries = []
        paused_entries = []

        for row in list(running_entries_to_cache):
            running_entries.append(
                dict(
                    project=row.project,
                    id=row.id,
                    start=AppConfig().in_app_timezone(row.timestamp_start),
                    note=row.note,
                    is_billable=row.is_billable,
                    is_paused=row.is_paused,
                    time_paused="null",
                    paused_hrs=str(Decimal(row.paused_hrs or 0)),
                )
            )

        if not running_entries:
            running_entries = self.default["running"]["entries"]

        for row in list(paused_entries_to_cache):
            paused_entries.append(
                dict(
                    project=row.project,
                    id=row.id,
                    start=AppConfig().in_app_timezone(row.timestamp_start),
                    note=row.note,
                    is_billable=row.is_billable,
                    is_paused=row.is_paused,
                    time_paused=AppConfig().in_app_timezone(row.time_paused),
                    paused_hrs=str(round(Decimal(row.paused_hrs or 0), 4)),
                )
            )

        get_console().set_window_title(__appname_sc__)
        with self.update() as cache:
            cache.running_entries = running_entries
            cache.paused_entries = paused_entries

    @property
    def default(self) -> dict[str, t.Any]:
        return {
            "running": {
                "entries": [
                    {
                        "project": None,
                        "id": None,
                        "start": None,
                        "note": None,
                        "is_billable": None,
                        "is_paused": False,
                        "time_paused": None,
                        "paused_hrs": 0,
                    }
                ],
            },
            "paused": {
                "entries": [],
            },
        }

    @property
    def default_entry(self):
        return self.default["running"]["entries"][0]

    @property
    def count_running_entries(self) -> int:
        return len(list(filter(lambda e: e != {}, self.running_entries)))

    @property
    def count_paused_entries(self) -> int:
        return len(list(filter(lambda e: e != {}, self.paused_entries)))

    @property
    def running_entries(self) -> list[dict[str, t.Any]]:
        return self._entries["running"]["entries"]

    @running_entries.setter
    def running_entries(self, __val: T) -> None:
        self._entries["running"]["entries"] = __val

    @property
    def active(self) -> dict[str, t.Any]:
        return self.running_entries[0]

    @property
    def paused_entries(self) -> list[dict[str, t.Any]]:
        try:
            return self._entries["paused"]["entries"]
        except KeyError:
            with self.update():
                self._entries["paused"]["entries"] = []
            return self._entries["paused"]["entries"]

    @paused_entries.setter
    def paused_entries(self, __val: T) -> None:
        self._entries["paused"]["entries"] = __val

    @property
    def project(self) -> str:
        return t.cast(str, self._ifnull(self.active["project"]))

    @project.setter
    def project(self, __val: T) -> None:
        self.active["project"] = __val

    @property
    def id(self) -> str:
        return t.cast(str, self._ifnull(_get.id(self.active)))

    @id.setter
    def id(self, __val: T) -> None:
        self.active["id"] = __val

    @property
    def start(self) -> datetime:
        start = t.cast(datetime, self._ifnull(self.active["start"]))
        if start and (start.tzinfo is None or start.tzinfo.utcoffset(start) is None):
            start = AppConfig().in_app_timezone(start)
            with self.update() as cache:
                cache.start = start
        return start

    @start.setter
    def start(self, __val: T) -> None:
        self.active["start"] = __val

    @property
    def note(self) -> str:
        return t.cast(str, self._ifnull(self.active["note"]))

    @note.setter
    def note(self, __val: T) -> None:
        self.active["note"] = __val

    @property
    def is_billable(self) -> bool:
        return t.cast(bool, self._ifnull(self.active["is_billable"]))

    @is_billable.setter
    def is_billable(self, __val: T) -> None:
        self.active["is_billable"] = __val

    @property
    def time_paused(self) -> datetime:
        time_paused = t.cast(datetime, self._ifnull(self.active["time_paused"]))
        if time_paused and (
            time_paused.tzinfo is None
            or time_paused.tzinfo.utcoffset(time_paused) is None
        ):
            time_paused = AppConfig().in_app_timezone(time_paused)
            with self.update() as cache:
                cache.time_paused = time_paused
        return time_paused

    @time_paused.setter
    def time_paused(self, __val: T) -> None:
        self.active["time_paused"] = __val

    @property
    def is_paused(self) -> bool:
        return t.cast(bool, self._ifnull(self.active["is_paused"]))

    @is_paused.setter
    def is_paused(self, __val: T) -> None:
        self.active["is_paused"] = __val

    @property
    def paused_hrs(self) -> Decimal:
        return Decimal(self._ifnull(self.active["paused_hrs"]) or 0)

    @paused_hrs.setter
    def paused_hrs(self, __val: T) -> None:
        self.active["paused_hrs"] = f"{__val}"

    def _map_rstyle(self, row: dict[str, t.Any]) -> str:
        if row == self.running_entries[0]:
            return "bold"
        elif self._ifnull(row["time_paused"]):
            return "#888888"
        else:
            return ""

    @staticmethod
    def _ifnull(attr: T) -> T | None:
        return attr if attr != "null" else None

    @staticmethod
    def _map_s_columns(items: t.Sequence[t.Any]) -> dict[str, t.Any]:
        _kwargs: dict[str, t.Any] = dict(vertical="top")

        if items[0] == "id":
            _kwargs |= dict(
                header_style="green",
                overflow="crop",
                min_width=7,
                max_width=7,
            )
        elif items[0] == "note":
            _kwargs |= dict(header_style="green")
            if get_console().width >= 150:
                _kwargs |= dict(
                    overflow="fold",
                    min_width=50,
                    max_width=50,
                )
            elif get_console().width < 150:
                _kwargs |= dict(
                    overflow="ellipsis",
                    no_wrap=True,
                    min_width=25,
                    max_width=25,
                )
        elif items[0] == "project":
            _kwargs |= dict(header_style="green")
            if get_console().width >= 130:
                _kwargs |= dict(
                    overflow="fold",
                    min_width=20,
                    max_width=20,
                )
            elif get_console().width < 130:
                _kwargs |= dict(
                    overflow="ellipsis",
                    no_wrap=True,
                    min_width=10,
                    max_width=10,
                )
        elif items[0] == "paused_hrs":
            _kwargs |= dict(
                justify="right",
                header_style="cyan",
                overflow="crop",
                min_width=8,
                max_width=8,
            )
        elif items[0] in ("start", "time_paused", "paused"):
            _kwargs |= dict(
                justify="left",
                header_style="yellow",
                overflow="crop",
                min_width=19,
                max_width=19,
            )
        elif any([n in items[0] for n in ("billable", "paused")]):
            _kwargs |= dict(
                justify="left",
                header_style="red",
            )
            if get_console().width < 150:
                _kwargs |= dict(
                    overflow="ignore",
                    min_width=1,
                    max_width=1,
                )

        return _kwargs


class _EntryIdListSingleton(type):
    _instances: t.ClassVar[dict[object, _EntryIdListSingleton]] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args: P.args, **kwargs: P.kwargs) -> _EntryIdListSingleton:
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super(type(cls), cls).__call__(*args, **kwargs)
        return cls._instances[cls]


get_console().log("Validating cache")
TomlCache()._validate_toml_cache()


class EntryIdList(metaclass=_EntryIdListSingleton):
    id_pattern: t.Final[re.Pattern] = re.compile("^\w{7,40}$")

    @cached_property
    def ids(self) -> list[str]:
        routine = CliQueryRoutines()
        ids = routine.select(resource=routine.timesheet_id, fields=["id"])
        return list(map(_get.id, ids))

    def clear(self) -> None:
        del self.__dict__["ids"]

    def match_id(self, input_id: str) -> str:
        matching = list(filter(lambda i: i.startswith(input_id), self.ids))

        if not self.id_pattern.match(input_id):
            raise click.ClickException(
                message="[repr.str]%s[/repr.str] is not a valid ID. "
                "Must provide ID matching regex [code]^\w{7,40}$[/code]" % input_id
            )
        elif len(matching) >= 2:
            raise click.ClickException(
                message=f"Multiple possible entries starting with [code]{input_id}[/code]. "
                "Use a longer string to match ID."
            )
        elif not matching:
            raise click.ClickException(
                message=f"Cannot find entry ID: [code]{input_id}[/code]"
            )
        else:
            return first(matching)

    def reset(self) -> None:
        with suppress(Exception):
            self.clear()
        self.ids

    def add(self, input_id: str) -> None:
        self.ids.extend([input_id])


class EntryAppData:
    path: t.ClassVar[Path] = appdir.ENTRY_APPDATA

    def update(self, query_job: t.Optional["QueryJob"] = None) -> None:
        routine = CliQueryRoutines()
        query_job_projects = routine.select(
            resource=CliQueryRoutines().projects_id,
            fields=["*"],
        )

        appdata: dict[str, t.Any] = {"active": {}, "archived": {}}
        for row in list(query_job_projects):
            project = {}
            project["name"] = row.name
            project["description"] = row.description
            project["created"] = row.created
            project["meta"] = self._project_meta(row)
            project["notes"] = []
            if not row.archived:
                appdata["active"].update({row.name: project})
            else:
                appdata["archived"].update({row.name: project})

        if query_job and not query_job.done():
            query_job.result()  # Wait for timer:run to complete.

        query_job_notes = routine.select(
            resource=CliQueryRoutines().timesheet_id,
            fields=["project", "note", "timestamp_start"],
            order="project, timestamp_start desc",
        )

        rows = list(query_job_notes)

        try:
            projects = sorted(set(row.project for row in rows))
        except TypeError:
            ctx = click.get_current_context()
            ctx.fail(
                "[b][red]**WARNING**[/b][/red]. "
                "[red]Incomplete rows found in timesheet table. "
                "Remove these records before continuing to use this CLI."
            )

        def _map_notes(a: dict[str, t.Any], p: t.Any) -> dict[str, t.Any]:
            nonlocal appdata, rows
            __key = "active" if p in appdata["active"] else "archived"
            with suppress(Exception):
                appdata[__key][p].update({"notes": self._unique_notes(p, rows)})
            return appdata

        reduce(_map_notes, projects, appdata)
        self.path.write_text(rtoml.dumps(appdata), encoding="utf-8")

    def _unique_notes(self, project: str, rows: t.Sequence["Row"]) -> list["Row"]:
        return list(unique_everseen(map(_get.note, self._filter_notes(project, rows))))

    def _filter_notes(self, project: str, rows: t.Sequence["Row"]) -> list["Row"]:
        return list(filter(lambda r: r.project == project and r.note, rows))

    def _project_meta(self, row: "Row") -> str:
        return "".join(
            [
                "[",
                f"created={row.created.date()}",
                f", desc={row.description}" if row.description else "",
                f", archived={row.archived.date()}" if row.archived else "",
                "]",
            ]
        )


def never(arg: t.Any) -> t.Never: ...  # type: ignore[empty-body]
