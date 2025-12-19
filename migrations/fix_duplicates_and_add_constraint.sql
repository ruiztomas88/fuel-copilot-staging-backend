-- Remove duplicate entries before adding unique constraint
-- Keep only the latest record for each truck_id + timestamp_utc combination

USE fuel_copilot;

-- First, let's see how many duplicates we have
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT truck_id, timestamp_utc) as unique_combinations,
    COUNT(*) - COUNT(DISTINCT truck_id, timestamp_utc) as duplicates
FROM fuel_metrics;

-- Delete duplicates, keeping only the one with highest ID (most recent insert)
DELETE fm1 FROM fuel_metrics fm1
INNER JOIN fuel_metrics fm2 
WHERE 
    fm1.truck_id = fm2.truck_id 
    AND fm1.timestamp_utc = fm2.timestamp_utc
    AND fm1.id < fm2.id;

-- Verify duplicates are gone
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT truck_id, timestamp_utc) as unique_combinations,
    COUNT(*) - COUNT(DISTINCT truck_id, timestamp_utc) as duplicates_remaining
FROM fuel_metrics;

-- Now add the unique constraint
ALTER TABLE fuel_metrics 
ADD UNIQUE KEY `unique_truck_timestamp` (`truck_id`, `timestamp_utc`);

-- Confirm
SHOW CREATE TABLE fuel_metrics\G
