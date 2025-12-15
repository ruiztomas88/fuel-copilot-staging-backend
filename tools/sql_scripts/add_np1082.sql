-- ═══════════════════════════════════════════════════════════════════════════════
-- ADD NP1082 TO units_map
-- Run on Wialon VM: mysql -u root -p wialon_collect < add_np1082.sql
-- ═══════════════════════════════════════════════════════════════════════════════

USE wialon_collect;

-- Check if already exists
SELECT 'BEFORE:' as status, beyondId, unit, fuel_capacity 
FROM units_map 
WHERE beyondId = 'NP1082';

-- Insert or update
INSERT INTO units_map (beyondId, unit, fuel_capacity) 
VALUES ('NP1082', 869842053739178, 200)
ON DUPLICATE KEY UPDATE unit = 869842053739178, fuel_capacity = 200;

-- Verify
SELECT 'AFTER:' as status, beyondId, unit, fuel_capacity 
FROM units_map 
WHERE beyondId = 'NP1082';

-- Show total count
SELECT CONCAT('Total trucks: ', COUNT(*)) as summary FROM units_map;
