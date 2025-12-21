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
  AND refuel_time BETWEEN '2025-12-20 18:20:00' AND '2025-12-20 18:30:00';

-- Insert the lost refuel
INSERT INTO refuel_events (
    truck_id,
    refuel_time,
    before_pct,
    after_pct,
    gallons_added,
    refuel_type
) VALUES (
    'LC6799',
    '2025-12-20 18:25:56',
    66.0,
    92.8,
    53.6,
    'MANUAL_RECOVERY'
);

-- Verify insertion
SELECT 
    'AFTER INSERT - Should be 1 row:' as check_type,
    id,
    truck_id,
    refuel_time,
    before_pct,
    after_pct,
    gallons_added,
    refuel_type
FROM refuel_events
WHERE truck_id = 'LC6799'
  AND refuel_time BETWEEN '2025-12-20 18:20:00' AND '2025-12-20 18:30:00';

-- Show LC6799 refuel history
SELECT 
    'LC6799 REFUEL HISTORY:' as info,
    id,
    timestamp_utc,
    refuel_time,
    CONCAT(before_pct, '% → ', after_pct, '%') as fuel_change,
    CONCAT('+', gallons_added, ' gal') as volume,
    refuel_type
FROM refuel_events
WHERE truck_id = 'LC6799'
ORDER BY refuel_time
