CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING, IN _timestamp_paused TIMESTAMP)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  paused = TRUE,
  active = FALSE,
  timestamp_paused = TIMESTAMP_TRUNC(_timestamp_paused, SECOND),
  paused_counter = IFNULL(paused_counter, 0) + 1
WHERE
  id = _id;

END;
