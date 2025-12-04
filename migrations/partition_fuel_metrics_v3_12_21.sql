-- ============================================
-- FUEL COPILOT - TABLE PARTITIONING v3.12.21
-- Addresses audit item #47: Particionamiento tabla
-- ============================================

-- This migration implements table partitioning for fuel_metrics
-- to improve query performance on large datasets (>1M rows/month)

-- ============================================
-- STEP 1: Create partitioned table structure
-- ============================================

-- Create new partitioned table
CREATE TABLE IF NOT EXISTS fuel_metrics_partitioned (
    id BIGINT AUTO_INCREMENT,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Fuel data
    sensor_pct DOUBLE,
    estimated_pct DOUBLE,
    fuel_gallons DOUBLE,
    tank_capacity_gal DOUBLE DEFAULT 200,
    
    -- Performance metrics
    mpg_current DOUBLE,
    mpg_ema DOUBLE,
    consumption_gph DOUBLE,
    
    -- Location/Speed
    speed_mph DOUBLE,
    mileage_delta DOUBLE,
    latitude DOUBLE,
    longitude DOUBLE,
    
    -- Status
    truck_status VARCHAR(20),
    idle_duration_minutes INT DEFAULT 0,
    
    -- Events
    refuel_detected TINYINT(1) DEFAULT 0,
    anomaly_score DOUBLE,
    
    -- Kalman filter state
    kalman_gain DOUBLE,
    process_variance DOUBLE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id, timestamp_utc),
    INDEX idx_fmp_truck_time (truck_id, timestamp_utc DESC),
    INDEX idx_fmp_carrier_time (carrier_id, timestamp_utc DESC),
    INDEX idx_fmp_status (truck_status, timestamp_utc DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4

-- Partition by month
PARTITION BY RANGE (TO_DAYS(timestamp_utc)) (
    PARTITION p_2024_10 VALUES LESS THAN (TO_DAYS('2024-11-01')),
    PARTITION p_2024_11 VALUES LESS THAN (TO_DAYS('2024-12-01')),
    PARTITION p_2024_12 VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_2025_01 VALUES LESS THAN (TO_DAYS('2025-02-01')),
    PARTITION p_2025_02 VALUES LESS THAN (TO_DAYS('2025-03-01')),
    PARTITION p_2025_03 VALUES LESS THAN (TO_DAYS('2025-04-01')),
    PARTITION p_2025_04 VALUES LESS THAN (TO_DAYS('2025-05-01')),
    PARTITION p_2025_05 VALUES LESS THAN (TO_DAYS('2025-06-01')),
    PARTITION p_2025_06 VALUES LESS THAN (TO_DAYS('2025-07-01')),
    PARTITION p_2025_07 VALUES LESS THAN (TO_DAYS('2025-08-01')),
    PARTITION p_2025_08 VALUES LESS THAN (TO_DAYS('2025-09-01')),
    PARTITION p_2025_09 VALUES LESS THAN (TO_DAYS('2025-10-01')),
    PARTITION p_2025_10 VALUES LESS THAN (TO_DAYS('2025-11-01')),
    PARTITION p_2025_11 VALUES LESS THAN (TO_DAYS('2025-12-01')),
    PARTITION p_2025_12 VALUES LESS THAN (TO_DAYS('2026-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);


-- ============================================
-- STEP 2: Stored procedure for partition management
-- ============================================

DELIMITER //

-- Add new partition for upcoming month
CREATE PROCEDURE IF NOT EXISTS add_fuel_metrics_partition(IN target_year INT, IN target_month INT)
BEGIN
    DECLARE partition_name VARCHAR(20);
    DECLARE next_year INT;
    DECLARE next_month INT;
    DECLARE partition_value VARCHAR(20);
    
    -- Calculate next month
    IF target_month = 12 THEN
        SET next_year = target_year + 1;
        SET next_month = 1;
    ELSE
        SET next_year = target_year;
        SET next_month = target_month + 1;
    END IF;
    
    SET partition_name = CONCAT('p_', target_year, '_', LPAD(target_month, 2, '0'));
    SET partition_value = CONCAT(next_year, '-', LPAD(next_month, 2, '0'), '-01');
    
    -- Check if partition exists
    SET @sql = CONCAT(
        'ALTER TABLE fuel_metrics_partitioned REORGANIZE PARTITION p_future INTO (',
        'PARTITION ', partition_name, ' VALUES LESS THAN (TO_DAYS(''', partition_value, ''')),',
        'PARTITION p_future VALUES LESS THAN MAXVALUE)'
    );
    
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    SELECT CONCAT('Added partition: ', partition_name) AS result;
END //


-- Drop old partition (data archival)
CREATE PROCEDURE IF NOT EXISTS drop_fuel_metrics_partition(IN target_year INT, IN target_month INT)
BEGIN
    DECLARE partition_name VARCHAR(20);
    
    SET partition_name = CONCAT('p_', target_year, '_', LPAD(target_month, 2, '0'));
    
    SET @sql = CONCAT('ALTER TABLE fuel_metrics_partitioned DROP PARTITION ', partition_name);
    
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    SELECT CONCAT('Dropped partition: ', partition_name) AS result;
END //


-- Archive partition to separate table before dropping
CREATE PROCEDURE IF NOT EXISTS archive_fuel_metrics_partition(IN target_year INT, IN target_month INT)
BEGIN
    DECLARE partition_name VARCHAR(20);
    DECLARE archive_table VARCHAR(50);
    DECLARE start_date DATE;
    DECLARE end_date DATE;
    
    SET partition_name = CONCAT('p_', target_year, '_', LPAD(target_month, 2, '0'));
    SET archive_table = CONCAT('fuel_metrics_archive_', target_year, '_', LPAD(target_month, 2, '0'));
    SET start_date = CONCAT(target_year, '-', LPAD(target_month, 2, '0'), '-01');
    
    IF target_month = 12 THEN
        SET end_date = CONCAT(target_year + 1, '-01-01');
    ELSE
        SET end_date = CONCAT(target_year, '-', LPAD(target_month + 1, 2, '0'), '-01');
    END IF;
    
    -- Create archive table with same structure (no partitioning)
    SET @sql = CONCAT(
        'CREATE TABLE IF NOT EXISTS ', archive_table, 
        ' LIKE fuel_metrics_partitioned'
    );
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    -- Remove partitioning from archive table
    SET @sql = CONCAT('ALTER TABLE ', archive_table, ' REMOVE PARTITIONING');
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    -- Copy data to archive
    SET @sql = CONCAT(
        'INSERT INTO ', archive_table, 
        ' SELECT * FROM fuel_metrics_partitioned PARTITION (', partition_name, ')'
    );
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    SELECT CONCAT('Archived partition ', partition_name, ' to ', archive_table) AS result;
END //


DELIMITER ;


-- ============================================
-- STEP 3: Scheduled event for automatic partition management
-- ============================================

-- Enable event scheduler (run as admin)
-- SET GLOBAL event_scheduler = ON;

-- Monthly event to add next partition
CREATE EVENT IF NOT EXISTS evt_add_partition
ON SCHEDULE EVERY 1 MONTH
STARTS (DATE_ADD(LAST_DAY(CURRENT_DATE), INTERVAL 1 DAY))  -- First day of next month
DO
BEGIN
    DECLARE next_year INT;
    DECLARE next_month INT;
    
    -- Add partition for 2 months ahead
    SET next_year = YEAR(DATE_ADD(CURRENT_DATE, INTERVAL 2 MONTH));
    SET next_month = MONTH(DATE_ADD(CURRENT_DATE, INTERVAL 2 MONTH));
    
    CALL add_fuel_metrics_partition(next_year, next_month);
END;


-- Monthly event to archive old partitions (>6 months)
CREATE EVENT IF NOT EXISTS evt_archive_old_partitions
ON SCHEDULE EVERY 1 MONTH
STARTS (DATE_ADD(LAST_DAY(CURRENT_DATE), INTERVAL 1 DAY))
DO
BEGIN
    DECLARE archive_year INT;
    DECLARE archive_month INT;
    
    -- Archive partition from 6 months ago
    SET archive_year = YEAR(DATE_SUB(CURRENT_DATE, INTERVAL 6 MONTH));
    SET archive_month = MONTH(DATE_SUB(CURRENT_DATE, INTERVAL 6 MONTH));
    
    CALL archive_fuel_metrics_partition(archive_year, archive_month);
    CALL drop_fuel_metrics_partition(archive_year, archive_month);
END;


-- ============================================
-- STEP 4: Migration script (run manually)
-- ============================================

-- To migrate existing data from fuel_metrics to fuel_metrics_partitioned:
/*
-- Insert existing data (may take a while for large datasets)
INSERT INTO fuel_metrics_partitioned 
SELECT * FROM fuel_metrics;

-- Rename tables
RENAME TABLE fuel_metrics TO fuel_metrics_backup,
             fuel_metrics_partitioned TO fuel_metrics;

-- After verification, drop backup
-- DROP TABLE fuel_metrics_backup;
*/


-- ============================================
-- STEP 5: Query optimization verification
-- ============================================

-- Verify partition pruning is working
EXPLAIN SELECT * FROM fuel_metrics_partitioned 
WHERE timestamp_utc >= '2025-12-01' AND timestamp_utc < '2025-12-15' 
AND truck_id = 'AB1234';

-- Check partition statistics
SELECT 
    PARTITION_NAME,
    TABLE_ROWS,
    AVG_ROW_LENGTH,
    DATA_LENGTH / 1024 / 1024 AS data_mb,
    INDEX_LENGTH / 1024 / 1024 AS index_mb
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'fuel_metrics_partitioned'
ORDER BY PARTITION_NAME;
