"""
Schema Migration Script
Adds missing columns to fuel_metrics table to match SQLAlchemy model
Run once after deploying to update database schema
"""
import os
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)

cursor = conn.cursor()

# Add missing columns to match tools/database_models.py
alterations = [
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS data_age_min DOUBLE AFTER timestamp_utc",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS sensor_ema_pct DOUBLE AFTER sensor_gallons",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS ecu_level_pct DOUBLE AFTER sensor_ema_pct",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS model_level_pct DOUBLE AFTER ecu_level_pct",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS confidence_indicator VARCHAR(20) AFTER model_level_pct",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS idle_mode VARCHAR(30) AFTER idle_method",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS odom_delta_mi DOUBLE AFTER odometer_mi",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS static_anchors_total INT DEFAULT 0 AFTER anchor_type",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS micro_anchors_total INT DEFAULT 0 AFTER static_anchors_total",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS refuel_events_total INT DEFAULT 0 AFTER micro_anchors_total",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS refuel_gallons DOUBLE AFTER refuel_events_total",
    "ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS flags VARCHAR(255) AFTER refuel_gallons",
]

print("Migrating fuel_metrics schema...")
for i, sql in enumerate(alterations, 1):
    # MySQL doesn't support IF NOT EXISTS in ALTER TABLE, so we try-catch
    try:
        cursor.execute(sql.replace(" IF NOT EXISTS", ""))
        print(f"{i}. Added: {sql.split('ADD COLUMN')[1].split('AFTER')[0].strip()}")
    except pymysql.err.OperationalError as e:
        if "Duplicate column name" in str(e):
            print(f"{i}. Skipped (exists): {sql.split('ADD COLUMN')[1].split('AFTER')[0].strip()}")
        else:
            print(f"{i}. Error: {e}")
            raise

conn.commit()
conn.close()
print("\nSchema migration complete!")
