CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(
    IN id STRING,
    IN project STRING,
    IN note STRING,
    IN start_date TIMESTAMP,
    IN end_date TIMESTAMP,
    IN is_billable BOOL
  )
BEGIN
DECLARE note_parsed STRING;
SET note_parsed = NULLIF(note, "None");

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
    is_active,
    is_billable,
    is_archived,
    is_paused,
    duration
  )
VALUES
  (
    id,
    DATE(start_date),
    project,
    note_parsed,
    start_date,
    EXTRACT(DATETIME FROM start_date AT TIME ZONE "${TIMEZONE}"),
    end_date,
    EXTRACT(DATETIME FROM end_date AT TIME ZONE "${TIMEZONE}"),
    FALSE,
    is_billable,
    FALSE,
    FALSE,
    CAST(TIMESTAMP_DIFF(end_date, start_date, MICROSECOND) / 3.6e+9 AS NUMERIC)
  );

END;
