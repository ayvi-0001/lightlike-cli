import typing as t
from threading import Thread, current_thread
from time import sleep

import rich_click as click
from prompt_toolkit.patch_stdout import patch_stdout
from rich import print as rprint
from rich.repr import rich_repr
from rich.rule import Rule

from lightlike.internal import utils

__all__: t.Sequence[str] = ("spawn",)


def spawn(
    ctx: click.RichContext,
    fn: t.Callable,
    kwargs: dict[str, t.Any] | None = None,
    delay: int | None = None,
) -> Thread:
    def wrapper(**kwargs) -> None:
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
                rprint(
                    f"{rich_repr(current_thread())}".replace("wrapper", repr(fn))  # type: ignore[call-overload]
                )

            utils.notify_and_log_error(error)

    thread = Thread(target=wrapper, kwargs=kwargs)
    thread.start()
    return thread
