import typing as t

__all__: t.Sequence[str] = ("shutdown",)


def shutdown() -> t.NoReturn:
    import logging
    import sys

    from lightlike.app.client import get_client
    from lightlike.internal import appdir

    get_client().close()  # type:ignore[no-untyped-call]
    appdir._log().debug("Closed Bigquery client HTTPS connection.")
    appdir._log().debug("Exiting gracefully.")
    logging.shutdown()
    sys.exit(0)
