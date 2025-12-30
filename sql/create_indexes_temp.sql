-- ========================================
-- PERFORMANCE INDEXES - FUEL COPILOT
-- ========================================
-- Fecha: 26 Diciembre 2025
-- Objetivo: Optimizar queries críticos
-- Impacto esperado: 10-50x improvement
-- ========================================

-- ========================================
-- 1. TRUCKS TABLE
-- ========================================

-- Status-based queries (dashboard filtering)
CREATE INDEX idx_trucks_status ON trucks(truck_status);

-- Recent updates (sorting by last update)
CREATE INDEX idx_trucks_updated ON trucks(updated_at);

-- Company filtering (multi-tenant)
CREATE INDEX idx_trucks_company ON trucks(company_id);

-- Composite: status + updated (common query pattern)
CREATE INDEX idx_trucks_status_updated ON trucks(truck_status, updated_at);

-- Composite: active trucks by company
CREATE INDEX idx_trucks_company_status ON trucks(company_id, truck_status);

-- ========================================
-- 2. FUEL_EVENTS TABLE
-- ========================================

-- Time-based queries (historical data)
CREATE INDEX idx_fuel_events_timestamp 
ON fuel_events(timestamp);

-- Truck-specific queries
CREATE INDEX idx_fuel_events_truck_id 
ON fuel_events(truck_id);

-- Composite: truck + time (most common pattern)
CREATE INDEX idx_fuel_events_truck_time 
ON fuel_events(truck_id, timestamp);

-- Event type filtering (theft detection, refuels)
CREATE INDEX idx_fuel_events_event_type 
ON fuel_events(event_type);

-- Composite: truck + type + time
CREATE INDEX idx_fuel_events_truck_type_time 
ON fuel_events(truck_id, event_type, timestamp);

-- ========================================
-- 3. FUEL_METRICS TABLE
-- ========================================

-- Truck-specific time series
CREATE INDEX idx_fuel_metrics_truck_time 
ON fuel_metrics(truck_id, timestamp_utc);

-- Time-based queries
CREATE INDEX idx_fuel_metrics_timestamp 
ON fuel_metrics(timestamp_utc);

-- Idle detection queries
CREATE INDEX idx_fuel_metrics_idle 
ON fuel_metrics(idle_mode, timestamp_utc);

-- ========================================
-- 4. SENSOR_DATA TABLE
-- ========================================

-- Most common: truck + time
CREATE INDEX idx_sensor_data_truck_time 
ON sensor_data(truck_id, timestamp);

-- Time-based queries
CREATE INDEX idx_sensor_data_timestamp 
ON sensor_data(timestamp);

-- Sensor type filtering
CREATE INDEX idx_sensor_data_type 
ON sensor_data(sensor_type);

-- ========================================
-- 5. DTC_EVENTS TABLE
-- ========================================

-- Truck-specific DTCs
CREATE INDEX idx_dtc_events_truck 
ON dtc_events(truck_id);

-- Active DTCs (dashboard filtering)
CREATE INDEX idx_dtc_events_active 
ON dtc_events(is_active);

-- Severity filtering
CREATE INDEX idx_dtc_events_severity 
ON dtc_events(severity);

-- Time-based queries
CREATE INDEX idx_dtc_events_timestamp 
ON dtc_events(timestamp);

-- Composite: truck + active + severity (common dashboard query)
CREATE INDEX idx_dtc_events_truck_active_severity 
ON dtc_events(truck_id, is_active, severity);

-- Composite: active + severity + time (alerts)
CREATE INDEX idx_dtc_events_active_severity_time 
ON dtc_events(is_active, severity, timestamp);

-- ========================================
-- 6. TRUCK_SENSORS_CACHE TABLE
-- ========================================

-- Primary lookup by truck_id (most frequent query)
CREATE INDEX idx_truck_sensors_cache_truck 
ON truck_sensors_cache(truck_id);

-- Freshness check
CREATE INDEX idx_truck_sensors_cache_timestamp 
ON truck_sensors_cache(timestamp);

-- Data age for staleness detection
CREATE INDEX idx_truck_sensors_cache_age 
ON truck_sensors_cache(data_age_seconds);

-- ========================================
-- 7. REFUEL_EVENTS TABLE
-- ========================================

-- Truck-specific refuels
CREATE INDEX idx_refuel_events_truck 
ON refuel_events(truck_id);

-- Time-based queries
CREATE INDEX idx_refuel_events_timestamp 
ON refuel_events(timestamp);

-- Composite: truck + time
CREATE INDEX idx_refuel_events_truck_time 
ON refuel_events(truck_id, timestamp);

-- Refuel type filtering
CREATE INDEX idx_refuel_events_type 
ON refuel_events(refuel_type);

-- ========================================
-- 8. MAINTENANCE_EVENTS TABLE
-- ========================================

-- Truck-specific maintenance
CREATE INDEX idx_maintenance_events_truck 
ON maintenance_events(truck_id);

-- Time-based queries
CREATE INDEX idx_maintenance_events_timestamp 
ON maintenance_events(timestamp);

-- Type filtering
CREATE INDEX idx_maintenance_events_type 
ON maintenance_events(event_type);

-- Composite: truck + time
CREATE INDEX idx_maintenance_events_truck_time 
ON maintenance_events(truck_id, timestamp);

-- ========================================
-- 9. TRIPS TABLE
-- ========================================

-- Truck-specific trips
CREATE INDEX idx_trips_truck 
ON trips(truck_id);

-- Time-based queries (start time)
CREATE INDEX idx_trips_start_time 
ON trips(start_time);

-- Composite: truck + start time
CREATE INDEX idx_trips_truck_start 
ON trips(truck_id, start_time);

-- Distance-based queries (long trips)
CREATE INDEX idx_trips_distance 
ON trips(distance_miles);

-- ========================================
-- 10. GPS_DATA TABLE
-- ========================================

-- Truck-specific GPS
CREATE INDEX idx_gps_data_truck 
ON gps_data(truck_id);

-- Time-based queries
CREATE INDEX idx_gps_data_timestamp 
ON gps_data(timestamp);

-- Composite: truck + time
CREATE INDEX idx_gps_data_truck_time 
ON gps_data(truck_id, timestamp);

-- Geospatial queries (if using POINT type, create spatial index)
-- CREATE SPATIAL INDEX idx_gps_data_location ON gps_data(location);

-- ========================================
-- VERIFICATION QUERIES
-- ========================================

-- Run these to verify indexes were created:

-- Show all indexes on trucks table
-- SHOW INDEX FROM trucks;

-- Show all indexes in database
-- SELECT 
--     TABLE_NAME,
--     INDEX_NAME,
--     GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as COLUMNS
-- FROM information_schema.STATISTICS
-- WHERE TABLE_SCHEMA = 'fuel_monitoring'
-- GROUP BY TABLE_NAME, INDEX_NAME
-- ORDER BY TABLE_NAME, INDEX_NAME;

-- ========================================
-- PERFORMANCE TESTING
-- ========================================

-- Test query performance before/after:

-- Example 1: Get active DTCs for truck
-- EXPLAIN SELECT * FROM dtc_events 
-- WHERE truck_id = 'FL-0208' 
-- AND is_active = 1 
-- ORDER BY severity DESC;

-- Example 2: Get recent fuel events
-- EXPLAIN SELECT * FROM fuel_events 
-- WHERE truck_id = 'FL-0208' 
-- AND timestamp > DATE_SUB(NOW(), INTERVAL 7 DAY)
-- ORDER BY timestamp DESC;

-- Example 3: Fleet summary
-- EXPLAIN SELECT truck_id, truck_status, updated_at 
-- FROM trucks 
-- WHERE truck_status = 'active' 
-- ORDER BY updated_at DESC;

-- ========================================
-- MAINTENANCE NOTES
-- ========================================

-- 1. Monitor index usage:
--    SELECT * FROM sys.schema_unused_indexes;

-- 2. Rebuild indexes periodically (if fragmented):
--    OPTIMIZE TABLE trucks;

-- 3. Update table statistics after bulk inserts:
--    ANALYZE TABLE fuel_events;

-- 4. Consider partitioning for large time-series tables:
--    ALTER TABLE fuel_metrics PARTITION BY RANGE (YEAR(timestamp_utc)) (...);

-- ========================================
-- END OF SCRIPT
-- ========================================
