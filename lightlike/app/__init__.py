import typing as t

__all__: t.Sequence[str] = ("shutdown",)


def shutdown() -> t.NoReturn:
    import sys

    from lightlike.app.client import get_client
    from lightlike.internal import utils

    get_client().close()  # type:ignore[no-untyped-call]
    utils._log().debug("Closed Bigquery client HTTPS connection.")
    utils._log().debug("Exiting gracefully.")
    utils._shutdown_log()
    sys.exit(0)
