"""
Migration: Create dtc_events table for DTC history and ML
Version: 5.7.3
Date: December 2025

This table stores DTC (Diagnostic Trouble Code) events for:
- Historical tracking of engine issues
- ML training data for predictive maintenance
- Fleet-wide DTC pattern analysis

Run: python migrations/add_dtc_events_table.py
"""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Get MySQL connection"""
    return pymysql.connect(
        host=os.getenv("LOCAL_DB_HOST", "localhost"),
        user=os.getenv("LOCAL_DB_USER", "root"),
        password=os.getenv("LOCAL_DB_PASSWORD", ""),
        database=os.getenv("LOCAL_DB_NAME", "fuel_copilot"),
        charset="utf8mb4",
    )


def table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists"""
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    return cursor.fetchone()[0] > 0


def run_migration():
    """Create dtc_events table if it doesn't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if table_exists(cursor, "dtc_events"):
            print("✅ Table dtc_events already exists")
            return True

        print("📝 Creating dtc_events table...")

        cursor.execute(
            """
            CREATE TABLE dtc_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(20) NOT NULL,
                carrier_id VARCHAR(50),
                timestamp_utc DATETIME NOT NULL,
                
                -- DTC Code details
                spn INT NOT NULL COMMENT 'Suspect Parameter Number',
                fmi INT NOT NULL COMMENT 'Failure Mode Identifier',
                dtc_code VARCHAR(20) NOT NULL COMMENT 'Formatted code e.g. SPN524.FMI4',
                raw_value VARCHAR(100) COMMENT 'Original value from Wialon',
                
                -- Classification
                severity VARCHAR(20) NOT NULL COMMENT 'CRITICAL, WARNING, INFO',
                system VARCHAR(50) COMMENT 'ENGINE, TRANSMISSION, AFTERTREATMENT, etc',
                description TEXT COMMENT 'Human-readable description',
                recommended_action TEXT COMMENT 'What to do',
                
                -- Context at time of DTC
                latitude DECIMAL(10, 6),
                longitude DECIMAL(10, 6),
                speed_mph DECIMAL(6, 2),
                engine_hours DECIMAL(10, 2),
                odometer_mi DECIMAL(12, 2),
                
                -- Status tracking
                status VARCHAR(20) DEFAULT 'ACTIVE' COMMENT 'ACTIVE, RESOLVED, ACKNOWLEDGED',
                resolved_at DATETIME,
                resolved_by VARCHAR(100),
                notes TEXT,
                
                -- Metadata
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                -- Indexes for common queries
                INDEX idx_truck_time (truck_id, timestamp_utc),
                INDEX idx_severity (severity),
                INDEX idx_dtc_code (dtc_code),
                INDEX idx_status (status),
                INDEX idx_system (system)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='DTC (Diagnostic Trouble Code) events for fleet health tracking'
        """
        )

        conn.commit()
        print("✅ Successfully created dtc_events table")

        # Verify
        cursor.execute("DESCRIBE dtc_events")
        columns = cursor.fetchall()
        print(f"📊 Table has {len(columns)} columns")

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("DTC Events Table Migration v5.7.3")
    print("=" * 60)
    success = run_migration()
    exit(0 if success else 1)
