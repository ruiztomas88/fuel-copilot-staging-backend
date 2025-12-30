#!/usr/bin/env python3
"""
Comparar sensores disponibles en Wialon vs sensores que estamos usando
Identificar sensores útiles que NO estamos extrayendo
"""
import pymysql

# Sensores que ACTUALMENTE extraemos en nuestro código
CURRENT_SENSORS = {
    "speed",
    "rpm",
    "fuel_lvl",
    "fuel_rate",
    "odometer",
    "altitude",
    "latitude",
    "longitude",
    "engine_hours",
    "hdop",
    "coolant_temp",
    "total_fuel_used",
    "pwr_ext",
    "engine_load",
    "oil_press",
    "oil_temp",
    "def_level",
    "intake_air_temp",
    "ambient_temp",
    "trans_temp",
    "fuel_temp",
    "intercooler_temp",
    "intake_press",
}

# Mapeo de parámetros Wialon a nuestros nombres
WIALON_PARAM_MAP = {
    "speed": "GPS Speed",
    "rpm": "RPM",
    "fuel_lvl": "Fuel Level",
    "fuel_rate": "Fuel Rate",
    "odom": "Odometer",
    "altitude": "Altitude",
    "engine_hours": "Engine Hours",
    "hdop": "DOP",
    "cool_temp": "Coolant Temperature",
    "total_fuel_used": "Total Fuel Used",
    "pwr_ext": "Battery",
    "engine_load": "Engine Load",
    "oil_press": "Oil Pressure",
    "oil_temp": "Oil Temperature",
    "def_level": "DEF Level",
    "intk_t": "Intake Temperature",
    "air_temp": "Ambient Temperature",
    "trams_t": "Transmission Temp",
    "fuel_t": "Fuel Temperature",
    "intrclr_t": "Intercooler Temp",
    "intake_pressure": "Intake Pressure",
}

conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    cursor = conn.cursor()

    print("=" * 80)
    print("ANÁLISIS: SENSORES DISPONIBLES vs SENSORES QUE USAMOS")
    print("=" * 80)

    # Obtener todos los sensores con alta disponibilidad (>50 trucks)
    cursor.execute(
        """
        SELECT p, n, sensor_id, COUNT(DISTINCT unit) as truck_count, type
        FROM sensors
        WHERE p IS NOT NULL AND p != ''
        GROUP BY p, n, sensor_id, type
        HAVING truck_count > 50
        ORDER BY truck_count DESC, sensor_id
    """
    )

    available_sensors = cursor.fetchall()

    print(
        f"\n✅ Sensores con alta disponibilidad (>50 trucks): {len(available_sensors)}\n"
    )

    # Categorizar sensores por utilidad
    mpg_fuel_sensors = []
    idle_sensors = []
    predictive_sensors = []
    driver_behavior_sensors = []
    cost_sensors = []
    missing_sensors = []

    for s in available_sensors:
        param = s["p"]
        name = s["n"]
        sid = s["sensor_id"]
        count = s["truck_count"]
        stype = s["type"]

        # Verificar si ya lo usamos
        is_used = param in WIALON_PARAM_MAP.keys()

        sensor_info = {
            "id": sid,
            "param": param,
            "name": name,
            "trucks": count,
            "type": stype,
            "used": is_used,
        }

        # Clasificar por categoría
        if param in [
            "gear",
            "brake_switch",
            "actual_retarder",
            "obd_speed",
            "engine_load",
        ]:
            driver_behavior_sensors.append(sensor_info)

        if param in [
            "oil_level",
            "cool_lvl",
            "j1939_fmi",
            "j1939_spn",
            "dtc",
            "oil_press",
            "oil_temp",
            "trams_t",
            "intrclr_t",
            "intake_pressure",
        ]:
            predictive_sensors.append(sensor_info)

        if param in ["idle_hours", "pto_hours", "total_idle_fuel", "fuel_economy"]:
            idle_sensors.append(sensor_info)

        if param in [
            "fuel_lvl",
            "fuel_rate",
            "total_fuel_used",
            "fuel_t",
            "odom",
            "speed",
            "rpm",
            "fuel_economy",
        ]:
            mpg_fuel_sensors.append(sensor_info)

        if param in ["total_fuel_used", "total_idle_fuel", "fuel_economy", "odom"]:
            cost_sensors.append(sensor_info)

        # Identificar sensores NO usados pero útiles
        if not is_used and param not in [
            "gps_locked",
            "event_id",
            "rssi",
            "roaming",
            "mcc",
            "mnc",
            "lac",
            "mode",
            "bus",
            "sats",
            "course",
            "barometer",
            "battery",
            "pwr_int",
            "vin",
        ]:
            missing_sensors.append(sensor_info)

    # Reportes por categoría
    print("\n" + "=" * 80)
    print("🚗 DRIVER BEHAVIOR - Sensores disponibles")
    print("=" * 80)
    for s in driver_behavior_sensors:
        status = "✅ USANDO" if s["used"] else "❌ NO USADO"
        print(
            f"{status} | ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
        )

    print("\n" + "=" * 80)
    print("🔧 PREDICTIVE MAINTENANCE - Sensores disponibles")
    print("=" * 80)
    for s in predictive_sensors:
        status = "✅ USANDO" if s["used"] else "❌ NO USADO"
        print(
            f"{status} | ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
        )

    print("\n" + "=" * 80)
    print("⏸️  IDLE & PTO - Sensores disponibles")
    print("=" * 80)
    for s in idle_sensors:
        status = "✅ USANDO" if s["used"] else "❌ NO USADO"
        print(
            f"{status} | ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
        )

    print("\n" + "=" * 80)
    print("⛽ MPG & FUEL - Sensores disponibles")
    print("=" * 80)
    for s in mpg_fuel_sensors:
        status = "✅ USANDO" if s["used"] else "❌ NO USADO"
        print(
            f"{status} | ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
        )

    print("\n" + "=" * 80)
    print("💰 COST ANALYSIS - Sensores disponibles")
    print("=" * 80)
    for s in cost_sensors:
        status = "✅ USANDO" if s["used"] else "❌ NO USADO"
        print(
            f"{status} | ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
        )

    print("\n" + "=" * 80)
    print("🆕 SENSORES ÚTILES QUE NO ESTAMOS USANDO")
    print("=" * 80)
    print(f"Total: {len(missing_sensors)} sensores\n")

    # Priorizar por relevancia
    high_priority = []
    medium_priority = []
    low_priority = []

    for s in missing_sensors:
        # Alta prioridad: críticos para funcionalidad core
        if s["param"] in [
            "gear",
            "odom",
            "idle_hours",
            "pto_hours",
            "fuel_economy",
            "total_idle_fuel",
            "brake_switch",
            "actual_retarder",
            "j1939_fmi",
            "j1939_spn",
            "dtc",
            "oil_level",
            "cool_lvl",
        ]:
            high_priority.append(s)
        # Media prioridad: mejoran análisis existente
        elif s["param"] in ["obd_speed", "fuel_t", "intrclr_t"]:
            medium_priority.append(s)
        # Baja prioridad: nice-to-have
        else:
            low_priority.append(s)

    if high_priority:
        print("🔴 ALTA PRIORIDAD - Agregar AHORA:")
        for s in high_priority:
            print(
                f"   ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
            )

    if medium_priority:
        print("\n🟡 MEDIA PRIORIDAD - Considerar agregar:")
        for s in medium_priority:
            print(
                f"   ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
            )

    if low_priority:
        print("\n🟢 BAJA PRIORIDAD - Opcional:")
        for s in low_priority:
            print(
                f"   ID {s['id']:3} | {s['param']:20} | {s['name']:30} | {s['trucks']} trucks"
            )

    # Resumen de impacto
    print("\n" + "=" * 80)
    print("📊 IMPACTO DE AGREGAR SENSORES FALTANTES")
    print("=" * 80)

    impacts = {
        "gear": "Driver behavior scoring, shift analysis, fuel efficiency",
        "odom": "CRÍTICO - MPG accuracy, distance tracking, maintenance scheduling",
        "idle_hours": "Idle cost calculation, efficiency analysis",
        "pto_hours": "PTO usage tracking, specialized equipment monitoring",
        "total_idle_fuel": "CRÍTICO - Idle fuel cost, efficiency optimization",
        "fuel_economy": "ECU-calculated MPG for validation/comparison",
        "brake_switch": "Brake wear analysis, driver safety scoring",
        "actual_retarder": "Engine brake usage, driver behavior, brake maintenance",
        "j1939_fmi": "Detailed fault diagnostics (Failure Mode Indicator)",
        "j1939_spn": "Detailed fault diagnostics (Suspect Parameter Number)",
        "dtc": "Basic fault count (already partially tracked)",
        "oil_level": "Critical engine health, predictive maintenance",
        "cool_lvl": "Coolant monitoring, overheat prediction",
        "obd_speed": "OBD speed vs GPS speed validation",
    }

    for param, impact in impacts.items():
        sensor = next(
            (s for s in high_priority + medium_priority if s["param"] == param), None
        )
        if sensor:
            print(f"\n{param:20} → {impact}")
            print(f"{'':20}    Disponible en {sensor['trucks']} trucks")

finally:
    conn.close()
