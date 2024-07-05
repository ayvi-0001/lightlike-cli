import logging
import sys
import typing as t


def shutdown() -> t.NoReturn:

    from lightlike.app.client import get_client
    from lightlike.internal import appdir

    get_client().close()  # type:ignore[no-untyped-call]
    appdir._log().debug("Closed Bigquery client HTTPS connection.")
    appdir._log().debug("Exiting gracefully.")
    logging.shutdown()
    sys.exit(0)
