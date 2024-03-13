CREATE OR REPLACE FUNCTION
  ${DATASET.NAME}.${__name__}(
    timestamp_end TIMESTAMP,
    timestamp_start TIMESTAMP,
    is_paused BOOL,
    time_paused TIMESTAMP,
    paused_hrs NUMERIC
  ) RETURNS NUMERIC AS (
    ROUND(
      CAST(
        TIMESTAMP_DIFF(
          CASE
            WHEN is_paused = TRUE THEN time_paused
            WHEN timestamp_end IS NULL THEN CURRENT_TIMESTAMP()
            ELSE timestamp_end
          END,
          timestamp_start,
          MICROSECOND
        ) / 3.6e+9 AS NUMERIC
      ) - IFNULL(paused_hrs, 0),
      4
    )
  );
