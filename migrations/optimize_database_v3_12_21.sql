-- ============================================
-- FUEL COPILOT - DATABASE OPTIMIZATION v3.12.21
-- Run this migration for improved performance
-- ============================================

-- ============================================
-- Performance Indexes for fuel_metrics
-- ============================================

-- Composite index for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_fm_carrier_truck_time 
ON fuel_metrics (carrier_id, truck_id, timestamp_utc DESC);

-- Index for refuel detection queries
CREATE INDEX IF NOT EXISTS idx_fm_refuel_detected 
ON fuel_metrics (refuel_detected, timestamp_utc DESC);

-- Index for efficiency analysis (MPG queries)
CREATE INDEX IF NOT EXISTS idx_fm_mpg_analysis 
ON fuel_metrics (truck_id, mpg_current, timestamp_utc);

-- Index for idle time analysis
CREATE INDEX IF NOT EXISTS idx_fm_idle_analysis 
ON fuel_metrics (truck_id, idle_duration_minutes, timestamp_utc);

-- Index for fuel level monitoring
CREATE INDEX IF NOT EXISTS idx_fm_fuel_level 
ON fuel_metrics (truck_id, fuel_percent, timestamp_utc DESC);

-- ============================================
-- Performance Indexes for refuel_events
-- ============================================

-- Composite index for carrier-level refuel reports
CREATE INDEX IF NOT EXISTS idx_re_carrier_time 
ON refuel_events (carrier_id, timestamp_utc DESC);

-- Index for anomaly detection
CREATE INDEX IF NOT EXISTS idx_re_confidence 
ON refuel_events (confidence, validated, timestamp_utc DESC);

-- Index for gallons analysis
CREATE INDEX IF NOT EXISTS idx_re_gallons 
ON refuel_events (truck_id, gallons_added, timestamp_utc);

-- ============================================
-- Performance Indexes for truck_history
-- ============================================

-- Index for status history queries
CREATE INDEX IF NOT EXISTS idx_th_status 
ON truck_history (truck_id, status, timestamp DESC);

-- Index for fuel level history
CREATE INDEX IF NOT EXISTS idx_th_fuel_level 
ON truck_history (truck_id, fuel_percent, timestamp DESC);


-- ============================================
-- TABLE: alerts (for alert tracking)
-- ============================================
CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Alert Details
    alert_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL,  -- LOW, MEDIUM, HIGH, CRITICAL
    message TEXT,
    details JSON,
    
    -- Status
    acknowledged TINYINT(1) DEFAULT 0,
    acknowledged_at DATETIME,
    acknowledged_by VARCHAR(100),
    notes TEXT,
    
    -- Notification Status
    sms_sent TINYINT(1) DEFAULT 0,
    email_sent TINYINT(1) DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_alerts_truck_time (truck_id, timestamp_utc DESC),
    INDEX idx_alerts_carrier_time (carrier_id, timestamp_utc DESC),
    INDEX idx_alerts_type (alert_type, timestamp_utc DESC),
    INDEX idx_alerts_priority (priority, acknowledged, timestamp_utc DESC),
    INDEX idx_alerts_unacked (acknowledged, priority, timestamp_utc DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================
-- TABLE: theft_events (theft detection log)
-- ============================================
CREATE TABLE IF NOT EXISTS theft_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Event Details
    fuel_before DOUBLE,
    fuel_after DOUBLE,
    gallons_lost DOUBLE,
    drop_percent DOUBLE,
    
    -- Detection Info
    detection_method VARCHAR(50),
    confidence DOUBLE,
    anomaly_score DOUBLE,
    
    -- Location
    latitude DOUBLE,
    longitude DOUBLE,
    location_name VARCHAR(200),
    
    -- Status
    status VARCHAR(30) DEFAULT 'suspected',  -- suspected, investigating, confirmed, cleared
    investigated_at DATETIME,
    investigated_by VARCHAR(100),
    resolution_notes TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_theft_truck_time (truck_id, timestamp_utc DESC),
    INDEX idx_theft_carrier_time (carrier_id, timestamp_utc DESC),
    INDEX idx_theft_status (status, confidence DESC),
    INDEX idx_theft_confidence (confidence DESC, timestamp_utc DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================
-- TABLE: audit_log (for security auditing)
-- ============================================
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- User Info
    user_id VARCHAR(100),
    username VARCHAR(100),
    user_role VARCHAR(50),
    carrier_id VARCHAR(50),
    
    -- Action Details
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    
    -- Request Info
    method VARCHAR(10),
    path VARCHAR(500),
    query_params TEXT,
    request_body TEXT,
    
    -- Response Info
    status_code INT,
    response_time_ms INT,
    
    -- Context
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Result
    success TINYINT(1) DEFAULT 1,
    error_message TEXT,
    
    INDEX idx_audit_timestamp (timestamp_utc DESC),
    INDEX idx_audit_user (user_id, timestamp_utc DESC),
    INDEX idx_audit_action (action, timestamp_utc DESC),
    INDEX idx_audit_resource (resource_type, resource_id, timestamp_utc DESC),
    INDEX idx_audit_carrier (carrier_id, timestamp_utc DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================
-- TABLE: api_keys (for API key authentication)
-- ============================================
CREATE TABLE IF NOT EXISTS api_keys (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash of the key
    key_prefix VARCHAR(8) NOT NULL,  -- First 8 chars for identification
    
    -- Owner Info
    name VARCHAR(100) NOT NULL,
    description TEXT,
    carrier_id VARCHAR(50),
    user_id VARCHAR(100),
    
    -- Permissions
    role VARCHAR(50) DEFAULT 'viewer',
    scopes JSON,  -- Array of allowed scopes
    
    -- Limits
    rate_limit_per_minute INT DEFAULT 60,
    rate_limit_per_day INT DEFAULT 10000,
    
    -- Status
    is_active TINYINT(1) DEFAULT 1,
    last_used_at DATETIME,
    usage_count BIGINT DEFAULT 0,
    
    -- Expiration
    expires_at DATETIME,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_apikey_hash (key_hash),
    INDEX idx_apikey_prefix (key_prefix),
    INDEX idx_apikey_carrier (carrier_id, is_active),
    INDEX idx_apikey_user (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================
-- TABLE: driver_metrics (daily driver stats)
-- ============================================
CREATE TABLE IF NOT EXISTS driver_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    driver_id VARCHAR(100),
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Distance
    total_miles DOUBLE DEFAULT 0,
    
    -- Fuel
    total_gallons DOUBLE DEFAULT 0,
    mpg_avg DOUBLE,
    fuel_cost DOUBLE DEFAULT 0,
    
    -- Efficiency
    efficiency_score DOUBLE,
    idle_percent DOUBLE,
    idle_gallons DOUBLE DEFAULT 0,
    
    -- Events
    refuel_count INT DEFAULT 0,
    anomaly_count INT DEFAULT 0,
    
    -- Trends
    mpg_trend VARCHAR(10),  -- up, down, stable
    mpg_trend_percent DOUBLE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_driver_date (driver_id, truck_id, date),
    INDEX idx_dm_carrier_date (carrier_id, date DESC),
    INDEX idx_dm_truck_date (truck_id, date DESC),
    INDEX idx_dm_efficiency (efficiency_score DESC, date DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================
-- Partitioning for fuel_metrics (if large dataset)
-- ============================================
-- NOTE: Run this manually if you have millions of rows
-- This requires dropping and recreating the table

/*
ALTER TABLE fuel_metrics 
PARTITION BY RANGE (TO_DAYS(timestamp_utc)) (
    PARTITION p_2024_01 VALUES LESS THAN (TO_DAYS('2024-02-01')),
    PARTITION p_2024_02 VALUES LESS THAN (TO_DAYS('2024-03-01')),
    PARTITION p_2024_03 VALUES LESS THAN (TO_DAYS('2024-04-01')),
    PARTITION p_2024_04 VALUES LESS THAN (TO_DAYS('2024-05-01')),
    PARTITION p_2024_05 VALUES LESS THAN (TO_DAYS('2024-06-01')),
    PARTITION p_2024_06 VALUES LESS THAN (TO_DAYS('2024-07-01')),
    PARTITION p_2024_07 VALUES LESS THAN (TO_DAYS('2024-08-01')),
    PARTITION p_2024_08 VALUES LESS THAN (TO_DAYS('2024-09-01')),
    PARTITION p_2024_09 VALUES LESS THAN (TO_DAYS('2024-10-01')),
    PARTITION p_2024_10 VALUES LESS THAN (TO_DAYS('2024-11-01')),
    PARTITION p_2024_11 VALUES LESS THAN (TO_DAYS('2024-12-01')),
    PARTITION p_2024_12 VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
*/


-- ============================================
-- Stored Procedure: Cleanup old data
-- ============================================
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS cleanup_old_data(IN days_to_keep INT)
BEGIN
    DECLARE cutoff_date DATETIME;
    SET cutoff_date = DATE_SUB(NOW(), INTERVAL days_to_keep DAY);
    
    -- Delete old fuel_metrics
    DELETE FROM fuel_metrics WHERE timestamp_utc < cutoff_date;
    SELECT ROW_COUNT() AS fuel_metrics_deleted;
    
    -- Delete old truck_history
    DELETE FROM truck_history WHERE timestamp < cutoff_date;
    SELECT ROW_COUNT() AS truck_history_deleted;
    
    -- Delete old audit_log (keep 90 days regardless)
    DELETE FROM audit_log WHERE timestamp_utc < DATE_SUB(NOW(), INTERVAL 90 DAY);
    SELECT ROW_COUNT() AS audit_log_deleted;
    
    -- Optimize tables
    OPTIMIZE TABLE fuel_metrics;
    OPTIMIZE TABLE truck_history;
    OPTIMIZE TABLE audit_log;
END //

DELIMITER ;


-- ============================================
-- Stored Procedure: Daily aggregation
-- ============================================
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS aggregate_daily_metrics(IN target_date DATE)
BEGIN
    -- Aggregate driver/truck metrics for the day
    INSERT INTO driver_metrics (
        date, truck_id, carrier_id,
        total_miles, total_gallons, mpg_avg,
        efficiency_score, idle_percent, refuel_count
    )
    SELECT 
        target_date,
        truck_id,
        carrier_id,
        SUM(mileage_delta) as total_miles,
        SUM(consumption_gph * (TIMESTAMPDIFF(SECOND, LAG(timestamp_utc) OVER (PARTITION BY truck_id ORDER BY timestamp_utc), timestamp_utc) / 3600)) as total_gallons,
        AVG(mpg_current) as mpg_avg,
        AVG(CASE WHEN mpg_current > 0 THEN (mpg_current / 7.0) * 100 ELSE 0 END) as efficiency_score,
        SUM(CASE WHEN idle_duration_minutes > 0 THEN idle_duration_minutes ELSE 0 END) / 
            (COUNT(*) * 5) * 100 as idle_percent,
        SUM(refuel_detected) as refuel_count
    FROM fuel_metrics
    WHERE DATE(timestamp_utc) = target_date
    GROUP BY truck_id, carrier_id
    ON DUPLICATE KEY UPDATE
        total_miles = VALUES(total_miles),
        total_gallons = VALUES(total_gallons),
        mpg_avg = VALUES(mpg_avg),
        efficiency_score = VALUES(efficiency_score),
        idle_percent = VALUES(idle_percent),
        refuel_count = VALUES(refuel_count),
        updated_at = NOW();
END //

DELIMITER ;


-- ============================================
-- Event: Nightly cleanup (requires event scheduler)
-- ============================================
-- Enable event scheduler if not already enabled:
-- SET GLOBAL event_scheduler = ON;

CREATE EVENT IF NOT EXISTS evt_nightly_cleanup
ON SCHEDULE EVERY 1 DAY
STARTS (TIMESTAMP(CURRENT_DATE) + INTERVAL 3 HOUR)  -- 3 AM
DO
    CALL cleanup_old_data(365);


CREATE EVENT IF NOT EXISTS evt_daily_aggregation
ON SCHEDULE EVERY 1 DAY
STARTS (TIMESTAMP(CURRENT_DATE) + INTERVAL 1 HOUR)  -- 1 AM
DO
    CALL aggregate_daily_metrics(DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY));


-- ============================================
-- Verify optimization applied
-- ============================================
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
