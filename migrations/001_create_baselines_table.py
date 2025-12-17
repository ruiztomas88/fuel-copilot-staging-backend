"""
Database Migration: Create engine_health_baselines table
═══════════════════════════════════════════════════════════════════════════════

BUG-001 FIX: Persist engine health baselines to database instead of losing them
on server restart.

Run with: python3 migrations/001_create_baselines_table.py
"""

from sqlalchemy import text
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database_pool import get_local_engine


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS engine_health_baselines (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(50) NOT NULL,
    sensor_name VARCHAR(100) NOT NULL,
    
    -- Statistics
    mean_value DECIMAL(10, 4) NOT NULL,
    std_dev DECIMAL(10, 4) NOT NULL,
    min_value DECIMAL(10, 4) NOT NULL,
    max_value DECIMAL(10, 4) NOT NULL,
    median_value DECIMAL(10, 4) DEFAULT NULL,
    
    -- Metadata
    sample_count INT NOT NULL,
    days_analyzed INT NOT NULL DEFAULT 30,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for fast lookup
    UNIQUE KEY unique_truck_sensor (truck_id, sensor_name),
    KEY idx_truck_id (truck_id),
    KEY idx_last_updated (last_updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_truck_sensor_updated 
ON engine_health_baselines(truck_id, sensor_name, last_updated);
"""


def run_migration():
    """Execute the migration"""
    print("🔧 BUG-001 FIX: Creating engine_health_baselines table...")

    engine = get_local_engine()
    if not engine:
        print("❌ ERROR: Could not connect to database")
        print("   Set MYSQL_PASSWORD environment variable")
        return False

    try:
        with engine.connect() as conn:
            # Create table
            print("   Creating table...")
            conn.execute(text(CREATE_TABLE_SQL))
            conn.commit()
            print("   ✅ Table created")

            # Create additional index
            print("   Creating indexes...")
            conn.execute(text(CREATE_INDEX_SQL))
            conn.commit()
            print("   ✅ Indexes created")

            # Verify
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_name = 'engine_health_baselines'
            """
                )
            )
            count = result.scalar()

            if count > 0:
                print("\n✅ Migration completed successfully!")
                print(f"   Table: engine_health_baselines")
                print(
                    f"   Columns: truck_id, sensor_name, mean_value, std_dev, min_value, max_value, ..."
                )
                return True
            else:
                print("\n❌ Migration failed - table not found")
                return False

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
