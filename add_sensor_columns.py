#!/usr/bin/env python3
"""
Add obd_speed and engine_brake columns to truck_sensors_cache table
"""

import pymysql

from config import get_local_db_config


def main():
    try:
        db_config = get_local_db_config()
        print(f"Connecting to {db_config['database']} at {db_config['host']}...")

        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        # Check if columns already exist
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'truck_sensors_cache' 
            AND COLUMN_NAME IN ('obd_speed', 'engine_brake')
        """,
            (db_config["database"],),
        )

        existing_count = cursor.fetchone()[0]

        if existing_count == 2:
            print("✅ Columnas obd_speed y engine_brake ya existen")
            return

        print(f"Agregando columnas (existen {existing_count}/2)...")

        # Add obd_speed if not exists
        try:
            cursor.execute("ALTER TABLE truck_sensors_cache ADD COLUMN obd_speed FLOAT")
            print("✅ Columna obd_speed agregada")
        except pymysql.err.OperationalError as e:
            if "Duplicate column name" in str(e):
                print("ℹ️ Columna obd_speed ya existe")
            else:
                raise

        # Add engine_brake if not exists
        try:
            cursor.execute(
                "ALTER TABLE truck_sensors_cache ADD COLUMN engine_brake BOOLEAN"
            )
            print("✅ Columna engine_brake agregada")
        except pymysql.err.OperationalError as e:
            if "Duplicate column name" in str(e):
                print("ℹ️ Columna engine_brake ya existe")
            else:
                raise

        conn.commit()
        print("\n✅ Tabla truck_sensors_cache actualizada correctamente")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    main()
