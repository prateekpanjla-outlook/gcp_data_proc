-- All pipeline errors across phases 1-3
-- Useful for alerting and debugging

SELECT
    timestamp,
    resource.type AS service_type,
    CASE resource.type
        WHEN 'cloud_run_job' THEN 'phase1_ingestion'
        WHEN 'cloud_run_revision' THEN 'phase2_processing'
        WHEN 'cloud_function' THEN 'phase3_bq_load'
    END AS phase,
    severity,
    textPayload AS error_message
FROM `PROJECT_ID.pipeline_logs.*`
WHERE severity IN ('ERROR', 'WARNING')
ORDER BY timestamp DESC
LIMIT 100
