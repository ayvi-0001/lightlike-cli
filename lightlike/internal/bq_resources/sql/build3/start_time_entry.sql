CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(
    IN id STRING,
    IN project STRING,
    IN note STRING,
    IN start_time TIMESTAMP,
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
    billable,
    active,
    archived,
    paused
  )
VALUES
  (
    id,
    EXTRACT(DATE FROM start_time AT TIME ZONE "${TIMEZONE}"),
    project,
    NULLIF(note, "None"),
    start_time,
    EXTRACT(DATETIME FROM start_time AT TIME ZONE "${TIMEZONE}"),
    billable,
    TRUE,
    FALSE,
    FALSE
  );

END;
