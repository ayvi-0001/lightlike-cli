CREATE OR REPLACE PROCEDURE 
  ${DATASET.NAME}.${__name__}(
    IN start_date TIMESTAMP,
    IN end_date TIMESTAMP,
    IN where_clause ANY TYPE,
    IN round_ BOOL,
    IN type_ ANY TYPE
  ) OPTIONS(strict_mode=FALSE)
BEGIN

IF round_ IS TRUE THEN
EXECUTE IMMEDIATE
  FORMAT(
'''
SELECT DISTINCT
  SUM(duration) OVER() AS total_report,
  SUM(duration) OVER(PARTITION BY project) AS total_project,
  SUM(duration) OVER(PARTITION BY date) AS total_day,
  date,
  project,
  is_billable AS billable,
  SUM(duration) OVER(PARTITION BY date, project, is_billable) AS duration,
  STRING_AGG(note || " - " || duration, "%s") OVER(PARTITION BY date, project, is_billable) AS notes,
FROM
  (
    SELECT
      date,
      project,
      is_billable,
      note,
      IF(
        ${DATASET.NAME}.rounding_step(SUM(duration) - FLOOR(SUM(duration))) = 1,
        ROUND(SUM(duration)),
        FLOOR(SUM(duration)) + ${DATASET.NAME}.rounding_step(SUM(duration) - FLOOR(SUM(duration)))
      ) AS duration,
    FROM
      ${DATASET.NAME}.${TABLES.TIMESHEET}
    WHERE
      date BETWEEN %T AND %T AND is_archived IS FALSE AND is_paused IS FALSE
      %s /* additional where clause */
    GROUP BY
      project,
      date,
      is_billable,
      note
    HAVING
      duration != 0
  )
QUALIFY total_day != 0
ORDER BY
  date,
  project
''',
  IF(type_ = "file", ", ", "\\n"),
  CAST(EXTRACT(DATE FROM TIMESTAMP(start_date) AT TIME ZONE "${TIMEZONE}") AS STRING),
  CAST(EXTRACT(DATE FROM TIMESTAMP(end_date) AT TIME ZONE "${TIMEZONE}") AS STRING),
  IF(where_clause != "", "AND ("||where_clause||")", "")
);

ELSE
EXECUTE IMMEDIATE
  FORMAT(
'''
SELECT DISTINCT
  SUM(duration) OVER() AS total_report,
  SUM(duration) OVER(PARTITION BY project) AS total_project,
  SUM(duration) OVER(PARTITION BY date) AS total_day,
  date,
  project,
  is_billable AS billable,
  SUM(duration) OVER(PARTITION BY date, project, is_billable) AS duration,
  STRING_AGG(note || " - " || duration, "%s") OVER(PARTITION BY date, project, is_billable) AS notes,
FROM
  (
    SELECT
      date,
      project,
      is_billable,
      note,
      ROUND(SUM(duration), 4) AS duration,
    FROM
      ${DATASET.NAME}.${TABLES.TIMESHEET}
    WHERE
      date BETWEEN %T AND %T AND is_archived IS FALSE AND is_paused IS FALSE
      %s /* additional where clause */
    GROUP BY
      project,
      date,
      is_billable,
      note
  )
ORDER BY
  date,
  project
''',
  IF(type_ = "file", ", ", "\\n"),
  CAST(EXTRACT(DATE FROM TIMESTAMP(start_date) AT TIME ZONE "${TIMEZONE}") AS STRING),
  CAST(EXTRACT(DATE FROM TIMESTAMP(end_date) AT TIME ZONE "${TIMEZONE}") AS STRING),
  IF(where_clause != "", "AND ("||where_clause||")", "")
);
END IF;

END;
