from __future__ import annotations

import typing as t
from threading import Lock

__all__: t.Sequence[str] = ("_Singleton",)


P = t.ParamSpec("P")


class _Singleton(type):
    _instances: dict[object, _Singleton] = {}
    _locks: dict[str, Lock] = {}

    def __call__(cls, *args: P.args, **kwargs: P.kwargs) -> _Singleton:
        if cls.__name__ not in cls._locks:
            cls._locks[cls.__name__] = Lock()

        with cls._locks[cls.__name__]:
            if cls not in cls._instances:
                cls._instances[cls] = super(type(cls), cls).__call__(*args, **kwargs)
        return cls._instances[cls]
