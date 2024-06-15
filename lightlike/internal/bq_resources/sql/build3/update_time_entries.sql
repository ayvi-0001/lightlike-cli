CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(
    IN ids ARRAY<STRING>,
    IN new_project STRING,
    IN new_note STRING,
    IN new_billable BOOL,
    IN new_start TIME,
    IN new_end TIME,
    IN new_date DATE
  )
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  project = COALESCE(new_project, project),
  note = COALESCE(new_note, note),
  billable = COALESCE(new_billable, billable),
  timestamp_start = TIMESTAMP_TRUNC(TIMESTAMP(DATETIME(COALESCE(new_date, EXTRACT(DATE from start)), COALESCE(new_start, TIME(start)))), SECOND),
  start = DATETIME_TRUNC(DATETIME(COALESCE(new_date, EXTRACT(DATE from start)), COALESCE(new_start, TIME(start))), SECOND),
  timestamp_end = TIMESTAMP_TRUNC(TIMESTAMP(DATETIME(COALESCE(new_date, EXTRACT(DATE from `end`)), COALESCE(new_end, TIME(`end`)))), SECOND),
  `end` = DATETIME_TRUNC(DATETIME(COALESCE(new_date, EXTRACT(DATE from `end`)), COALESCE(new_end, TIME(`end`))), SECOND),
  date = COALESCE(new_date, date),
  hours = ROUND(
    SAFE_CAST(
      SAFE_DIVIDE(
        TIMESTAMP_DIFF(
          DATETIME(COALESCE(new_date, EXTRACT(DATE from `end`)), COALESCE(new_end, TIME(`end`))),
          DATETIME(COALESCE(new_date, EXTRACT(DATE from start)), COALESCE(new_start, TIME(start))),
          SECOND
        ),
        3600
      ) - IFNULL(paused_hours, 0)
      AS NUMERIC
    ),
    4
  )
WHERE
  id IN UNNEST(ids);

END;
