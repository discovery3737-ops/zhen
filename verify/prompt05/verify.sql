-- Prompt05: Parquet blob metadata exists
\echo '--- Prompt05 DB checks ---'
SELECT to_regclass('public.fact_track_day_blob') IS NOT NULL AS track_blob_exists;

SELECT dt, vehicle_no, payload_format, payload_path, point_count, byte_size
FROM fact_track_day_blob
ORDER BY dt DESC, vehicle_no
LIMIT 10;
