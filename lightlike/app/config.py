from __future__ import annotations

import os
import typing as t
from contextlib import contextmanager
from functools import wraps
from hashlib import sha256
from zoneinfo import ZoneInfo

import rtoml
from fasteners import ReaderWriterLock

from lightlike.__about__ import __config__
from lightlike.internal import factory, utils

if t.TYPE_CHECKING:
    from datetime import _TzInfo
    from hashlib import _Hash as HASH
    from pathlib import Path

__all__: t.Sequence[str] = ("AppConfig",)


class AppConfig(metaclass=factory.Singleton):
    _rw_lock: ReaderWriterLock = ReaderWriterLock()

    @staticmethod
    def ensure_config[**P, R](
        fn: t.Callable[t.Concatenate[AppConfig, P], R],
    ) -> t.Callable[t.Concatenate[AppConfig, P], R]:
        @wraps(fn)
        def inner(self: AppConfig, *args: P.args, **kwargs: P.kwargs) -> R:
            self.config = self.load
            r = fn(self, *args, **kwargs)
            self.config = self.load
            return r

        return inner

    def __init__(self, path: Path = __config__) -> None:
        self.path = path
        self.config: dict[str, t.Any] = self.load

    def __setitem__(self, __key: str, __val: object, /) -> None:
        self.config[__key] = __val

    def __getitem__[T](self, __key: str, /) -> T:
        return self.config[__key]

    @ensure_config
    @contextmanager
    def rw(self) -> t.Generator[AppConfig, t.Any]:
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
    def get[Q](self, *keys: str, default: None = None) -> Q | None: ...
    @t.overload
    def get[Q](self, *keys: str, default: dict[str, Q]) -> dict[str, Q]: ...
    @t.overload
    def get[Q](self, *keys: str, default: Q) -> Q: ...

    def get[Q](
        self,
        *keys: str,
        default: Q | dict[str, Q] | None = None,
    ) -> Q | dict[str, Q] | None:
        return utils.reduce_keys(*keys, sequence=self.load, default=default)

    @property
    def saved_password(self) -> str | None:
        config_password: str | None = self.get("user", "password")
        saved_password: str | None = config_password if config_password != "null" else None  # ruff: ignore[hardcoded-password-string]
        return saved_password

    @property
    def stay_logged_in(self) -> bool | None:
        stay_logged_in: bool | None = self.get("user", "stay-logged-in")
        return stay_logged_in

    @property
    def editor(self) -> str | None:
        editor: str | None = self.get(
            "settings",
            "editor",
            default=os.environ.get("EDITOR"),
        )
        return editor

    @property
    def tzname(self) -> str:
        default_tzinfo: str = utils.get_local_timezone_string(default="UTC")
        return self.get("settings", "timezone", default=default_tzinfo)

    @property
    def tzinfo(self) -> _TzInfo:
        return ZoneInfo(self.tzname)

    def update_user_credentials(
        self,
        password: str | HASH | None = None,
        salt: bytes | None = None,
        *,
        stay_logged_in: bool | None = None,
    ) -> None:
        with self.rw() as config:
            if password:
                if isinstance(password, str):
                    config["user"].update(password=password)
                elif isinstance(password, type(sha256(b"_Hash"))):
                    config["user"].update(
                        password=password.hexdigest(),
                    )

            if password == "null":  # ruff: ignore[hardcoded-password-string]
                config["user"].update(password="")
            if salt:
                config["user"].update(salt=salt)
            if stay_logged_in is not None:
                config["user"].update({"stay-logged-in": stay_logged_in})
