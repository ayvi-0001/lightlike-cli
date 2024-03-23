from __future__ import annotations

import threading
import typing as t
from contextlib import contextmanager
from datetime import datetime
from functools import reduce
from operator import getitem

import fasteners  # type: ignore[import-untyped, import-not-found]
import rtoml
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.styles import Style
from pytz import timezone

from lightlike._console import PROMPT_TOML
from lightlike.app import _get
from lightlike.internal import appdir, utils
from lightlike.internal.enums import CredentialsSource

if t.TYPE_CHECKING:
    from fasteners import ReaderWriterLock
    from pytz.tzinfo import BaseTzInfo, DstTzInfo, StaticTzInfo

    TZ: t.TypeAlias = t.Union["BaseTzInfo", "DstTzInfo", "StaticTzInfo"]

__all__: t.Sequence[str] = ("AppConfig",)


P = t.ParamSpec("P")


class _AppConfigSingleton(type):
    _instances: t.ClassVar[dict[object, _AppConfigSingleton]] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args: P.args, **kwargs: P.kwargs) -> _AppConfigSingleton:
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super(type(cls), cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AppConfig(metaclass=_AppConfigSingleton):
    __slots__: t.ClassVar[t.Sequence[str]] = (
        "path",
        "config",
        "prompt_style",
        "cursor_shape",
        "history",
        "username",
        "hostname",
        "_prompt_config",
    )
    _rw_lock: t.ClassVar["ReaderWriterLock"] = fasteners.ReaderWriterLock()

    def __init__(self) -> None:
        self.path = appdir.CONFIG
        self._prompt_config = rtoml.load(PROMPT_TOML)
        self.prompt_style = Style.from_dict(self._prompt_config["style"])
        self.cursor_shape = getattr(CursorShape, self._prompt_config["cursor-shape"])
        self.history = appdir.REPL_FILE_HISTORY

        with self._rw_lock.read_lock():
            self.config = self._load()

        self.username: str = self.get("user", "name")
        self.hostname: str = self.get("user", "host")

    def __setitem__(self, __key: str, __val: t.Any) -> None:
        self.config[__key] = __val

    def __getitem__(self, __key: str) -> t.Any:
        return self.config[__key]

    @contextmanager
    def update(self) -> t.Generator[AppConfig, t.Any, None]:
        try:
            with self._rw_lock.read_lock():
                yield self
        finally:
            with self._rw_lock.write_lock():
                self.path.write_text(self._serialize_toml(self.config))
            with self._rw_lock.read_lock():
                self.config = self._load()

    @staticmethod
    def _serialize_toml(toml_obj: t.MutableMapping[str, t.Any]) -> str:
        return utils._format_toml(toml_obj)

    @staticmethod
    def _reduce_keys(*keys: t.Sequence[str], sequence: t.Any) -> t.Any:
        return reduce(getitem, [*keys], sequence)

    def _load(self) -> t.Any:
        return rtoml.load(self.path)

    def get(self, *keys: t.Sequence[str], default: t.Optional[t.Any] = None) -> t.Any:
        try:
            return self._reduce_keys(*keys, sequence=self._load())
        except KeyError:
            return default

    @property
    def active_project(self) -> str:
        return self.get("client", "active_project")

    @property
    def credentials_source(self) -> CredentialsSource:
        match self.get("client", "credentials_source"):
            case "from-environment":
                return CredentialsSource.from_environment
            case "from-service-account-key":
                return CredentialsSource.from_service_account_key
            case _:
                return CredentialsSource.not_set

    @property
    def tz(self) -> "TZ":
        return timezone(self.get("settings", "timezone"))

    @property
    def now(self) -> datetime:
        return self.in_app_timezone(datetime.now())

    def in_app_timezone(self, dt: datetime) -> datetime:
        return dt.astimezone(self.tz).replace(microsecond=0)

    @property
    def default_timer_add_min(self) -> float:
        timer_add_min: float = self.get("settings", "timer_add_min")
        return -timer_add_min if _get.sign(timer_add_min) != -1 else timer_add_min

    @property
    def general_settings(self) -> dict[str, t.Any]:
        settings = self.config["settings"]
        editor = settings["editor"]
        timezone = settings["timezone"]
        is_billable = settings["is_billable"]
        quiet_start = settings["quiet_start"]
        note_history = settings["note_history"]

        match settings["week_start"]:
            case 0:
                week_start = "Sunday"
            case 1:
                week_start = "Monday"

        return {
            "editor": editor,
            "timezone": timezone,
            "is_billable": is_billable,
            "quiet_start": quiet_start,
            "week_start": week_start,
            "note_history": note_history,
        }

    @property
    def query_settings(self) -> dict[str, t.Any]:
        settings = self.config["settings"]["query"]
        mouse_support = settings["mouse_support"]
        save_txt = settings["save_txt"]
        save_query_info = settings["save_query_info"]
        save_svg = settings["save_svg"]
        hide_table_render = settings["hide_table_render"]

        return {
            "mouse_support": mouse_support,
            "save_txt": save_txt,
            "save_query_info": save_query_info,
            "save_svg": save_svg,
            "hide_table_render": hide_table_render,
        }
