-- ========================================
-- PERFORMANCE INDEXES - FUEL COPILOT
-- For Existing Tables Only
-- ========================================
-- Fecha: 26 Diciembre 2025
-- DB: fuel_copilot_local
-- ========================================

-- ========================================
-- 1. FUEL_METRICS TABLE
-- ========================================

-- Truck-specific time series (most common query)
CREATE INDEX idx_fuel_metrics_truck_time ON fuel_metrics(truck_id, timestamp_utc);

-- Time-based queries
CREATE INDEX idx_fuel_metrics_timestamp ON fuel_metrics(timestamp_utc);

-- Idle detection queries
CREATE INDEX idx_fuel_metrics_idle ON fuel_metrics(idle_mode, timestamp_utc);

-- ========================================
-- 2. DTC_EVENTS TABLE
-- ========================================

-- Truck-specific DTCs
CREATE INDEX idx_dtc_events_truck ON dtc_events(truck_id);

-- Status filtering (ACTIVE, RESOLVED, etc.)
CREATE INDEX idx_dtc_events_status ON dtc_events(status);

-- Severity filtering
CREATE INDEX idx_dtc_events_severity ON dtc_events(severity);

-- Time-based queries
CREATE INDEX idx_dtc_events_timestamp ON dtc_events(timestamp_utc);

-- Critical DTCs
CREATE INDEX idx_dtc_events_critical ON dtc_events(is_critical);

-- Category filtering
CREATE INDEX idx_dtc_events_category ON dtc_events(category);

-- Composite: truck + status + severity (common dashboard query)
CREATE INDEX idx_dtc_events_truck_status_severity ON dtc_events(truck_id, status, severity);

-- Composite: status + severity + time (alerts)
CREATE INDEX idx_dtc_events_status_severity_time ON dtc_events(status, severity, timestamp_utc);

-- SPN lookup for DTC decoding
CREATE INDEX idx_dtc_events_spn ON dtc_events(spn);

-- ========================================
-- 3. TRUCK_SENSORS_CACHE TABLE
-- ========================================

-- Primary lookup by truck_id (most frequent query)
CREATE INDEX idx_truck_sensors_cache_truck ON truck_sensors_cache(truck_id);

-- Freshness check
CREATE INDEX idx_truck_sensors_cache_timestamp ON truck_sensors_cache(timestamp);

-- Data age for staleness detection
CREATE INDEX idx_truck_sensors_cache_age ON truck_sensors_cache(data_age_seconds);

-- ========================================
-- 4. REFUEL_EVENTS TABLE
-- ========================================

-- Truck-specific refuels
CREATE INDEX idx_refuel_events_truck ON refuel_events(truck_id);

-- Time-based queries
CREATE INDEX idx_refuel_events_time ON refuel_events(refuel_time);

-- Composite: truck + time
CREATE INDEX idx_refuel_events_truck_time ON refuel_events(truck_id, refuel_time);

-- Refuel type filtering
CREATE INDEX idx_refuel_events_type ON refuel_events(refuel_type);

-- Validated refuels
CREATE INDEX idx_refuel_events_validated ON refuel_events(validated);

-- ========================================
-- 5. TRUCK_SPECS TABLE
-- ========================================

-- Truck lookup
CREATE INDEX idx_truck_specs_truck ON truck_specs(truck_id);

-- ========================================
-- 6. DRIVER_SCORES TABLE
-- ========================================

-- Truck-specific scores
CREATE INDEX idx_driver_scores_truck ON driver_scores(truck_id);

-- Time-based queries (if timestamp column exists)
-- CREATE INDEX idx_driver_scores_timestamp ON driver_scores(timestamp);

-- ========================================
-- 7. ANOMALY_DETECTIONS TABLE
-- ========================================

-- Truck-specific anomalies
CREATE INDEX idx_anomaly_detections_truck ON anomaly_detections(truck_id);

-- Time-based queries
CREATE INDEX idx_anomaly_detections_timestamp ON anomaly_detections(timestamp);

-- Type filtering
CREATE INDEX idx_anomaly_detections_type ON anomaly_detections(anomaly_type);

-- ========================================
-- 8. PM_PREDICTIONS TABLE (Predictive Maintenance)
-- ========================================

-- Truck-specific predictions
CREATE INDEX idx_pm_predictions_truck ON pm_predictions(truck_id);

-- Component filtering
CREATE INDEX idx_pm_predictions_component ON pm_predictions(component);

-- ========================================
-- 9. ENGINE_HEALTH_ALERTS TABLE
-- ========================================

-- Truck-specific alerts
CREATE INDEX idx_engine_health_alerts_truck ON engine_health_alerts(truck_id);

-- Time-based queries
CREATE INDEX idx_engine_health_alerts_timestamp ON engine_health_alerts(timestamp);

-- Severity filtering
CREATE INDEX idx_engine_health_alerts_severity ON engine_health_alerts(severity);

-- ========================================
-- 10. CC_CORRELATION_EVENTS TABLE (Command Center)
-- ========================================

-- Truck-specific events
CREATE INDEX idx_cc_correlation_events_truck ON cc_correlation_events(truck_id);

-- Time-based queries
CREATE INDEX idx_cc_correlation_events_timestamp ON cc_correlation_events(timestamp);

-- ========================================
-- VERIFICATION
-- ========================================

-- Check which indexes were created successfully:
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as COLUMNS,
    INDEX_TYPE
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'fuel_copilot_local'
  AND INDEX_NAME LIKE 'idx_%'
GROUP BY TABLE_NAME, INDEX_NAME, INDEX_TYPE
ORDER BY TABLE_NAME, INDEX_NAME;
