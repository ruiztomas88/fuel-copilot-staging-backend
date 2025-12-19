-- Add UNIQUE constraint to prevent duplicate entries
-- This allows ON DUPLICATE KEY UPDATE to work properly

USE fuel_copilot;

-- Add unique constraint on truck_id + timestamp_utc
-- This prevents multiple records for same truck at same time
ALTER TABLE fuel_metrics 
ADD UNIQUE KEY `unique_truck_timestamp` (`truck_id`, `timestamp_utc`);

-- Verify the constraint was added
SHOW CREATE TABLE fuel_metrics\G
