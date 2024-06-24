CREATE OR REPLACE FUNCTION
  ${DATASET.NAME}.${__name__}(field STRING, expression STRING, flags STRING)
RETURNS BOOL
LANGUAGE js AS
r"""
const regexPattern = new RegExp(`${expression}`, `${flags}`);
return regexPattern.test(`${field}`);
""";
