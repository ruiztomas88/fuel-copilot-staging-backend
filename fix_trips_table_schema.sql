-- ========================================================================
-- SCRIPT DE VALIDACIÓN Y CORRECCIÓN DE TABLA trips
-- ========================================================================
-- Este script verifica y agrega columnas faltantes en la tabla trips
-- de la base de datos local (fuel_copilot)
-- ========================================================================

USE fuel_copilot;

-- Verificar si la tabla trips existe
SELECT 'Verificando tabla trips...' as status;

-- Agregar columnas faltantes si no existen
ALTER TABLE trips ADD COLUMN IF NOT EXISTS driver VARCHAR(100) COMMENT 'Nombre del conductor';
ALTER TABLE trips ADD COLUMN IF NOT EXISTS harsh_accel_count INT DEFAULT 0 COMMENT 'Conteo de aceleraciones bruscas';
ALTER TABLE trips ADD COLUMN IF NOT EXISTS harsh_brake_count INT DEFAULT 0 COMMENT 'Conteo de frenadas bruscas';
ALTER TABLE trips ADD COLUMN IF NOT EXISTS speeding_count INT DEFAULT 0 COMMENT 'Conteo de excesos de velocidad';
ALTER TABLE trips ADD COLUMN IF NOT EXISTS duration_hours DECIMAL(10,2) COMMENT 'Duración del viaje en horas';

-- Verificar estructura final
SELECT 'Estructura de la tabla trips:' as status;
DESCRIBE trips;

-- Mostrar conteo de registros
SELECT 
    COUNT(*) as total_trips,
    COUNT(driver) as trips_con_conductor,
    SUM(harsh_accel_count) as total_aceleraciones_bruscas,
    SUM(harsh_brake_count) as total_frenadas_bruscas,
    SUM(speeding_count) as total_excesos_velocidad
FROM trips;

SELECT '✅ Script completado' as status;
