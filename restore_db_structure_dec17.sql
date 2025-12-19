-- ============================================================================
-- RESTORE DATABASE STRUCTURE - December 17, 2025
-- ============================================================================
-- This script recreates the EXACT 27-table structure that was working
-- before the database recreation on Dec 19.
--
-- IMPORTANT: This script:
-- 1. Drops the 5 EXTRA tables that shouldn't exist
-- 2. Ensures the 27 correct tables exist with proper structure
-- 3. Does NOT delete data - only fixes structure
--
-- Run on VM with:
--   mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot < restore_db_structure_dec17.sql
--
-- ============================================================================

USE fuel_copilot;

-- ============================================================================
-- STEP 1: DROP THE 5 EXTRA TABLES (that weren't in Dec 17 database)
-- ============================================================================
DROP TABLE IF EXISTS truck_ignition_events;
DROP TABLE IF EXISTS truck_specs;
DROP TABLE IF EXISTS truck_speeding_events;
DROP TABLE IF EXISTS truck_trips;
DROP TABLE IF EXISTS truck_units;

-- ============================================================================
-- STEP 2: ENSURE THE 27 CORRECT TABLES EXIST
-- ============================================================================

-- Command Center Tables (7 tables)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cc_algorithm_state (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    algorithm_name VARCHAR(50) NOT NULL,
    state JSON,
    confidence FLOAT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_truck (truck_id),
    INDEX idx_algorithm (algorithm_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cc_anomaly_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(20),
    details JSON,
    resolved BOOLEAN DEFAULT FALSE,
    INDEX idx_truck_time (truck_id, detected_at),
    INDEX idx_type (anomaly_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cc_correlation_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50),
    correlation_score FLOAT,
    related_events JSON,
    INDEX idx_truck (truck_id),
    INDEX idx_time (event_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cc_def_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    def_level_pct FLOAT,
    consumption_rate FLOAT,
    prediction JSON,
    INDEX idx_truck_time (truck_id, timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cc_maintenance_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    maintenance_type VARCHAR(50),
    predicted_date DATE,
    confidence FLOAT,
    details JSON,
    INDEX idx_truck (truck_id),
    INDEX idx_predicted (predicted_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cc_risk_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    risk_type VARCHAR(50),
    risk_score FLOAT,
    factors JSON,
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_type (risk_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS command_center_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value JSON,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Engine Health Tables (5 tables)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS engine_health_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    alert_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20),
    message TEXT,
    sensor_values JSON,
    acknowledged BOOLEAN DEFAULT FALSE,
    INDEX idx_truck_time (truck_id, alert_timestamp),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS engine_health_baselines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    baseline_value FLOAT,
    std_deviation FLOAT,
    sample_count INT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_truck_sensor (truck_id, sensor_name),
    INDEX idx_truck (truck_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS engine_health_notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    notification_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_type VARCHAR(50),
    message TEXT,
    sent_via VARCHAR(20),
    delivery_status VARCHAR(20),
    INDEX idx_truck_time (truck_id, notification_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS engine_health_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    snapshot_timestamp DATETIME NOT NULL,
    oil_pressure FLOAT,
    oil_temp FLOAT,
    coolant_temp FLOAT,
    rpm INT,
    engine_load FLOAT,
    intake_temp FLOAT,
    health_score FLOAT,
    INDEX idx_truck_time (truck_id, snapshot_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS engine_health_thresholds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20),
    sensor_name VARCHAR(50) NOT NULL,
    warning_min FLOAT,
    warning_max FLOAT,
    critical_min FLOAT,
    critical_max FLOAT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_truck_sensor (truck_id, sensor_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Predictive Maintenance Tables (3 tables)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pm_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    component VARCHAR(50) NOT NULL,
    prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    predicted_failure_date DATE,
    confidence FLOAT,
    current_health_score FLOAT,
    factors JSON,
    INDEX idx_truck_component (truck_id, component),
    INDEX idx_predicted (predicted_failure_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pm_sensor_daily_avg (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    avg_value FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    sample_count INT,
    UNIQUE KEY unique_truck_date_sensor (truck_id, date, sensor_name),
    INDEX idx_truck_date (truck_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pm_sensor_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    sensor_value FLOAT,
    anomaly_detected BOOLEAN DEFAULT FALSE,
    INDEX idx_truck_time_sensor (truck_id, timestamp_utc, sensor_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Main Tables (6 tables)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fuel_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50),
    truck_status VARCHAR(20),
    latitude FLOAT,
    longitude FLOAT,
    speed_mph FLOAT,
    estimated_liters FLOAT,
    estimated_gallons FLOAT,
    estimated_pct FLOAT,
    sensor_pct FLOAT,
    sensor_liters FLOAT,
    sensor_gallons FLOAT,
    consumption_lph FLOAT,
    consumption_gph FLOAT,
    mpg_current FLOAT,
    rpm INT,
    engine_hours FLOAT,
    odometer_mi FLOAT,
    altitude_ft FLOAT,
    hdop FLOAT,
    coolant_temp_f FLOAT,
    idle_gph FLOAT,
    idle_method VARCHAR(50),
    idle_mode VARCHAR(50),
    drift_pct FLOAT,
    drift_warning VARCHAR(10),
    anchor_detected VARCHAR(10),
    anchor_type VARCHAR(20),
    data_age_min FLOAT,
    oil_pressure_psi FLOAT,
    oil_temp_f FLOAT,
    battery_voltage FLOAT,
    engine_load_pct FLOAT,
    def_level_pct FLOAT,
    ambient_temp_f FLOAT,
    intake_air_temp_f FLOAT,
    trans_temp_f FLOAT,
    fuel_temp_f FLOAT,
    intercooler_temp_f FLOAT,
    intake_press_kpa FLOAT,
    retarder_level INT,
    sats INT,
    pwr_int FLOAT,
    terrain_factor FLOAT,
    gps_quality VARCHAR(100),
    idle_hours_ecu FLOAT,
    dtc INT,
    dtc_code VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_truck_timestamp (truck_id, timestamp_utc),
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_truck_status (truck_id, truck_status),
    INDEX idx_timestamp (timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dtc_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    unit_id INT,
    timestamp_utc DATETIME NOT NULL,
    dtc_code VARCHAR(50) NOT NULL,
    component VARCHAR(100),
    severity VARCHAR(20),
    status VARCHAR(20) DEFAULT 'NEW',
    description TEXT,
    action_required TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_code (dtc_code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS refuel_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50),
    fuel_before FLOAT,
    fuel_after FLOAT,
    gallons_added FLOAT,
    refuel_type VARCHAR(50) DEFAULT 'NORMAL',
    latitude FLOAT,
    longitude FLOAT,
    confidence FLOAT,
    validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_truck_time (truck_id, timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS telemetry_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    data_type VARCHAR(50),
    value FLOAT,
    unit VARCHAR(20),
    metadata JSON,
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_type (data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    start_location JSON,
    end_location JSON,
    distance_miles FLOAT,
    duration_hours FLOAT,
    avg_speed FLOAT,
    fuel_consumed_gallons FLOAT,
    trip_mpg FLOAT,
    INDEX idx_truck_start (truck_id, start_time),
    INDEX idx_truck_end (truck_id, end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS truck_health_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    health_score FLOAT,
    component_scores JSON,
    alerts_count INT,
    maintenance_status VARCHAR(50),
    INDEX idx_truck_time (truck_id, timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Support Tables (7 tables)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gps_quality_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    satellites INT,
    hdop FLOAT,
    quality VARCHAR(20),
    estimated_accuracy_m FLOAT,
    INDEX idx_truck_time (truck_id, timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS j1939_spn_lookup (
    id INT AUTO_INCREMENT PRIMARY KEY,
    spn INT NOT NULL,
    name VARCHAR(255),
    description TEXT,
    unit VARCHAR(50),
    data_length INT,
    resolution FLOAT,
    offset FLOAT,
    UNIQUE KEY unique_spn (spn),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS maintenance_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    alert_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_type VARCHAR(50),
    component VARCHAR(100),
    severity VARCHAR(20),
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    INDEX idx_truck_time (truck_id, alert_timestamp),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    component VARCHAR(100) NOT NULL,
    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    predicted_maintenance_date DATE,
    confidence FLOAT,
    reason TEXT,
    INDEX idx_truck_component (truck_id, component),
    INDEX idx_predicted (predicted_maintenance_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS truck_sensors_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    unit_id INT,
    timestamp_utc DATETIME NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    altitude FLOAT,
    speed FLOAT,
    course INT,
    satellites INT,
    hdop FLOAT,
    inputs INT,
    outputs INT,
    adc JSON,
    fuel_lvl FLOAT,
    fuel_rate FLOAT,
    rpm INT,
    odometer FLOAT,
    engine_hours FLOAT,
    total_fuel_used FLOAT,
    coolant_temp FLOAT,
    pwr_ext FLOAT,
    pwr_int FLOAT,
    engine_load FLOAT,
    oil_press FLOAT,
    oil_temp FLOAT,
    def_level FLOAT,
    intake_air_temp FLOAT,
    trans_temp FLOAT,
    fuel_temp FLOAT,
    intercooler_temp FLOAT,
    intake_press FLOAT,
    retarder INT,
    idle_hours FLOAT,
    dtc INT,
    dtc_code VARCHAR(255),
    barometer FLOAT,
    ambient_temp FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_truck_timestamp (truck_id, timestamp_utc),
    INDEX idx_truck_updated (truck_id, updated_at),
    INDEX idx_timestamp (timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS voltage_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    voltage FLOAT NOT NULL,
    voltage_type VARCHAR(20),
    is_engine_running BOOLEAN,
    status VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'Database structure restored successfully!' as Status;
SELECT CONCAT('Total tables: ', COUNT(*)) as TableCount 
FROM information_schema.tables 
WHERE table_schema = 'fuel_copilot';

-- Show all tables
SHOW TABLES;
