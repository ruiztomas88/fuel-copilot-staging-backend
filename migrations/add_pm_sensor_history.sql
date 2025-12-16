-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration: Predictive Maintenance Sensor History Table
-- Version: 5.11.0
-- Date: December 2025
-- 
-- This table stores sensor readings for trend analysis in predictive maintenance.
-- Only stores readings every 15-30 minutes (not every second) to control growth.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Main sensor history table
CREATE TABLE IF NOT EXISTS pm_sensor_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    value FLOAT NOT NULL,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite index for fast queries by truck+sensor+time
    INDEX idx_truck_sensor_time (truck_id, sensor_name, timestamp),
    
    -- Index for cleanup queries (older than X days)
    INDEX idx_timestamp (timestamp),
    
    -- Index for fleet-wide queries
    INDEX idx_sensor_time (sensor_name, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Daily aggregates for long-term trend analysis (keeps data compact)
CREATE TABLE IF NOT EXISTS pm_sensor_daily_avg (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    avg_value FLOAT NOT NULL,
    min_value FLOAT NOT NULL,
    max_value FLOAT NOT NULL,
    reading_count INT NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint: one row per truck+sensor+date
    UNIQUE KEY uk_truck_sensor_date (truck_id, sensor_name, date),
    
    -- Index for trend queries
    INDEX idx_truck_sensor_date (truck_id, sensor_name, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Maintenance predictions cache (updated periodically)
CREATE TABLE IF NOT EXISTS pm_predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    component VARCHAR(100) NOT NULL,
    current_value FLOAT,
    trend_per_day FLOAT,
    trend_direction ENUM('DEGRADANDO', 'ESTABLE', 'MEJORANDO', 'DESCONOCIDO') DEFAULT 'DESCONOCIDO',
    days_to_warning FLOAT,
    days_to_critical FLOAT,
    urgency ENUM('CRÍTICO', 'ALTO', 'MEDIO', 'BAJO', 'NINGUNO') DEFAULT 'NINGUNO',
    confidence ENUM('HIGH', 'MEDIUM', 'LOW') DEFAULT 'LOW',
    recommended_action TEXT,
    estimated_cost_if_fail VARCHAR(50),
    analyzed_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique: one prediction per truck+sensor
    UNIQUE KEY uk_truck_sensor (truck_id, sensor_name),
    
    -- Index for urgency-based queries
    INDEX idx_urgency (urgency, truck_id),
    
    -- Index for fleet overview
    INDEX idx_analyzed (analyzed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- STORED PROCEDURES
-- ═══════════════════════════════════════════════════════════════════════════════

-- Procedure to insert sensor reading and update daily average
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS insert_pm_sensor_reading(
    IN p_truck_id VARCHAR(20),
    IN p_sensor_name VARCHAR(50),
    IN p_value FLOAT,
    IN p_timestamp DATETIME
)
BEGIN
    DECLARE v_date DATE;
    SET v_date = DATE(p_timestamp);
    
    -- Insert raw reading
    INSERT INTO pm_sensor_history (truck_id, sensor_name, value, timestamp)
    VALUES (p_truck_id, p_sensor_name, p_value, p_timestamp);
    
    -- Update or insert daily average
    INSERT INTO pm_sensor_daily_avg (truck_id, sensor_name, date, avg_value, min_value, max_value, reading_count)
    VALUES (p_truck_id, p_sensor_name, v_date, p_value, p_value, p_value, 1)
    ON DUPLICATE KEY UPDATE
        avg_value = (avg_value * reading_count + p_value) / (reading_count + 1),
        min_value = LEAST(min_value, p_value),
        max_value = GREATEST(max_value, p_value),
        reading_count = reading_count + 1;
END //

DELIMITER ;


-- ═══════════════════════════════════════════════════════════════════════════════
-- CLEANUP PROCEDURE (run daily via cron)
-- ═══════════════════════════════════════════════════════════════════════════════

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS cleanup_pm_old_data(
    IN p_raw_days INT,      -- Keep raw readings for X days (default: 30)
    IN p_daily_days INT     -- Keep daily averages for X days (default: 365)
)
BEGIN
    -- Delete raw readings older than p_raw_days
    DELETE FROM pm_sensor_history 
    WHERE timestamp < DATE_SUB(NOW(), INTERVAL p_raw_days DAY);
    
    -- Delete daily averages older than p_daily_days
    DELETE FROM pm_sensor_daily_avg 
    WHERE date < DATE_SUB(CURDATE(), INTERVAL p_daily_days DAY);
    
    -- Log cleanup
    SELECT 
        ROW_COUNT() as deleted_rows,
        NOW() as cleanup_time;
END //

DELIMITER ;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SAMPLE QUERIES FOR REFERENCE
-- ═══════════════════════════════════════════════════════════════════════════════

-- Get last 7 days of daily averages for trend analysis
-- SELECT date, avg_value 
-- FROM pm_sensor_daily_avg 
-- WHERE truck_id = 'FM3679' AND sensor_name = 'trans_temp' 
-- AND date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
-- ORDER BY date;

-- Get all critical/high urgency predictions
-- SELECT * FROM pm_predictions 
-- WHERE urgency IN ('CRÍTICO', 'ALTO')
-- ORDER BY days_to_critical;

-- Get fleet summary by urgency
-- SELECT urgency, COUNT(*) as count 
-- FROM pm_predictions 
-- GROUP BY urgency;
