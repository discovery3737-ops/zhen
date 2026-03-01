-- Prompt09: delivery logs exist (template)
\echo '--- Prompt09 DB checks ---'
SELECT to_regclass('public.send_log') IS NOT NULL AS send_log_exists;
