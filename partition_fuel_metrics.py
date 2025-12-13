"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              FUEL_METRICS TABLE PARTITIONING MIGRATION                        ║
║                       v5.5.4 - December 2025                                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  This script adds RANGE partitioning to fuel_metrics table by month.         ║
║                                                                                ║
║  Benefits:                                                                     ║
║  - 10-50x faster queries on recent data (last 7-30 days)                      ║
║  - Easy archival: DROP PARTITION instead of DELETE                            ║
║  - Better index performance per partition                                      ║
║  - Parallel query execution across partitions                                  ║
║                                                                                ║
║  IMPORTANT: Run during maintenance window (low traffic)                        ║
║  Estimated time: 5-15 minutes depending on table size                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python partition_fuel_metrics.py --dry-run    # Preview changes
    python partition_fuel_metrics.py --execute    # Apply changes
    python partition_fuel_metrics.py --status     # Check partition status
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_mysql_connection():
    """Get MySQL connection from environment or .env file"""
    try:
        import pymysql
        from dotenv import load_dotenv

        # Load .env if exists
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        _password = os.getenv("DB_PASSWORD")
        if not _password:
            logger.error("DB_PASSWORD environment variable required")
            return None

        connection = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "fuel_admin"),
            password=_password,
            database=os.getenv("DB_NAME", "fuel_copilot"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to MySQL: {e}")
        return None


def check_current_partitions(conn) -> Dict[str, Any]:
    """Check if table is already partitioned and get current status"""
    with conn.cursor() as cursor:
        # Check if partitioned
        cursor.execute(
            """
            SELECT PARTITION_NAME, PARTITION_ORDINAL_POSITION, 
                   PARTITION_DESCRIPTION, TABLE_ROWS
            FROM INFORMATION_SCHEMA.PARTITIONS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'fuel_metrics'
            AND PARTITION_NAME IS NOT NULL
            ORDER BY PARTITION_ORDINAL_POSITION
        """
        )
        partitions = cursor.fetchall()

        # Get table stats
        cursor.execute(
            """
            SELECT COUNT(*) as row_count,
                   MIN(timestamp_utc) as min_date,
                   MAX(timestamp_utc) as max_date
            FROM fuel_metrics
        """
        )
        stats = cursor.fetchone()

        # Get table size
        cursor.execute(
            """
            SELECT 
                ROUND(DATA_LENGTH / 1024 / 1024, 2) as data_mb,
                ROUND(INDEX_LENGTH / 1024 / 1024, 2) as index_mb
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'fuel_metrics'
        """
        )
        size = cursor.fetchone()

        return {
            "is_partitioned": len(partitions) > 0,
            "partitions": partitions,
            "partition_count": len(partitions),
            "row_count": stats["row_count"] if stats else 0,
            "min_date": stats["min_date"] if stats else None,
            "max_date": stats["max_date"] if stats else None,
            "data_mb": size["data_mb"] if size else 0,
            "index_mb": size["index_mb"] if size else 0,
        }


def generate_partition_sql(start_date: datetime, months_ahead: int = 6) -> str:
    """
    Generate SQL to partition fuel_metrics table by month.

    Creates partitions from start_date through months_ahead into the future.
    """
    partitions = []

    # Start from beginning of start_date's month
    current = datetime(start_date.year, start_date.month, 1)
    end_date = datetime.now() + timedelta(days=30 * months_ahead)

    while current <= end_date:
        # Next month for LESS THAN clause
        if current.month == 12:
            next_month = datetime(current.year + 1, 1, 1)
        else:
            next_month = datetime(current.year, current.month + 1, 1)

        partition_name = f"p{current.year}{current.month:02d}"
        partitions.append(
            f"    PARTITION {partition_name} VALUES LESS THAN ('{next_month.strftime('%Y-%m-%d')}')"
        )

        current = next_month

    # Add MAXVALUE partition for future data
    partitions.append("    PARTITION p_future VALUES LESS THAN MAXVALUE")

    return ",\n".join(partitions)


def get_partition_migration_sql(conn) -> List[str]:
    """
    Generate SQL statements to migrate existing table to partitioned table.

    Strategy:
    1. Create new partitioned table
    2. Copy data from old table
    3. Rename tables (atomic swap)
    4. Drop old table
    """
    status = check_current_partitions(conn)

    if status["is_partitioned"]:
        logger.info("Table is already partitioned!")
        return []

    # Determine start date (oldest data or 6 months ago)
    if status["min_date"]:
        start_date = status["min_date"]
    else:
        start_date = datetime.now() - timedelta(days=180)

    partition_defs = generate_partition_sql(start_date, months_ahead=6)

    sqls = []

    # Step 1: Create new partitioned table
    sqls.append(
        f"""
-- Step 1: Create partitioned table structure
CREATE TABLE fuel_metrics_partitioned (
    id BIGINT AUTO_INCREMENT,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    unit_id BIGINT,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    
    -- Location & Status
    truck_status VARCHAR(20),
    latitude DOUBLE,
    longitude DOUBLE,
    speed DOUBLE,
    speed_mph DOUBLE,
    
    -- Fuel Data
    fuel_level_raw DOUBLE,
    fuel_level_filtered DOUBLE,
    fuel_capacity INT,
    fuel_percent DOUBLE,
    estimated_pct DOUBLE,
    estimated_gallons DOUBLE,
    sensor_pct DOUBLE,
    sensor_gallons DOUBLE,
    
    -- Consumption
    consumption_gph DOUBLE,
    consumption_lph DOUBLE,
    consumption_rate DOUBLE,
    mpg_current DOUBLE,
    mpg_avg_24h DOUBLE,
    
    -- Engine Data
    engine_rpm INT,
    rpm INT,
    engine_hours DOUBLE,
    odometer DOUBLE,
    odometer_miles DOUBLE,
    odometer_mi DOUBLE,
    mileage_delta DOUBLE,
    
    -- Temperatures & Sensors
    coolant_temp_f DOUBLE,
    oil_pressure_psi DOUBLE,
    oil_temp_f DOUBLE,
    altitude_ft DOUBLE,
    hdop DOUBLE,
    battery_voltage DOUBLE,
    engine_load_pct DOUBLE,
    def_level_pct DOUBLE,
    intake_air_temp_f DOUBLE,
    ambient_temp_f DOUBLE,
    
    -- Idle Detection
    idle_method VARCHAR(30),
    idle_mode VARCHAR(30),
    idle_gph DOUBLE,
    idle_hours DOUBLE,
    idle_duration_minutes INT,
    
    -- Kalman Filter
    kalman_estimate DOUBLE,
    kalman_uncertainty DOUBLE,
    drift_pct DOUBLE,
    drift_warning VARCHAR(10),
    
    -- Anchors
    anchor_type VARCHAR(20),
    anchor_fuel_level DOUBLE,
    anchor_detected VARCHAR(10),
    micro_anchors_total INT DEFAULT 0,
    
    -- Refuel Detection
    refuel_detected VARCHAR(10),
    refuel_amount DOUBLE,
    refuel_events_total INT DEFAULT 0,
    refuel_gallons DOUBLE,
    
    -- Theft Detection
    theft_detected VARCHAR(10),
    
    -- Metadata
    data_age_min DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Primary key includes partition column for MySQL requirement
    PRIMARY KEY (id, timestamp_utc),
    
    -- Indexes optimized for common queries
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_carrier (carrier_id),
    INDEX idx_status (truck_status),
    INDEX idx_truck_status_time (truck_id, truck_status, timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE COLUMNS(timestamp_utc) (
{partition_defs}
);
"""
    )

    # Step 2: Copy data with batching for large tables
    sqls.append(
        """
-- Step 2: Copy data to partitioned table
-- Note: For very large tables (>10M rows), consider batched inserts
INSERT INTO fuel_metrics_partitioned 
SELECT * FROM fuel_metrics;
"""
    )

    # Step 3: Atomic rename
    sqls.append(
        """
-- Step 3: Atomic table swap
RENAME TABLE 
    fuel_metrics TO fuel_metrics_old,
    fuel_metrics_partitioned TO fuel_metrics;
"""
    )

    # Step 4: Drop old table (commented for safety)
    sqls.append(
        """
-- Step 4: Drop old table (run manually after verification)
-- DROP TABLE fuel_metrics_old;
"""
    )

    return sqls


def add_future_partition(conn, year: int, month: int) -> str:
    """Add a new partition for a future month"""
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    partition_name = f"p{year}{month:02d}"

    return f"""
ALTER TABLE fuel_metrics
REORGANIZE PARTITION p_future INTO (
    PARTITION {partition_name} VALUES LESS THAN ('{next_month.strftime('%Y-%m-%d')}'),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
"""


def drop_old_partition(partition_name: str) -> str:
    """Generate SQL to drop an old partition (for archival)"""
    return f"""
-- Archive old data by dropping partition
-- WARNING: This permanently deletes all data in the partition!
ALTER TABLE fuel_metrics DROP PARTITION {partition_name};
"""


def main():
    parser = argparse.ArgumentParser(description="Partition fuel_metrics table")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show SQL without executing"
    )
    parser.add_argument("--execute", action="store_true", help="Execute the migration")
    parser.add_argument(
        "--status", action="store_true", help="Show current partition status"
    )
    parser.add_argument("--add-partition", type=str, help="Add partition for YYYY-MM")

    args = parser.parse_args()

    if not any([args.dry_run, args.execute, args.status, args.add_partition]):
        parser.print_help()
        return

    conn = get_mysql_connection()
    if not conn:
        logger.error("Could not connect to database")
        sys.exit(1)

    try:
        if args.status:
            status = check_current_partitions(conn)
            print("\n" + "=" * 60)
            print("FUEL_METRICS TABLE STATUS")
            print("=" * 60)
            print(f"Partitioned: {'Yes' if status['is_partitioned'] else 'No'}")
            print(f"Total rows: {status['row_count']:,}")
            print(f"Data size: {status['data_mb']} MB")
            print(f"Index size: {status['index_mb']} MB")
            print(f"Date range: {status['min_date']} to {status['max_date']}")

            if status["is_partitioned"]:
                print(f"\nPartitions ({status['partition_count']}):")
                for p in status["partitions"]:
                    print(f"  - {p['PARTITION_NAME']}: ~{p['TABLE_ROWS']:,} rows")
            else:
                print(
                    "\n⚠️  Table is NOT partitioned. Run with --dry-run to see migration SQL."
                )
            print("=" * 60 + "\n")

        elif args.add_partition:
            try:
                year, month = map(int, args.add_partition.split("-"))
                sql = add_future_partition(conn, year, month)
                print(f"\nSQL to add partition for {year}-{month:02d}:")
                print(sql)

                if args.execute:
                    with conn.cursor() as cursor:
                        cursor.execute(sql)
                    conn.commit()
                    print("✅ Partition added successfully!")
            except ValueError:
                print("Error: Use format YYYY-MM (e.g., --add-partition 2026-01)")

        elif args.dry_run or args.execute:
            sqls = get_partition_migration_sql(conn)

            if not sqls:
                print("No migration needed - table is already partitioned.")
                return

            print("\n" + "=" * 60)
            print("PARTITION MIGRATION SQL")
            print("=" * 60)

            for i, sql in enumerate(sqls, 1):
                print(f"\n-- Statement {i}:")
                print(sql)

            if args.execute:
                confirm = input(
                    "\n⚠️  Execute migration? This will modify the database. (yes/no): "
                )
                if confirm.lower() == "yes":
                    print("\nExecuting migration...")
                    with conn.cursor() as cursor:
                        for i, sql in enumerate(sqls[:-1], 1):  # Skip DROP TABLE
                            print(f"  Step {i}...", end=" ")
                            # Split multiple statements
                            for stmt in sql.split(";"):
                                stmt = stmt.strip()
                                if stmt and not stmt.startswith("--"):
                                    cursor.execute(stmt)
                            print("✅")
                    conn.commit()
                    print("\n✅ Migration complete!")
                    print("   Old table saved as 'fuel_metrics_old'")
                    print("   Run 'DROP TABLE fuel_metrics_old' after verification")
                else:
                    print("Migration cancelled.")
            else:
                print("\nRun with --execute to apply these changes.")

            print("=" * 60 + "\n")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
