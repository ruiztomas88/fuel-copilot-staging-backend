-- ============================================================================
-- ENGINE HEALTH MONITORING TABLES
-- Fuel Copilot v3.13.0
-- ============================================================================
-- Run this migration to create the engine health monitoring tables
-- mysql -u fuel_admin -p'FuelCopilot2025!' fuel_copilot < migrations/create_engine_health_tables.sql
-- ============================================================================

USE fuel_copilot;

-- ============================================================================
-- 1. ENGINE HEALTH ALERTS TABLE
-- Stores all health alerts (critical, warning, watch)
-- ============================================================================
CREATE TABLE IF NOT EXISTS engine_health_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- Alert identification
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'DF_INTERNATIONAL',
    
    -- Alert details
    category ENUM('oil_pressure', 'coolant_temp', 'oil_temp', 'battery', 
                  'def_level', 'engine_load', 'trend', 'differential') NOT NULL,
    severity ENUM('critical', 'warning', 'watch', 'info') NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    
    -- Values
    current_value DECIMAL(10,2),
    threshold_value DECIMAL(10,2),
    baseline_value DECIMAL(10,2),
    
    -- Alert content
    message TEXT NOT NULL,
    action_required TEXT,
    trend_direction ENUM('rising', 'falling', 'stable'),
    
    -- Status tracking
    is_active BOOLEAN DEFAULT TRUE,
    acknowledged_at DATETIME,
    acknowledged_by VARCHAR(100),
    resolved_at DATETIME,
    resolution_notes TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes for fast queries
    INDEX idx_truck_active (truck_id, is_active),
    INDEX idx_severity_active (severity, is_active),
    INDEX idx_created_at (created_at),
    INDEX idx_category (category),
    INDEX idx_carrier_severity (carrier_id, severity, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 2. ENGINE HEALTH BASELINES TABLE
-- Stores calculated baseline statistics per truck per sensor
-- ============================================================================
CREATE TABLE IF NOT EXISTS engine_health_baselines (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- Identification
    truck_id VARCHAR(20) NOT NULL,
    sensor_name VARCHAR(50) NOT NULL,
    
    -- 30-day baseline statistics
    mean_30d DECIMAL(10,3),
    std_30d DECIMAL(10,3),
    min_30d DECIMAL(10,3),
    max_30d DECIMAL(10,3),
    
    -- 7-day baseline statistics
    mean_7d DECIMAL(10,3),
    std_7d DECIMAL(10,3),
    min_7d DECIMAL(10,3),
    max_7d DECIMAL(10,3),
    
    -- Sample info
    sample_count_30d INT DEFAULT 0,
    sample_count_7d INT DEFAULT 0,
    
    -- Timestamps
    last_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Unique constraint - one baseline per truck per sensor
    UNIQUE KEY uk_truck_sensor (truck_id, sensor_name),
    INDEX idx_truck (truck_id),
    INDEX idx_sensor (sensor_name),
    INDEX idx_last_calc (last_calculated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 3. ENGINE HEALTH SNAPSHOTS TABLE
-- Stores periodic health status snapshots for historical analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS engine_health_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- Identification
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'DF_INTERNATIONAL',
    snapshot_time DATETIME NOT NULL,
    
    -- Overall status
    overall_status ENUM('healthy', 'warning', 'critical', 'offline', 'unknown') NOT NULL,
    
    -- Sensor values at snapshot time
    oil_pressure_psi DECIMAL(5,1),
    oil_pressure_status VARCHAR(20),
    
    coolant_temp_f DECIMAL(5,1),
    coolant_temp_status VARCHAR(20),
    
    oil_temp_f DECIMAL(5,1),
    oil_temp_status VARCHAR(20),
    
    battery_voltage DECIMAL(4,2),
    battery_status VARCHAR(20),
    
    def_level_pct DECIMAL(5,2),
    def_level_status VARCHAR(20),
    
    engine_load_pct DECIMAL(5,2),
    engine_load_status VARCHAR(20),
    
    rpm DECIMAL(6,1),
    
    -- Alert counts at snapshot
    alert_count_critical INT DEFAULT 0,
    alert_count_warning INT DEFAULT 0,
    
    -- Trends at snapshot
    oil_pressure_trend VARCHAR(20),
    coolant_temp_trend VARCHAR(20),
    battery_trend VARCHAR(20),
    
    -- Data quality
    data_age_minutes DECIMAL(6,1),
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_truck_time (truck_id, snapshot_time),
    INDEX idx_status_time (overall_status, snapshot_time),
    INDEX idx_carrier_time (carrier_id, snapshot_time),
    INDEX idx_snapshot_time (snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 4. ENGINE HEALTH ALERT NOTIFICATIONS TABLE
-- Tracks which alerts have been sent via SMS/Email
-- ============================================================================
CREATE TABLE IF NOT EXISTS engine_health_notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- Link to alert
    alert_id BIGINT NOT NULL,
    
    -- Notification details
    notification_type ENUM('sms', 'email', 'push', 'webhook') NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    
    -- Status
    status ENUM('pending', 'sent', 'failed', 'delivered') DEFAULT 'pending',
    sent_at DATETIME,
    delivered_at DATETIME,
    error_message TEXT,
    
    -- Content sent
    message_content TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_alert (alert_id),
    INDEX idx_status (status),
    INDEX idx_type_status (notification_type, status),
    
    FOREIGN KEY (alert_id) REFERENCES engine_health_alerts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 5. MAINTENANCE PREDICTIONS TABLE
-- Stores predictive maintenance recommendations
-- ============================================================================
CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- Identification
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'DF_INTERNATIONAL',
    
    -- Prediction details
    component VARCHAR(100) NOT NULL,  -- 'Oil System', 'Cooling System', etc.
    urgency ENUM('low', 'medium', 'high', 'critical') NOT NULL,
    prediction TEXT NOT NULL,
    recommended_action TEXT,
    
    -- Cost estimates
    estimated_repair_cost VARCHAR(50),
    if_ignored_cost VARCHAR(50),
    
    -- Prediction validity
    predicted_failure_date DATE,
    confidence_pct DECIMAL(5,2),
    
    -- Based on which sensors/alerts
    based_on_sensors JSON,  -- List of sensors that triggered this prediction
    based_on_alert_ids JSON,  -- List of alert IDs
    
    -- Status
    status ENUM('active', 'scheduled', 'completed', 'dismissed') DEFAULT 'active',
    scheduled_date DATE,
    completed_date DATE,
    completion_notes TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_truck_status (truck_id, status),
    INDEX idx_urgency (urgency, status),
    INDEX idx_carrier (carrier_id, status),
    INDEX idx_predicted_date (predicted_failure_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 6. SENSOR THRESHOLDS CONFIGURATION TABLE (Optional - for custom thresholds)
-- Allows per-truck or fleet-wide threshold customization
-- ============================================================================
CREATE TABLE IF NOT EXISTS engine_health_thresholds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Scope (NULL truck_id = fleet-wide default)
    truck_id VARCHAR(20),
    carrier_id VARCHAR(50) DEFAULT 'DF_INTERNATIONAL',
    
    -- Sensor
    sensor_name VARCHAR(50) NOT NULL,
    
    -- Thresholds
    critical_low DECIMAL(10,3),
    warning_low DECIMAL(10,3),
    watch_low DECIMAL(10,3),
    normal_min DECIMAL(10,3),
    normal_max DECIMAL(10,3),
    watch_high DECIMAL(10,3),
    warning_high DECIMAL(10,3),
    critical_high DECIMAL(10,3),
    
    -- Trend thresholds
    trend_warning_change DECIMAL(10,3),
    trend_critical_change DECIMAL(10,3),
    
    -- Metadata
    unit VARCHAR(20),
    description VARCHAR(255),
    action_critical TEXT,
    action_warning TEXT,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Unique per truck/sensor combination
    UNIQUE KEY uk_truck_sensor (truck_id, sensor_name),
    INDEX idx_sensor (sensor_name),
    INDEX idx_carrier (carrier_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- INSERT DEFAULT THRESHOLDS (Fleet-wide)
-- ============================================================================
INSERT INTO engine_health_thresholds 
(truck_id, sensor_name, critical_low, warning_low, watch_low, normal_min, normal_max, 
 watch_high, warning_high, critical_high, trend_warning_change, trend_critical_change,
 unit, description, action_critical, action_warning)
VALUES
-- Oil Pressure
(NULL, 'oil_pressure_psi', 20, 30, 35, 35, 65, NULL, NULL, NULL, -10, -15,
 'psi', 'Engine Oil Pressure',
 'STOP ENGINE IMMEDIATELY - Check oil level and pump',
 'Schedule oil change and pump inspection within 48 hours'),

-- Coolant Temperature
(NULL, 'coolant_temp_f', NULL, NULL, NULL, 180, 210, 215, 220, 230, 10, 20,
 '°F', 'Coolant Temperature',
 'PULL OVER IMMEDIATELY - Risk of engine damage',
 'Check coolant level, radiator, and thermostat'),

-- Oil Temperature
(NULL, 'oil_temp_f', NULL, NULL, NULL, 180, 235, 240, 250, 260, NULL, NULL,
 '°F', 'Engine Oil Temperature',
 'REDUCE LOAD - Oil viscosity compromised',
 'Check oil cooler and cooling system'),

-- Battery Voltage (engine running)
(NULL, 'battery_voltage_on', 13.0, 13.5, NULL, 13.8, 14.4, NULL, 14.8, 15.0, -0.3, NULL,
 'V', 'Battery Voltage (Engine Running)',
 'Check alternator and battery immediately',
 'Schedule electrical system inspection'),

-- Battery Voltage (engine off)
(NULL, 'battery_voltage_off', 12.0, 12.3, 12.4, 12.4, 12.8, NULL, NULL, NULL, -0.3, NULL,
 'V', 'Battery Voltage (Engine Off)',
 'Charge or replace battery before next trip',
 'Schedule battery replacement'),

-- DEF Level
(NULL, 'def_level_pct', 5, 10, 15, 15, 100, NULL, NULL, NULL, NULL, NULL,
 '%', 'DEF Level',
 'REFILL DEF IMMEDIATELY - Engine derate imminent',
 'Schedule DEF refill within 24 hours'),

-- Engine Load
(NULL, 'engine_load_pct', NULL, NULL, NULL, 20, 80, 85, 90, 95, NULL, NULL,
 '%', 'Engine Load',
 'REDUCE LOAD - Risk of overheating and wear',
 'Monitor engine temperatures closely')

ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- CREATE VIEWS FOR EASY QUERYING
-- ============================================================================

-- View: Active critical alerts
CREATE OR REPLACE VIEW v_active_critical_alerts AS
SELECT 
    a.*,
    TIMESTAMPDIFF(MINUTE, a.created_at, NOW()) as minutes_active
FROM engine_health_alerts a
WHERE a.is_active = TRUE 
  AND a.severity = 'critical'
ORDER BY a.created_at DESC;

-- View: Fleet health summary
CREATE OR REPLACE VIEW v_fleet_health_summary AS
SELECT 
    DATE(snapshot_time) as date,
    COUNT(DISTINCT truck_id) as total_trucks,
    SUM(CASE WHEN overall_status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
    SUM(CASE WHEN overall_status = 'warning' THEN 1 ELSE 0 END) as warning_count,
    SUM(CASE WHEN overall_status = 'critical' THEN 1 ELSE 0 END) as critical_count,
    SUM(CASE WHEN overall_status = 'offline' THEN 1 ELSE 0 END) as offline_count,
    AVG(alert_count_critical) as avg_critical_alerts,
    AVG(alert_count_warning) as avg_warning_alerts
FROM engine_health_snapshots
WHERE snapshot_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(snapshot_time)
ORDER BY date DESC;

-- View: Trucks needing attention
CREATE OR REPLACE VIEW v_trucks_needing_attention AS
SELECT 
    truck_id,
    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_alerts,
    COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warning_alerts,
    GROUP_CONCAT(DISTINCT category) as alert_categories,
    MIN(created_at) as oldest_alert,
    MAX(created_at) as newest_alert
FROM engine_health_alerts
WHERE is_active = TRUE
GROUP BY truck_id
HAVING critical_alerts > 0 OR warning_alerts > 0
ORDER BY critical_alerts DESC, warning_alerts DESC;

-- ============================================================================
-- VERIFY TABLES CREATED
-- ============================================================================
SELECT 'Engine Health Tables Created Successfully!' as status;

SHOW TABLES LIKE 'engine_health%';
SHOW TABLES LIKE 'maintenance_predictions';
