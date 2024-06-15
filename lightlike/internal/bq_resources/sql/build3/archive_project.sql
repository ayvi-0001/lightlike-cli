CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _name STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET
  archived = ${DATASET.NAME}.current_datetime()
WHERE
  name = _name;

END;
