-- ============================================================================
-- Migration: Add Idle Validation tracking table
-- Version: v5.7.6
-- Date: December 14, 2025
-- Description: Track idle validation results for accuracy monitoring
-- ============================================================================

USE fuel_analytics;

-- Table to store idle validation results
CREATE TABLE IF NOT EXISTS idle_validation_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    truck_id VARCHAR(50) NOT NULL,
    
    -- Validation data
    calculated_idle_hours FLOAT NOT NULL COMMENT 'Our calculated idle hours',
    ecu_idle_hours FLOAT DEFAULT NULL COMMENT 'ECU reported idle hours (cumulative)',
    ecu_engine_hours FLOAT DEFAULT NULL COMMENT 'ECU total engine hours',
    deviation_pct FLOAT DEFAULT NULL COMMENT 'Percentage deviation from ECU',
    
    -- Results
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    confidence ENUM('HIGH', 'MEDIUM', 'LOW') DEFAULT 'MEDIUM',
    needs_investigation BOOLEAN DEFAULT FALSE,
    
    -- Context
    idle_ratio_pct FLOAT DEFAULT NULL COMMENT 'idle_hours/engine_hours ratio',
    message VARCHAR(500) DEFAULT NULL,
    
    -- Indexes
    INDEX idx_truck_timestamp (truck_id, timestamp_utc DESC),
    INDEX idx_needs_investigation (needs_investigation, timestamp_utc DESC),
    INDEX idx_deviation (deviation_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Tracks idle calculation validation against ECU';

-- Add columns to fuel_metrics for quick access
ALTER TABLE fuel_metrics 
ADD COLUMN IF NOT EXISTS idle_validation_status ENUM('VALID', 'WARNING', 'ERROR') DEFAULT NULL,
ADD COLUMN IF NOT EXISTS idle_deviation_pct FLOAT DEFAULT NULL;

-- Verify
-- DESCRIBE idle_validation_log;
-- SELECT * FROM idle_validation_log LIMIT 5;
