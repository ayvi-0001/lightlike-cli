CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(
    IN new_note STRING,
    IN old_note STRING,
    IN _project STRING
  )
BEGIN

UPDATE
  ${DATASET.NAME}.${TABLES.TIMESHEET}
SET
  note = new_note
WHERE
  REGEXP_CONTAINS(note, old_note)
  AND project = _project;

END;
