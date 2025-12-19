-- ============================================
-- AGREGAR TABLA truck_sensors_cache
-- ============================================

USE fuel_copilot;

CREATE TABLE IF NOT EXISTS truck_sensors_cache (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    unit_id BIGINT NOT NULL,
    sensor_name VARCHAR(255) NOT NULL,
    sensor_id BIGINT NOT NULL,
    sensor_type VARCHAR(50),
    latest_value DOUBLE,
    last_updated DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_unit_sensor (unit_id, sensor_name),
    INDEX idx_unit (unit_id),
    INDEX idx_sensor_id (sensor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Cache de sensores de Wialon por truck';

SELECT 'Tabla truck_sensors_cache creada!' AS status;
