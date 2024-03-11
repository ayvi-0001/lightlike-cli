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
      is_active BOOL,
      is_billable BOOL,
      is_archived BOOL,
      is_paused BOOL,
      time_paused TIMESTAMP,
      paused_counter INT64,
      paused_hrs NUMERIC,
      duration NUMERIC
    );

/* version 0.4.21 -> 0.4.23 */
BEGIN
ALTER TABLE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
RENAME COLUMN paused_duration  TO paused_hrs;
EXCEPTION WHEN ERROR
THEN SELECT
  @@error.message,
  @@error.stack_trace,
  @@error.statement_text,
  @@error.formatted_stack_trace;
END;
