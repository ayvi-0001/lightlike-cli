#   THIS FILE IS NOT USED FOR ANYTHING
#   This is just an example of how to implement the apscheduler jobstore in BigQuery.
#   An additional install would be required for the script to work:
#     package: https://github.com/googleapis/python-bigquery-sqlalchemy
#     command: pip install sqlalchemy-bigquery[bqstorage]
#     or
#     pip install "lightlike[sqlalchemy-bigquery] @ git+https://github.com/ayvi-0001/lightlike-cli@main"

import typing as t

from apscheduler.executors.pool import ProcessPoolExecutor, ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy import Column, Float, LargeBinary, MetaData, Table, Unicode
from sqlalchemy.engine import Engine, create_engine

__all__: t.Sequence[str] = ("build_bigquery_scheduler",)

P = t.ParamSpec("P")


def build_bigquery_scheduler(*args: P.args, **kwargs: P.kwargs) -> dict[str, t.Any]:
    # Can create a client with new credentials here, or import get_client() from lightlike.app.client and use that.
    credentials: service_account.Credentials = ...
    client = bigquery.Client(credentials=credentials)

    # from lightlike.app.client import get_client
    # client = get_client()

    # We can exclude project id from the url and let it use the default project based on the credentials.
    engine: Engine = create_engine(url="bigquery://", connect_args={"client": client})

    tablename = str(kwargs.get("tablename", "jobs"))
    tableschema = str(kwargs.get("tableschema", "apscheduler"))
    bigquery_description = str(kwargs.get("bigquery_description", "apscheduler jobs"))

    _create_jobs_table_in_bigquery(
        engine=engine,
        tablename=tablename,
        tableschema=tableschema,
        bigquery_description=bigquery_description,
    )

    scheduler_kwargs = dict(
        jobstores={
            "bigquery": SQLAlchemyJobStore(
                engine=engine,
                tableschema=tableschema,
                tablename=tablename,
            ),
        },
        executors={
            "bigquery": ThreadPoolExecutor(20),
            "processpool": ProcessPoolExecutor(10),
        },
    )

    return scheduler_kwargs


def _create_jobs_table_in_bigquery(
    engine: Engine,
    tablename: str,
    tableschema: str,
    bigquery_description: str,
) -> None:
    """
    SQLAlchemy will raise an error when first creating the jobs table in BigQuery,
    by trying to index the `next_run_time` field, which is not implemented for BigQuery tables.
    This function creates the same table except with index=False.
    """
    table = Table(
        tablename,
        MetaData(),
        Column("id", Unicode(191), primary_key=True),
        Column("next_run_time", Float(25), index=False),
        Column("job_state", LargeBinary, nullable=False),
        schema=tableschema,
        bigquery_description=bigquery_description,
    )
    table.create(engine, True)
