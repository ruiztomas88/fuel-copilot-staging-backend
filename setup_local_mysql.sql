-- ============================================
-- FUEL COPILOT - SETUP LOCAL DATABASE (VM)
-- ============================================
-- Run as MySQL root user:
-- mysql -u root -p < setup_local_mysql.sql
-- ============================================

-- Create database
CREATE DATABASE IF NOT EXISTS fuel_copilot
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

-- Create user (skip if exists)
CREATE USER IF NOT EXISTS 'fuel_admin'@'localhost' IDENTIFIED BY 'FuelCopilot2025!';

-- Grant permissions
GRANT ALL PRIVILEGES ON fuel_copilot.* TO 'fuel_admin'@'localhost';
FLUSH PRIVILEGES;

USE fuel_copilot;

-- ============================================
-- TABLE: fuel_metrics (main data table)
-- ============================================
CREATE TABLE IF NOT EXISTS fuel_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Location & Status
    truck_status VARCHAR(20),  -- MOVING, STOPPED, IDLE
    latitude DOUBLE,
    longitude DOUBLE,
    speed DOUBLE,
    
    -- Fuel Data
    fuel_level_raw DOUBLE,
    fuel_level_filtered DOUBLE,
    fuel_capacity INT,
    fuel_percent DOUBLE,
    
    -- Consumption
    consumption_gph DOUBLE,
    consumption_rate DOUBLE,
    mpg_current DOUBLE,
    mpg_avg_24h DOUBLE,
    
    -- Engine Data
    engine_rpm INT,
    engine_hours DOUBLE,
    odometer DOUBLE,
    mileage_delta DOUBLE,
    
    -- Idle Detection
    idle_method VARCHAR(30),
    idle_duration_minutes INT,
    idle_gph DOUBLE COMMENT 'Idle fuel consumption rate (GPH) - v5.7.6',
    
    -- Kalman Filter
    kalman_estimate DOUBLE,
    kalman_uncertainty DOUBLE,
    
    -- Anchors
    anchor_type VARCHAR(20),
    anchor_fuel_level DOUBLE,
    
    -- Refuel Detection
    refuel_detected TINYINT(1) DEFAULT 0,
    refuel_amount DOUBLE,
    refuel_events_total INT DEFAULT 0,
    
    -- Sensor Data (added v3.12.22)
    engine_load DOUBLE COMMENT 'Engine load percentage',
    coolant_temp DOUBLE COMMENT 'Engine coolant temperature (°C)',
    ambient_temp DOUBLE COMMENT 'Ambient air temperature (°C)',
    
    -- DTC Data (added v5.7.5)
    active_dtc_count INT DEFAULT 0 COMMENT 'Number of active DTCs',
    dtc_codes JSON COMMENT 'Array of active DTC codes',
    dtc_severity VARCHAR(20) COMMENT 'Highest DTC severity: CRITICAL, HIGH, MEDIUM, LOW',
    
    -- Predictive Maintenance Sensors (added v5.12.2)
    trans_temp_f DECIMAL(5,2) COMMENT 'Transmission oil temperature (°F)',
    fuel_temp_f DECIMAL(5,2) COMMENT 'Fuel temperature (°F)',
    intercooler_temp_f DECIMAL(5,2) COMMENT 'Intercooler outlet temperature (°F)',
    intake_press_kpa DECIMAL(6,2) COMMENT 'Intake manifold pressure (kPa)',
    retarder_level DECIMAL(5,2) COMMENT 'Retarder/Jake brake level (%)',
    
    -- Additional Sensors (added v5.12.3)
    oil_pressure_psi DECIMAL(5,1) COMMENT 'Engine oil pressure (PSI)',
    oil_temp_f DECIMAL(5,1) COMMENT 'Engine oil temperature (°F)',
    boost_pressure_psi DOUBLE COMMENT 'Turbo boost pressure (PSI)',
    exhaust_temp_f DOUBLE COMMENT 'Exhaust gas temperature (°F)',
    def_level_pct DECIMAL(5,2) COMMENT 'DEF tank level (%)',
    battery_voltage DECIMAL(4,2) COMMENT 'Battery voltage (V)',
    engine_load_pct DECIMAL(5,2) COMMENT 'Engine load percentage (0-100%)',
    ambient_temp_f DECIMAL(5,2) COMMENT 'Ambient air temperature (°F)',
    intake_air_temp_f DECIMAL(5,2) COMMENT 'Intake manifold air temperature (°F)',
    sats INT COMMENT 'Number of GPS satellites in view',
    gps_quality VARCHAR(100) COMMENT 'GPS quality descriptor',
    pwr_int DECIMAL(4,2) COMMENT 'Internal power voltage',
    terrain_factor DECIMAL(6,3) DEFAULT 1.000 COMMENT 'Terrain difficulty multiplier (1.0 = flat)',
    idle_hours_ecu DECIMAL(10,2) COMMENT 'Total engine idle hours from ECU',
    dtc INT DEFAULT 0 COMMENT 'Number of active DTCs (legacy)',
    dtc_code VARCHAR(500) COMMENT 'Comma-separated DTC codes in SPN.FMI format',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_carrier (carrier_id),
    INDEX idx_status (truck_status),
    INDEX idx_unit (unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Main fuel metrics table with sensor data';

-- ============================================
-- TABLE: refuel_events (detected refuels)
-- ============================================
CREATE TABLE IF NOT EXISTS refuel_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Refuel Details
    fuel_before DOUBLE,
    fuel_after DOUBLE,
    gallons_added DOUBLE,
    refuel_type VARCHAR(30),  -- NORMAL, GAP_DETECTED, CONSECUTIVE
    
    -- Location
    latitude DOUBLE,
    longitude DOUBLE,
    
    -- Validation
    confidence DOUBLE,
    validated TINYINT(1) DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_unit (unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: theft_events (fuel theft detection)
-- ============================================
CREATE TABLE IF NOT EXISTS theft_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Theft Details
    fuel_before DOUBLE,
    fuel_after DOUBLE,
    gallons_stolen DOUBLE,
    theft_confidence DOUBLE,
    
    -- Detection Method
    detection_method VARCHAR(50),  -- KALMAN, CUSUM, MANUAL
    
    -- Location
    latitude DOUBLE,
    longitude DOUBLE,
    
    -- Validation
    validated TINYINT(1) DEFAULT 0,
    false_positive TINYINT(1) DEFAULT 0,
    
    -- Alert Status
    alert_sent TINYINT(1) DEFAULT 0,
    alert_timestamp DATETIME,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_validated (validated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: truck_history (historical snapshots)
-- ============================================
CREATE TABLE IF NOT EXISTS truck_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    
    -- Status
    status VARCHAR(20),
    fuel_level DOUBLE,
    fuel_percent DOUBLE,
    
    -- Location
    latitude DOUBLE,
    longitude DOUBLE,
    speed DOUBLE,
    
    -- Engine
    odometer DOUBLE,
    engine_hours DOUBLE,
    
    -- Consumption
    mpg DOUBLE,
    consumption_gph DOUBLE,
    
    INDEX idx_truck_time (truck_id, timestamp),
    INDEX idx_timestamp (timestamp),
    INDEX idx_unit (unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: kalman_state (Kalman filter state)
-- ============================================
CREATE TABLE IF NOT EXISTS kalman_state (
    truck_id VARCHAR(20) PRIMARY KEY,
    unit_id BIGINT,
    
    -- State
    estimate DOUBLE,
    uncertainty DOUBLE,
    last_update DATETIME,
    
    -- Config
    process_variance DOUBLE DEFAULT 0.5,
    measurement_variance DOUBLE DEFAULT 3.0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_unit (unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: mpg_baseline (MPG baselines per truck)
-- ============================================
CREATE TABLE IF NOT EXISTS mpg_baseline (
    truck_id VARCHAR(20) PRIMARY KEY,
    unit_id BIGINT,
    
    -- Baseline MPG
    baseline_mpg DOUBLE,
    baseline_samples INT DEFAULT 0,
    
    -- Context
    avg_speed DOUBLE,
    avg_load DOUBLE,
    
    -- Metadata
    last_calibration DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_unit (unit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: sensor_cache (cached sensor mappings)
-- ============================================
CREATE TABLE IF NOT EXISTS sensor_cache (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    unit_id BIGINT NOT NULL,
    sensor_name VARCHAR(255) NOT NULL,
    sensor_id BIGINT NOT NULL,
    
    -- Metadata
    last_verified DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_unit_sensor (unit_id, sensor_name),
    INDEX idx_unit (unit_id),
    INDEX idx_sensor_id (sensor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: command_center_history (CC snapshots)
-- ============================================
CREATE TABLE IF NOT EXISTS command_center_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    
    -- Priority & Health
    priority_score DOUBLE,
    health_score DOUBLE,
    
    -- Flags
    needs_attention TINYINT(1) DEFAULT 0,
    critical_alert TINYINT(1) DEFAULT 0,
    
    -- Insights (JSON)
    insights JSON,
    anomalies JSON,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp),
    INDEX idx_timestamp (timestamp),
    INDEX idx_priority (priority_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLE: predictive_maintenance_sensor_history
-- ============================================
CREATE TABLE IF NOT EXISTS predictive_maintenance_sensor_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    
    -- Sensors
    trans_temp_f DOUBLE,
    fuel_temp_f DOUBLE,
    intercooler_temp_f DOUBLE,
    intake_press_kpa DOUBLE,
    retarder_level DOUBLE,
    oil_pressure_psi DOUBLE,
    boost_pressure_psi DOUBLE,
    exhaust_temp_f DOUBLE,
    def_level_pct DOUBLE,
    battery_voltage DOUBLE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- Verify setup
-- ============================================
SELECT 'Database setup completed successfully!' AS status;
SHOW TABLES;
