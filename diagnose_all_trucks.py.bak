"""
Diagnóstico Completo de Trucks
================================
Revisa todos los camiones y reporta:
- Sensores disponibles en Wialon
- Estado online/offline
- Última actualización de datos
- Problemas de configuración
"""

import pymysql
import yaml
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
    "user": os.getenv("WIALON_DB_USER", "tomas"),
    "password": os.getenv("WIALON_DB_PASS", "Tomas2025"),
    "connect_timeout": 30,
}

FUEL_COPILOT_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": os.getenv("MYSQL_USER", "fuel_admin"),
    "password": os.getenv("MYSQL_PASSWORD", "FuelCopilot2025!"),
    "database": "fuel_copilot",
}

# Sensores críticos para operación completa
CRITICAL_SENSORS = [
    "fuel_lvl",
    "fuel_rate",
    "rpm",
    "engine_load",
    "engine_hours",
    "oil_press",
    "oil_temp",
    "cool_temp",
    "def_level",
    "intake_pressure",
    "speed",
    "odom",
]

NICE_TO_HAVE_SENSORS = [
    "fuel_t",
    "intk_t",
    "intrclr_t",
    "barometer",
    "gear",
    "idle_hours",
    "total_fuel_used",
    "pwr_ext",
    "pwr_int",
]


def load_truck_config():
    """Carga configuración de trucks desde tanks.yaml"""
    tanks_path = Path(__file__).parent / "tanks.yaml"
    with open(tanks_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config.get("trucks", {})


def get_truck_sensors_from_wialon(unit_id):
    """Obtiene sensores disponibles para un unit en la última hora"""
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cutoff_epoch = int(datetime.now(timezone.utc).timestamp()) - 3600

    query = """
        SELECT DISTINCT p as sensor_name
        FROM sensors
        WHERE unit = %s AND m >= %s
        ORDER BY p
    """

    cursor.execute(query, (unit_id, cutoff_epoch))
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return [row["sensor_name"] for row in results]


def get_last_message_time(unit_id):
    """Obtiene el timestamp del último mensaje de un unit"""
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    query = """
        SELECT MAX(m) as last_epoch
        FROM sensors
        WHERE unit = %s
    """

    cursor.execute(query, (unit_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result and result["last_epoch"]:
        last_time = datetime.fromtimestamp(result["last_epoch"], tz=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
        return last_time, age_minutes
    return None, None


def analyze_truck(truck_id, config):
    """Analiza un truck y retorna diagnóstico completo"""
    unit_id = config.get("unit_id")

    if not unit_id:
        return {
            "truck_id": truck_id,
            "status": "ERROR",
            "error": "No unit_id configured",
        }

    # Obtener sensores disponibles
    sensors = get_truck_sensors_from_wialon(unit_id)

    # Obtener última actualización
    last_time, age_minutes = get_last_message_time(unit_id)

    # Clasificar sensores
    has_critical = [s for s in CRITICAL_SENSORS if s in sensors]
    missing_critical = [s for s in CRITICAL_SENSORS if s not in sensors]
    has_nice = [s for s in NICE_TO_HAVE_SENSORS if s in sensors]

    # Determinar estado
    if age_minutes is None:
        status = "NO_DATA"
    elif age_minutes < 5:
        status = "ONLINE"
    elif age_minutes < 60:
        status = "RECENT"
    elif age_minutes < 1440:  # 24 hours
        status = "OFFLINE"
    else:
        status = "INACTIVE"

    # Nivel de sensores
    critical_pct = (
        (len(has_critical) / len(CRITICAL_SENSORS) * 100) if CRITICAL_SENSORS else 0
    )

    if critical_pct >= 90:
        sensor_level = "COMPLETE"
    elif critical_pct >= 60:
        sensor_level = "PARTIAL"
    elif critical_pct >= 30:
        sensor_level = "LIMITED"
    else:
        sensor_level = "GPS_ONLY"

    return {
        "truck_id": truck_id,
        "unit_id": unit_id,
        "status": status,
        "sensor_level": sensor_level,
        "total_sensors": len(sensors),
        "critical_sensors": len(has_critical),
        "critical_pct": critical_pct,
        "missing_critical": missing_critical,
        "last_update": (
            last_time.strftime("%Y-%m-%d %H:%M:%S UTC") if last_time else "NEVER"
        ),
        "age_minutes": round(age_minutes, 1) if age_minutes else None,
        "all_sensors": sensors,
    }


def main():
    print("=" * 80)
    print("FUEL COPILOT - TRUCK DIAGNOSTICS")
    print("=" * 80)
    print()

    truck_config = load_truck_config()

    if not truck_config:
        print("❌ No trucks found in tanks.yaml")
        return

    print(f"📊 Analyzing {len(truck_config)} trucks...")
    print()

    results = []
    for truck_id, config in truck_config.items():
        print(f"Checking {truck_id}...", end=" ")
        result = analyze_truck(truck_id, config)
        results.append(result)
        print(
            f"{result['status']} - {result['sensor_level']} ({result['total_sensors']} sensors)"
        )

    print()
    print("=" * 80)
    print("SUMMARY BY STATUS")
    print("=" * 80)

    by_status = defaultdict(list)
    for r in results:
        by_status[r["status"]].append(r["truck_id"])

    for status in ["ONLINE", "RECENT", "OFFLINE", "INACTIVE", "NO_DATA", "ERROR"]:
        trucks = by_status.get(status, [])
        if trucks:
            print(f"\n{status}: {len(trucks)} trucks")
            print(f"  {', '.join(trucks)}")

    print()
    print("=" * 80)
    print("SUMMARY BY SENSOR LEVEL")
    print("=" * 80)

    by_level = defaultdict(list)
    for r in results:
        by_level[r["sensor_level"]].append(r["truck_id"])

    for level in ["COMPLETE", "PARTIAL", "LIMITED", "GPS_ONLY"]:
        trucks = by_level.get(level, [])
        if trucks:
            print(f"\n{level}: {len(trucks)} trucks")
            print(f"  {', '.join(trucks[:20])}")
            if len(trucks) > 20:
                print(f"  ... and {len(trucks) - 20} more")

    print()
    print("=" * 80)
    print("TRUCKS WITH MISSING CRITICAL SENSORS")
    print("=" * 80)

    problematic = [
        r
        for r in results
        if r["critical_pct"] < 90 and r["status"] in ["ONLINE", "RECENT"]
    ]

    if problematic:
        for r in problematic:
            print(f"\n{r['truck_id']} (Unit {r['unit_id']}):")
            print(f"  Status: {r['status']} ({r['age_minutes']:.1f} min ago)")
            print(
                f"  Sensors: {r['total_sensors']} total, {r['critical_sensors']}/{len(CRITICAL_SENSORS)} critical ({r['critical_pct']:.0f}%)"
            )
            if r["missing_critical"]:
                print(f"  Missing: {', '.join(r['missing_critical'][:10])}")
    else:
        print("\n✅ All online/recent trucks have adequate sensor coverage")

    print()
    print("=" * 80)
    print("DETAILED TRUCK REPORT")
    print("=" * 80)

    # Solicitar truck específico para detalle
    print("\nEnter truck ID for detailed report (or press Enter to skip):")
    truck_input = input("> ").strip()

    if truck_input:
        detail = next(
            (r for r in results if r["truck_id"].upper() == truck_input.upper()), None
        )
        if detail:
            print(f"\n{'=' * 80}")
            print(f"DETAILED REPORT: {detail['truck_id']}")
            print(f"{'=' * 80}")
            print(f"Unit ID: {detail['unit_id']}")
            print(f"Status: {detail['status']}")
            print(f"Sensor Level: {detail['sensor_level']}")
            print(f"Last Update: {detail['last_update']}")
            if detail["age_minutes"]:
                print(f"Data Age: {detail['age_minutes']:.1f} minutes")
            print(f"\nTotal Sensors: {detail['total_sensors']}")
            print(
                f"Critical Sensors: {detail['critical_sensors']}/{len(CRITICAL_SENSORS)} ({detail['critical_pct']:.0f}%)"
            )

            if detail["all_sensors"]:
                print(f"\nAll Available Sensors:")
                for sensor in sorted(detail["all_sensors"]):
                    marker = "✓" if sensor in CRITICAL_SENSORS else " "
                    print(f"  [{marker}] {sensor}")

            if detail["missing_critical"]:
                print(f"\nMissing Critical Sensors:")
                for sensor in detail["missing_critical"]:
                    print(f"  ❌ {sensor}")
        else:
            print(f"\n❌ Truck {truck_input} not found")

    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    online_incomplete = len(
        [
            r
            for r in results
            if r["status"] in ["ONLINE", "RECENT"] and r["sensor_level"] != "COMPLETE"
        ]
    )
    gps_only = len([r for r in results if r["sensor_level"] == "GPS_ONLY"])
    offline = len([r for r in results if r["status"] == "OFFLINE"])

    if online_incomplete > 0:
        print(f"\n⚠️  {online_incomplete} trucks online but missing sensors")
        print("   → Check Wialon sensor configuration for these trucks")
        print("   → Verify ELD/OBD device is properly connected")

    if gps_only > 0:
        print(f"\n⚠️  {gps_only} trucks with GPS only (no engine sensors)")
        print("   → These trucks need OBD/J1939 connection configured in Wialon")
        print("   → Check if ELD devices support ECU data")

    if offline > 0:
        print(f"\n⚠️  {offline} trucks offline")
        print("   → Check if trucks are parked or ELD devices are disconnected")

    print("\n✅ Next Steps:")
    print("   1. Start sensor_cache_updater service to populate local cache")
    print("   2. Fix Wialon sensor mappings for incomplete trucks")
    print("   3. Verify ELD device configuration for GPS-only trucks")

    print()


if __name__ == "__main__":
    main()
