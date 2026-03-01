-- Prompt06: track summary exists
\echo '--- Prompt06 DB checks ---'
SELECT to_regclass('public.fact_track_day_summary') IS NOT NULL AS track_summary_exists;

SELECT dt, vehicle_no, mileage_km, max_speed, point_count
FROM fact_track_day_summary
ORDER BY dt DESC
LIMIT 10;
