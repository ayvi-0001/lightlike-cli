CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(
    IN id STRING,
    IN project STRING,
    IN note STRING,
    IN start_date TIMESTAMP,
    IN end_date TIMESTAMP,
    IN billable BOOL
  )
BEGIN

INSERT INTO
  ${DATASET.NAME}.${TABLES.TIMESHEET} (
    id,
    date,
    project,
    note,
    timestamp_start,
    start,
    timestamp_end,
    `end`,
    active,
    billable,
    archived,
    paused,
    hours
  )
VALUES
  (
    id,
    DATE(start_date),
    project,
    NULLIF(note, "None"),
    start_date,
    DATETIME_TRUNC(EXTRACT(DATETIME FROM start_date AT TIME ZONE "${TIMEZONE}"), SECOND),
    end_date,
    DATETIME_TRUNC(EXTRACT(DATETIME FROM end_date AT TIME ZONE "${TIMEZONE}"), SECOND),
    FALSE,
    billable,
    FALSE,
    FALSE,
    ROUND(CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(end_date, start_date, SECOND), 3600) AS NUMERIC), 4)
  );

END;
