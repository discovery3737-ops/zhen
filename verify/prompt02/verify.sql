-- Prompt02: noVNC credential status checks
\echo '--- Prompt02 DB checks ---'
SELECT to_regclass('public.app_credential') IS NOT NULL AS app_credential_exists;

SELECT tenant_id, name, status, updated_at
FROM app_credential
ORDER BY updated_at DESC
LIMIT 3;
