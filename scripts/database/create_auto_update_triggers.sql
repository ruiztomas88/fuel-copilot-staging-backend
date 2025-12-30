-- ============================================================================
-- AUTO-UPDATE TRIGGERS PARA DAILY_TRUCK_METRICS
-- Se ejecutan automáticamente cuando wialon_sync inserta en fuel_metrics
-- ============================================================================

USE fuel_copilot;

-- Primero eliminamos el trigger si existe
DROP TRIGGER IF EXISTS after_fuel_metrics_insert;

DELIMITER $$

-- Trigger que actualiza daily_truck_metrics automáticamente
CREATE TRIGGER after_fuel_metrics_insert
AFTER INSERT ON fuel_metrics
FOR EACH ROW
BEGIN
    -- Actualizar o insertar registro diario para este truck_id + fecha
    INSERT INTO daily_truck_metrics (
        truck_id, 
        date, 
        miles_traveled,
        fuel_consumed_gallons,
        avg_mpg,
        idle_hours,
        idle_fuel_gallons,
        moving_hours,
        total_records,
        avg_speed_mph,
        max_speed_mph,
        overspeeding_events,
        high_rpm_events,
        avg_rpm,
        voltage_issues,
        gps_issues
    )
    SELECT
        NEW.truck_id,
        DATE(NEW.timestamp_utc) as date,
        GREATEST(0, COALESCE(MAX(odometer_mi) - MIN(odometer_mi), 0)) as miles_traveled,
        SUM(COALESCE(consumption_gph, 0) * 0.033) as fuel_consumed_gallons,
        COALESCE(AVG(NULLIF(mpg_current, 0)), 5.7) as avg_mpg,
        SUM(CASE WHEN truck_status = 'IDLE' THEN 0.033 ELSE 0 END) as idle_hours,
        SUM(CASE WHEN truck_status = 'IDLE' THEN COALESCE(idle_gph, consumption_gph, 0) * 0.033 ELSE 0 END) as idle_fuel_gallons,
        SUM(CASE WHEN truck_status = 'MOVING' THEN 0.033 ELSE 0 END) as moving_hours,
        COUNT(*) as total_records,
        AVG(NULLIF(speed_mph, 0)) as avg_speed_mph,
        MAX(speed_mph) as max_speed_mph,
        SUM(CASE WHEN speed_mph > 70 THEN 1 ELSE 0 END) as overspeeding_events,
        SUM(CASE WHEN rpm > 1800 THEN 1 ELSE 0 END) as high_rpm_events,
        AVG(NULLIF(rpm, 0)) as avg_rpm,
        SUM(CASE WHEN battery_voltage < 12.0 OR battery_voltage > 14.5 THEN 1 ELSE 0 END) as voltage_issues,
        SUM(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 ELSE 0 END) as gps_issues
    FROM fuel_metrics
    WHERE truck_id = NEW.truck_id
    AND DATE(timestamp_utc) = DATE(NEW.timestamp_utc)
    GROUP BY truck_id, DATE(timestamp_utc)
    ON DUPLICATE KEY UPDATE
        miles_traveled = VALUES(miles_traveled),
        fuel_consumed_gallons = VALUES(fuel_consumed_gallons),
        avg_mpg = VALUES(avg_mpg),
        idle_hours = VALUES(idle_hours),
        idle_fuel_gallons = VALUES(idle_fuel_gallons),
        moving_hours = VALUES(moving_hours),
        total_records = VALUES(total_records),
        avg_speed_mph = VALUES(avg_speed_mph),
        max_speed_mph = VALUES(max_speed_mph),
        overspeeding_events = VALUES(overspeeding_events),
        high_rpm_events = VALUES(high_rpm_events),
        avg_rpm = VALUES(avg_rpm),
        voltage_issues = VALUES(voltage_issues),
        gps_issues = VALUES(gps_issues),
        updated_at = CURRENT_TIMESTAMP;
END$$

DELIMITER ;

-- Trigger para actualizar fleet_summary automáticamente
DROP TRIGGER IF EXISTS after_daily_metrics_update;

DELIMITER $$

CREATE TRIGGER after_daily_metrics_update
AFTER INSERT ON daily_truck_metrics
FOR EACH ROW
BEGIN
    INSERT INTO fleet_summary (
        summary_date,
        total_trucks,
        active_trucks,
        total_miles,
        total_fuel_gallons,
        fleet_avg_mpg,
        total_idle_hours,
        total_moving_hours
    )
    SELECT
        NEW.date as summary_date,
        COUNT(DISTINCT truck_id) as total_trucks,
        SUM(CASE WHEN miles_traveled > 0 THEN 1 ELSE 0 END) as active_trucks,
        SUM(miles_traveled) as total_miles,
        SUM(fuel_consumed_gallons) as total_fuel_gallons,
        AVG(avg_mpg) as fleet_avg_mpg,
        SUM(idle_hours) as total_idle_hours,
        SUM(moving_hours) as total_moving_hours
    FROM daily_truck_metrics
    WHERE date = NEW.date
    GROUP BY date
    ON DUPLICATE KEY UPDATE
        total_trucks = VALUES(total_trucks),
        active_trucks = VALUES(active_trucks),
        total_miles = VALUES(total_miles),
        total_fuel_gallons = VALUES(total_fuel_gallons),
        fleet_avg_mpg = VALUES(fleet_avg_mpg),
        total_idle_hours = VALUES(total_idle_hours),
        total_moving_hours = VALUES(total_moving_hours),
        updated_at = CURRENT_TIMESTAMP;
END$$

DELIMITER ;

-- Verificar que se crearon
SHOW TRIGGERS WHERE `Table` IN ('fuel_metrics', 'daily_truck_metrics');
