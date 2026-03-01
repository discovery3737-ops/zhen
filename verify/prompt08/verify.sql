-- Prompt08: geocode cache table exists and addresses are populated
\echo '--- Prompt08 DB checks ---'
SELECT to_regclass('public.geocode_cache') IS NOT NULL AS geocode_cache_exists;

SELECT grid_key, address, updated_at
FROM geocode_cache
ORDER BY updated_at DESC
LIMIT 10;
