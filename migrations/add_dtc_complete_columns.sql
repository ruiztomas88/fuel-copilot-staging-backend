-- ============================================
-- Migration: Add DTC Complete System Columns
-- Author: Fuel Copilot Team
-- Date: December 26, 2025
-- Version: DTC v1.0.0
-- ============================================

USE fuel_copilot_local;

-- Add new columns to dtc_events table for complete DTC system
-- Note: MySQL doesn't support IF NOT EXISTS in ALTER TABLE, so we'll handle errors gracefully

-- Check if columns exist first, then add them one by one
SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'component');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN component VARCHAR(100) COMMENT "Component name (from SPN)"', 'SELECT "Column component already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'category');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN category VARCHAR(50) COMMENT "DTC category: Engine, Fuel, Electrical, etc."', 'SELECT "Column category already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'is_critical');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN is_critical BOOLEAN DEFAULT FALSE COMMENT "True if severity is CRITICAL"', 'SELECT "Column is_critical already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'action_required');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN action_required TEXT COMMENT "Action required based on severity"', 'SELECT "Column action_required already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'spn_explanation');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN spn_explanation TEXT COMMENT "Detailed SPN explanation (Spanish)"', 'SELECT "Column spn_explanation already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'fmi_explanation');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN fmi_explanation TEXT COMMENT "Detailed FMI explanation (Spanish)"', 'SELECT "Column fmi_explanation already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'full_description');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN full_description TEXT COMMENT "Combined SPN + FMI description"', 'SELECT "Column full_description already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'status');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN status VARCHAR(20) DEFAULT "NEW" COMMENT "Status: NEW, ACKNOWLEDGED, RESOLVED"', 'SELECT "Column status already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'resolved_at');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN resolved_at DATETIME NULL COMMENT "When the DTC was resolved"', 'SELECT "Column resolved_at already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

SET @exist := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'fuel_copilot_local' AND TABLE_NAME = 'dtc_events' AND COLUMN_NAME = 'resolved_by');
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE dtc_events ADD COLUMN resolved_by VARCHAR(100) NULL COMMENT "Who resolved the DTC"', 'SELECT "Column resolved_by already exists" as Info');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;

-- Add indexes (these will fail silently if they exist)
CREATE INDEX IF NOT EXISTS idx_critical_dtc ON dtc_events(is_critical, resolved_at);
CREATE INDEX IF NOT EXISTS idx_category_dtc ON dtc_events(category);

-- Show updated structure
DESCRIBE dtc_events;

SELECT '✅ Migration complete: DTC Complete System columns added' as status;
