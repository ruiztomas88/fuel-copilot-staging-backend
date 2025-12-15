-- ═══════════════════════════════════════════════════════════════════════════════
-- ADD IDLE TRACKING COLUMNS TO fuel_metrics TABLE (VM)
-- ═══════════════════════════════════════════════════════════════════════════════
-- Run this on the VM to add missing idle_gph and idle_method columns
-- These columns are required for the v5.4.6 idle consumption tracking
-- ═══════════════════════════════════════════════════════════════════════════════

USE fuel_copilot;

-- Check if columns already exist before adding them
SET @db_name = 'fuel_copilot';
SET @table_name = 'fuel_metrics';

-- Add idle_gph column if it doesn't exist
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = @db_name 
  AND TABLE_NAME = @table_name 
  AND COLUMN_NAME = 'idle_gph';

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE fuel_metrics ADD COLUMN idle_gph DECIMAL(6,3) DEFAULT NULL COMMENT ''Idle consumption in gallons per hour''',
    'SELECT ''Column idle_gph already exists'' AS message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add idle_method column if it doesn't exist (pero ya existe según el esquema)
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = @db_name 
  AND TABLE_NAME = @table_name 
  AND COLUMN_NAME = 'idle_method';

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE fuel_metrics ADD COLUMN idle_method VARCHAR(50) DEFAULT NULL COMMENT ''Method used to calculate idle: SENSOR_FUEL_RATE, ECU_IDLE_COUNTER, CALCULATED_DELTA, FALLBACK_CONSENSUS''',
    'SELECT ''Column idle_method already exists'' AS message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add idle_mode column if it doesn't exist (pero ya existe según el esquema)
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = @db_name 
  AND TABLE_NAME = @table_name 
  AND COLUMN_NAME = 'idle_mode';

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE fuel_metrics ADD COLUMN idle_mode VARCHAR(50) DEFAULT NULL COMMENT ''Idle classification: OPTIMAL, ACCEPTABLE, HIGH, EXCESSIVE''',
    'SELECT ''Column idle_mode already exists'' AS message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verify the columns were added
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'fuel_copilot'
  AND TABLE_NAME = 'fuel_metrics'
  AND COLUMN_NAME IN ('idle_gph', 'idle_method', 'idle_mode')
ORDER BY ORDINAL_POSITION;

-- Show summary
SELECT 
    CASE 
        WHEN COUNT(*) = 3 THEN '✅ SUCCESS: All 3 idle columns exist'
        WHEN COUNT(*) = 0 THEN '❌ ERROR: No idle columns found'
        ELSE CONCAT('⚠️  WARNING: Only ', COUNT(*), ' of 3 idle columns exist')
    END AS status,
    COUNT(*) as columns_found
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'fuel_copilot'
  AND TABLE_NAME = 'fuel_metrics'
  AND COLUMN_NAME IN ('idle_gph', 'idle_method', 'idle_mode');
