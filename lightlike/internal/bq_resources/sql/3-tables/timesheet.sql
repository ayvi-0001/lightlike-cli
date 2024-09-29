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
    labels=[("version", "${VERSION}")]
  );


# BEGIN
# DECLARE version STRING;

# SET version = (
#   WITH
#     table_options AS (
#       SELECT
#         ARRAY(
#           SELECT AS STRUCT
#             arr[SAFE_OFFSET(0)] AS `key`,
#             arr[SAFE_OFFSET(1)] AS value
#           FROM
#             UNNEST(REGEXP_EXTRACT_ALL(option_value, r'STRUCT\(("[^"]+", "[^"]+")\)')) AS kv,
#             UNNEST([STRUCT(SPLIT(REPLACE(kv, '"', ''), ', ') AS arr)])
#         ) AS labels,
#       FROM
#         ${DATASET.NAME}.INFORMATION_SCHEMA.TABLE_OPTIONS
#       WHERE
#         table_name = "${TABLES.PROJECTS}"
#         AND option_name = "labels"
#     )
# 
#   SELECT
#     labels.value,
#   FROM
#     table_options
#   CROSS JOIN
#     UNNEST(labels) AS labels
#   WHERE
#     `key` = "version"
# );
# 

# END;


ALTER TABLE 
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET OPTIONS(
  labels=[("version", "${VERSION}")]
);
