CREATE TABLE IF NOT EXISTS
  ${DATASET.NAME}.${TABLES.PROJECTS}
    (
      name STRING,
      description STRING,
      -- default_billable BOOL,
      created DATETIME,
      archived DATETIME
    );

IF NOT (
  SELECT row_count <> 0 FROM ${DATASET.NAME}.__TABLES__ WHERE table_id = "${TABLES.PROJECTS}"
)
THEN
INSERT INTO
  ${DATASET.NAME}.${TABLES.PROJECTS}
VALUES
  ("no-project", "default", ${DATASET.NAME}.now(), NULL);
END IF;
