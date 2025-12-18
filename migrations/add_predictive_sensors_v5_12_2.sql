-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration: Add Predictive Maintenance Sensors to fuel_metrics
-- Version: 5.12.2
-- Date: December 2025
-- Author: AI Integration Team
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose:
--   Add temperature and pressure sensors needed for Command Center predictive
--   maintenance correlations. These sensors were recently mapped from Wialon
--   (intk_t, fuel_t, intrclr_t, trams_t, intake_pressure, actual_retarder).
--
-- Enables:
--   - overheating_syndrome detection (cool_temp + oil_temp + trams_t correlation)
--   - turbo_lag detection (intk_t + engine_load + cool_temp correlation)
--   - Transmission health monitoring
--   - Fuel system thermal analysis
--   - Turbocharger performance tracking
--
-- ═══════════════════════════════════════════════════════════════════════════════

USE fuel_copilot;

-- Add transmission temperature (°F)
ALTER TABLE fuel_metrics 
ADD COLUMN trans_temp_f DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Transmission oil temperature in Fahrenheit - from Wialon sensor trams_t';

-- Add fuel temperature (°F)
ALTER TABLE fuel_metrics 
ADD COLUMN fuel_temp_f DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Fuel temperature in Fahrenheit - from Wialon sensor fuel_t';

-- Add intercooler temperature (°F)
ALTER TABLE fuel_metrics 
ADD COLUMN intercooler_temp_f DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Intercooler temperature in Fahrenheit - from Wialon sensor intrclr_t';

-- Add intake manifold pressure (kPa)
ALTER TABLE fuel_metrics 
ADD COLUMN intake_press_kpa DECIMAL(6,2) DEFAULT NULL 
COMMENT 'Intake manifold pressure in kPa - from Wialon sensor intake_pressure';

-- Add retarder status/level
ALTER TABLE fuel_metrics 
ADD COLUMN retarder_level DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Retarder brake status/level - from Wialon sensor actual_retarder';

-- ═══════════════════════════════════════════════════════════════════════════════
-- Verification Query
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT 
    COUNT(*) as total_rows,
    COUNT(trans_temp_f) as has_trans_temp,
    COUNT(fuel_temp_f) as has_fuel_temp,
    COUNT(intercooler_temp_f) as has_intercooler,
    COUNT(intake_press_kpa) as has_intake_press,
    COUNT(retarder_level) as has_retarder,
    ROUND(COUNT(trans_temp_f) * 100.0 / COUNT(*), 2) as trans_temp_coverage_pct
FROM fuel_metrics
WHERE timestamp > DATE_SUB(NOW(), INTERVAL 24 HOUR);

-- Expected Result:
-- After wialon_sync runs, coverage should increase from 0% to ~30-40%
-- (matching the sensor availability we saw in FF7702 test - 38.7%)
