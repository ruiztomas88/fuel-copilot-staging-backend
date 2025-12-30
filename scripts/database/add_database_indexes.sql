-- =====================================================
-- FUEL COPILOT - DATABASE INDEXES OPTIMIZATION
-- =====================================================
-- Purpose: Add missing indexes to improve query performance
-- Impact: 10-50x faster queries
-- Date: December 26, 2025
-- =====================================================

-- Check existing indexes first
SHOW INDEX FROM fuel_metrics;
SHOW INDEX FROM fuel_events;
SHOW INDEX FROM refuel_events;
SHOW INDEX FROM dtc_events;
SHOW INDEX FROM truck_sensors_cache;

-- =====================================================
-- FUEL_METRICS TABLE INDEXES (Primary table)
-- =====================================================

-- Truck + Time compound (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_fuel_truck_time 
    ON fuel_metrics(truck_id, created_at DESC);

-- Status for filtering MOVING/STOPPED
CREATE INDEX IF NOT EXISTS idx_fuel_status 
    ON fuel_metrics(truck_status);

-- Created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_fuel_created 
    ON fuel_metrics(created_at DESC);

-- Compound for fleet summary queries
CREATE INDEX IF NOT EXISTS idx_fuel_compound 
    ON fuel_metrics(truck_id, truck_status, created_at DESC);

-- =====================================================
-- FUEL_EVENTS TABLE INDEXES
-- =====================================================

-- Truck + Timestamp for event history
CREATE INDEX IF NOT EXISTS idx_fuel_events_truck_time 
    ON fuel_events(truck_id, timestamp DESC);

-- Event type for filtering (theft, refuel, etc)
CREATE INDEX IF NOT EXISTS idx_fuel_events_type 
    ON fuel_events(event_type);

-- Timestamp for recent events
CREATE INDEX IF NOT EXISTS idx_fuel_events_timestamp 
    ON fuel_events(timestamp DESC);

-- =====================================================
-- REFUEL_EVENTS TABLE INDEXES
-- =====================================================

-- Truck + Time for refuel history
CREATE INDEX IF NOT EXISTS idx_refuel_truck_time 
    ON refuel_events(truck_id, refuel_time DESC);

-- Validated flag for filtering confirmed refuels
CREATE INDEX IF NOT EXISTS idx_refuel_validated 
    ON refuel_events(validated);

-- Refuel time for recent refuels
CREATE INDEX IF NOT EXISTS idx_refuel_time 
    ON refuel_events(refuel_time DESC);

-- =====================================================
-- DTC_EVENTS TABLE INDEXES
-- =====================================================

-- Truck ID for per-truck DTCs
CREATE INDEX IF NOT EXISTS idx_dtc_truck 
    ON dtc_events(truck_id);

-- Active flag for current DTCs
CREATE INDEX IF NOT EXISTS idx_dtc_active 
    ON dtc_events(is_active);

-- Severity for critical alerts
CREATE INDEX IF NOT EXISTS idx_dtc_severity 
    ON dtc_events(severity);

-- Compound for active critical DTCs per truck
CREATE INDEX IF NOT EXISTS idx_dtc_compound 
    ON dtc_events(truck_id, is_active, severity);

-- Created timestamp for recent DTCs
CREATE INDEX IF NOT EXISTS idx_dtc_created 
    ON dtc_events(created_at DESC);

-- =====================================================
-- TRUCK_SENSORS_CACHE TABLE INDEXES
-- =====================================================

-- Truck ID (primary lookup)
CREATE INDEX IF NOT EXISTS idx_sensors_truck 
    ON truck_sensors_cache(truck_id);

-- Last updated for freshness checks
CREATE INDEX IF NOT EXISTS idx_sensors_updated 
    ON truck_sensors_cache(last_updated DESC);

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================
-- Run these after creating indexes to verify

-- Check indexes on fuel_metrics
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX,
    CARDINALITY
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'fuel_copilot_local'
  AND TABLE_NAME = 'fuel_metrics'
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- Test query performance with EXPLAIN
EXPLAIN SELECT * 
FROM fuel_metrics 
WHERE truck_id = 'CO0681' 
  AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC
LIMIT 100;

-- Should show "Using index" instead of "Using filesort"
