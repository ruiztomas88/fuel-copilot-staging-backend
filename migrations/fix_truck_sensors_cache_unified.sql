-- ============================================
-- FIX truck_sensors_cache - ESTRUCTURA UNIFICADA
-- ============================================
-- Este script corrige la tabla truck_sensors_cache para que tenga
-- la estructura correcta tanto en Mac como en Windows VM.
--
-- Uso: mysql -u fuel_admin -p fuel_copilot < fix_truck_sensors_cache_unified.sql

USE fuel_copilot;

-- Step 1: Drop tabla existente y recrear con estructura correcta
DROP TABLE IF EXISTS truck_sensors_cache;

CREATE TABLE truck_sensors_cache (
  -- Identificación
  truck_id VARCHAR(20) NOT NULL,
  unit_id INT NOT NULL,
  
  -- Timestamp
  timestamp DATETIME NOT NULL,
  wialon_epoch INT NOT NULL,
  
  -- Oil System
  oil_pressure_psi DECIMAL(10,2) DEFAULT NULL,
  oil_temp_f DECIMAL(10,2) DEFAULT NULL,
  oil_level_pct DECIMAL(10,2) DEFAULT NULL,
  
  -- DEF System
  def_level_pct DECIMAL(10,2) DEFAULT NULL,
  def_temp_f DECIMAL(10,2) DEFAULT NULL COMMENT 'DEF temperature F',
  def_quality DECIMAL(10,2) DEFAULT NULL COMMENT 'DEF quality percentage',
  
  -- Engine
  engine_load_pct DECIMAL(10,2) DEFAULT NULL,
  rpm INT DEFAULT NULL,
  coolant_temp_f DECIMAL(10,2) DEFAULT NULL,
  coolant_level_pct DECIMAL(10,2) DEFAULT NULL,
  
  -- Transmission & Brakes
  gear INT DEFAULT NULL,
  brake_active TINYINT(1) DEFAULT NULL,
  
  -- Air Intake
  intake_pressure_bar DECIMAL(10,4) DEFAULT NULL,
  intake_temp_f DECIMAL(10,2) DEFAULT NULL,
  intercooler_temp_f DECIMAL(10,2) DEFAULT NULL,
  
  -- Fuel
  fuel_temp_f DECIMAL(10,2) DEFAULT NULL,
  fuel_level_pct DECIMAL(10,2) DEFAULT NULL,
  fuel_rate_gph DECIMAL(10,4) DEFAULT NULL,
  fuel_pressure_psi DECIMAL(10,2) DEFAULT NULL COMMENT 'Fuel rail pressure PSI',
  
  -- Environmental
  ambient_temp_f DECIMAL(10,2) DEFAULT NULL,
  barometric_pressure_inhg DECIMAL(10,4) DEFAULT NULL,
  
  -- Electrical
  voltage DECIMAL(10,2) DEFAULT NULL,
  backup_voltage DECIMAL(10,2) DEFAULT NULL,
  
  -- Operational Hours
  engine_hours DECIMAL(12,2) DEFAULT NULL,
  idle_hours DECIMAL(12,2) DEFAULT NULL,
  pto_hours DECIMAL(12,2) DEFAULT NULL,
  total_idle_fuel_gal DECIMAL(12,2) DEFAULT NULL,
  total_fuel_used_gal DECIMAL(12,2) DEFAULT NULL,
  
  -- Diagnostics
  dtc_count INT DEFAULT NULL,
  dtc_code VARCHAR(50) DEFAULT NULL,
  
  -- GPS/Location
  latitude DECIMAL(11,8) DEFAULT NULL,
  longitude DECIMAL(11,8) DEFAULT NULL,
  speed_mph DECIMAL(10,2) DEFAULT NULL,
  altitude_ft DECIMAL(10,2) DEFAULT NULL,
  odometer_mi DECIMAL(12,2) DEFAULT NULL COMMENT 'Odometer reading in miles',
  heading_deg DECIMAL(10,2) DEFAULT NULL COMMENT 'GPS heading in degrees',
  
  -- Emissions & Aftertreatment
  throttle_position_pct DECIMAL(10,2) DEFAULT NULL COMMENT 'Throttle position %',
  turbo_pressure_psi DECIMAL(10,2) DEFAULT NULL COMMENT 'Turbo boost pressure PSI',
  dpf_pressure_psi DECIMAL(10,2) DEFAULT NULL COMMENT 'DPF differential pressure',
  dpf_soot_pct DECIMAL(10,2) DEFAULT NULL COMMENT 'DPF soot load %',
  dpf_ash_pct DECIMAL(10,2) DEFAULT NULL COMMENT 'DPF ash load %',
  dpf_status VARCHAR(20) DEFAULT NULL COMMENT 'DPF status',
  egr_position_pct DECIMAL(10,2) DEFAULT NULL COMMENT 'EGR valve position %',
  egr_temp_f DECIMAL(10,2) DEFAULT NULL COMMENT 'EGR temperature F',
  
  -- Other Systems
  alternator_status VARCHAR(20) DEFAULT NULL COMMENT 'Alternator status',
  transmission_temp_f DECIMAL(10,2) DEFAULT NULL COMMENT 'Transmission oil temp F',
  transmission_pressure_psi DECIMAL(10,2) DEFAULT NULL COMMENT 'Transmission pressure PSI',
  
  -- Metadata
  data_age_seconds INT DEFAULT NULL COMMENT 'Age of data in seconds',
  last_updated TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  -- Constraints
  PRIMARY KEY (truck_id),
  KEY idx_timestamp (timestamp),
  KEY idx_last_updated (last_updated),
  KEY idx_data_age (data_age_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
  COMMENT='Real-time sensor cache updated every 30 seconds from Wialon';

SELECT '✅ Tabla truck_sensors_cache recreada con estructura unificada!' AS status;
SELECT 'Total columnas:', COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'fuel_copilot' AND TABLE_NAME = 'truck_sensors_cache';
