CREATE OR REPLACE FUNCTION
  ${DATASET.NAME}.${__name__}(field STRING, expression STRING)
RETURNS BOOL
LANGUAGE js AS
r"""
const regexPattern = new RegExp(`${expression}`);
return regexPattern.test(field);
""";
