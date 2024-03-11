from threading import Thread, current_thread
from typing import Any, Callable, Sequence

import rich_click as click
from prompt_toolkit.patch_stdout import patch_stdout
from rich import get_console
from rich.repr import rich_repr
from rich.rule import Rule

from lightlike.lib.third_party._rich_format_error import _rich_format_error

__all__: Sequence[str] = ("spawn",)


def spawn(
    ctx: click.Context, fn: Callable, kwargs: dict[str, Any] | None = None
) -> Thread:
    def wrapper(**kwargs) -> None:
        try:
            with ctx:
                fn(**kwargs) if kwargs else fn()
        except Exception as e:
            with patch_stdout(raw=True):
                console = get_console()
                console.print(
                    Rule(title="[bold][red]WARNING", characters="*", style="bold red")
                )
                console.print(
                    str(rich_repr(current_thread())).replace("wrapper", repr(fn)),  # type: ignore[call-overload]
                    justify="center",
                )
                _rich_format_error(click.ClickException(f"{e}"))

    thread = Thread(target=wrapper, kwargs=kwargs)
    thread.start()
    return thread
