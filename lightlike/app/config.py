# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import typing as t
from contextlib import contextmanager
from functools import cached_property
from operator import setitem
from threading import Lock

import rtoml
from fasteners import ReaderWriterLock
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.styles import Style
from pytz import timezone

from lightlike.__about__ import __config__
from lightlike.internal import toml, utils

if t.TYPE_CHECKING:
    from datetime import _TzInfo

    from fasteners import ReaderWriterLock


__all__: t.Sequence[str] = ("AppConfig",)


P = t.ParamSpec("P")


class _Singleton(type):
    _instances: t.ClassVar[dict[object, _Singleton]] = {}
    _lock: Lock = Lock()

    def __call__(cls, *args: P.args, **kwargs: P.kwargs) -> _Singleton:
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super(type(cls), cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AppConfig(metaclass=_Singleton):
    _rw_lock: t.ClassVar[ReaderWriterLock] = ReaderWriterLock()

    def __init__(self) -> None:
        self.path = __config__

        with self._rw_lock.read_lock():
            self.config = self.load()

        self._prompt_config = utils.update_dict(
            rtoml.load(toml.PROMPT), self.config.get("prompt", {})
        )
        self.prompt_style: Style = Style.from_dict(
            self._prompt_config["style"],
        )
        self.cursor_shape: CursorShape = getattr(
            CursorShape,
            self._prompt_config["cursor-shape"],
            CursorShape.BLOCK,
        )

    def __setitem__(self, __key: str, __val: t.Any) -> None:
        self.config[__key] = __val

    def __getitem__(self, __key: str) -> t.Any:
        return self.config[__key]

    @contextmanager
    def rw(self) -> t.Generator[AppConfig, t.Any, None]:
        try:
            with self._rw_lock.read_lock():
                self.config = self.load()
                yield self
        finally:
            with self._rw_lock.write_lock():
                self.path.write_text(utils._format_toml(self.config))
            with self._rw_lock.read_lock():
                self.config = self.load()

    def load(self) -> t.Any:
        with self._rw_lock.read_lock():
            return rtoml.load(self.path)

    def get(self, *keys: t.Sequence[str], default: t.Optional[t.Any] = None) -> t.Any:
        return utils.reduce_keys(*keys, sequence=self.load(), default=default)

    @cached_property
    def tz(self) -> "_TzInfo":
        return timezone(self.get("settings", "timezone"))

    # no setter on cached properties
    tz.__setattr__ = lambda s, v: setitem(s.__dict__, "tz", v)  # type: ignore
