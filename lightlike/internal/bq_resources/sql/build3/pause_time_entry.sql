CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING, IN _time_paused TIMESTAMP)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  is_paused = TRUE,
  is_active = FALSE,
  time_paused = _time_paused,
  paused_counter = IFNULL(paused_counter, 0) + 1
WHERE
  id = _id;

END;
