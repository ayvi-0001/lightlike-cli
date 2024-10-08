from __future__ import annotations

import typing as t
from contextlib import contextmanager
from functools import wraps
from hashlib import sha3_256, sha256
from pathlib import Path

import rtoml
from fasteners import ReaderWriterLock
from pytz import timezone

from lightlike.__about__ import __config__
from lightlike.internal import factory, utils

if t.TYPE_CHECKING:
    from datetime import _TzInfo


__all__: t.Sequence[str] = ("AppConfig",)


_Hash = type(sha256(b"_Hash"))

T = t.TypeVar("T")
P = t.ParamSpec("P")


class AppConfig(metaclass=factory._Singleton):
    _rw_lock: ReaderWriterLock = ReaderWriterLock()

    @staticmethod
    def ensure_config(fn: t.Callable[..., T]) -> t.Callable[..., T]:
        @wraps(fn)
        def inner(self: t.Self, *args: P.args, **kwargs: P.kwargs) -> T:
            self.config = self.load
            r: T = fn(self, *args, **kwargs)
            self.config = self.load
            return r

        return inner

    def __init__(self, path: Path = __config__) -> None:
        self.path = path
        self.config: dict[str, t.Any] = self.load

    def __setitem__(self, __key: str, __val: t.Any) -> None:
        self.config[__key] = __val

    def __getitem__(self, __key: str) -> t.Any:
        return self.config[__key]

    @ensure_config
    @contextmanager
    def rw(self) -> t.Generator[AppConfig, t.Any, None]:
        try:
            with self._rw_lock.read_lock():
                yield self
        finally:
            with self._rw_lock.write_lock():
                self.path.write_text(
                    utils.format_toml(self.config),
                    encoding="utf-8",
                )

    @property
    def load(self) -> dict[str, t.Any]:
        with self._rw_lock.read_lock():
            return rtoml.load(self.path)

    @t.overload
    def get(self, *keys: str, default: t.Literal[None] = None) -> t.Any | None: ...

    @t.overload
    def get(self, *keys: str, default: dict[str, t.Any]) -> dict[str, t.Any]: ...

    @t.overload
    def get(self, *keys: str, default: T) -> T: ...

    def get(
        self, *keys: str, default: T | dict[str, t.Any] | None = None
    ) -> t.Any | T | dict[str, t.Any] | None:
        return utils.reduce_keys(*keys, sequence=self.load, default=default)

    @property
    def saved_password(self) -> str | None:
        config_password: str | None = self.get("user", "password")
        saved_password: str | None = (
            config_password if config_password != "null" else None
        )
        return saved_password

    @property
    def stay_logged_in(self) -> bool | None:
        stay_logged_in: bool | None = self.get("user", "stay-logged-in")
        return stay_logged_in

    @property
    def tzname(self) -> str:
        default_tzinfo: str = utils.get_local_timezone_string(default="UTC")
        return self.get("settings", "timezone", default=default_tzinfo)

    @property
    def tzinfo(self) -> "_TzInfo":
        return timezone(self.tzname)

    def _update_user_credentials(
        self,
        password: str | sha3_256 | None = None,
        salt: bytes | None = None,
        stay_logged_in: bool | None = None,
    ) -> None:
        with self.rw() as config:
            if password:
                if isinstance(password, str):
                    config["user"].update(password=password)
                elif isinstance(password, _Hash):
                    config["user"].update(
                        password=password.hexdigest(),
                    )

            if password == "null":
                config["user"].update(password="")
            if salt:
                config["user"].update(salt=salt)
            if stay_logged_in is not None:
                config["user"].update({"stay-logged-in": stay_logged_in})
