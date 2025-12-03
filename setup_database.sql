mysql -u fuel_admin -pFuelCopilot2025! fuel_copilot-- ============================================
-- FUEL COPILOT - DATABASE SETUP
-- Run this script to create required tables
-- ============================================

USE wialon_collect;

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
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_carrier (carrier_id),
    INDEX idx_status (truck_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
    INDEX idx_timestamp (timestamp_utc)
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
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- Verify tables created
-- ============================================
SHOW TABLES LIKE 'fuel_%';
SHOW TABLES LIKE 'refuel_%';
SHOW TABLES LIKE 'truck_%';
