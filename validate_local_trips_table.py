#!/usr/bin/env python3
"""
Validar columnas de la tabla trips en la base de datos LOCAL (fuel_copilot)
"""
import pymysql

LOCAL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "fuel_admin",
    "password": "FuelCopilot2025!",
    "database": "fuel_copilot",
}

# Columnas que debe tener la tabla trips local
REQUIRED_COLUMNS = {
    "id": "INT AUTO_INCREMENT PRIMARY KEY",
    "truck_id": "VARCHAR(20) NOT NULL",
    "start_time": "DATETIME NOT NULL",
    "end_time": "DATETIME NOT NULL",
    "distance_mi": "DECIMAL(10,2)",
    "avg_speed_mph": "DECIMAL(10,2)",
    "max_speed_mph": "DECIMAL(10,2)",
    "odometer_start": "DECIMAL(12,2)",
    "odometer_end": "DECIMAL(12,2)",
    "fuel_consumed_gal": "DECIMAL(10,2)",
    "avg_mpg": "DECIMAL(10,2)",
    "driver": "VARCHAR(100)",
    "harsh_accel_count": "INT DEFAULT 0",
    "harsh_brake_count": "INT DEFAULT 0",
    "speeding_count": "INT DEFAULT 0",
    "duration_hours": "DECIMAL(10,2)",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

print("=" * 80)
print("🔍 VALIDACIÓN DE TABLA trips EN BASE LOCAL (fuel_copilot)")
print("=" * 80)

try:
    conn = pymysql.connect(**LOCAL_CONFIG)
    cursor = conn.cursor()

    # Verificar si la tabla existe
    cursor.execute(
        """
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'fuel_copilot' 
        AND table_name = 'trips'
    """
    )

    exists = cursor.fetchone()[0] > 0

    if not exists:
        print("\n❌ La tabla 'trips' NO EXISTE en fuel_copilot")
        print("\n📝 Script SQL para crear la tabla:")
        print("-" * 80)
        print(
            """
CREATE TABLE trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    distance_mi DECIMAL(10,2),
    avg_speed_mph DECIMAL(10,2),
    max_speed_mph DECIMAL(10,2),
    odometer_start DECIMAL(12,2),
    odometer_end DECIMAL(12,2),
    fuel_consumed_gal DECIMAL(10,2),
    avg_mpg DECIMAL(10,2),
    driver VARCHAR(100),
    harsh_accel_count INT DEFAULT 0,
    harsh_brake_count INT DEFAULT 0,
    speeding_count INT DEFAULT 0,
    duration_hours DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_truck_time (truck_id, start_time),
    INDEX idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )
        print("-" * 80)
        cursor.close()
        conn.close()
        exit(1)

    # Obtener estructura actual
    cursor.execute("DESCRIBE trips")
    columns = cursor.fetchall()
    existing_columns = {col[0]: col[1] for col in columns}

    print(f"\n✅ Tabla 'trips' existe en fuel_copilot")
    print(f"\n📋 Columnas actuales ({len(existing_columns)}):")
    for col_name, col_type in existing_columns.items():
        print(f"  - {col_name:25} {col_type}")

    # Verificar columnas requeridas
    print("\n" + "=" * 80)
    print("🔍 VALIDACIÓN DE COLUMNAS:")
    print("=" * 80)

    missing = []
    found = []

    for req_col in REQUIRED_COLUMNS.keys():
        if req_col in existing_columns:
            found.append(req_col)
            print(f"  ✅ {req_col}")
        else:
            missing.append(req_col)
            print(f"  ❌ {req_col} - FALTA")

    if missing:
        print("\n" + "=" * 80)
        print(f"❌ FALTAN {len(missing)} COLUMNAS")
        print("=" * 80)
        print("\n📝 Ejecuta este SQL para agregarlas:")
        print("-" * 80)
        for col in missing:
            col_def = REQUIRED_COLUMNS[col]
            print(f"ALTER TABLE trips ADD COLUMN {col} {col_def};")
        print("-" * 80)
    else:
        print("\n✅ ¡PERFECTO! Todas las columnas requeridas existen")

    # Mostrar estadísticas
    print("\n" + "=" * 80)
    print("📊 ESTADÍSTICAS:")
    print("=" * 80)

    cursor.execute("SELECT COUNT(*) FROM trips")
    total = cursor.fetchone()[0]
    print(f"  • Total de trips: {total}")

    if total > 0:
        cursor.execute(
            """
            SELECT 
                COUNT(DISTINCT truck_id) as trucks,
                MIN(start_time) as primer_trip,
                MAX(end_time) as ultimo_trip
            FROM trips
        """
        )
        stats = cursor.fetchone()
        print(f"  • Camiones con trips: {stats[0]}")
        print(f"  • Primer trip: {stats[1]}")
        print(f"  • Último trip: {stats[2]}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    exit(1)
