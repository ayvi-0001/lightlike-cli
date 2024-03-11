CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN _id STRING)
BEGIN
DECLARE query STRUCT<id STRING>;

SET query = STRUCT<STRING>(
  (
    SELECT
      id
    FROM
      ${DATASET.NAME}.${TABLES.TIMESHEET}
    WHERE
      REGEXP_CONTAINS(id, r'^'||_id)
  )
);

IF (SELECT query.id) IS NULL
THEN
  RAISE USING MESSAGE = FORMAT("Did not find id: %s", _id);
END IF;

DELETE FROM
  ${DATASET.NAME}.${TABLES.TIMESHEET}
WHERE
  id = query.id;

EXCEPTION WHEN ERROR THEN
IF CONTAINS_SUBSTR(@@error.message, FORMAT("Did not find id: %s", _id))
THEN
  RAISE USING MESSAGE = @@error.message;
ELSEIF CONTAINS_SUBSTR(@@error.message, "Scalar subquery produced more than one element")
THEN
  RAISE USING MESSAGE = FORMAT("Multiple possible entries starting with %s. Use a longer string to match time entry.", _id);
ELSE
  RAISE USING MESSAGE = @@error.message;
END IF;

END;
