CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING, _end TIMESTAMP)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  timestamp_end = TIMESTAMP_TRUNC(_end, SECOND),
  `end` = DATETIME_TRUNC(EXTRACT(DATETIME FROM _end AT TIME ZONE "${TIMEZONE}"), SECOND),
  hours = ROUND(
    SAFE_CAST(SAFE_DIVIDE(TIMESTAMP_DIFF(IFNULL(_end, ${DATASET.NAME}.current_timestamp()), timestamp_start, SECOND), 3600) AS NUMERIC)
    - SAFE_CAST(IF(paused = TRUE, SAFE_DIVIDE(TIMESTAMP_DIFF(_end, timestamp_paused, SECOND), 3600), 0) + IFNULL(paused_hours, 0) AS NUMERIC),
    4
  ),
  paused_hours = ROUND(SAFE_CAST(IF(paused = TRUE, SAFE_DIVIDE(TIMESTAMP_DIFF(_end, timestamp_paused, SECOND), 3600), 0) + IFNULL(paused_hours, 0) AS NUMERIC), 4),
  active = FALSE,
  paused = FALSE,
  timestamp_paused = NULL
WHERE
  id = _id;

END;
