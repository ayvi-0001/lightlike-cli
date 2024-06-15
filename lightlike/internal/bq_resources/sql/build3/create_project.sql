CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN name STRING, IN description STRING, default_billable BOOL)
BEGIN

INSERT INTO
  ${DATASET.NAME}.${TABLES.PROJECTS}(
    name,
    description,
    default_billable,
    created
  )
VALUES
  (
    name,
    NULLIF(description, ""),
    default_billable,
    ${DATASET.NAME}.current_datetime()
  );

END;
