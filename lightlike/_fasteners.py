import functools
import typing as t

from fasteners import InterProcessLock, InterProcessReaderWriterLock

if t.TYPE_CHECKING:
    import logging
    import pathlib
    from collections.abc import Callable

# Same decorated functions from fasteners except added kwarg logger
# to pass to InterProcessLocks. Types added to quiet mypy.

__all__: t.Sequence[str] = (
    "interprocess_locked",
    "interprocess_read_locked",
    "interprocess_write_locked",
)


def interprocess_locked[**P, R](
    path: pathlib.Path | str,
    logger: logging.Logger | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    lock = InterProcessLock(path, logger=logger)

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with lock:
                return fn(*args, **kwargs)

        return wrapper

    return decorator


def interprocess_read_locked[**P, R](
    path: pathlib.Path | str,
    logger: logging.Logger | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    lock = InterProcessReaderWriterLock(path, logger=logger)

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with lock.read_lock():
                return fn(*args, **kwargs)

        return wrapper

    return decorator


def interprocess_write_locked[**P, R](
    path: pathlib.Path | str,
    logger: logging.Logger | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    lock = InterProcessReaderWriterLock(path, logger=logger)

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with lock.write_lock():
                return fn(*args, **kwargs)

        return wrapper

    return decorator
