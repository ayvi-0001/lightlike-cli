CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _name STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET
  archived = NULL
WHERE
  name = _name;

END;
