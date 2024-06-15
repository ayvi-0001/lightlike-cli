CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN project STRING, IN value BOOL)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET
  default_billable = value
WHERE
  name = project;

END;
