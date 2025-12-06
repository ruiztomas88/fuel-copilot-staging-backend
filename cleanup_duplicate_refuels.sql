-- Script to remove duplicate refuels from refuel_events table
-- Keeps the first occurrence (lowest id) for each truck/time combination

-- First, view duplicates
SELECT 
    truck_id, 
    DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:%i') as refuel_time,
    COUNT(*) as count,
    GROUP_CONCAT(id ORDER BY id) as ids,
    GROUP_CONCAT(gallons_added ORDER BY id) as gallons
FROM refuel_events
GROUP BY truck_id, DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:%i')
HAVING COUNT(*) > 1
ORDER BY timestamp_utc DESC;

-- Then delete duplicates (keeps lowest id)
DELETE r1 FROM refuel_events r1
INNER JOIN refuel_events r2 
WHERE r1.id > r2.id 
  AND r1.truck_id = r2.truck_id 
  AND ABS(TIMESTAMPDIFF(MINUTE, r1.timestamp_utc, r2.timestamp_utc)) < 5
  AND ABS(r1.gallons_added - r2.gallons_added) < 5;
