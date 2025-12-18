-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration: Add ALL Missing Sensor Columns to fuel_metrics
-- Version: 5.12.3
-- Date: December 2025
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose:
--   Add ALL sensor columns that wialon_sync is trying to insert but don't exist.
--   This includes engine health sensors, diagnostic data, GPS quality, etc.
--
-- Context:
--   fuel_metrics table was created with only basic fuel-tracking columns.
--   wialon_sync_enhanced.py expects to save 14+ additional sensor columns.
--   Missing columns cause INSERT failures and data loss.
--
-- ═══════════════════════════════════════════════════════════════════════════════

USE fuel_copilot;

-- ENGINE HEALTH SENSORS (for Command Center predictive maintenance)
ALTER TABLE fuel_metrics 
ADD COLUMN oil_pressure_psi DECIMAL(5,1) DEFAULT NULL 
COMMENT 'Engine oil pressure in PSI - from Wialon sensor oil_press';

ALTER TABLE fuel_metrics 
ADD COLUMN oil_temp_f DECIMAL(5,1) DEFAULT NULL 
COMMENT 'Engine oil temperature in Fahrenheit - from Wialon sensor oil_temp';

ALTER TABLE fuel_metrics 
ADD COLUMN battery_voltage DECIMAL(4,2) DEFAULT NULL 
COMMENT 'Battery voltage in volts - from Wialon sensor pwr_ext';

ALTER TABLE fuel_metrics 
ADD COLUMN engine_load_pct DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Engine load percentage (0-100%) - from Wialon sensor engine_load';

ALTER TABLE fuel_metrics 
ADD COLUMN def_level_pct DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Diesel Exhaust Fluid level percentage - from Wialon sensor def_level';

-- TEMPERATURE SENSORS (already added in v5.12.2, safe to re-run)
-- trans_temp_f, fuel_temp_f, intercooler_temp_f already exist

-- ENVIRONMENTAL SENSORS
ALTER TABLE fuel_metrics 
ADD COLUMN ambient_temp_f DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Ambient/outside air temperature in Fahrenheit - from Wialon sensor ambient_temp';

ALTER TABLE fuel_metrics 
ADD COLUMN intake_air_temp_f DECIMAL(5,2) DEFAULT NULL 
COMMENT 'Intake manifold air temperature in Fahrenheit - from Wialon sensor intk_t';

-- GPS QUALITY METRICS
ALTER TABLE fuel_metrics 
ADD COLUMN sats INT DEFAULT NULL 
COMMENT 'Number of GPS satellites in view';

ALTER TABLE fuel_metrics 
ADD COLUMN gps_quality VARCHAR(100) DEFAULT NULL 
COMMENT 'GPS quality descriptor: EXCELLENT|sats=X|acc=Ym format';

-- POWER/ELECTRICAL
ALTER TABLE fuel_metrics 
ADD COLUMN pwr_int DECIMAL(4,2) DEFAULT NULL 
COMMENT 'Internal power voltage - from Wialon sensor pwr_int';

-- TERRAIN/ENVIRONMENTAL ADJUSTMENTS
ALTER TABLE fuel_metrics 
ADD COLUMN terrain_factor DECIMAL(6,3) DEFAULT 1.000 
COMMENT 'Terrain difficulty multiplier for fuel consumption (1.0 = flat, >1.0 = hilly)';

-- ENGINE USAGE TRACKING
ALTER TABLE fuel_metrics 
ADD COLUMN idle_hours_ecu DECIMAL(10,2) DEFAULT NULL 
COMMENT 'Total engine idle hours from ECU - from Wialon sensor idle_hours';

-- DIAGNOSTIC TROUBLE CODES
ALTER TABLE fuel_metrics 
ADD COLUMN dtc INT DEFAULT 0 
COMMENT 'Number of active Diagnostic Trouble Codes (0 = no issues)';

ALTER TABLE fuel_metrics 
ADD COLUMN dtc_code VARCHAR(500) DEFAULT NULL 
COMMENT 'Comma-separated DTC codes in SPN.FMI format (e.g., "100.4,157.3")';

-- ═══════════════════════════════════════════════════════════════════════════════
-- Verification Query
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT 
    COUNT(*) as total_rows,
    -- Engine Health
    COUNT(oil_pressure_psi) as has_oil_pressure,
    COUNT(oil_temp_f) as has_oil_temp,
    COUNT(battery_voltage) as has_battery,
    COUNT(engine_load_pct) as has_engine_load,
    COUNT(def_level_pct) as has_def_level,
    -- Temperature
    COUNT(coolant_temp_f) as has_coolant_temp,
    COUNT(trans_temp_f) as has_trans_temp,
    COUNT(intake_air_temp_f) as has_intake_temp,
    COUNT(ambient_temp_f) as has_ambient_temp,
    -- Diagnostics
    COUNT(dtc_code) as has_dtc,
    -- GPS
    COUNT(gps_quality) as has_gps_quality,
    -- Overall health
    ROUND(COUNT(oil_pressure_psi) * 100.0 / COUNT(*), 2) as oil_coverage_pct,
    ROUND(COUNT(dtc_code) * 100.0 / COUNT(*), 2) as dtc_coverage_pct
FROM fuel_metrics
WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR);

-- Expected Result:
-- After wialon_sync runs with these columns, coverage should increase significantly
-- Oil sensors: ~30-40% (based on FF7702 test results)
-- DTC sensors: ~40-50% (trucks with J1939 support)
-- GPS quality: ~90%+ (most trucks have GPS)
