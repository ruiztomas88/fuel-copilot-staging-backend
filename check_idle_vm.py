"""
🔍 QUICK IDLE CHECK - Para ejecutar en la VM Windows

Verifica:
1. Si el backend está usando fuel_rate sensor
2. Si fuel_rate existe en Wialon
3. Qué método de idle está siendo usado
"""

import pymysql
from datetime import datetime

print("=" * 80)
print("🔍 IDLE CONSUMPTION DIAGNOSTIC")
print("=" * 80)
print()

# 1. Check fuel_copilot database
try:
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="fuel_copilot",
        password="Fc2024Secure!",
        database="fuel_copilot",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    cursor = conn.cursor()

    # Get latest idle readings for each truck
    query = """
        SELECT 
            truck_id,
            idle_gph,
            idle_method,
            rpm,
            timestamp_utc,
            TIMESTAMPDIFF(SECOND, timestamp_utc, NOW()) as age_seconds
        FROM sensor_data
        WHERE truck_id IN ('RT9127', 'RT9129', 'RT9134', 'RT9135')
            AND truck_status = 'STOPPED'
            AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
        ORDER BY truck_id, timestamp_utc DESC
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    # Get latest per truck
    trucks = {}
    for row in rows:
        if row["truck_id"] not in trucks:
            trucks[row["truck_id"]] = row

    print("📊 CURRENT IDLE STATUS (fuel_copilot database)")
    print("-" * 80)

    for truck_id in ["RT9127", "RT9129", "RT9134", "RT9135"]:
        if truck_id in trucks:
            data = trucks[truck_id]
            method = data["idle_method"]

            if method == "SENSOR_FUEL_RATE":
                icon = "✅"
            elif method == "FALLBACK_CONSENSUS":
                icon = "⚠️ "
            else:
                icon = "❓"

            print(
                f"{truck_id}: {data['idle_gph']:.2f} GPH  {icon} {method}  "
                f"(RPM: {data['rpm'] or 'N/A'}, {data['age_seconds']}s ago)"
            )
        else:
            print(f"{truck_id}: NO DATA (not stopped in last 10min)")

    conn.close()

except Exception as e:
    print(f"❌ Error connecting to fuel_copilot DB: {e}")

print()
print("-" * 80)
print()

# 2. Check Wialon for fuel_rate sensor
try:
    wialon_conn = pymysql.connect(
        host="20.127.200.135",
        port=3306,
        user="tomas",
        password="Tomas2025",
        database="wialon_collect",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    cursor = wialon_conn.cursor()

    print("🔬 WIALON fuel_rate SENSOR (last 5 minutes)")
    print("-" * 80)

    unit_map = {
        "RT9127": 2201,
        "RT9129": 2202,
        "RT9134": 2203,
        "RT9135": 2204,
    }

    for truck_id, unit_id in unit_map.items():
        # Check fuel_rate
        query = """
            SELECT value, FROM_UNIXTIME(m) as ts, TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(m), NOW()) as age
            FROM sensors
            WHERE unit = %s AND p = 'fuel_rate'
                AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 5 MINUTE)
            ORDER BY m DESC LIMIT 1
        """
        cursor.execute(query, (unit_id,))
        fuel_rate_row = cursor.fetchone()

        # Check RPM
        query = """
            SELECT value, FROM_UNIXTIME(m) as ts, TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(m), NOW()) as age
            FROM sensors
            WHERE unit = %s AND p = 'rpm'
                AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 5 MINUTE)
            ORDER BY m DESC LIMIT 1
        """
        cursor.execute(query, (unit_id,))
        rpm_row = cursor.fetchone()

        if fuel_rate_row:
            lph = fuel_rate_row["value"]
            gph = lph / 3.78541
            age = fuel_rate_row["age"]

            # Check if in valid range
            if 0.5 <= gph <= 5.0:
                range_status = "✅ VALID"
            else:
                range_status = f"⚠️  OUT OF RANGE (should be 0.5-5.0)"

            print(
                f"{truck_id}: fuel_rate = {lph:.2f} LPH ({gph:.2f} GPH)  {range_status}  ({age}s ago)"
            )
        else:
            print(f"{truck_id}: fuel_rate = ❌ NOT FOUND")

        if rpm_row:
            rpm = rpm_row["value"]
            state = "🟢 IDLE" if rpm < 1000 else "🔵 RUNNING"
            print(f"         rpm = {rpm:.0f}  {state}")

    wialon_conn.close()

except Exception as e:
    print(f"❌ Error connecting to Wialon DB: {e}")

print()
print("=" * 80)
print()
print("💡 WHAT TO CHECK:")
print()
print("1. ⚠️  If all show FALLBACK_CONSENSUS:")
print("   → Backend might not be restarted after git pull")
print("   → Run: nssm restart FuelAnalyticsBackend")
print()
print("2. ❌ If fuel_rate NOT FOUND in Wialon:")
print("   → Sensor not enabled in Pacific Track")
print("   → Should see ~7000 samples/day normally")
print()
print("3. ⚠️  If fuel_rate OUT OF RANGE:")
print("   → Sensor value invalid (too high/low for idle)")
print("   → Will fall back to 0.8 GPH estimate")
print()
print("4. ✅ If fuel_rate VALID but still using FALLBACK:")
print("   → Check backend logs for detailed reason")
print("   → tail -f logs/backend-stdout.log | grep 'fuel_rate'")
