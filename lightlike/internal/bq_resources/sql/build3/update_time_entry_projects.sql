CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN current_name STRING, IN new_name STRING)
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  project = new_name
WHERE
  project = current_name;

END;
