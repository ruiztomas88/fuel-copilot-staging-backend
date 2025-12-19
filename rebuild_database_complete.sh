#!/bin/bash
###############################################################################
# FUEL COPILOT - COMPLETE DATABASE REBUILD SCRIPT
# Este script reconstruye COMPLETAMENTE la base de datos con todas las
# tablas, columnas, e índices que se han ido agregando en todas las versiones
#
# IMPORTANTE: Este script consolida TODAS las migraciones que se hicieron
# durante el desarrollo del sistema
###############################################################################

set -e  # Exit on error

DB_USER="fuel_admin"
DB_PASS="FuelCopilot2025!"
DB_NAME="fuel_copilot"

echo "========================================="
echo "FUEL COPILOT - DATABASE REBUILD"
echo "========================================="
echo ""
echo "⚠️  WARNING: This will rebuild the database structure"
echo "    Existing data will be PRESERVED"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Starting database rebuild..."
echo ""

# Execute complete rebuild SQL
mysql -u${DB_USER} -p"${DB_PASS}" ${DB_NAME} <<'EOSQL'

-- ============================================
-- PARTE 1: TABLAS PRINCIPALES
-- ============================================

-- ============================================
-- TABLE: fuel_metrics (COMPLETE VERSION)
-- ============================================
-- Esta tabla contiene TODAS las columnas que se fueron agregando

-- Primero verificamos qué columnas faltan y las agregamos
ALTER TABLE fuel_metrics 
    ADD COLUMN IF NOT EXISTS carrier_id VARCHAR(50) DEFAULT 'skylord' AFTER unit_id;

-- Location columns
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='latitude');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN latitude DECIMAL(11,8) AFTER altitude_ft', 
    'SELECT "latitude exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='longitude');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN longitude DECIMAL(11,8) AFTER latitude', 
    'SELECT "longitude exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Sensor columns (v3.12.22)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='engine_load_pct');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN engine_load_pct DECIMAL(5,2) COMMENT "Engine load percentage (0-100%)"', 
    'SELECT "engine_load_pct exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- DTC columns (v5.7.5)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='active_dtc_count');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN active_dtc_count INT DEFAULT 0 COMMENT "Number of active DTCs"', 
    'SELECT "active_dtc_count exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='dtc_codes');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN dtc_codes JSON COMMENT "Array of active DTC codes"', 
    'SELECT "dtc_codes exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='dtc_severity');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN dtc_severity VARCHAR(20) COMMENT "Highest DTC severity: CRITICAL, HIGH, MEDIUM, LOW"', 
    'SELECT "dtc_severity exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Temperature columns (v5.3.3)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='trans_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN trans_temp_f DECIMAL(5,2) COMMENT "Transmission oil temperature (°F)"', 
    'SELECT "trans_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='fuel_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN fuel_temp_f DECIMAL(5,2) COMMENT "Fuel temperature (°F)"', 
    'SELECT "fuel_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='intercooler_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN intercooler_temp_f DECIMAL(5,2) COMMENT "Intercooler outlet temperature (°F)"', 
    'SELECT "intercooler_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Predictive Maintenance sensors (v5.12.2)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='intake_press_kpa');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN intake_press_kpa DECIMAL(6,2) COMMENT "Intake manifold pressure (kPa)"', 
    'SELECT "intake_press_kpa exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='retarder_level');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN retarder_level DECIMAL(5,2) COMMENT "Retarder/Jake brake level (%)"', 
    'SELECT "retarder_level exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Additional sensors (v5.12.3)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='oil_pressure_psi');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN oil_pressure_psi DECIMAL(5,1) COMMENT "Engine oil pressure (PSI)"', 
    'SELECT "oil_pressure_psi exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='oil_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN oil_temp_f DECIMAL(5,1) COMMENT "Engine oil temperature (°F)"', 
    'SELECT "oil_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='boost_pressure_psi');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN boost_pressure_psi DOUBLE COMMENT "Turbo boost pressure (PSI)"', 
    'SELECT "boost_pressure_psi exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='exhaust_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN exhaust_temp_f DOUBLE COMMENT "Exhaust gas temperature (°F)"', 
    'SELECT "exhaust_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='def_level_pct');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN def_level_pct DECIMAL(5,2) COMMENT "DEF tank level (%)"', 
    'SELECT "def_level_pct exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='battery_voltage');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN battery_voltage DECIMAL(4,2) COMMENT "Battery voltage (V)"', 
    'SELECT "battery_voltage exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='ambient_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN ambient_temp_f DECIMAL(5,2) COMMENT "Ambient air temperature (°F)"', 
    'SELECT "ambient_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='intake_air_temp_f');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN intake_air_temp_f DECIMAL(5,2) COMMENT "Intake manifold air temperature (°F)"', 
    'SELECT "intake_air_temp_f exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Idle validation columns (v5.7.6)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='idle_gph');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN idle_gph DOUBLE COMMENT "Idle fuel consumption rate (GPH)"', 
    'SELECT "idle_gph exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- GPS & misc sensors
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='sats');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN sats INT COMMENT "Number of GPS satellites in view"', 
    'SELECT "sats exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='gps_quality');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN gps_quality VARCHAR(100) COMMENT "GPS quality descriptor"', 
    'SELECT "gps_quality exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='pwr_int');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN pwr_int DECIMAL(4,2) COMMENT "Internal power voltage"', 
    'SELECT "pwr_int exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='terrain_factor');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN terrain_factor DECIMAL(6,3) DEFAULT 1.000 COMMENT "Terrain difficulty multiplier"', 
    'SELECT "terrain_factor exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics' AND COLUMN_NAME='idle_hours_ecu');
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE fuel_metrics ADD COLUMN idle_hours_ecu DECIMAL(10,2) COMMENT "Total engine idle hours from ECU"', 
    'SELECT "idle_hours_ecu exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================
-- PARTE 2: OTRAS TABLAS
-- ============================================

-- truck_sensors_cache
CREATE TABLE IF NOT EXISTS truck_sensors_cache (
    truck_id VARCHAR(20) PRIMARY KEY,
    unit_id INT NOT NULL,
    timestamp DATETIME,
    wialon_epoch INT,
    oil_pressure_psi DECIMAL(10,2),
    oil_temp_f DECIMAL(10,2),
    oil_level_pct DECIMAL(10,2),
    def_level_pct DECIMAL(10,2),
    def_temp_f DECIMAL(10,2),
    def_quality DECIMAL(10,2),
    engine_load_pct DECIMAL(10,2),
    rpm INT,
    coolant_temp_f DECIMAL(10,2),
    coolant_level_pct DECIMAL(10,2),
    gear INT,
    brake_active TINYINT(1),
    intake_pressure_bar DECIMAL(10,4),
    intake_temp_f DECIMAL(10,2),
    intercooler_temp_f DECIMAL(10,2),
    fuel_temp_f DECIMAL(10,2),
    fuel_level_pct DECIMAL(10,2),
    fuel_rate_gph DECIMAL(10,4),
    fuel_pressure_psi DECIMAL(10,2),
    ambient_temp_f DECIMAL(10,2),
    barometric_pressure_inhg DECIMAL(10,4),
    voltage DECIMAL(10,2),
    backup_voltage DECIMAL(10,2),
    engine_hours DECIMAL(12,2),
    idle_hours DECIMAL(12,2),
    pto_hours DECIMAL(12,2),
    total_idle_fuel_gal DECIMAL(12,2),
    total_fuel_used_gal DECIMAL(12,2),
    dtc_count INT,
    dtc_code VARCHAR(50),
    latitude DECIMAL(11,8),
    longitude DECIMAL(11,8),
    speed_mph DECIMAL(10,2),
    altitude_ft DECIMAL(10,2),
    odometer_mi DECIMAL(12,2),
    heading_deg DECIMAL(10,2),
    throttle_position_pct DECIMAL(10,2),
    turbo_pressure_psi DECIMAL(10,2),
    dpf_pressure_psi DECIMAL(10,2),
    dpf_soot_pct DECIMAL(10,2),
    dpf_ash_pct DECIMAL(10,2),
    dpf_status VARCHAR(20),
    egr_position_pct DECIMAL(10,2),
    egr_temp_f DECIMAL(10,2),
    alternator_status VARCHAR(20),
    transmission_temp_f DECIMAL(10,2),
    transmission_pressure_psi DECIMAL(10,2),
    data_age_seconds INT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp),
    INDEX idx_data_age (data_age_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- dtc_events
CREATE TABLE IF NOT EXISTS dtc_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    dtc_code VARCHAR(50) NOT NULL,
    component VARCHAR(100),
    severity VARCHAR(20),
    status VARCHAR(20) DEFAULT 'NEW',
    description TEXT,
    action_required TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_truck_timestamp (truck_id, timestamp_utc),
    INDEX idx_status (status),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- units_map (mapping de trucks a unit_ids de Wialon)
CREATE TABLE IF NOT EXISTS units_map (
    unit_id BIGINT PRIMARY KEY,
    truck_id VARCHAR(20) UNIQUE NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_truck (truck_id),
    INDEX idx_carrier (carrier_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT '✅ Database rebuild completed!' AS status;
SELECT 'Checking table structures...' AS info;

-- Show table summaries
SELECT TABLE_NAME, 
       (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'fuel_copilot' AND TABLE_NAME = t.TABLE_NAME) AS column_count,
       TABLE_ROWS as approx_rows
FROM INFORMATION_SCHEMA.TABLES t
WHERE TABLE_SCHEMA = 'fuel_copilot' 
  AND TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;

EOSQL

echo ""
echo "========================================="
echo "✅ Database rebuild completed!"
echo "========================================="
echo ""
echo "To verify, run:"
echo "  mysql -u${DB_USER} -p'${DB_PASS}' ${DB_NAME} -e 'SHOW TABLES;'"
echo ""
