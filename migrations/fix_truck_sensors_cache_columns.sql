-- ============================================
-- AGREGAR COLUMNAS FALTANTES A truck_sensors_cache
-- ============================================

USE fuel_copilot;

ALTER TABLE truck_sensors_cache
ADD COLUMN truck_id VARCHAR(20) AFTER id,
ADD COLUMN timestamp DATETIME AFTER truck_id,
ADD COLUMN wialon_epoch BIGINT AFTER timestamp,
ADD COLUMN oil_pressure_psi DECIMAL(5,1) AFTER wialon_epoch,
ADD COLUMN oil_temp_f DECIMAL(5,1),
ADD COLUMN oil_level_pct DECIMAL(5,2),
ADD COLUMN def_level_pct DECIMAL(5,2),
ADD COLUMN def_temp_f DECIMAL(5,2),
ADD COLUMN def_quality VARCHAR(50),
ADD COLUMN engine_load_pct DECIMAL(5,2),
ADD COLUMN rpm INT,
ADD COLUMN coolant_temp_f DECIMAL(5,2),
ADD COLUMN coolant_level_pct DECIMAL(5,2),
ADD COLUMN gear INT,
ADD COLUMN brake_active TINYINT(1),
ADD COLUMN intake_pressure_bar DECIMAL(6,2),
ADD COLUMN intake_temp_f DECIMAL(5,2),
ADD COLUMN intercooler_temp_f DECIMAL(5,2),
ADD COLUMN fuel_temp_f DECIMAL(5,2),
ADD COLUMN fuel_level_pct DECIMAL(5,2),
ADD COLUMN fuel_rate_gph DECIMAL(6,3),
ADD COLUMN fuel_pressure_psi DECIMAL(6,2),
ADD COLUMN ambient_temp_f DECIMAL(5,2),
ADD COLUMN barometric_pressure_inhg DECIMAL(5,2),
ADD COLUMN voltage DECIMAL(4,2),
ADD COLUMN backup_voltage DECIMAL(4,2),
ADD COLUMN engine_hours DECIMAL(10,2),
ADD COLUMN idle_hours DECIMAL(10,2),
ADD COLUMN pto_hours DECIMAL(10,2),
ADD COLUMN total_idle_fuel_gal DECIMAL(10,2),
ADD COLUMN total_fuel_used_gal DECIMAL(10,2),
ADD COLUMN dtc_count INT DEFAULT 0,
ADD COLUMN dtc_code VARCHAR(500),
ADD COLUMN latitude DOUBLE,
ADD COLUMN longitude DOUBLE,
ADD COLUMN speed_mph DOUBLE,
ADD COLUMN altitude_ft DOUBLE,
ADD COLUMN odometer_mi DOUBLE,
ADD COLUMN heading_deg DECIMAL(5,2),
ADD COLUMN throttle_position_pct DECIMAL(5,2),
ADD COLUMN turbo_pressure_psi DECIMAL(6,2),
ADD COLUMN dpf_pressure_psi DECIMAL(6,2),
ADD COLUMN dpf_soot_pct DECIMAL(5,2),
ADD COLUMN dpf_ash_pct DECIMAL(5,2),
ADD COLUMN dpf_status VARCHAR(50),
ADD COLUMN egr_position_pct DECIMAL(5,2),
ADD COLUMN egr_temp_f DECIMAL(6,2),
ADD COLUMN alternator_status VARCHAR(50),
ADD COLUMN transmission_temp_f DECIMAL(5,2),
ADD COLUMN transmission_pressure_psi DECIMAL(6,2),
ADD COLUMN data_age_seconds INT;

-- Agregar índice para truck_id
ALTER TABLE truck_sensors_cache
ADD INDEX idx_truck_id (truck_id),
ADD INDEX idx_timestamp (timestamp);

SELECT 'Columnas agregadas a truck_sensors_cache!' AS status;
DESCRIBE truck_sensors_cache;
