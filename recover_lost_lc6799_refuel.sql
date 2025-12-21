-- recover_lost_lc6799_refuel.sql
-- 🔧 v5.17.1: Manually insert lost refuel for LC6799
-- This refuel was DETECTED (Kalman reset to 92.8%) but NOT SAVED due to pending buffer bug

-- Context:
--   Date: 2025-12-20 18:25:56 UTC
--   Truck: LC6799
--   Jump: 66.0% → 92.8% (26.8 percentage points)
--   Tank: ~200 gallons capacity
--   Volume: ~53.6 gallons added
--   Evidence: fuel_metrics shows Kalman reset, refuel_events is empty

USE fuel_copilot;

-- First check if it's already there (shouldn't be)
SELECT 
    'BEFORE INSERT - Should be 0 rows:' as check_type,
    COUNT(*) as count
FROM refuel_events
WHERE truck_id = 'LC6799'
  AND timestamp_utc BETWEEN '2025-12-20 18:20:00' AND '2025-12-20 18:30:00';

-- Insert the lost refuel
INSERT INTO refuel_events (
    truck_id,
    timestamp_utc,
    fuel_before,
    fuel_after,
    gallons_added,
    latitude,
    longitude,
    refuel_type,
    notes
) VALUES (
    'LC6799',
    '2025-12-20 18:25:56',
    66.0,
    92.8,
    53.6,
    NULL,  -- Location data was not captured
    NULL,
    'MANUAL_RECOVERY',
    'v5.17.1: Recovered lost refuel - detected by Kalman but not saved due to pending buffer bug'
);

-- Verify insertion
SELECT 
    'AFTER INSERT - Should be 1 row:' as check_type,
    id,
    truck_id,
    timestamp_utc,
    fuel_before,
    fuel_after,
    gallons_added,
    refuel_type,
    notes
FROM refuel_events
WHERE truck_id = 'LC6799'
  AND timestamp_utc BETWEEN '2025-12-20 18:20:00' AND '2025-12-20 18:30:00';

-- Show LC6799 refuel history
SELECT 
    'LC6799 REFUEL HISTORY:' as info,
    id,
    timestamp_utc,
    CONCAT(fuel_before, '% → ', fuel_after, '%') as fuel_change,
    CONCAT('+', gallons_added, ' gal') as volume,
    refuel_type
FROM refuel_events
WHERE truck_id = 'LC6799'
ORDER BY timestamp_utc DESC
LIMIT 10;
