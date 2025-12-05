-- ============================================================================
-- Migration: Add new sensor columns to fuel_metrics
-- Version: v3.12.22
-- Date: 2025-12-05
-- Description: Add oil_pressure_psi, battery_voltage, engine_load_pct, 
--              oil_temp_f, and def_level_pct columns to fuel_metrics table
-- ============================================================================

USE fuel_analytics;

-- Add new sensor columns to fuel_metrics table
ALTER TABLE fuel_metrics
ADD COLUMN oil_pressure_psi FLOAT DEFAULT NULL,
ADD COLUMN battery_voltage FLOAT DEFAULT NULL,
ADD COLUMN engine_load_pct FLOAT DEFAULT NULL,
ADD COLUMN oil_temp_f FLOAT DEFAULT NULL,
ADD COLUMN def_level_pct FLOAT DEFAULT NULL;

-- Add indexes for better query performance on new columns
CREATE INDEX idx_oil_pressure ON fuel_metrics(oil_pressure_psi);
CREATE INDEX idx_battery_voltage ON fuel_metrics(battery_voltage);
CREATE INDEX idx_engine_load ON fuel_metrics(engine_load_pct);
CREATE INDEX idx_oil_temp ON fuel_metrics(oil_temp_f);
CREATE INDEX idx_def_level ON fuel_metrics(def_level_pct);

-- Verify columns were added
DESCRIBE fuel_metrics;
