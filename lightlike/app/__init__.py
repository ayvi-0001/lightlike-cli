import logging
import sys
import typing as t

if t.TYPE_CHECKING:
    import click


def call_on_close(_ctx: click.Context | None = None, /) -> t.NoReturn:  # ruff: ignore[non-empty-init-module]
    from lightlike.client import get_client
    from lightlike.internal import appdir
    from lightlike.scheduler import get_scheduler

    get_client().close()
    appdir.log().debug("Closed Bigquery client HTTPS connection.")

    if (scheduler := get_scheduler()).running:
        scheduler.shutdown()

    logging.shutdown()
    appdir.log().debug("Exiting gracefully.")
    sys.exit(0)
