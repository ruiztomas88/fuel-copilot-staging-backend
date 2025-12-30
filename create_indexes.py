#!/usr/bin/env python3
"""
Script para crear indexes de forma segura (DROP IF EXISTS primero)
"""
import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Configuración
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "fuel_copilot_local",
}

# Definición de indexes a crear
INDEXES = [
    # FUEL_METRICS
    ("fuel_metrics", "idx_fuel_metrics_truck_time", ["truck_id", "timestamp_utc"]),
    ("fuel_metrics", "idx_fuel_metrics_timestamp", ["timestamp_utc"]),
    ("fuel_metrics", "idx_fuel_metrics_idle", ["idle_mode", "timestamp_utc"]),
    # DTC_EVENTS
    ("dtc_events", "idx_dtc_events_truck", ["truck_id"]),
    ("dtc_events", "idx_dtc_events_status", ["status"]),
    ("dtc_events", "idx_dtc_events_severity", ["severity"]),
    ("dtc_events", "idx_dtc_events_timestamp", ["timestamp_utc"]),
    ("dtc_events", "idx_dtc_events_critical", ["is_critical"]),
    ("dtc_events", "idx_dtc_events_category", ["category"]),
    (
        "dtc_events",
        "idx_dtc_events_truck_status_severity",
        ["truck_id", "status", "severity"],
    ),
    ("dtc_events", "idx_dtc_events_spn", ["spn"]),
    # TRUCK_SENSORS_CACHE
    ("truck_sensors_cache", "idx_truck_sensors_cache_truck", ["truck_id"]),
    ("truck_sensors_cache", "idx_truck_sensors_cache_timestamp", ["timestamp"]),
    ("truck_sensors_cache", "idx_truck_sensors_cache_age", ["data_age_seconds"]),
    # REFUEL_EVENTS
    ("refuel_events", "idx_refuel_events_truck", ["truck_id"]),
    ("refuel_events", "idx_refuel_events_time", ["refuel_time"]),
    ("refuel_events", "idx_refuel_events_truck_time", ["truck_id", "refuel_time"]),
    ("refuel_events", "idx_refuel_events_type", ["refuel_type"]),
    ("refuel_events", "idx_refuel_events_validated", ["validated"]),
    # TRUCK_SPECS
    ("truck_specs", "idx_truck_specs_truck", ["truck_id"]),
    # DRIVER_SCORES
    ("driver_scores", "idx_driver_scores_truck", ["truck_id"]),
    # ANOMALY_DETECTIONS
    ("anomaly_detections", "idx_anomaly_detections_truck", ["truck_id"]),
    ("anomaly_detections", "idx_anomaly_detections_timestamp", ["timestamp"]),
    ("anomaly_detections", "idx_anomaly_detections_type", ["anomaly_type"]),
    # PM_PREDICTIONS
    ("pm_predictions", "idx_pm_predictions_truck", ["truck_id"]),
    ("pm_predictions", "idx_pm_predictions_component", ["component"]),
    # ENGINE_HEALTH_ALERTS
    ("engine_health_alerts", "idx_engine_health_alerts_truck", ["truck_id"]),
    ("engine_health_alerts", "idx_engine_health_alerts_timestamp", ["timestamp"]),
    ("engine_health_alerts", "idx_engine_health_alerts_severity", ["severity"]),
]


def create_indexes():
    """Crear indexes de forma segura"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    created = 0
    skipped = 0
    errors = 0

    print("🔄 Creando indexes de performance...")
    print(f"   Database: {DB_CONFIG['database']}")
    print(f"   Total indexes: {len(INDEXES)}\n")

    for table, index_name, columns in INDEXES:
        try:
            # Verificar si la tabla existe
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if not cursor.fetchone():
                print(f"⚠️  Skip: Table '{table}' no existe")
                skipped += 1
                continue

            # Verificar si las columnas existen
            cursor.execute(f"DESCRIBE {table}")
            table_columns = [row[0] for row in cursor.fetchall()]

            missing_columns = [col for col in columns if col not in table_columns]
            if missing_columns:
                print(
                    f"⚠️  Skip: {table}.{index_name} - Columnas missing: {missing_columns}"
                )
                skipped += 1
                continue

            # Drop index si existe
            cursor.execute(f"SHOW INDEX FROM {table} WHERE Key_name = '{index_name}'")
            if cursor.fetchone():
                cursor.execute(f"DROP INDEX {index_name} ON {table}")
                print(f"🔄 Dropped existing: {table}.{index_name}")

            # Crear index
            columns_str = ", ".join(columns)
            sql = f"CREATE INDEX {index_name} ON {table}({columns_str})"
            cursor.execute(sql)

            print(f"✅ Created: {table}.{index_name} ({columns_str})")
            created += 1

        except Exception as e:
            print(f"❌ Error: {table}.{index_name} - {str(e)}")
            errors += 1

    conn.close()

    print(f"\n{'='*60}")
    print(f"✅ Created: {created}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"❌ Errors: {errors}")
    print(f"{'='*60}\n")

    return created, skipped, errors


if __name__ == "__main__":
    create_indexes()
