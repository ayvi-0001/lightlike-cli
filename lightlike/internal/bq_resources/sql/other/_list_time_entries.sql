CREATE OR REPLACE PROCEDURE 
  ${DATASET.NAME}.${__name__}(IN _date TIMESTAMP, IN where_clause ANY TYPE)
OPTIONS(strict_mode=FALSE)
BEGIN

EXECUTE IMMEDIATE
  FORMAT(
    """
SELECT
  LEFT(id, 7) AS id,
  date,
  FORMAT_DATETIME("%%T", start) AS start,
  FORMAT_DATETIME("%%T", `end`) AS `end`,
  project,
  note,
  is_billable AS billable,
  is_active AS active,
  is_paused AS paused,
  paused_hrs,
  ${DATASET.NAME}.duration(timestamp_end, timestamp_start, is_paused, time_paused, paused_hrs) AS duration,
  ROUND(SUM(${DATASET.NAME}.duration(timestamp_end, timestamp_start, is_paused, time_paused, paused_hrs)) OVER(timer), 3) AS total,
FROM
  ${DATASET.NAME}.${TABLES.TIMESHEET}
WHERE
  date = %T AND is_archived IS FALSE
  %s /* additional where clause */
WINDOW
  timer AS (
    ORDER BY timestamp_start, timestamp_end, is_paused, time_paused, paused_counter, paused_hrs
  )
ORDER BY
  timestamp_start,
  timestamp_end;
    """,
  CAST(EXTRACT(DATE FROM TIMESTAMP(_date) AT TIME ZONE "${TIMEZONE}") AS STRING),
  IF(where_clause != "", "AND ("||where_clause||")", "")
);

END;
