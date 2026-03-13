-- Phase 3 BQ load summary: rows loaded per file, failures
-- Parses unstructured f-string logs from phase3 main.py:
--   "Loaded {rows} rows"
--   "Processing event: bucket={bucket}, file={file}, size={size}"
--   "Failed to load {gcs_uri}: {error}"

-- Successful loads
SELECT
    DATE(timestamp) AS load_date,
    REGEXP_EXTRACT(textPayload, r'file=([^,]+),') AS file_name,
    CAST(REGEXP_EXTRACT(textPayload, r'Loaded (\d+) rows') AS INT64) AS rows_loaded,
    'success' AS status,
    timestamp
FROM `PROJECT_ID.pipeline_logs.cloudfunctions_googleapis_com_cloud_functions`
WHERE textPayload LIKE '%Loaded%rows%'

UNION ALL

-- Failed loads
SELECT
    DATE(timestamp) AS load_date,
    REGEXP_EXTRACT(textPayload, r'Failed to load gs://[^/]+/(.+):') AS file_name,
    0 AS rows_loaded,
    'failed' AS status,
    timestamp
FROM `PROJECT_ID.pipeline_logs.cloudfunctions_googleapis_com_cloud_functions`
WHERE textPayload LIKE '%Failed to load%'

ORDER BY timestamp DESC
