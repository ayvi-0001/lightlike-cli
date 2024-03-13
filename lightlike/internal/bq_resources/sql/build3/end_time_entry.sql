CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  timestamp_end = CURRENT_TIMESTAMP(),
  `end` = ${DATASET.NAME}.now(),
  duration = ${DATASET.NAME}.duration(CURRENT_TIMESTAMP(), timestamp_start, NULL, NULL, paused_hrs),
  is_active = FALSE
WHERE
  id = _id;

END;
