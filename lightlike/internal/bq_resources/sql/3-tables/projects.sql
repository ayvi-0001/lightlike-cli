DECLARE version STRING;

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
        table_name = "${TABLES.PROJECTS}"
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

IF NOT EXISTS(
  SELECT
    column_name
  FROM
    ${DATASET.NAME}.INFORMATION_SCHEMA.COLUMNS
  WHERE
    table_name = "${TABLES.PROJECTS}"
    AND column_name ="default_billable"
  )
THEN
  DROP SNAPSHOT TABLE IF EXISTS ${DATASET.NAME}.${TABLES.PROJECTS}_pre_v_0_9_0;
  CREATE SNAPSHOT TABLE
    ${DATASET.NAME}.${TABLES.PROJECTS}_pre_v_0_9_0
  CLONE
    ${DATASET.NAME}.${TABLES.PROJECTS}
  OPTIONS(
    description="Temporary backup before v0.9.0 update. Expires 5 days after update.",
    expiration_timestamp=CURRENT_TIMESTAMP + INTERVAL 5 DAY
  );

  /* Cannot replace a table with a different partitioning spec - dropping timesheet table first.  */
  DROP TABLE
    ${DATASET.NAME}.${TABLES.PROJECTS};

  /*
  add default billable value
  add partition on created field
  */
  CREATE OR REPLACE TABLE
    ${DATASET.NAME}.${TABLES.PROJECTS}
  PARTITION BY
    DATE(created) AS
  SELECT
    name,
    description,
    FALSE AS default_billable,
    DATETIME_TRUNC(created, SECOND) created,
    DATETIME_TRUNC(archived, SECOND) archived,
  FROM
    ${DATASET.NAME}.${TABLES.PROJECTS}_pre_v_0_9_0;
END IF;
END;
END IF;

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

update_v_0_9_2: BEGIN
/*
# Updated: v.0.9.2.
  v.0.9.0 forgot to add partitions to new table default.
  Partitions only got added if table existed on or before v0.8.17 and updated to v0.9.0.
  Patch projects tables that are still missing partitions.
*/
IF NOT (
  SELECT
    partition_id IS NOT NULL
  FROM
    `${DATASET.NAME}.INFORMATION_SCHEMA.PARTITIONS`
  WHERE
    table_name = "${TABLES.PROJECTS}"
)
AND version IS NOT NULL
THEN

  DROP SNAPSHOT TABLE IF EXISTS ${DATASET.NAME}.${TABLES.PROJECTS}_patch_v_0_9_2;
  CREATE SNAPSHOT TABLE
    ${DATASET.NAME}.${TABLES.PROJECTS}_patch_v_0_9_2
  CLONE
    ${DATASET.NAME}.${TABLES.PROJECTS}
  OPTIONS(
    description="Temporary backup before v0.9.2 update. Expires 5 days after update.",
    expiration_timestamp=CURRENT_TIMESTAMP + INTERVAL 5 DAY
  );

  /* Cannot replace a table with a different partitioning spec - dropping timesheet table first.  */
  DROP TABLE
    ${DATASET.NAME}.${TABLES.PROJECTS};

  /* add partition on created field */
  CREATE OR REPLACE TABLE
    ${DATASET.NAME}.${TABLES.PROJECTS}
  PARTITION BY
    DATE(created) AS
  SELECT
    name,
    description,
    default_billable,
    created,
    archived,
  FROM
    ${DATASET.NAME}.${TABLES.PROJECTS}_patch_v_0_9_2;

END IF;
EXCEPTION WHEN ERROR THEN
  IF NOT CONTAINS_SUBSTR(@@error.message, "Scalar subquery produced more than one element")
  THEN RAISE USING MESSAGE = @@error.message;
  END IF;
END update_v_0_9_2;

ALTER TABLE 
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET OPTIONS(
  labels=[("version", "v0-9-2")]
);
