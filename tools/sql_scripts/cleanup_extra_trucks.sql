-- ============================================================================
-- CLEANUP: Remove trucks from units_map that are not in tanks.yaml
-- Generated: December 10, 2025
-- ============================================================================
-- 
-- This script removes 88 trucks that were added by AI but are NOT defined
-- in tanks.yaml. Our program should only monitor trucks in tanks.yaml.
--
-- Run this on the VM with: mysql -u root -p wialon_collect < cleanup_extra_trucks.sql
-- ============================================================================

-- First, verify the count before deletion
SELECT COUNT(*) as total_before FROM units_map;

-- Delete trucks NOT in tanks.yaml (88 trucks)
DELETE FROM units_map WHERE beyondId IN (
    'AG8915', 'AQ7161', 'BM0674', 'CH5291', 'CL0639', 'CR8850', 'DC8258', 'DJ6858',
    'DQ7596', 'DS5425', 'DZ0459', 'EB5420', 'EC9283', 'EH5291', 'EN8870', 'ER8832',
    'ER9588', 'FR7757', 'FS9409', 'GB0648', 'GC0913', 'GC1268', 'GC6621', 'GP2228',
    'GS5030', 'HC4965', 'HC9729', 'HS8148', 'IB9790', 'JA3725', 'JB6554', 'JE8853',
    'JG2710', 'JG5275', 'JG7683', 'JG9925', 'JL2974', 'JM3714', 'JP5290', 'JR1524',
    'JR4821', 'JR6913', 'JT2141', 'JT2876', 'JV1422', 'LG0118', 'LG5601', 'LH1141',
    'LL5064', 'LO7815', 'LT3656', 'MG1371', 'MG2507', 'MG5345', 'MG6835', 'ML4429',
    'MM4560', 'MM5000', 'MM8185', 'MP8605', 'MR2714', 'NG1052', 'NG6283', 'OA2474',
    'OC5631', 'OM7769', 'OP9923', 'PV8526', 'RC2470', 'RD9583', 'RG9130', 'RL7973',
    'RR0495', 'RR6135', 'SA4300V', 'SA6114V', 'SA8468V', 'ST3216', 'Unit-303',
    'WC5101', 'WR7867', 'WR7895', 'YG5998', 'YG7957', 'YR2987', 'YR4424', 'YS3930',
    'YT9458'
);

-- Verify the count after deletion (should be 41)
SELECT COUNT(*) as total_after FROM units_map;

-- Show remaining trucks (should match tanks.yaml)
SELECT beyondId FROM units_map ORDER BY beyondId;
