-- Prompt03: configuration tables exist
\echo '--- Prompt03 DB checks ---'
SELECT to_regclass('public.global_config') IS NOT NULL AS global_config_exists;
SELECT to_regclass('public.dataset_def') IS NOT NULL AS dataset_def_exists;
SELECT to_regclass('public.dataset_config') IS NOT NULL AS dataset_config_exists;
SELECT to_regclass('public.schedule_config') IS NOT NULL AS schedule_config_exists;
SELECT to_regclass('public.delivery_config') IS NOT NULL AS delivery_config_exists;

SELECT key, value FROM global_config ORDER BY key LIMIT 20;
SELECT dataset_code, enabled FROM dataset_config ORDER BY dataset_code;
SELECT enabled, time FROM schedule_config LIMIT 5;
SELECT mode, target, notify_admins FROM delivery_config LIMIT 5;
