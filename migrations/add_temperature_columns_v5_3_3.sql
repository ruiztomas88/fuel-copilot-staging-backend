-- ============================================================================
-- Migration: Add temperature sensor columns and critical index
-- Version: v5.3.3
-- Date: 2025-12-10
-- Description: 
--   1. Add ambient_temp_f and intake_air_temp_f columns to fuel_metrics
--   2. Create critical composite index for truck_id + timestamp_utc (N+1 fix)
-- ============================================================================

USE fuel_copilot;

-- ============================================================================
-- 1. ADD TEMPERATURE COLUMNS (from Wialon sensors, currently not stored)
-- ============================================================================

-- Check if columns exist before adding
SET @col_exists = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot' 
    AND TABLE_NAME = 'fuel_metrics' 
    AND COLUMN_NAME = 'ambient_temp_f'
);

-- Add ambient_temp_f if not exists
ALTER TABLE fuel_metrics
ADD COLUMN IF NOT EXISTS ambient_temp_f FLOAT DEFAULT NULL
COMMENT 'Ambient/Outside temperature in Fahrenheit (from air_temp sensor)';

-- Add intake_air_temp_f if not exists  
ALTER TABLE fuel_metrics
ADD COLUMN IF NOT EXISTS intake_air_temp_f FLOAT DEFAULT NULL
COMMENT 'Engine intake air temperature in Fahrenheit';

-- ============================================================================
-- 2. CREATE CRITICAL COMPOSITE INDEX (BIGGEST PERFORMANCE IMPACT)
-- ============================================================================
-- This index fixes the N+1 query pattern in get_all_trucks()
-- Before: 41 separate queries (one per truck)
-- After: 1 query using index for efficient truck_id + timestamp lookup

-- Check if index exists before creating
SET @idx_exists = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.STATISTICS 
    WHERE TABLE_SCHEMA = 'fuel_copilot' 
    AND TABLE_NAME = 'fuel_metrics' 
    AND INDEX_NAME = 'idx_truck_timestamp'
);

-- Create composite index if not exists
-- DESC on timestamp_utc because we always want the LATEST record
CREATE INDEX IF NOT EXISTS idx_truck_timestamp 
ON fuel_metrics(truck_id, timestamp_utc DESC);

-- ============================================================================
-- 3. VERIFY CHANGES
-- ============================================================================

-- Show new columns
SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'fuel_copilot' 
AND TABLE_NAME = 'fuel_metrics'
AND COLUMN_NAME IN ('ambient_temp_f', 'intake_air_temp_f');

-- Show indexes
SHOW INDEX FROM fuel_metrics WHERE Key_name = 'idx_truck_timestamp';

-- ============================================================================
-- 4. EXPECTED QUERY IMPROVEMENT
-- ============================================================================
-- 
-- BEFORE (without index):
-- SELECT ... FROM fuel_metrics WHERE truck_id = 'JC1282' 
--   ORDER BY timestamp_utc DESC LIMIT 1
-- → Full table scan: ~500ms per truck × 41 trucks = 20+ seconds
--
-- AFTER (with idx_truck_timestamp):
-- Same query → Index seek: ~5ms per truck × 41 trucks = ~200ms
-- 
-- Or even better, single query with window function:
-- SELECT * FROM (
--   SELECT *, ROW_NUMBER() OVER (PARTITION BY truck_id ORDER BY timestamp_utc DESC) as rn
--   FROM fuel_metrics WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
-- ) t WHERE rn = 1
-- → Single pass: ~100ms total
-- ============================================================================
