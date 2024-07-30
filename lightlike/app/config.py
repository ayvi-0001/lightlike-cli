from __future__ import annotations

import typing as t
from contextlib import contextmanager
from hashlib import sha3_256, sha256
from pathlib import Path

import rtoml
from fasteners import ReaderWriterLock

from lightlike.__about__ import __config__
from lightlike.internal import factory, utils

__all__: t.Sequence[str] = ("AppConfig",)


_Hash = type(sha256(b"_Hash"))

P = t.ParamSpec("P")


class AppConfig(metaclass=factory._Singleton):
    _rw_lock: ReaderWriterLock = ReaderWriterLock()

    def __init__(self, path: Path = __config__) -> None:
        self.path = path
        self.config: dict[str, t.Any] = self.load()

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
            self.config = self.load()

    def load(self) -> dict[str, t.Any]:
        with self._rw_lock.read_lock():
            return rtoml.load(self.path)

    def get(self, *keys: t.Sequence[str], default: t.Optional[t.Any] = None) -> t.Any:
        return utils.reduce_keys(*keys, sequence=self.load(), default=default)

    def saved_password(self) -> str | None:
        config_password: str | None = self.get("user", "password")
        saved_password: str | None = (
            config_password if config_password != "null" else None
        )
        return saved_password

    def stay_logged_in(self) -> bool | None:
        stay_logged_in: bool | None = self.get("user", "stay_logged_in")
        return stay_logged_in

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
                config["user"].update(stay_logged_in=stay_logged_in)
