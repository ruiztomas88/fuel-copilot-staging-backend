"""
Actualizar units_map con los unit_ids correctos para FF7702, JB6858, RT9127
"""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to fuel_copilot database
_password = os.getenv("MYSQL_PASSWORD")
if not _password:
    raise ValueError("MYSQL_PASSWORD environment variable required")

try:
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "fuel_admin"),
        password=_password,
        database=os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    cursor = conn.cursor()

    print("=" * 80)
    print("🔧 UPDATING units_map")
    print("=" * 80)
    print()

    # Check current values first
    print("📋 BEFORE UPDATE:")
    print("-" * 80)
    cursor.execute(
        "SELECT beyondId, unit FROM units_map WHERE beyondId IN ('FF7702', 'JB6858', 'RT9127')"
    )
    results = cursor.fetchall()
    for row in results:
        print(f"  {row['beyondId']}: {row['unit']}")

    if not results:
        print("  (No entries found - need to INSERT)")

    print()

    # Updates
    updates = {
        "FF7702": 401989385,
        "JB6858": 402007354,
        "RT9127": 401905963,
    }

    print("🔨 APPLYING UPDATES:")
    print("-" * 80)

    for truck_id, unit_id in updates.items():
        # Check if exists
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM units_map WHERE beyondId = %s", (truck_id,)
        )
        exists = cursor.fetchone()["cnt"] > 0

        if exists:
            # Update
            cursor.execute(
                "UPDATE units_map SET unit = %s WHERE beyondId = %s",
                (unit_id, truck_id),
            )
            print(f"  ✅ Updated {truck_id} -> {unit_id}")
        else:
            # Insert
            cursor.execute(
                "INSERT INTO units_map (beyondId, unit, fuel_capacity) VALUES (%s, %s, 200)",
                (truck_id, unit_id),
            )
            print(f"  ➕ Inserted {truck_id} -> {unit_id}")

    conn.commit()

    print()
    print("📋 AFTER UPDATE:")
    print("-" * 80)
    cursor.execute(
        "SELECT beyondId, unit FROM units_map WHERE beyondId IN ('FF7702', 'JB6858', 'RT9127')"
    )
    results = cursor.fetchall()
    for row in results:
        print(f"  {row['beyondId']}: {row['unit']}")

    print()
    print("=" * 80)
    print("✅ units_map actualizado correctamente")
    print("🔄 Ahora reinicia WialonSyncService para que recargue el mapping")
    print("=" * 80)

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
