-- ============================================================================
-- Migration: Add DTC columns to fuel_metrics
-- Version: v5.7.5
-- Date: December 14, 2025
-- Description: Add dtc (count/flag) and dtc_code (actual codes) to fuel_metrics
-- ============================================================================

USE fuel_analytics;

-- Add DTC columns
ALTER TABLE fuel_metrics 
ADD COLUMN IF NOT EXISTS dtc FLOAT DEFAULT NULL COMMENT 'DTC count or flag (0=none, >0=active DTCs)',
ADD COLUMN IF NOT EXISTS dtc_code VARCHAR(255) DEFAULT NULL COMMENT 'Actual DTC codes in SPN.FMI format (e.g., 100.4,157.3)';

-- Add index for DTC queries
CREATE INDEX IF NOT EXISTS idx_dtc ON fuel_metrics(dtc);
CREATE INDEX IF NOT EXISTS idx_dtc_code ON fuel_metrics(dtc_code(50));

-- Verify
-- DESCRIBE fuel_metrics;
-- SELECT truck_id, dtc, dtc_code FROM fuel_metrics WHERE dtc > 0 LIMIT 10;
