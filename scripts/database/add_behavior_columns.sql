-- Add columns for new sensors and behavior tracking to fuel_metrics
-- Run: mysql -h localhost -u root fuel_copilot_local < add_behavior_columns.sql

-- Add obd_speed_mph (from new sensor)
ALTER TABLE fuel_metrics ADD COLUMN obd_speed_mph FLOAT AFTER speed_mph;

-- Add engine_brake_active (from new sensor)  
ALTER TABLE fuel_metrics ADD COLUMN engine_brake_active TINYINT(1) AFTER rpm;

-- Add acceleration rate (calculated from speed changes)
ALTER TABLE fuel_metrics ADD COLUMN accel_rate_mpss FLOAT COMMENT 'Acceleration rate in mph/s' AFTER obd_speed_mph;

-- Add harsh acceleration flag (accel > 4 mph/s)
ALTER TABLE fuel_metrics ADD COLUMN harsh_accel TINYINT(1) DEFAULT 0 COMMENT 'Harsh acceleration detected' AFTER accel_rate_mpss;

-- Add harsh braking flag (decel < -4 mph/s)
ALTER TABLE fuel_metrics ADD COLUMN harsh_brake TINYINT(1) DEFAULT 0 COMMENT 'Harsh braking detected' AFTER harsh_accel;

-- Add gear position
ALTER TABLE fuel_metrics ADD COLUMN gear TINYINT COMMENT 'Current gear (-1=R, 0=N, 1-18=forward)' AFTER rpm;

-- Add oil level percentage
ALTER TABLE fuel_metrics ADD COLUMN oil_level_pct FLOAT COMMENT 'Oil level percentage' AFTER def_level_pct;

-- Add barometric pressure
ALTER TABLE fuel_metrics ADD COLUMN barometric_pressure_inhg FLOAT COMMENT 'Barometric pressure in inHg' AFTER ambient_temp_f;

-- Add PTO hours
ALTER TABLE fuel_metrics ADD COLUMN pto_hours FLOAT COMMENT 'Power Take-Off hours' AFTER idle_hours_ecu;

SELECT 'Columns added successfully!' as status;
