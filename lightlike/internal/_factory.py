from __future__ import annotations

import threading
import typing as t

__all__: t.Sequence[str] = ("Singleton", "singleton")

T = t.TypeVar("T")
P = t.ParamSpec("P")


class Singleton(type):
    _instances: t.ClassVar[dict[object, Singleton]] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args: P.args, **kwargs: P.kwargs) -> Singleton:
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super(type(cls), cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def singleton(cls) -> t.Callable[P, T]:
    instances: dict[object, T] = {}

    def get_instance(*args: P.args, **kwargs: P.kwargs) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
