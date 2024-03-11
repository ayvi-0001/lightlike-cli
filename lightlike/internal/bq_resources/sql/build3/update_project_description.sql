CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _name STRING, IN _description STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET
  description = _description
WHERE
  name = _name;

END;
