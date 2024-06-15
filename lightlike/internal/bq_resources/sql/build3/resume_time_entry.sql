CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING, IN time_resume TIMESTAMP)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  paused = FALSE,
  active = TRUE,
  paused_hours = ROUND(SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(time_resume, timestamp_paused, SECOND), 3600) + IFNULL(paused_hours, 0) AS NUMERIC), 4),
  timestamp_paused = NULL
WHERE
  id = _id;

END;
