-- ═══════════════════════════════════════════════════════════════════════
-- MIGRATION: Add odom_delta_mi column to fuel_metrics
-- ═══════════════════════════════════════════════════════════════════════
-- Purpose: Support BUG-002 fix (cost_per_mile calculation requires distance)
-- Date: December 23, 2025
-- Version: v3.12.31
--
-- Usage:
--   mysql -u fuel_admin -p fuel_copilot < migrate_add_odom_delta_mi.sql
--
-- Rollback (if needed):
--   ALTER TABLE fuel_metrics DROP COLUMN odom_delta_mi;
-- ═══════════════════════════════════════════════════════════════════════

USE fuel_copilot;

-- Verificar tabla existe
SELECT 'Checking fuel_metrics table...' AS status;
SELECT COUNT(*) AS total_rows FROM fuel_metrics;

-- ───────────────────────────────────────────────────────────────────────
-- Add odom_delta_mi column (miles traveled since last reading)
-- ───────────────────────────────────────────────────────────────────────
-- This column stores the validated distance delta used for MPG and cost_per_mile calculations
-- Range: 0.1 to 500 miles (sanity checks in code)

ALTER TABLE fuel_metrics 
ADD COLUMN odom_delta_mi DECIMAL(8,3) NULL 
COMMENT 'Validated odometer delta (miles) since last reading - used for cost_per_mile'
AFTER odometer_mi;

-- ═══════════════════════════════════════════════════════════════════════
-- VERIFICATION
-- ═══════════════════════════════════════════════════════════════════════

-- Verify column was added
DESCRIBE fuel_metrics;

-- Check column exists in correct position
SELECT 
    COLUMN_NAME, 
    COLUMN_TYPE, 
    IS_NULLABLE, 
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'fuel_copilot' 
  AND TABLE_NAME = 'fuel_metrics' 
  AND COLUMN_NAME = 'odom_delta_mi';

SELECT '✅ Migration Complete: odom_delta_mi column added successfully!' AS status;
SELECT 'Note: Existing rows will have NULL values - new data will populate this column' AS note;
