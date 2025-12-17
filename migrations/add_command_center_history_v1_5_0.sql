-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration: Fleet Command Center v1.5.0 History Tables
-- Version: 1.5.0
-- Date: December 2025
-- 
-- These tables persist Command Center calculations for:
-- 1. Machine Learning training data
-- 2. Historical trend analysis
-- 3. Service restart resilience
-- ═══════════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. TRUCK RISK SCORE HISTORY
--    Stores composite risk scores for each truck over time
--    Used for: ML to predict which trucks will have problems
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cc_risk_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    
    -- Risk Score Components
    risk_score FLOAT NOT NULL,
    risk_level ENUM('CRITICAL', 'HIGH', 'MEDIUM', 'LOW') NOT NULL,
    
    -- Component Scores (for ML feature extraction)
    sensor_health_score FLOAT,
    dtc_score FLOAT,
    trend_score FLOAT,
    offline_score FLOAT,
    maintenance_score FLOAT,
    
    -- Context at time of calculation
    active_issues_count INT DEFAULT 0,
    dtc_active BOOLEAN DEFAULT FALSE,
    days_since_maintenance INT,
    
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_truck_time (truck_id, timestamp),
    INDEX idx_risk_level (risk_level, timestamp),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. ANOMALY DETECTION HISTORY
--    Stores every anomaly detected by EWMA/CUSUM algorithms
--    Used for: ML to learn anomaly patterns, operator review
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cc_anomaly_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    
    -- Anomaly Details
    anomaly_type ENUM('EWMA', 'CUSUM', 'THRESHOLD', 'CORRELATION') NOT NULL,
    severity ENUM('CRITICAL', 'HIGH', 'MEDIUM', 'LOW') NOT NULL,
    
    -- Values at detection
    sensor_value FLOAT NOT NULL,
    ewma_value FLOAT,
    cusum_value FLOAT,
    threshold_used FLOAT,
    z_score FLOAT,
    
    -- Detection context
    is_confirmed BOOLEAN DEFAULT FALSE,  -- Did it result in actual failure?
    false_positive BOOLEAN DEFAULT NULL, -- NULL = unknown, TRUE = false alarm
    notes TEXT,
    
    detected_at DATETIME NOT NULL,
    resolved_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_truck_sensor (truck_id, sensor_name, detected_at),
    INDEX idx_anomaly_type (anomaly_type, detected_at),
    INDEX idx_severity (severity, detected_at),
    INDEX idx_unresolved (resolved_at, truck_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. EWMA/CUSUM STATE PERSISTENCE
--    Stores algorithm state so it survives service restarts
--    Updated periodically (every 5-10 min), not every reading
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cc_algorithm_state (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    
    -- EWMA State
    ewma_value FLOAT,
    ewma_variance FLOAT,
    
    -- CUSUM State
    cusum_high FLOAT DEFAULT 0,
    cusum_low FLOAT DEFAULT 0,
    
    -- Baseline (for drift detection)
    baseline_mean FLOAT,
    baseline_std FLOAT,
    samples_count INT DEFAULT 0,
    
    -- Trend info
    trend_direction ENUM('UP', 'DOWN', 'STABLE') DEFAULT 'STABLE',
    trend_slope FLOAT,
    
    updated_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint: one state per truck+sensor
    UNIQUE KEY uk_truck_sensor (truck_id, sensor_name),
    
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 4. FAILURE CORRELATION EVENTS
--    When multi-sensor patterns are detected
--    Used for: ML to learn failure signatures
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cc_correlation_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    
    -- Pattern Info
    pattern_name VARCHAR(100) NOT NULL,
    pattern_description TEXT,
    confidence FLOAT NOT NULL,
    
    -- Sensors involved (JSON array)
    sensors_involved JSON NOT NULL,
    sensor_values JSON NOT NULL,
    
    -- Prediction
    predicted_component VARCHAR(100),
    predicted_failure_days INT,
    recommended_action TEXT,
    
    -- Outcome tracking (for ML feedback loop)
    actual_failure_occurred BOOLEAN DEFAULT NULL,
    actual_failure_date DATE,
    prediction_accuracy FLOAT,
    
    detected_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_pattern (truck_id, pattern_name, detected_at),
    INDEX idx_pattern (pattern_name, detected_at),
    INDEX idx_confidence (confidence, detected_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 5. DEF CONSUMPTION HISTORY
--    For DEF usage prediction ML model
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cc_def_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    
    def_level FLOAT NOT NULL,
    fuel_used_since_refill FLOAT,
    estimated_def_used FLOAT,
    consumption_rate FLOAT,  -- gallons DEF per 100 gallons diesel
    
    is_refill_event BOOLEAN DEFAULT FALSE,
    
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp),
    INDEX idx_refills (truck_id, is_refill_event, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 6. MAINTENANCE COST TRACKING
--    For cost prediction ML model
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cc_maintenance_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    
    -- Event Details
    event_type ENUM('SCHEDULED', 'UNSCHEDULED', 'EMERGENCY', 'PREVENTIVE') NOT NULL,
    component VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Costs
    parts_cost DECIMAL(10,2),
    labor_cost DECIMAL(10,2),
    total_cost DECIMAL(10,2),
    downtime_hours FLOAT,
    
    -- Link to prediction (if any)
    was_predicted BOOLEAN DEFAULT FALSE,
    prediction_days_ahead INT,
    related_anomaly_id BIGINT,
    
    -- Sensor context before failure (for ML)
    sensors_before_failure JSON,
    
    event_date DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_date (truck_id, event_date),
    INDEX idx_component (component, event_date),
    INDEX idx_event_type (event_type, event_date),
    
    FOREIGN KEY (related_anomaly_id) REFERENCES cc_anomaly_history(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ═══════════════════════════════════════════════════════════════════════════════
-- STORED PROCEDURES
-- ═══════════════════════════════════════════════════════════════════════════════

DELIMITER //

-- Procedure to save risk score (called every analysis cycle)
CREATE PROCEDURE IF NOT EXISTS sp_save_risk_score(
    IN p_truck_id VARCHAR(20),
    IN p_risk_score FLOAT,
    IN p_risk_level VARCHAR(20),
    IN p_sensor_health_score FLOAT,
    IN p_dtc_score FLOAT,
    IN p_trend_score FLOAT,
    IN p_offline_score FLOAT,
    IN p_maintenance_score FLOAT,
    IN p_active_issues INT,
    IN p_dtc_active BOOLEAN,
    IN p_days_since_maintenance INT
)
BEGIN
    INSERT INTO cc_risk_history (
        truck_id, risk_score, risk_level,
        sensor_health_score, dtc_score, trend_score, offline_score, maintenance_score,
        active_issues_count, dtc_active, days_since_maintenance, timestamp
    ) VALUES (
        p_truck_id, p_risk_score, p_risk_level,
        p_sensor_health_score, p_dtc_score, p_trend_score, p_offline_score, p_maintenance_score,
        p_active_issues, p_dtc_active, p_days_since_maintenance, NOW()
    );
END //

-- Procedure to save/update algorithm state
CREATE PROCEDURE IF NOT EXISTS sp_save_algorithm_state(
    IN p_truck_id VARCHAR(20),
    IN p_sensor_name VARCHAR(50),
    IN p_ewma_value FLOAT,
    IN p_ewma_variance FLOAT,
    IN p_cusum_high FLOAT,
    IN p_cusum_low FLOAT,
    IN p_baseline_mean FLOAT,
    IN p_baseline_std FLOAT,
    IN p_samples_count INT,
    IN p_trend_direction VARCHAR(10),
    IN p_trend_slope FLOAT
)
BEGIN
    INSERT INTO cc_algorithm_state (
        truck_id, sensor_name,
        ewma_value, ewma_variance,
        cusum_high, cusum_low,
        baseline_mean, baseline_std, samples_count,
        trend_direction, trend_slope,
        updated_at
    ) VALUES (
        p_truck_id, p_sensor_name,
        p_ewma_value, p_ewma_variance,
        p_cusum_high, p_cusum_low,
        p_baseline_mean, p_baseline_std, p_samples_count,
        p_trend_direction, p_trend_slope,
        NOW()
    )
    ON DUPLICATE KEY UPDATE
        ewma_value = p_ewma_value,
        ewma_variance = p_ewma_variance,
        cusum_high = p_cusum_high,
        cusum_low = p_cusum_low,
        baseline_mean = p_baseline_mean,
        baseline_std = p_baseline_std,
        samples_count = p_samples_count,
        trend_direction = p_trend_direction,
        trend_slope = p_trend_slope,
        updated_at = NOW();
END //

-- Procedure to cleanup old history (run daily via cron)
CREATE PROCEDURE IF NOT EXISTS sp_cleanup_command_center_history(
    IN p_days_to_keep INT
)
BEGIN
    DECLARE cutoff_date DATETIME;
    SET cutoff_date = DATE_SUB(NOW(), INTERVAL p_days_to_keep DAY);
    
    -- Keep risk scores for 90 days by default
    DELETE FROM cc_risk_history WHERE timestamp < cutoff_date;
    SELECT ROW_COUNT() AS risk_deleted;
    
    -- Keep resolved anomalies for 180 days, unresolved forever
    DELETE FROM cc_anomaly_history 
    WHERE resolved_at IS NOT NULL 
      AND detected_at < DATE_SUB(NOW(), INTERVAL 180 DAY);
    SELECT ROW_COUNT() AS anomalies_deleted;
    
    -- Keep DEF history for 365 days
    DELETE FROM cc_def_history WHERE timestamp < DATE_SUB(NOW(), INTERVAL 365 DAY);
    SELECT ROW_COUNT() AS def_deleted;
    
    -- Optimize tables
    OPTIMIZE TABLE cc_risk_history;
    OPTIMIZE TABLE cc_anomaly_history;
    OPTIMIZE TABLE cc_def_history;
END //

DELIMITER ;


-- ═══════════════════════════════════════════════════════════════════════════════
-- INITIAL DATA / INDEXES
-- ═══════════════════════════════════════════════════════════════════════════════

-- Create event for daily cleanup (if event scheduler is enabled)
-- Run: SET GLOBAL event_scheduler = ON;
CREATE EVENT IF NOT EXISTS ev_cleanup_cc_history
ON SCHEDULE EVERY 1 DAY
STARTS CURRENT_DATE + INTERVAL 3 HOUR  -- Run at 3 AM
DO
    CALL sp_cleanup_command_center_history(90);


-- ═══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION
-- ═══════════════════════════════════════════════════════════════════════════════
SELECT 'Command Center History Tables Created Successfully!' AS status;

SELECT table_name, table_rows, data_length, index_length
FROM information_schema.tables 
WHERE table_schema = DATABASE() 
  AND table_name LIKE 'cc_%'
ORDER BY table_name;
