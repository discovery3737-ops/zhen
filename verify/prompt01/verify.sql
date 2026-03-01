-- Prompt01: integration baseline DB checks
\echo '--- Prompt01 DB checks ---'
SELECT to_regclass('public.app_job_run') IS NOT NULL AS app_job_run_exists;

SELECT run_id, dt, status, started_at, finished_at
FROM app_job_run
ORDER BY started_at DESC
LIMIT 5;
