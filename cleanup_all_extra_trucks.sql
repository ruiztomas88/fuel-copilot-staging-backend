-- ============================================================================
-- CLEANUP: Remove trucks from units_map that are not in tanks.yaml
-- Generated: December 10, 2025
-- ============================================================================
--
-- This script removes all trucks that are NOT defined in tanks.yaml.
-- Our program should only monitor trucks in tanks.yaml.
--
-- Run this on the database: mysql -u fuel_admin -p fuel_copilot < cleanup_all_extra_trucks.sql
-- ============================================================================

-- First, verify the count before deletion
SELECT COUNT(*) as total_before FROM units_map;

-- Get the list of trucks to keep from tanks.yaml
-- Trucks to keep: VD3579, JC1282, JC9352, NQ6975, GP9677, JB8004, FM2416, FM3679, FM9838, JB6858, JP3281, JR7099, RA9250, RH1522, RR1272, BV6395, CO0681, CS8087, DR6664, DO9356, DO9693, FS7166, MA8159, MO0195, PC1280, RD5229, RR3094, RT9127, SG5760, YM6023, MJ9547, FM3363, GC9751, LV1422, LC6799, RC6625, FF7702, OG2033, OS3717, EM8514, MR7679

-- Delete trucks NOT in tanks.yaml
DELETE FROM units_map WHERE beyondId NOT IN (
    'VD3579', 'JC1282', 'JC9352', 'NQ6975', 'GP9677', 'JB8004', 'FM2416', 'FM3679', 'FM9838', 'JB6858', 'JP3281', 'JR7099', 'RA9250', 'RH1522', 'RR1272', 'BV6395', 'CO0681', 'CS8087', 'DR6664', 'DO9356', 'DO9693', 'FS7166', 'MA8159', 'MO0195', 'PC1280', 'RD5229', 'RR3094', 'RT9127', 'SG5760', 'YM6023', 'MJ9547', 'FM3363', 'GC9751', 'LV1422', 'LC6799', 'RC6625', 'FF7702', 'OG2033', 'OS3717', 'EM8514', 'MR7679'
);

-- Verify the count after deletion (should be 41)
SELECT COUNT(*) as total_after FROM units_map;

-- Show remaining trucks (should match tanks.yaml)
SELECT beyondId FROM units_map ORDER BY beyondId;