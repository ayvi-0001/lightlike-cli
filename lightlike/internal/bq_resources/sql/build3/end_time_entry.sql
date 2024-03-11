CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  timestamp_end = CURRENT_TIMESTAMP(),
  `end` = ${DATASET.NAME}.now(),
  duration = CAST(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp_start, MICROSECOND) / 3.6e+9 AS NUMERIC) - IFNULL(paused_hrs, 0),
  is_active = FALSE
WHERE
  id = _id;

END;
