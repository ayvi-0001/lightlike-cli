CREATE OR REPLACE FUNCTION
  ${DATASET.NAME}.${__name__}(
    is_paused BOOL,
    time_paused TIMESTAMP,
    paused_hrs NUMERIC
  ) RETURNS NUMERIC AS (
    ROUND(
      CAST(
        IF(
          is_paused = TRUE, 
          DATETIME_DIFF(CURRENT_TIMESTAMP(), time_paused, MICROSECOND) / 3.6e+9,
          0
        )
        AS NUMERIC
      ) + IFNULL(paused_hrs, 0),
      4
    )
  );
