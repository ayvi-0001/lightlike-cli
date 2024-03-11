CREATE OR REPLACE FUNCTION
  ${DATASET.NAME}.${__name__}(step ANY TYPE)
RETURNS FLOAT64 AS (
CASE
  WHEN step >= 0 AND step < 0.15
    THEN 0
  WHEN step >= 0.15 AND step < 0.35
    THEN 0.25
  WHEN step >= 0.35 AND step < 0.625
    THEN 0.5
  WHEN step >= 0.625 AND step < 0.85
    THEN 0.75
  WHEN step >= 0.85
    THEN 1
END
);
