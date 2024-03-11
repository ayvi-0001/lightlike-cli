CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _name STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  is_archived = FALSE
WHERE
  project = _name;

END;
