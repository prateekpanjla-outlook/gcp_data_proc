-- Phase 2 processing summary: files processed, records in/out, errors, duration
-- Parses unstructured f-string logs from file_processor.py:
--   "Completed {file_name}: {records_in} in, {records_out} out, {errors} errors, {duration}s"

SELECT
    DATE(timestamp) AS processing_date,
    REGEXP_EXTRACT(textPayload, r'Completed ([^:]+):') AS file_name,
    CAST(REGEXP_EXTRACT(textPayload, r'(\d+) in,') AS INT64) AS records_in,
    CAST(REGEXP_EXTRACT(textPayload, r'(\d+) out,') AS INT64) AS records_out,
    CAST(REGEXP_EXTRACT(textPayload, r'(\d+) errors,') AS INT64) AS errors,
    CAST(REGEXP_EXTRACT(textPayload, r'([\d.]+)s$') AS FLOAT64) AS duration_seconds,
    timestamp
FROM `PROJECT_ID.pipeline_logs.run_googleapis_com_stdout`
WHERE
    textPayload LIKE '%Completed%'
    AND textPayload LIKE '%in,%out,%errors%'
ORDER BY timestamp DESC
