CREATE TABLE IF NOT EXISTS
  ${DATASET.NAME}.${TABLES.PROJECTS}
    (
      name STRING,
      description STRING,
      default_billable BOOL,
      created DATETIME,
      archived DATETIME
    )
  PARTITION BY
    DATE(created)
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


/* add default project if it doesn't exist. */
IF NOT (
  SELECT
    row_count <> 0
  FROM
    ${DATASET.NAME}.__TABLES__
  WHERE
    table_id = "${TABLES.PROJECTS}"
)
THEN
INSERT INTO
  ${DATASET.NAME}.${TABLES.PROJECTS}
VALUES
  ("no-project", "default", FALSE, ${DATASET.NAME}.current_datetime(), NULL);
END IF;


ALTER TABLE 
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET OPTIONS(
  labels=[("version", "${VERSION}")]
);
