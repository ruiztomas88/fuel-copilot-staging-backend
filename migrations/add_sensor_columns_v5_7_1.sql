-- ============================================================================
-- Migration: Add sensor columns for ML and diagnostics
-- Version: v5.7.1
-- Date: December 13, 2025
-- ============================================================================

-- 1. Add new columns to fuel_metrics for sensor data persistence
ALTER TABLE fuel_metrics 
ADD COLUMN IF NOT EXISTS sats TINYINT UNSIGNED DEFAULT NULL COMMENT 'GPS satellites count (0-30)',
ADD COLUMN IF NOT EXISTS pwr_int FLOAT DEFAULT NULL COMMENT 'Internal/battery voltage (V)',
ADD COLUMN IF NOT EXISTS terrain_factor FLOAT DEFAULT 1.0 COMMENT 'Terrain consumption adjustment factor',
ADD COLUMN IF NOT EXISTS gps_quality VARCHAR(20) DEFAULT NULL COMMENT 'GPS quality level (EXCELLENT/GOOD/MODERATE/POOR/CRITICAL)',
ADD COLUMN IF NOT EXISTS idle_hours_ecu FLOAT DEFAULT NULL COMMENT 'ECU cumulative idle hours counter';

-- 2. Create table for DTC events (diagnostic trouble codes)
CREATE TABLE IF NOT EXISTS dtc_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    dtc_code VARCHAR(20) NOT NULL COMMENT 'Full DTC code (e.g., SPN123.FMI4)',
    spn INT COMMENT 'Suspect Parameter Number',
    fmi INT COMMENT 'Failure Mode Identifier',
    severity VARCHAR(20) DEFAULT 'WARNING' COMMENT 'CRITICAL/WARNING/INFO',
    system VARCHAR(50) DEFAULT 'UNKNOWN' COMMENT 'System (ENGINE/TRANSMISSION/AFTERTREATMENT/etc)',
    description TEXT COMMENT 'Human-readable description',
    raw_value VARCHAR(100) COMMENT 'Raw value from Wialon',
    resolved_at DATETIME DEFAULT NULL COMMENT 'When the DTC was cleared',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_dtc_code (dtc_code),
    INDEX idx_severity (severity),
    INDEX idx_unresolved (resolved_at, truck_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Diagnostic Trouble Code events for maintenance tracking';

-- 3. Create table for voltage events (anomalies only, not every reading)
CREATE TABLE IF NOT EXISTS voltage_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    voltage FLOAT NOT NULL COMMENT 'Voltage reading (V)',
    status VARCHAR(20) NOT NULL COMMENT 'CRITICAL_LOW/LOW/HIGH/CRITICAL_HIGH',
    is_engine_running BOOLEAN DEFAULT FALSE,
    rpm INT DEFAULT NULL,
    message TEXT,
    resolved_at DATETIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_status (status),
    INDEX idx_unresolved (resolved_at, truck_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Voltage anomaly events for electrical issue tracking';

-- 4. Create table for GPS quality events (only when quality degrades)
CREATE TABLE IF NOT EXISTS gps_quality_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    satellites TINYINT UNSIGNED NOT NULL,
    quality VARCHAR(20) NOT NULL COMMENT 'POOR/CRITICAL',
    estimated_accuracy_m FLOAT COMMENT 'Estimated position accuracy in meters',
    duration_minutes INT DEFAULT NULL COMMENT 'How long quality was degraded',
    location_lat DOUBLE DEFAULT NULL,
    location_lon DOUBLE DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_quality (quality)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='GPS quality degradation events';

-- 5. Add indexes for ML queries on fuel_metrics
ALTER TABLE fuel_metrics
ADD INDEX IF NOT EXISTS idx_mpg_analysis (truck_id, timestamp_utc, mpg_current, speed_mph),
ADD INDEX IF NOT EXISTS idx_idle_analysis (truck_id, timestamp_utc, idle_gph, rpm, truck_status),
ADD INDEX IF NOT EXISTS idx_drift_analysis (truck_id, timestamp_utc, drift_pct, sensor_pct, estimated_pct);

-- ============================================================================
-- Verification queries (run these to confirm migration worked)
-- ============================================================================

-- Check new columns exist:
-- DESCRIBE fuel_metrics;

-- Check new tables exist:
-- SHOW TABLES LIKE '%events';
-- SHOW TABLES LIKE 'dtc%';

-- ============================================================================
-- Rollback (if needed)
-- ============================================================================
-- ALTER TABLE fuel_metrics 
--   DROP COLUMN IF EXISTS sats,
--   DROP COLUMN IF EXISTS pwr_int,
--   DROP COLUMN IF EXISTS terrain_factor,
--   DROP COLUMN IF EXISTS gps_quality,
--   DROP COLUMN IF EXISTS idle_hours_ecu;
-- DROP TABLE IF EXISTS dtc_events;
-- DROP TABLE IF EXISTS voltage_events;
-- DROP TABLE IF EXISTS gps_quality_events;
