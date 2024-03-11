CREATE OR REPLACE PROCEDURE
  ${DATASET.NAME}.${__name__}(IN name STRING, IN description STRING)
BEGIN

INSERT INTO
  ${DATASET.NAME}.${TABLES.PROJECTS}(name, description, created)
VALUES
  (name, NULLIF(description, ""), ${DATASET.NAME}.now());

END;
