CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN current_name STRING, IN new_name STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.PROJECTS}
SET
  name = new_name
WHERE
  name = current_name;

END;
