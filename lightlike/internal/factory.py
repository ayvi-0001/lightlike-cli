from __future__ import annotations

import typing as t
from threading import Lock

__all__: t.Sequence[str] = ("Singleton",)


class Singleton(type):
    _instances: t.ClassVar[dict[type, object]] = {}
    _locks: t.ClassVar[dict[type, Lock]] = {}

    def __call__[T, **P](cls: type[T], *args: P.args, **kwargs: P.kwargs) -> T:
        lock: Lock = Singleton._locks.setdefault(cls, Lock())

        with lock:
            if cls not in Singleton._instances:
                instance: T = super().__call__(  # ty: ignore[invalid-super-argument]
                    *t.cast("t.Any", args),
                    **t.cast("t.Any", kwargs),
                )
                Singleton._instances[cls] = instance

        return t.cast("T", Singleton._instances[cls])
