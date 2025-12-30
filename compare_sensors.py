#!/usr/bin/env python3
"""
Comparar sensores en TruckSensorData vs sensores disponibles en Wialon
Identificar qué falta EXTRAER de la base de datos
"""

# Sensores YA DEFINIDOS en TruckSensorData (wialon_reader.py)
SENSORS_IN_CODE = {
    # Basic
    "fuel_lvl",
    "speed",
    "rpm",
    "odometer",
    "fuel_rate",
    "coolant_temp",
    "hdop",
    "altitude",
    "pwr_ext",
    "oil_press",
    "engine_hours",
    # Advanced
    "total_fuel_used",
    "total_idle_fuel",
    "engine_load",
    "ambient_temp",
    "oil_temp",
    "def_level",
    "intake_air_temp",
    # DTC & GPS
    "dtc",
    "j1939_spn",
    "j1939_fmi",
    "idle_hours",
    "sats",
    "pwr_int",
    "course",
    # Driver behavior
    "fuel_economy",
    "gear",
    "barometer",
    # Temperatures
    "fuel_temp",
    "intercooler_temp",
    "turbo_temp",
    "trans_temp",
    # Pressures
    "intake_press",
    "boost",
    # Counters
    "pto_hours",
    # Brake
    "brake_app_press",
    "brake_primary_press",
    "brake_secondary_press",
    "brake_switch",
    "parking_brake",
    "abs_status",
    # Misc
    "rpm_hi_res",
    "seatbelt",
    "vin",
    "harsh_accel",
    "harsh_brake",
    "harsh_corner",
    "rssi",
    "coolant_level",
    "oil_level",
    "gps_locked",
    "battery",
    "roaming",
    "event_id",
    "bus",
    "mode",
}

# Mapeo de sensores Wialon a nuestros nombres
WIALON_TO_CODE = {
    # ALTA PRIORIDAD
    "odom": "odometer",  # ❌ NO SE EXTRAE de Wialon DB
    "gear": "gear",  # ❌ NO SE EXTRAE
    "idle_hours": "idle_hours",  # ❌ NO SE EXTRAE
    "total_idle_fuel": "total_idle_fuel",  # ❌ NO SE EXTRAE
    "dtc": "dtc",  # ✅ YA SE EXTRAE
    "cool_lvl": "coolant_level",  # ❌ NO SE EXTRAE
    # MEDIA PRIORIDAD
    "obd_speed": None,  # ❌ NO EXISTE en TruckSensorData
    "fuel_economy": "fuel_economy",  # ❌ NO SE EXTRAE
    "brake_switch": "brake_switch",  # ❌ NO SE EXTRAE
    "actual_retarder": None,  # ❌ NO EXISTE en TruckSensorData
    "pto_hours": "pto_hours",  # ❌ NO SE EXTRAE
    "trams_t": "trans_temp",  # ❌ NO SE EXTRAE
    # BAJA PRIORIDAD
    "j1939_fmi": "j1939_fmi",  # ❌ NO SE EXTRAE
    "j1939_spn": "j1939_spn",  # ❌ NO SE EXTRAE
    "oil_level": "oil_level",  # ❌ NO SE EXTRAE
    "fuel_t": "fuel_temp",  # ❌ NO SE EXTRAE
    "intrclr_t": "intercooler_temp",  # ❌ NO SE EXTRAE
}

print("=" * 80)
print("ANÁLISIS: SENSORES DEFINIDOS vs SENSORES EXTRAÍDOS")
print("=" * 80)

print(f"\n✅ Sensores en TruckSensorData: {len(SENSORS_IN_CODE)}")
print(f"🔍 Sensores críticos mapeados: {len(WIALON_TO_CODE)}")

print("\n" + "=" * 80)
print("🔴 ALTA PRIORIDAD - AGREGAR A EXTRACCIÓN:")
print("=" * 80)
high_priority = [
    ("odom", "odometer", 30, 147, "CRÍTICO - MPG accuracy"),
    ("gear", "gear", 20, 36, "Driver behavior, shift analysis"),
    ("idle_hours", "idle_hours", 25, 131, "Idle time tracking"),
    ("total_idle_fuel", "total_idle_fuel", 41, 45, "Idle cost calculation"),
    ("cool_lvl", "coolant_level", 10, 138, "Coolant monitoring"),
]

for wialon_param, code_field, sensor_id, trucks, benefit in high_priority:
    status = (
        "✅ DEFINIDO"
        if code_field and code_field in SENSORS_IN_CODE
        else "❌ FALTA DEFINIR"
    )
    print(
        f"{status} | {wialon_param:20} → {code_field:20} | ID {sensor_id:3} | {trucks:3} trucks"
    )
    print(f"{'':12}  Beneficio: {benefit}")

print("\n" + "=" * 80)
print("🟡 MEDIA PRIORIDAD - AGREGAR A EXTRACCIÓN:")
print("=" * 80)
medium_priority = [
    ("obd_speed", "obd_speed", 16, 147, "Speed validation GPS vs ECU"),
    ("fuel_economy", "fuel_economy", 4, 27, "ECU MPG validation"),
    ("brake_switch", "brake_switch", 45, 32, "Brake usage analysis"),
    ("actual_retarder", "engine_brake", 52, 30, "Engine brake usage"),
    ("pto_hours", "pto_hours", 35, 21, "PTO tracking"),
    ("trams_t", "trans_temp", 50, 22, "Transmission temp"),
]

need_to_add = []
for wialon_param, code_field, sensor_id, trucks, benefit in medium_priority:
    status = (
        "✅ DEFINIDO"
        if code_field and code_field in SENSORS_IN_CODE
        else "❌ FALTA DEFINIR"
    )
    print(
        f"{status} | {wialon_param:20} → {code_field:20} | ID {sensor_id:3} | {trucks:3} trucks"
    )
    print(f"{'':12}  Beneficio: {benefit}")
    if not code_field or code_field not in SENSORS_IN_CODE:
        need_to_add.append((wialon_param, code_field, sensor_id))

print("\n" + "=" * 80)
print("🟢 BAJA PRIORIDAD - AGREGAR A EXTRACCIÓN:")
print("=" * 80)
low_priority = [
    ("j1939_fmi", "j1939_fmi", 44, 27, "Fault Mode Indicator"),
    ("j1939_spn", "j1939_spn", 51, 25, "Suspect Parameter Number"),
    ("oil_level", "oil_level", 31, 40, "Oil level monitoring"),
    ("fuel_t", "fuel_temp", 46, 28, "Fuel temperature"),
    ("intrclr_t", "intercooler_temp", 43, 28, "Intercooler temp"),
]

for wialon_param, code_field, sensor_id, trucks, benefit in low_priority:
    status = "✅ DEFINIDO" if code_field in SENSORS_IN_CODE else "❌ FALTA DEFINIR"
    print(
        f"{status} | {wialon_param:20} → {code_field:20} | ID {sensor_id:3} | {trucks:3} trucks"
    )
    print(f"{'':12}  Beneficio: {benefit}")

print("\n" + "=" * 80)
print("📋 RESUMEN DE ACCIONES NECESARIAS:")
print("=" * 80)

print(
    """
1️⃣  AGREGAR CAMPOS A TruckSensorData:
   - obd_speed: Optional[float] = None  # OBD speed (mph)
   - engine_brake: Optional[int] = None  # Engine brake/retarder status

2️⃣  ACTUALIZAR EXTRACCIÓN en wialon_reader.py:
   Agregar a la query SQL que lee de Wialon los siguientes sensor_ids:
   
   ALTA PRIORIDAD:
   - ID 30: odom → odometer
   - ID 20: gear → gear
   - ID 25: idle_hours → idle_hours
   - ID 41: total_idle_fuel → total_idle_fuel
   - ID 10: cool_lvl → coolant_level
   
   MEDIA PRIORIDAD:
   - ID 16: obd_speed → obd_speed (NUEVO CAMPO)
   - ID 4: fuel_economy → fuel_economy
   - ID 45: brake_switch → brake_switch
   - ID 52: actual_retarder → engine_brake (NUEVO CAMPO)
   - ID 35: pto_hours → pto_hours
   - ID 50: trams_t → trans_temp
   
   BAJA PRIORIDAD:
   - ID 44/48: j1939_fmi → j1939_fmi
   - ID 51: j1939_spn → j1939_spn
   - ID 31: oil_level → oil_level
   - ID 46: fuel_t → fuel_temp
   - ID 43: intrclr_t → intercooler_temp

3️⃣  UBICACIÓN DEL CÓDIGO A MODIFICAR:
   - wialon_reader.py línea ~136: class TruckSensorData
   - wialon_reader.py línea ~400-700: método que hace query a Wialon DB
   
TOTAL SENSORES A EXTRAER: 17 sensores (5 alta + 6 media + 6 baja)
CAMPOS NUEVOS A AGREGAR: 2 (obd_speed, engine_brake)
"""
)
