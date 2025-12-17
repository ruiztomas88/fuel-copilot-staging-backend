"""
🔧 UNIVERSAL WIALON TO DASHBOARD SENSOR FIX
============================================
Este script actualiza COMPLETAMENTE el sistema para que TODO lo que llega
de Wialon se muestre en el dashboard.

PROBLEMA ORIGINAL:
- Dashboard muestra N/A para sensores que Wialon SÍ reporta
- Múltiples archivos con mapeos diferentes
- Tabla truck_sensors_cache incompleta
- API endpoint no retorna todos los campos

SOLUCIÓN:
1. Agregar campos faltantes a truck_sensors_cache
2. Actualizar wialon_full_sync_service.py con mapeo correcto
3. Actualizar API /trucks/{id}/sensors para retornar TODO
4. Documentar mapeo completo

Author: Fuel Analytics Team
Date: December 17, 2025
"""

# =============================================================================
# MAPEO OFICIAL: Wialon Parameter → truck_sensors_cache Column
# =============================================================================

SENSOR_MAPPING = {
    # ========== MOTOR / ENGINE ==========
    "oil_press": "oil_pressure_psi",
    "oil_temp": "oil_temp_f",
    "coolant_temp": "coolant_temp_f",
    "rpm": "rpm",
    "throttle_pos": "throttle_position_pct",
    "intake_manifold_temp": "intake_temp_f",
    "engine_hours": "engine_hours",
    "idle_hours": "idle_hours",
    # ========== TURBO ==========
    "turbo_press": "turbo_pressure_psi",
    # ========== DEF / EMISSIONS ==========
    "def_level": "def_level_pct",
    "def_temp": "def_temp_f",
    "def_quality": "def_quality",
    # ========== FUEL ==========
    "fuel_rate": "fuel_rate_gph",
    "fuel_press": "fuel_pressure_psi",
    "fuel_temp": "fuel_temp_f",
    # ========== DPF (Diesel Particulate Filter) ==========
    "dpf_diff_press": "dpf_pressure_psi",
    "dpf_soot_level": "dpf_soot_pct",
    "dpf_ash_level": "dpf_ash_pct",
    "dpf_status": "dpf_status",
    # ========== EGR (Exhaust Gas Recirculation) ==========
    "egr_valve_pos": "egr_position_pct",
    "egr_temp": "egr_temp_f",
    # ========== ELECTRICAL ==========
    "battery_volt": "voltage",
    "alternator_status": "alternator_status",
    # ========== ENVIRONMENT ==========
    "ambient_air_temp": "ambient_temp_f",
    "barometric_press": "barometric_pressure_inhg",
    # ========== GPS ==========
    "speed": "speed_mph",
    "odometer": "odometer_mi",  # ⚠️ CRÍTICO - estaba faltando!
    "lat": "latitude",
    "lon": "longitude",
    "altitude": "altitude_ft",
    "direction": "heading_deg",
    # ========== TRANSMISSION ==========
    "transmission_oil_temp": "transmission_temp_f",
    "transmission_oil_press": "transmission_pressure_psi",
    "trans_gear": "gear",
}

# =============================================================================
# SQL PARA AGREGAR CAMPOS FALTANTES
# =============================================================================

ADD_COLUMNS_SQL = """
-- Critical: Odometer
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS odometer_mi DECIMAL(12,2) COMMENT 'Odometer miles';

-- DEF System
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS def_temp_f DECIMAL(10,2) COMMENT 'DEF temperature F';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS def_quality DECIMAL(10,2) COMMENT 'DEF quality %';

-- Engine Performance
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS throttle_position_pct DECIMAL(10,2) COMMENT 'Throttle position %';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS turbo_pressure_psi DECIMAL(10,2) COMMENT 'Turbo boost pressure PSI';

-- Fuel System
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS fuel_pressure_psi DECIMAL(10,2) COMMENT 'Fuel rail pressure PSI';

-- DPF (Diesel Particulate Filter)
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_pressure_psi DECIMAL(10,2) COMMENT 'DPF differential pressure PSI';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_soot_pct DECIMAL(10,2) COMMENT 'DPF soot load %';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_ash_pct DECIMAL(10,2) COMMENT 'DPF ash load %';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_status VARCHAR(20) COMMENT 'DPF status';

-- EGR (Exhaust Gas Recirculation)
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS egr_position_pct DECIMAL(10,2) COMMENT 'EGR valve position %';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS egr_temp_f DECIMAL(10,2) COMMENT 'EGR temperature F';

-- Electrical
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS alternator_status VARCHAR(20) COMMENT 'Alternator status';

-- Transmission
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS transmission_temp_f DECIMAL(10,2) COMMENT 'Transmission oil temp F';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS transmission_pressure_psi DECIMAL(10,2) COMMENT 'Transmission pressure PSI';

-- GPS
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS heading_deg DECIMAL(10,2) COMMENT 'GPS heading degrees';
"""

# =============================================================================
# QUERY ACTUALIZADO PARA wialon_full_sync_service.py
# =============================================================================

WIALON_SELECT_QUERY = """
SELECT 
    unit,
    MAX(CASE WHEN parameter = 'oil_press' THEN value END) as oil_pressure_psi,
    MAX(CASE WHEN parameter = 'oil_temp' THEN value END) as oil_temp_f,
    MAX(CASE WHEN parameter = 'coolant_temp' THEN value END) as coolant_temp_f,
    MAX(CASE WHEN parameter = 'def_level' THEN value END) as def_level_pct,
    MAX(CASE WHEN parameter = 'def_temp' THEN value END) as def_temp_f,
    MAX(CASE WHEN parameter = 'def_quality' THEN value END) as def_quality,
    MAX(CASE WHEN parameter = 'rpm' THEN value END) as rpm,
    MAX(CASE WHEN parameter = 'throttle_pos' THEN value END) as throttle_position_pct,
    MAX(CASE WHEN parameter = 'turbo_press' THEN value END) as turbo_pressure_psi,
    MAX(CASE WHEN parameter = 'intake_manifold_temp' THEN value END) as intake_temp_f,
    MAX(CASE WHEN parameter = 'fuel_rate' THEN value END) as fuel_rate_gph,
    MAX(CASE WHEN parameter = 'fuel_press' THEN value END) as fuel_pressure_psi,
    MAX(CASE WHEN parameter = 'fuel_temp' THEN value END) as fuel_temp_f,
    MAX(CASE WHEN parameter = 'dpf_diff_press' THEN value END) as dpf_pressure_psi,
    MAX(CASE WHEN parameter = 'dpf_soot_level' THEN value END) as dpf_soot_pct,
    MAX(CASE WHEN parameter = 'dpf_ash_level' THEN value END) as dpf_ash_pct,
    MAX(CASE WHEN parameter = 'dpf_status' THEN value END) as dpf_status,
    MAX(CASE WHEN parameter = 'egr_valve_pos' THEN value END) as egr_position_pct,
    MAX(CASE WHEN parameter = 'egr_temp' THEN value END) as egr_temp_f,
    MAX(CASE WHEN parameter = 'ambient_air_temp' THEN value END) as ambient_temp_f,
    MAX(CASE WHEN parameter = 'barometric_press' THEN value END) as barometric_pressure_inhg,
    MAX(CASE WHEN parameter = 'battery_volt' THEN value END) as voltage,
    MAX(CASE WHEN parameter = 'alternator_status' THEN value END) as alternator_status,
    MAX(CASE WHEN parameter = 'speed' THEN value END) as speed_mph,
    MAX(CASE WHEN parameter = 'odometer' THEN value END) as odometer_mi,
    MAX(CASE WHEN parameter = 'engine_hours' THEN value END) as engine_hours,
    MAX(CASE WHEN parameter = 'idle_hours' THEN value END) as idle_hours,
    MAX(CASE WHEN parameter = 'lat' THEN value END) as latitude,
    MAX(CASE WHEN parameter = 'lon' THEN value END) as longitude,
    MAX(CASE WHEN parameter = 'altitude' THEN value END) as altitude_ft,
    MAX(CASE WHEN parameter = 'direction' THEN value END) as heading_deg,
    MAX(CASE WHEN parameter = 'transmission_oil_temp' THEN value END) as transmission_temp_f,
    MAX(CASE WHEN parameter = 'transmission_oil_press' THEN value END) as transmission_pressure_psi,
    MAX(CASE WHEN parameter = 'trans_gear' THEN value END) as gear,
    MAX(timestamp) as last_update
FROM sensors
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY unit
"""

# =============================================================================
# LISTA COMPLETA DE CAMPOS PARA API ENDPOINT
# =============================================================================

API_RESPONSE_FIELDS = [
    # IDs and metadata
    "truck_id",
    "timestamp",
    "data_available",
    "data_age_seconds",
    # Oil System
    "oil_pressure_psi",
    "oil_temp_f",
    "oil_level_pct",
    # DEF System
    "def_level_pct",
    "def_temp_f",
    "def_quality",
    # Engine
    "engine_load_pct",
    "rpm",
    "coolant_temp_f",
    "coolant_level_pct",
    "throttle_position_pct",
    # Turbo
    "turbo_pressure_psi",
    # Transmission
    "gear",
    "transmission_temp_f",
    "transmission_pressure_psi",
    "brake_active",
    # Air Intake
    "intake_pressure_bar",
    "intake_temp_f",
    "intercooler_temp_f",
    # Fuel
    "fuel_temp_f",
    "fuel_level_pct",
    "fuel_rate_gph",
    "fuel_pressure_psi",
    # DPF
    "dpf_pressure_psi",
    "dpf_soot_pct",
    "dpf_ash_pct",
    "dpf_status",
    # EGR
    "egr_position_pct",
    "egr_temp_f",
    # Environmental
    "ambient_temp_f",
    "barometric_pressure_inhg",
    # Electrical
    "voltage",
    "backup_voltage",
    "alternator_status",
    # Operational Counters
    "engine_hours",
    "idle_hours",
    "pto_hours",
    "total_idle_fuel_gal",
    "total_fuel_used_gal",
    "odometer_mi",  # ⚠️ CRÍTICO - agregar!
    # DTC
    "dtc_count",
    "dtc_code",
    # GPS
    "latitude",
    "longitude",
    "speed_mph",
    "altitude_ft",
    "heading_deg",  # ⚠️ NUEVO
]

# =============================================================================
# DEPLOYMENT CHECKLIST
# =============================================================================

DEPLOYMENT_STEPS = """
📋 DEPLOYMENT CHECKLIST - Wialon Sensor Fix
============================================

LOCAL (Dev Machine):
-------------------
☐ 1. Run migration: python migrations/add_all_missing_sensors.py
☐ 2. Update wialon_full_sync_service.py with new SELECT query
☐ 3. Update wialon_full_sync_service.py INSERT to include new fields
☐ 4. Update api_v2.py /trucks/{id}/sensors endpoint
☐ 5. Test locally
☐ 6. Commit and push to GitHub

VM (Production):
---------------
☐ 7. SSH to VM: ssh tomasruiz@20.127.200.135
☐ 8. Pull latest: cd /var/fuel-analytics-backend && git pull
☐ 9. Run migration: python migrations/add_all_missing_sensors.py
☐ 10. Stop old service: sudo systemctl stop sensor_cache_updater (if exists)
☐ 11. Restart sync: sudo systemctl restart wialon_full_sync
☐ 12. Check logs: tail -f /var/log/wialon_sync.log
☐ 13. Wait 30 seconds for first sync

VERIFICATION:
------------
☐ 14. Open dashboard
☐ 15. Check 3 random trucks
☐ 16. Verify: odometer shows value (not N/A)
☐ 17. Verify: barometer shows value
☐ 18. Verify: All new sensors visible
☐ 19. Verify: DTC descriptions showing (from previous fix)

ROLLBACK (if needed):
--------------------
- sudo systemctl restart wialon_full_sync
- Check logs for errors
- Revert to previous commit if critical failure
"""

if __name__ == "__main__":
    print(__doc__)
    print("\n" + "=" * 70)
    print("SENSOR MAPPING")
    print("=" * 70)
    print("\nWialon Parameter → truck_sensors_cache Column:")
    for wialon_param, db_column in sorted(SENSOR_MAPPING.items()):
        print(f"  {wialon_param:30} → {db_column}")

    print("\n" + "=" * 70)
    print("DEPLOYMENT STEPS")
    print("=" * 70)
    print(DEPLOYMENT_STEPS)
