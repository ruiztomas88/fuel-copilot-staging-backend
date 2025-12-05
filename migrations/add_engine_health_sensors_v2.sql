-- ============================================
-- FUEL COPILOT - ENGINE HEALTH SENSORS MIGRATION
-- v3.12.26: Add oil_temp_f column if missing
-- ============================================

-- Check and add oil_temp_f if it doesn't exist (some DBs may have it as oil_temp)
-- Run this on the VM after git pull

-- Add oil_temp_f if not exists
ALTER TABLE fuel_metrics 
ADD COLUMN IF NOT EXISTS oil_temp_f FLOAT DEFAULT NULL AFTER oil_pressure_psi;

-- Add intake_air_temp_f if not exists
ALTER TABLE fuel_metrics 
ADD COLUMN IF NOT EXISTS intake_air_temp_f FLOAT DEFAULT NULL AFTER def_level_pct;

-- Verify columns exist
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'fuel_copilot'
  AND TABLE_NAME = 'fuel_metrics'
  AND COLUMN_NAME IN ('oil_pressure_psi', 'oil_temp_f', 'battery_voltage', 'engine_load_pct', 'def_level_pct', 'intake_air_temp_f');
