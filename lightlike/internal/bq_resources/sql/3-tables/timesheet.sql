DECLARE version STRING;

CREATE TABLE IF NOT EXISTS
  ${DATASET.NAME}.${TABLES.TIMESHEET}
    (
      id STRING,
      date DATE,
      project STRING,
      note STRING,
      timestamp_start TIMESTAMP,
      start DATETIME,
      timestamp_end TIMESTAMP,
      `end` DATETIME,
      active BOOL,
      billable BOOL,
      archived BOOL,
      paused BOOL,
      timestamp_paused TIMESTAMP,
      paused_counter INT64,
      paused_hours NUMERIC,
      hours NUMERIC
    )
  PARTITION BY
    date
  OPTIONS(
    labels=[("version", "v0-9-2")]
  );

SET version = (
  WITH
    table_options AS (
      SELECT
        ARRAY(
          SELECT AS STRUCT
            arr[SAFE_OFFSET(0)] AS `key`,
            arr[SAFE_OFFSET(1)] AS value
          FROM
            UNNEST(REGEXP_EXTRACT_ALL(option_value, r'STRUCT\(("[^"]+", "[^"]+")\)')) AS kv,
            UNNEST([STRUCT(SPLIT(REPLACE(kv, '"', ''), ', ') AS arr)])
        ) AS labels,
      FROM
        ${DATASET.NAME}.INFORMATION_SCHEMA.TABLE_OPTIONS
      WHERE
        table_name = "${TABLES.TIMESHEET}"
        AND option_name = "labels"
    )

  SELECT
    labels.value,
  FROM
    table_options
  CROSS JOIN
    UNNEST(labels) AS labels
  WHERE
    `key` = "version"
);

IF version IS NULL THEN /* lables added in v0.9.0 */
BEGIN

BEGIN /* version 0.4.21 -> 0.4.23 */
ALTER TABLE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
RENAME COLUMN paused_duration TO paused_hrs;
EXCEPTION WHEN ERROR
THEN SELECT
  @@error.message,
  @@error.stack_trace,
  @@error.statement_text,
  @@error.formatted_stack_trace;
END;

IF EXISTS(
  SELECT
    column_name
  FROM
    ${DATASET.NAME}.INFORMATION_SCHEMA.COLUMNS
  WHERE
    table_name = "${TABLES.TIMESHEET}"
    AND column_name IN (
      "duration",
      "paused_hrs",
      "time_paused"
    )
  )
THEN
  DROP SNAPSHOT TABLE IF EXISTS ${DATASET.NAME}.${TABLES.TIMESHEET}_pre_v_0_9_0;
  CREATE SNAPSHOT TABLE
    ${DATASET.NAME}.${TABLES.TIMESHEET}_pre_v_0_9_0
  CLONE
    ${DATASET.NAME}.${TABLES.TIMESHEET}
  OPTIONS(
    description="Temporary backup before v0.9.0 update. Expires 5 days after update.",
    expiration_timestamp=CURRENT_TIMESTAMP + INTERVAL 5 DAY
  );

  /* Cannot replace a table with a different partitioning spec - dropping timesheet table first.  */
  DROP TABLE
    ${DATASET.NAME}.${TABLES.TIMESHEET};

  /* 
  truncate timestamp and datetime fields to exclude milliseconds
  round hours to 4 decimal places
  remove `is_` prefix from boolean fields
  add partition on date field
  */
  CREATE OR REPLACE TABLE
    ${DATASET.NAME}.${TABLES.TIMESHEET}
  PARTITION BY
    date AS
  SELECT
    id,
    date,
    project,
    note,
    TIMESTAMP_TRUNC(timestamp_start, SECOND) timestamp_start,
    DATETIME_TRUNC(start, SECOND) start,
    TIMESTAMP_TRUNC(timestamp_end, SECOND) timestamp_end,
    DATETIME_TRUNC(`end`, SECOND) `end`,
    is_active AS active,
    is_billable AS billable,
    is_archived AS archived,
    is_paused AS paused,
    time_paused AS timestamp_paused,
    paused_counter,
    CAST(paused_hrs AS NUMERIC) AS paused_hours,
    CAST(ROUND(duration, 4) AS NUMERIC) AS hours,
  FROM
    ${DATASET.NAME}.${TABLES.TIMESHEET}_pre_v_0_9_0;
END IF;

END;
END IF;

ALTER TABLE 
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET OPTIONS(
  labels=[("version", "v0-9-2")]
);
