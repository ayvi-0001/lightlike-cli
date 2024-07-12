# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import re
import typing as t
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from functools import cached_property, reduce
from operator import truth, xor
from pathlib import Path

import click
import rtoml
from fasteners import ReaderWriterLock
from more_itertools import first, locate, map_except, one, unique_everseen
from prompt_toolkit.patch_stdout import patch_stdout
from pytz import timezone
from rich import box, get_console
from rich.markup import escape
from rich.measure import Measurement
from rich.table import Table
from rich.text import Text

from lightlike import _console
from lightlike.__about__ import __appname_sc__
from lightlike.app import _get, dates, render
from lightlike.app.config import AppConfig
from lightlike.app.routines import CliQueryRoutines
from lightlike.internal import appdir, factory, markup, utils

if t.TYPE_CHECKING:
    from google.cloud.bigquery import QueryJob
    from google.cloud.bigquery.table import Row
    from rich.console import Console, ConsoleOptions, RenderResult

__all__: t.Sequence[str] = ("TimeEntryCache", "TimeEntryIdList", "TimeEntryAppData")


T = t.TypeVar("T")
P = t.ParamSpec("P")


class TimeEntryCache:
    __slots__: t.Sequence[str] = ("_entries", "_path")
    _rw_lock: ReaderWriterLock = ReaderWriterLock()

    def __init__(self, path: Path = appdir.CACHE) -> None:
        self._path = path

        with self._rw_lock.read_lock():
            self._entries = rtoml.load(self._path)

    def __bool__(self) -> bool:
        return truth(self.id)

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        now: datetime = dates.now(timezone(AppConfig().get("settings", "timezone")))

        fields = [
            "id",
            "start",
            "timestamp_paused",
            "project",
            "note",
            "billable",
            "paused",
            "paused_hours",
            "hours",
        ]

        entries = []
        for entry in self.running_entries.copy():
            if not self._ifnull(entry["id"]):
                continue

            if self._ifnull(entry["start"]):
                hours = dates.calculate_duration(
                    start_date=entry["start"],
                    end_date=now,
                    paused_hours=Decimal(entry["paused_hours"] or 0),
                )
                entry["hours"] = hours
            else:
                entry["hours"] = 0

            entries.append(entry)

        for entry in self.paused_entries.copy():
            new_paused_hour = self._add_hours(
                now, entry["timestamp_paused"], entry["paused_hours"]
            )
            hours = dates.calculate_duration(
                start_date=entry["start"],
                end_date=now,
                paused_hours=new_paused_hour,
            )

            entry["paused_hours"] = round(new_paused_hour, 4)
            entry["hours"] = hours or 0
            entries.append(entry)

        if not entries:
            console.print(markup.dimmed("No entries found"))
            return

        if console.width <= 125:
            console.print_json(data=entries, default=str, indent=4)
            return

        table = Table(box=box.MARKDOWN, border_style="bold", show_header=True)
        reduce(
            lambda n, f: table.add_column(
                f, **self._map_column_styles(f, get_console().width)
            ),
            fields,
            None,
        )
        reduce(
            lambda n, r: table.add_row(
                *render.map_cell_style(r.values()),
                style=self._map_row_style(r),
            ),
            entries,
            None,
        )
        yield table

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return Measurement(140, options.max_width)

    @contextmanager
    def rw(self) -> t.Generator[TimeEntryCache, t.Any, None]:
        try:
            with self._rw_lock.read_lock():
                yield self
        finally:
            with self._rw_lock.write_lock():
                self._path.write_text(self._serialize)
            with self._rw_lock.read_lock():
                self._entries = rtoml.load(self._path)

    @property
    def _serialize(self) -> str:
        return utils._format_toml(self._entries)

    def start_new_active_time_entry(self) -> None:
        with self.rw():
            self.running_entries.insert(
                0,
                {
                    "id": None,
                    "start": None,
                    "timestamp_paused": None,
                    "project": None,
                    "note": None,
                    "billable": None,
                    "paused": None,
                    "paused_hours": "0",
                },
            )

    def switch_active_entry(
        self, entry_id: str, now: datetime, continue_: bool
    ) -> None:
        if idx := self.index(self.running_entries, "id", [entry_id]):
            with self.rw():
                self.running_entries.insert(0, self.running_entries.pop(one(idx)))
            if not continue_:
                self.pause_entry(one(idx), now)
        else:
            if not continue_:
                self.pause_entry(0, now)
            self.resume_entry(entry_id, now)

    def resume_entry(self, _id: str, now: datetime) -> None:
        with self.rw():
            idx = one(self.index(self.paused_entries, "id", [_id]))
            entry = self.paused_entries[idx]
            paused_hours = self._add_hours(
                now, entry["timestamp_paused"], entry["paused_hours"]
            )
            entry["paused_hours"] = str(round(paused_hours, 4))
            entry["paused"] = False
            entry["timestamp_paused"] = None

            if not self:
                self.running_entries.pop(0)

            self.running_entries.insert(0, entry)
            self.paused_entries.pop(idx)

    def pause_entry(self, idx: int, timestamp: datetime) -> None:
        if idx == 0:
            with self.rw():
                self.active["paused"] = True
                self.active["timestamp_paused"] = timestamp
                self.paused_entries.append(self.active.copy())
                if self.count_running_entries == 1:
                    self.id = None  # type: ignore[assignment]
                    self.start = None  # type: ignore[assignment]
                    self.timestamp_paused = None  # type: ignore[assignment]
                    self.project = None  # type: ignore[assignment]
                    self.note = None  # type: ignore[assignment]
                    self.billable = None  # type: ignore[assignment]
                    self.paused = False
                    self.paused_hours = "0"  # type: ignore[assignment]
                else:
                    self.running_entries.pop(0)
        else:
            with self.rw():
                entry = self.running_entries.pop(idx)
                entry["paused"] = True
                entry["timestamp_paused"] = timestamp
                self.paused_entries.append(entry)

    def _clear_active(self) -> None:
        with self.rw():
            if self.count_running_entries == 1:
                self.id = None  # type: ignore[assignment]
                self.start = None  # type: ignore[assignment]
                self.timestamp_paused = None  # type: ignore[assignment]
                self.project = None  # type: ignore[assignment]
                self.note = None  # type: ignore[assignment]
                self.billable = None  # type: ignore[assignment]
                self.paused = False
                self.paused_hours = "0"  # type: ignore[assignment]
            else:
                self.running_entries.pop(0)

    def index(
        self,
        entries: list[dict[str, t.Any]],
        key: str,
        sequence: t.Sequence[str],
    ) -> t.Iterable[int]:
        predicate = lambda e: (any([e[key].startswith(s) for s in sequence]))
        return list(locate(entries, predicate))

    def exists(
        self,
        entries: list[dict[str, t.Any]],
        id_sequence: t.Sequence[str],
    ) -> bool:
        return True if self.index(entries, "id", id_sequence) else False

    def get(
        self,
        entries: list[dict[str, t.Any]],
        key: str,
        sequence: t.Sequence[str],
    ) -> list[dict[str, t.Any]]:
        idxs = self.index(entries, key, sequence)
        matching_entries = list(map_except(lambda i: entries[i], idxs, IndexError))
        return matching_entries or []

    def remove(
        self,
        entries: list[list[dict[str, t.Any]]],
        key: str,
        sequence: t.Sequence[str],
    ) -> None:
        with self.rw():
            for entry_list in entries:
                if idxs := self.index(entry_list, key, sequence):
                    for idx in idxs:
                        entry_list.pop(idx)

    def _add_hours(
        self, now: datetime, timestamp_paused: datetime, paused_hours: Decimal
    ) -> Decimal:
        diff: timedelta = now - timestamp_paused
        prev_paused_sec = Decimal(paused_hours) * Decimal(3600)
        new_paused_sec = Decimal(diff.total_seconds()) + prev_paused_sec
        new_paused_hours = Decimal(new_paused_sec) / Decimal(3600)
        return new_paused_hours

    def get_updated_paused_entries(self, now: datetime) -> list[dict[str, t.Any]]:
        updated_paused_entries = []

        for entry in self.paused_entries:
            copy = entry.copy()
            paused_hours = self._add_hours(
                now, entry["timestamp_paused"], entry["paused_hours"]
            )
            copy["paused_hours"] = str(round(paused_hours, 4))
            updated_paused_entries.append(copy)

        return updated_paused_entries

    def _to_meta(
        self,
        entry: dict[str, t.Any],
        now: datetime,
    ) -> str:
        meta = "{project}".format(project=entry.get("project"))

        if _note := self._ifnull(entry["note"]):
            meta += ", {note}".format(
                note=f"{_note[:50]}…" if len(_note) > 50 else _note
            )
        else:
            start = entry.get("start")
            if start and start != "null":
                meta += ", start={start_date}{start_time}".format(
                    start_date=f"{start.date()}-" if start.date() != now.date() else "",
                    start_time=start.time(),
                )

        timestamp_paused = entry.get("timestamp_paused")
        if timestamp_paused and timestamp_paused != "null":
            meta += ", paused=True"
        else:
            meta += ", running=True"

        return f"[{meta}]"

    def _reset(self) -> None:
        with self.rw():
            self._entries = self.default

    def validate(self) -> None:
        try:
            if self._path.exists():
                if xor(
                    self._path.read_text() == "",
                    not utils._identical_vectors(
                        list(self.active.keys()),
                        list(self.default_entry.keys()),
                    ),
                ):
                    self._reset()
            else:
                self._path.touch(exist_ok=True)
                self._reset()
        except Exception:
            # If any exception occurs, hard reset cache.
            self._reset()

    def sync(self, debug: bool = False) -> None:
        routine = CliQueryRoutines()
        running_entries_to_cache = routine._select(
            resource=routine.timesheet_id,
            fields=["*"],
            where=["active IS TRUE"],
            order=["timestamp_start"],
        )
        paused_entries_to_cache = routine._select(
            resource=routine.timesheet_id,
            fields=["*"],
            where=["paused IS TRUE"],
            order=["timestamp_start"],
        )

        running_entries: list[dict[str, t.Any]] = []
        paused_entries: list[dict[str, t.Any]] = []

        tzinfo = timezone(AppConfig().get("settings", "timezone"))

        active_index: str | None = self.active["id"] if self else None

        for row in list(running_entries_to_cache):
            entry = dict(
                id=row.id,
                start=dates.astimezone(row.timestamp_start, tzinfo),
                timestamp_paused="null",
                project=row.project,
                note=row.note,
                billable=row.billable,
                paused=row.paused,
                paused_hours=str(round(Decimal(row.paused_hours or 0), 4)),
            )
            if row.id == active_index:
                running_entries.insert(0, entry)
            else:
                running_entries.append(entry)

        if not running_entries:
            running_entries = self.default["running"]["entries"]

        for row in list(paused_entries_to_cache):
            paused_entries.append(
                dict(
                    id=row.id,
                    start=dates.astimezone(row.timestamp_start, tzinfo),
                    timestamp_paused=dates.astimezone(row.timestamp_paused, tzinfo),
                    project=row.project,
                    note=row.note,
                    billable=row.billable,
                    paused=row.paused,
                    paused_hours=str(round(Decimal(row.paused_hours or 0), 4)),
                )
            )

        get_console().set_window_title(__appname_sc__)
        with self.rw() as cache:
            cache.running_entries = running_entries
            cache.paused_entries = paused_entries

    @property
    def default(self) -> dict[str, t.Any]:
        return {
            "running": {
                "entries": [
                    {
                        "id": None,
                        "start": None,
                        "timestamp_paused": None,
                        "project": None,
                        "note": None,
                        "billable": None,
                        "paused": None,
                        "paused_hours": "0",
                    }
                ],
            },
            "paused": {
                "entries": [],
            },
        }

    @property
    def default_entry(self) -> t.Any:
        return self.default["running"]["entries"][0]

    @property
    def count_running_entries(self) -> int:
        return len(list(filter(lambda e: e != {}, self.running_entries)))

    @property
    def count_paused_entries(self) -> int:
        return len(list(filter(lambda e: e != {}, self.paused_entries)))

    @property
    def running_entries(self) -> list[dict[str, t.Any]]:
        return t.cast(
            list[dict[str, t.Any]],
            self._entries["running"]["entries"],
        )

    @running_entries.setter
    def running_entries(self, __val: T) -> None:
        self._entries["running"]["entries"] = __val

    @property
    def active(self) -> dict[str, t.Any]:
        return self.running_entries[0]

    @property
    def paused_entries(self) -> list[dict[str, t.Any]]:
        try:
            return t.cast(
                list[dict[str, t.Any]],
                self._entries["paused"]["entries"],
            )
        except KeyError:
            with self.rw():
                self._entries["paused"]["entries"] = []
            return t.cast(
                list[dict[str, t.Any]],
                self._entries["paused"]["entries"],
            )

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
        return t.cast(str, self._ifnull(_get._id(self.active)))

    @id.setter
    def id(self, __val: T) -> None:
        self.active["id"] = __val

    @property
    def start(self) -> datetime:
        start = t.cast(datetime, self._ifnull(self.active["start"]))
        start = dates.astimezone(
            start, timezone(AppConfig().get("settings", "timezone"))
        )
        with self.rw() as cache:
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
    def billable(self) -> bool:
        return t.cast(bool, self._ifnull(self.active["billable"]))

    @billable.setter
    def billable(self, __val: T) -> None:
        self.active["billable"] = __val

    @property
    def timestamp_paused(self) -> datetime:
        timestamp_paused = t.cast(
            datetime, self._ifnull(self.active["timestamp_paused"])
        )
        timestamp_paused = dates.astimezone(
            timestamp_paused, timezone(AppConfig().get("settings", "timezone"))
        )
        with self.rw() as cache:
            cache.timestamp_paused = timestamp_paused
        return timestamp_paused

    @timestamp_paused.setter
    def timestamp_paused(self, __val: T) -> None:
        self.active["timestamp_paused"] = __val

    @property
    def paused(self) -> bool:
        return t.cast(bool, self._ifnull(self.active["paused"]))

    @paused.setter
    def paused(self, __val: T) -> None:
        self.active["paused"] = __val

    @property
    def paused_hours(self) -> Decimal:
        return Decimal(self._ifnull(self.active["paused_hours"]) or 0)

    @paused_hours.setter
    def paused_hours(self, __val: T) -> None:
        self.active["paused_hours"] = f"{__val}"

    def _map_row_style(self, row: dict[str, t.Any]) -> str:
        if row == self.running_entries[0]:
            return "bold"
        elif self._ifnull(row["timestamp_paused"]):
            return "#888888"
        else:
            return ""

    @staticmethod
    def _ifnull(attr: T) -> T | None:
        return attr if attr != "null" else None

    @staticmethod
    def _map_column_styles(
        field: t.Sequence[t.Any], console_width: int
    ) -> dict[str, t.Any]:
        _kwargs: dict[str, t.Any] = dict(
            vertical="top",
            no_wrap=True,
        )

        if field in ("project", "note"):
            _kwargs |= dict(
                header_style="green",
                overflow="ellipsis",
            )
            if field == "project":
                _kwargs |= dict(
                    max_width=20,
                )
            elif field == "note":
                _kwargs |= dict(
                    max_width=50,
                    overflow="fold",
                    no_wrap=False,
                )
        elif field == "id":
            _kwargs |= dict(
                header_style="green",
                overflow="crop",
                min_width=7,
                max_width=7,
            )
        elif field in ("start", "timestamp_paused"):
            _kwargs |= dict(
                header_style="yellow",
                justify="left",
                overflow="crop",
                min_width=19,
                max_width=25,
            )
        elif field in ("billable", "paused"):
            _kwargs |= dict(
                header_style="red",
                justify="left",
            )
            if console_width < 150:
                _kwargs |= dict(
                    overflow="ignore",
                    min_width=1,
                    max_width=1,
                )
        elif field in ("paused_hours", "hours"):
            _kwargs |= dict(
                header_style="cyan",
                justify="right",
                overflow="crop",
                max_width=12,
            )
        return _kwargs


_console.if_not_quiet_start(get_console().log, "Validating cache")
TimeEntryCache().validate()


class TimeEntryIdList(metaclass=factory._Singleton):
    id_pattern: re.Pattern[str] = re.compile(r"^\w{,40}$")

    @cached_property
    def ids(self) -> list[str]:
        routine = CliQueryRoutines()
        query_job = routine._select(
            resource=routine.timesheet_id,
            order=["timestamp_start DESC"],
            fields=["id"],
        )
        return list(map(_get._id, query_job))

    def clear(self) -> None:
        del self.__dict__["ids"]

    def match_id(self, input_id: str) -> str:
        matching = list(filter(lambda i: i.startswith(input_id), self.ids))

        if not self.id_pattern.match(input_id):
            raise click.UsageError(
                message=Text.assemble(
                    markup.repr_str(input_id),
                    " is not a valid id. Provided id must match regex ",
                    markup.code(r"^\w{,40}$"),
                ).markup
            )
        elif len(matching) >= 2:
            raise click.UsageError(
                message=Text.assemble(
                    "Multiple possible entries starting with ",
                    markup.repr_str(input_id),
                    ". Use a longer string to match id.",
                ).markup
            )
        elif not matching:
            raise click.UsageError(
                message=Text.assemble(
                    "Cannot find entry id: ", markup.repr_str(input_id)
                ).markup
            )
        else:
            return first(matching)

    def reset(self) -> None:
        try:
            self.clear()
        except Exception as error:
            appdir._log().error(f"Error resetting session ids: {error}")
        self.ids

    def add(self, input_id: str, debug: bool = False) -> None:
        self.ids.extend([input_id])
        debug and patch_stdout(raw=True)(get_console().log)(
            "[DEBUG]", f"Added id {input_id} to id list."
        )

    def remove(self, input_ids: list[str], debug: bool = False) -> None:
        for input_id in input_ids:
            idx: int = self.ids.index(input_id)
            self.ids.pop(idx)
            debug and patch_stdout(raw=True)(get_console().log)(
                f"Removed id {input_id} at index {idx} from id list."
            )


class TimeEntryAppData:
    def __init__(self, path: Path = appdir.ENTRY_APPDATA) -> None:
        self.path = path

    def sync(
        self,
        trigger_query_job: t.Optional["QueryJob"] = None,
        debug: bool = False,
    ) -> None:
        console = get_console()

        debug and patch_stdout(raw=True)(console.log)(
            "[DEBUG]", "starting app data sync"
        )

        routine = CliQueryRoutines()
        projects_query = routine._select(
            resource=CliQueryRoutines().projects_id,
            fields=["*"],
        )

        appdata: dict[str, t.Any] = {"active": {}, "archived": {}}
        for row in list(projects_query):
            project = {}
            project["name"] = row.name
            project["description"] = row.description
            project["default_billable"] = row.default_billable
            project["created"] = row.created
            project["meta"] = self._project_meta(row)
            project["notes"] = []
            if not row.archived:
                appdata["active"].update({row.name: project})
            else:
                appdata["archived"].update({row.name: project})

        if trigger_query_job and not trigger_query_job.done():
            trigger_query_job.result()

        notes_query = routine._select(
            resource=CliQueryRoutines().timesheet_id,
            fields=["project", "note", "timestamp_start"],
            order=["project", "timestamp_start desc"],
        )

        rows = list(notes_query)

        try:
            projects = sorted(set(row.project for row in rows))
        except TypeError:
            ctx = click.get_current_context()
            ctx.fail(
                Text.assemble(
                    markup.br("**WARNING**"),
                    markup.red("Incomplete rows found in timesheet table."),
                    markup.red(
                        "Remove these records before continuing to use this cli."
                    ),
                ).markup
            )

        def _map_notes(a: dict[str, t.Any], p: t.Any) -> dict[str, t.Any]:
            nonlocal appdata, rows
            __key = "active" if p in appdata["active"] else "archived"
            try:
                appdata[__key][p].update({"notes": self._unique_notes(p, rows)})
            except Exception as error:
                appdir._log().error(f"Error attempting to map appdata notes: {error}")
            return appdata

        reduce(_map_notes, projects, appdata)
        self.path.write_text(rtoml.dumps(appdata), encoding="utf-8")

        debug and patch_stdout(raw=True)(console.log)(
            "[DEBUG]", "entry appdata sync complete"
        )

    def _unique_notes(self, project: str, rows: t.Sequence["Row"]) -> list["Row"]:
        return list(unique_everseen(map(_get.note, self._filter_notes(project, rows))))

    def _filter_notes(self, project: str, rows: t.Sequence["Row"]) -> list["Row"]:
        return list(filter(lambda r: r.project == project and r.note, rows))

    def _project_meta(self, row: "Row") -> str:
        return "".join(
            [
                "[",
                escape(f'created="{row.created.date()}"'),
                escape(f', desc="{row.description}"') if row.description else "",
                escape(f', archived="{row.archived.date()}"') if row.archived else "",
                "]",
            ]
        )

    def load(self) -> dict[str, t.Any]:
        return rtoml.load(self.path)
