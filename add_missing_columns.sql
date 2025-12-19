USE fuel_copilot;

-- Add missing columns to fuel_metrics
ALTER TABLE fuel_metrics 
    ADD COLUMN speed_mph DOUBLE COMMENT 'Speed in miles per hour',
    ADD COLUMN estimated_liters DOUBLE COMMENT 'Kalman-filtered fuel level in liters',
    ADD COLUMN estimated_gallons DOUBLE COMMENT 'Kalman-filtered fuel level in gallons',
    ADD COLUMN estimated_pct DOUBLE COMMENT 'Kalman-filtered fuel level percentage',
    ADD COLUMN sensor_pct DOUBLE COMMENT 'Raw sensor fuel percentage',
    ADD COLUMN sensor_liters DOUBLE COMMENT 'Raw sensor fuel in liters',
    ADD COLUMN sensor_gallons DOUBLE COMMENT 'Raw sensor fuel in gallons',
    ADD COLUMN consumption_lph DOUBLE COMMENT 'Fuel consumption in liters per hour',
    ADD COLUMN rpm INT COMMENT 'Engine RPM',
    ADD COLUMN odometer_mi DOUBLE COMMENT 'Odometer reading in miles',
    ADD COLUMN idle_mode VARCHAR(20) COMMENT 'Idle detection mode',
    ADD COLUMN drift_pct DECIMAL(5,2) COMMENT 'Kalman drift percentage',
    ADD COLUMN drift_warning VARCHAR(100) COMMENT 'Drift warning message',
    ADD COLUMN anchor_detected TINYINT(1) DEFAULT 0 COMMENT 'Fuel anchor detection flag',
    ADD COLUMN data_age_min INT COMMENT 'Data age in minutes',
    ADD COLUMN altitude_ft DOUBLE COMMENT 'Altitude in feet',
    ADD COLUMN hdop DOUBLE COMMENT 'Horizontal dilution of precision',
    ADD COLUMN coolant_temp_f DECIMAL(5,2) COMMENT 'Coolant temperature in Fahrenheit';

-- Create dtc_events table
CREATE TABLE IF NOT EXISTS dtc_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    dtc_code VARCHAR(50) NOT NULL COMMENT 'DTC code (e.g., SPN111.FMI3)',
    component VARCHAR(100) COMMENT 'Component name',
    severity VARCHAR(20) COMMENT 'Severity level: CRITICAL, MODERATE, LOW',
    status VARCHAR(20) DEFAULT 'NEW' COMMENT 'Status: NEW, ACKNOWLEDGED, RESOLVED',
    description TEXT COMMENT 'DTC description',
    action_required TEXT COMMENT 'Recommended action',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_truck_timestamp (truck_id, timestamp_utc),
    INDEX idx_status (status),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Schema update completed successfully!' as status;
