import typing as t
from threading import Thread, current_thread
from time import sleep

import click
from prompt_toolkit.patch_stdout import patch_stdout
from rich import print as rprint
from rich.repr import rich_repr
from rich.rule import Rule

from lightlike.internal import utils

__all__: t.Sequence[str] = ("spawn",)


def spawn(
    ctx: click.Context,
    fn: t.Callable[..., t.Any],
    kwargs: dict[str, t.Any] | None = None,
    delay: int | None = None,
) -> Thread:
    def wrapper(**kwargs: dict[str, t.Any]) -> t.Any:
        try:
            if delay and isinstance(delay, int):
                sleep(delay)
            with ctx:
                return fn(**kwargs) if kwargs else fn()
        except Exception as error:
            with patch_stdout(raw=True):
                rprint(
                    Rule(
                        title="[b][red]Error occured in another thread",
                        characters="- ",
                        style="bold red",
                        align="left",
                    )
                )
                thread_repr: str = f"{rich_repr(current_thread())}"  # type: ignore[call-overload]
                thread_repr.replace("wrapper", f"{fn!r}")
                rprint(thread_repr)

            utils.notify_and_log_error(error)

    thread: Thread = Thread(target=wrapper, kwargs=kwargs)
    thread.start()
    return thread
