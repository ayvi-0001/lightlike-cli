import logging
import sys
import typing as t

import click


def call_on_close(ctx: click.Context | None = None) -> t.NoReturn:
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
