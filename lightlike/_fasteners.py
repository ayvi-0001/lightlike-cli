import functools
import logging
import pathlib
import typing as t

from fasteners import InterProcessLock, InterProcessReaderWriterLock

# Same decorated functions from fasteners except added kwarg logger
# to pass to InterProcessLocks. Types added to quiet mypy.

__all__: t.Sequence[str] = (
    "interprocess_locked",
    "interprocess_read_locked",
    "interprocess_write_locked",
)


_AnyCallable: t.TypeAlias = t.Callable[..., t.Any]

P = t.ParamSpec("P")


def interprocess_locked(
    path: pathlib.Path | str, logger: logging.Logger | None = None
) -> t.Callable[..., _AnyCallable]:
    lock = InterProcessLock(path, logger=logger)

    def decorator(fn: _AnyCallable) -> _AnyCallable:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            with lock:
                return fn(*args, **kwargs)

        return wrapper

    return decorator


def interprocess_read_locked(
    path: pathlib.Path | str, logger: logging.Logger | None = None
) -> t.Callable[..., _AnyCallable]:
    lock = InterProcessReaderWriterLock(path, logger=logger)

    def decorator(fn: _AnyCallable) -> _AnyCallable:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            with lock.read_lock():
                return fn(*args, **kwargs)

        return wrapper

    return decorator


def interprocess_write_locked(
    path: pathlib.Path | str, logger: logging.Logger | None = None
) -> t.Callable[..., _AnyCallable]:
    lock = InterProcessReaderWriterLock(path, logger=logger)

    def decorator(fn: _AnyCallable) -> _AnyCallable:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> t.Any:
            with lock.write_lock():
                return fn(*args, **kwargs)

        return wrapper

    return decorator
