# from typing import Sequence

# from apscheduler.executors.pool import ProcessPoolExecutor, ThreadPoolExecutor
# from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from sqlalchemy.engine import create_engine


# __all__: Sequence[str] = ("job_scheduler",)


# engine_url = "bigquery://{project}/{dataset.name}"
# credentials =

# job_scheduler = AsyncIOScheduler(
#     jobstores={
#         "jobs": SQLAlchemyJobStore(
#             engine=create_engine(
#                 engine_url,
#                 credentials_path=credentials,
#             ),
#             tablename="jobs",
#         ),
#     },
#     executors={
#         "jobs": ThreadPoolExecutor(20),
#         "processpool": ProcessPoolExecutor(10),
#     },
# )
