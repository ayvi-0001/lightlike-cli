CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING, IN time_resume TIMESTAMP)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  is_paused = FALSE,
  is_active = TRUE,
  paused_hrs = ROUND(CAST(IFNULL(paused_hrs, 0) + ${DATASET.NAME}.duration(time_resume, time_paused, NULL, NULL, NULL) AS NUMERIC), 4),
  time_paused = NULL
WHERE
  id = _id;

END;
