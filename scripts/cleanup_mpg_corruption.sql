-- ═══════════════════════════════════════════════════════════════════════════════
-- FIX P0: DATABASE CORRUPTION - MPG VALUES
-- Fecha: 23 Diciembre 2025
-- Propósito: Limpiar valores MPG inflados/corruptos según auditoría
-- ═══════════════════════════════════════════════════════════════════════════════

-- IMPORTANTE: Este script limpia datos corruptos detectados en la auditoría
-- Los valores NULL se recalcularán automáticamente con los nuevos datos de Wialon

USE fuel_copilot;

-- PASO 1: Ver estado actual ANTES de limpiar
-- ═══════════════════════════════════════════════════════════════════════════════
SELECT '═══ ESTADO ANTES DE LIMPIAR ═══' as status;

SELECT 
    COUNT(*) as total_records,
    SUM(CASE WHEN mpg_current IS NULL THEN 1 ELSE 0 END) as null_mpg,
    SUM(CASE WHEN mpg_current > 8.5 THEN 1 ELSE 0 END) as inflated_mpg_above_8_5,
    SUM(CASE WHEN mpg_current < 2.5 AND mpg_current IS NOT NULL THEN 1 ELSE 0 END) as too_low_mpg_below_2_5,
    SUM(CASE WHEN mpg_current = 7.8 THEN 1 ELSE 0 END) as capped_at_7_8,
    SUM(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN 1 ELSE 0 END) as valid_mpg,
    ROUND(AVG(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN mpg_current END), 2) as avg_valid_mpg,
    ROUND(MIN(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN mpg_current END), 2) as min_valid_mpg,
    ROUND(MAX(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN mpg_current END), 2) as max_valid_mpg
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY);

-- PASO 2: Mostrar ejemplos de datos corruptos
-- ═══════════════════════════════════════════════════════════════════════════════
SELECT '═══ EJEMPLOS DE DATOS CORRUPTOS ═══' as status;

SELECT 
    truck_id,
    timestamp_utc,
    mpg_current,
    estimated_gallons,
    odometer_mi,
    speed_mph,
    truck_status,
    CASE 
        WHEN mpg_current > 8.5 THEN 'INFLADO (>8.5)'
        WHEN mpg_current < 2.5 THEN 'DEMASIADO BAJO (<2.5)'
        WHEN mpg_current = 7.8 THEN 'CAPEADO A 7.8 (artefacto)'
    END as tipo_corrupcion
FROM fuel_metrics
WHERE mpg_current > 8.5 
   OR mpg_current < 2.5 
   OR mpg_current = 7.8
ORDER BY mpg_current DESC
LIMIT 20;

-- PASO 3: BACKUP de valores que se van a modificar (OPCIONAL pero recomendado)
-- ═══════════════════════════════════════════════════════════════════════════════
-- Descomenta si quieres hacer backup:
/*
CREATE TABLE IF NOT EXISTS fuel_metrics_mpg_backup_20251223 AS
SELECT id, truck_id, timestamp_utc, mpg_current, estimated_gallons, odometer_mi
FROM fuel_metrics
WHERE mpg_current > 8.5 OR mpg_current < 2.5 OR mpg_current = 7.8;

SELECT CONCAT('Backup creado: ', COUNT(*), ' registros') as backup_status
FROM fuel_metrics_mpg_backup_20251223;
*/

-- PASO 4: LIMPIAR MPG inflados (>8.5 MPG - físicamente imposible para Class 8)
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE fuel_metrics 
SET mpg_current = NULL 
WHERE mpg_current > 8.5;

SELECT CONCAT('✅ Limpiados MPG > 8.5: ', ROW_COUNT(), ' registros') as fix_status;

-- PASO 5: LIMPIAR MPG demasiado bajos (<2.5 MPG - indica error de datos)
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE fuel_metrics 
SET mpg_current = NULL 
WHERE mpg_current < 2.5 AND mpg_current IS NOT NULL;

SELECT CONCAT('✅ Limpiados MPG < 2.5: ', ROW_COUNT(), ' registros') as fix_status;

-- PASO 6: LIMPIAR valores exactos 7.8 (artefacto del cleanup script anterior)
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE fuel_metrics 
SET mpg_current = NULL 
WHERE mpg_current = 7.8;

SELECT CONCAT('✅ Limpiados MPG = 7.8: ', ROW_COUNT(), ' registros') as fix_status;

-- PASO 7: LIMPIAR truck_sensors_cache también
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE truck_sensors_cache 
SET mpg_current = NULL 
WHERE mpg_current > 8.5 
   OR mpg_current < 2.5
   OR mpg_current = 7.8;

SELECT CONCAT('✅ Limpiados truck_sensors_cache: ', ROW_COUNT(), ' registros') as fix_status;

-- PASO 8: VERIFICAR limpieza
-- ═══════════════════════════════════════════════════════════════════════════════
SELECT '═══ ESTADO DESPUÉS DE LIMPIAR ═══' as status;

SELECT 
    COUNT(*) as total_records,
    SUM(CASE WHEN mpg_current IS NULL THEN 1 ELSE 0 END) as null_mpg,
    SUM(CASE WHEN mpg_current > 8.5 THEN 1 ELSE 0 END) as inflated_mpg,
    SUM(CASE WHEN mpg_current < 2.5 AND mpg_current IS NOT NULL THEN 1 ELSE 0 END) as too_low_mpg,
    SUM(CASE WHEN mpg_current = 7.8 THEN 1 ELSE 0 END) as capped_at_7_8,
    SUM(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN 1 ELSE 0 END) as valid_mpg,
    ROUND(AVG(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN mpg_current END), 2) as avg_valid_mpg,
    ROUND(MIN(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN mpg_current END), 2) as min_valid_mpg,
    ROUND(MAX(CASE WHEN mpg_current BETWEEN 2.5 AND 8.5 THEN mpg_current END), 2) as max_valid_mpg
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY);

-- Verificación crítica: No debería haber MPG fuera de rango
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN '✅ PASS: No hay MPG corruptos'
        ELSE CONCAT('❌ FAIL: Aún hay ', COUNT(*), ' MPG corruptos')
    END as verification_status
FROM fuel_metrics
WHERE mpg_current > 8.5 OR mpg_current < 2.5;

-- PASO 9: Mostrar distribución de MPG válidos por truck
-- ═══════════════════════════════════════════════════════════════════════════════
SELECT '═══ DISTRIBUCIÓN MPG POR TRUCK (últimos 7 días) ═══' as status;

SELECT 
    truck_id,
    COUNT(*) as records,
    ROUND(AVG(mpg_current), 2) as avg_mpg,
    ROUND(MIN(mpg_current), 2) as min_mpg,
    ROUND(MAX(mpg_current), 2) as max_mpg,
    ROUND(STDDEV(mpg_current), 2) as std_dev
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND mpg_current BETWEEN 2.5 AND 8.5
GROUP BY truck_id
ORDER BY avg_mpg DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- NOTAS FINALES:
-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. Los valores NULL se recalcularán automáticamente con nuevos datos de Wialon
-- 2. El MPG engine ahora tiene:
--    - min_fuel_gal aumentado de 0.75 a 1.5 (reduce varianza)
--    - Clamping post-EMA para garantizar max_mpg = 8.2
-- 3. Wialon config fijado: breadcrumbs (60s) → Report B con Total Fuel Used
-- 4. Valores válidos esperados: 4.0 - 7.5 MPG para Class 8 cargados
-- 5. Este script puede ejecutarse múltiples veces de forma segura (idempotente)
-- ═══════════════════════════════════════════════════════════════════════════════
