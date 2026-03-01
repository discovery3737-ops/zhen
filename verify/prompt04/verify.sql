-- Prompt04: MinIO integration + run stats
\echo '--- Prompt04 DB checks ---'
SELECT to_regclass('public.run_dataset_stat') IS NOT NULL AS run_dataset_stat_exists;

SELECT run_id, dt, status, message
FROM app_job_run
ORDER BY started_at DESC
LIMIT 5;
