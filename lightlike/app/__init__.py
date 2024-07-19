import logging
import sys
import typing as t
from contextlib import suppress

import click
from apscheduler.schedulers import SchedulerNotRunningError


def call_on_close(ctx: click.Context | None = None) -> t.NoReturn:
    from lightlike.client import get_client
    from lightlike.internal import appdir
    from lightlike.scheduler import get_scheduler

    get_client().close()
    appdir._log().debug("Closed Bigquery client HTTPS connection.")

    with suppress(SchedulerNotRunningError):
        get_scheduler().shutdown()

    logging.shutdown()
    appdir._log().debug("Exiting gracefully.")
    sys.exit(0)
