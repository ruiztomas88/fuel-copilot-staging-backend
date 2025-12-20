"""
🔧 FUEL ANALYTICS - FIX MISSING TABLES
Creates missing daily_truck_metrics, trip_data, fleet_summary
"""

import pymysql
from datetime import datetime, timedelta
import sys

DB_CONFIG = {
    'host': 'localhost',
    'user': 'fuel_admin',
    'password': 'FuelCopilot2025!',
    'database': 'fuel_copilot',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def create_daily_truck_metrics():
    """Create and populate daily_truck_metrics table"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()
        
        # 1. CREATE TABLE
        print("\n1️⃣ Creating daily_truck_metrics table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_truck_metrics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                miles_traveled DECIMAL(12,2) DEFAULT 0,
                fuel_consumed_gallons DECIMAL(12,2) DEFAULT 0,
                avg_mpg DECIMAL(5,2) DEFAULT 0,
                idle_hours DECIMAL(6,2) DEFAULT 0,
                idle_fuel_gallons DECIMAL(10,2) DEFAULT 0,
                moving_hours DECIMAL(6,2) DEFAULT 0,
                total_records INT DEFAULT 0,
                avg_speed_mph DECIMAL(5,1) DEFAULT 0,
                max_speed_mph DECIMAL(5,1) DEFAULT 0,
                overspeeding_events INT DEFAULT 0,
                high_rpm_events INT DEFAULT 0,
                avg_rpm INT DEFAULT 0,
                dtc_count INT DEFAULT 0,
                voltage_issues INT DEFAULT 0,
                gps_issues INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_truck_date (truck_id, date),
                KEY idx_truck_id (truck_id),
                KEY idx_date (date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("✅ Table created successfully")
        
        # 2. POPULATE FROM fuel_metrics
        print("\n2️⃣ Populating from fuel_metrics...")
        cursor.execute("""
            INSERT INTO daily_truck_metrics (
                truck_id, date, miles_traveled, fuel_consumed_gallons, avg_mpg,
                idle_hours, idle_fuel_gallons, moving_hours, total_records,
                avg_speed_mph, max_speed_mph, overspeeding_events,
                high_rpm_events, avg_rpm, voltage_issues, gps_issues
            )
            SELECT
                truck_id,
                DATE(timestamp_utc) as date,
                -- Miles: Use odometer delta only (prevent negative values)
                GREATEST(0, COALESCE(MAX(odometer_mi) - MIN(odometer_mi), 0)) as miles_traveled,
                -- Fuel consumed (gallons per 2-min record = GPH * 0.033 hours)
                SUM(COALESCE(consumption_gph, 0) * 0.033) as fuel_consumed_gallons,
                -- MPG
                COALESCE(AVG(NULLIF(mpg_current, 0)), 5.7) as avg_mpg,
                -- Idle hours (2-min records = 0.033 hours each)
                SUM(CASE WHEN truck_status = 'IDLE' THEN 0.033 ELSE 0 END) as idle_hours,
                SUM(CASE WHEN truck_status = 'IDLE' THEN COALESCE(idle_gph, consumption_gph, 0) * 0.033 ELSE 0 END) as idle_fuel_gallons,
                -- Moving hours
                SUM(CASE WHEN truck_status = 'MOVING' THEN 0.033 ELSE 0 END) as moving_hours,
                COUNT(*) as total_records,
                -- Speed metrics
                AVG(NULLIF(speed_mph, 0)) as avg_speed_mph,
                MAX(speed_mph) as max_speed_mph,
                SUM(CASE WHEN speed_mph > 70 THEN 1 ELSE 0 END) as overspeeding_events,
                -- RPM metrics
                SUM(CASE WHEN rpm > 1800 THEN 1 ELSE 0 END) as high_rpm_events,
                AVG(NULLIF(rpm, 0)) as avg_rpm,
                -- Diagnostics
                SUM(CASE WHEN battery_voltage < 12.0 OR battery_voltage > 14.5 THEN 1 ELSE 0 END) as voltage_issues,
                SUM(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 ELSE 0 END) as gps_issues
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY truck_id, DATE(timestamp_utc)
            ON DUPLICATE KEY UPDATE
                miles_traveled = VALUES(miles_traveled),
                fuel_consumed_gallons = VALUES(fuel_consumed_gallons),
                avg_mpg = VALUES(avg_mpg),
                idle_hours = VALUES(idle_hours),
                idle_fuel_gallons = VALUES(idle_fuel_gallons),
                moving_hours = VALUES(moving_hours),
                total_records = VALUES(total_records),
                avg_speed_mph = VALUES(avg_speed_mph),
                max_speed_mph = VALUES(max_speed_mph),
                overspeeding_events = VALUES(overspeeding_events),
                high_rpm_events = VALUES(high_rpm_events),
                avg_rpm = VALUES(avg_rpm),
                voltage_issues = VALUES(voltage_issues),
                gps_issues = VALUES(gps_issues),
                updated_at = CURRENT_TIMESTAMP;
        """)
        rows_inserted = cursor.rowcount
        conn.commit()
        print(f"✅ Inserted/updated {rows_inserted} daily records")
        
        # 3. VERIFY
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT truck_id), MIN(date), MAX(date) FROM daily_truck_metrics")
        result = cursor.fetchone()
        print(f"\n📊 DAILY_TRUCK_METRICS Summary:")
        print(f"   Total records: {result['COUNT(*)']}")
        print(f"   Unique trucks: {result['COUNT(DISTINCT truck_id)']}")
        print(f"   Date range: {result['MIN(date)']} to {result['MAX(date)']}")
        
        # Sample data
        cursor.execute("""
            SELECT truck_id, date, miles_traveled, fuel_consumed_gallons, avg_mpg
            FROM daily_truck_metrics
            ORDER BY date DESC
            LIMIT 5
        """)
        print("\n   Sample records:")
        for row in cursor.fetchall():
            print(f"   {row['truck_id']} | {row['date']} | {row['miles_traveled']:.1f} mi | {row['fuel_consumed_gallons']:.1f} gal | {row['avg_mpg']:.2f} MPG")
        
    finally:
        cursor.close()
        conn.close()


def create_trip_data():
    """Create trip_data table structure"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()
        
        print("\n3️⃣ Creating trip_data table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trip_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(50) NOT NULL,
                trip_start DATETIME NOT NULL,
                trip_end DATETIME NOT NULL,
                start_lat DECIMAL(10,6),
                start_lon DECIMAL(10,6),
                end_lat DECIMAL(10,6),
                end_lon DECIMAL(10,6),
                distance_mi DECIMAL(10,2) DEFAULT 0,
                fuel_consumed_gal DECIMAL(10,2) DEFAULT 0,
                trip_mpg DECIMAL(5,2) DEFAULT 0,
                avg_speed_mph DECIMAL(5,1) DEFAULT 0,
                idle_time_hours DECIMAL(6,2) DEFAULT 0,
                moving_time_hours DECIMAL(6,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                KEY idx_truck_id (truck_id),
                KEY idx_trip_start (trip_start),
                KEY idx_trip_end (trip_end)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("✅ trip_data table created (empty - requires trip detection algorithm)")
        
    finally:
        cursor.close()
        conn.close()


def create_fleet_summary():
    """Create fleet_summary table"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()
        
        print("\n4️⃣ Creating fleet_summary table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fleet_summary (
                id INT AUTO_INCREMENT PRIMARY KEY,
                summary_date DATE NOT NULL UNIQUE,
                total_trucks INT DEFAULT 0,
                active_trucks INT DEFAULT 0,
                total_miles DECIMAL(12,2) DEFAULT 0,
                total_fuel_gallons DECIMAL(12,2) DEFAULT 0,
                fleet_avg_mpg DECIMAL(5,2) DEFAULT 0,
                total_idle_hours DECIMAL(10,2) DEFAULT 0,
                total_moving_hours DECIMAL(10,2) DEFAULT 0,
                active_dtcs INT DEFAULT 0,
                critical_dtcs INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                KEY idx_date (summary_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("✅ fleet_summary table created")
        
        # Populate from daily_truck_metrics
        print("\n5️⃣ Populating fleet_summary from daily_truck_metrics...")
        cursor.execute("""
            INSERT INTO fleet_summary (
                summary_date, total_trucks, active_trucks,
                total_miles, total_fuel_gallons, fleet_avg_mpg,
                total_idle_hours, total_moving_hours
            )
            SELECT
                date as summary_date,
                COUNT(DISTINCT truck_id) as total_trucks,
                SUM(CASE WHEN miles_traveled > 0 THEN 1 ELSE 0 END) as active_trucks,
                SUM(miles_traveled) as total_miles,
                SUM(fuel_consumed_gallons) as total_fuel_gallons,
                AVG(avg_mpg) as fleet_avg_mpg,
                SUM(idle_hours) as total_idle_hours,
                SUM(moving_hours) as total_moving_hours
            FROM daily_truck_metrics
            GROUP BY date
            ON DUPLICATE KEY UPDATE
                total_trucks = VALUES(total_trucks),
                active_trucks = VALUES(active_trucks),
                total_miles = VALUES(total_miles),
                total_fuel_gallons = VALUES(total_fuel_gallons),
                fleet_avg_mpg = VALUES(fleet_avg_mpg),
                total_idle_hours = VALUES(total_idle_hours),
                total_moving_hours = VALUES(total_moving_hours),
                updated_at = CURRENT_TIMESTAMP;
        """)
        rows_inserted = cursor.rowcount
        conn.commit()
        print(f"✅ Fleet summary populated with {rows_inserted} daily summaries")
        
    finally:
        cursor.close()
        conn.close()


def check_dtc_display():
    """Verify DTCs exist and are queryable"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()
        
        print("\n6️⃣ Checking DTC data for Command Center...")
        cursor.execute("""
            SELECT truck_id, dtc_code, severity, component, description
            FROM dtc_events
            WHERE cleared_at IS NULL
            ORDER BY 
                CASE severity 
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    ELSE 4
                END,
                detected_at DESC
            LIMIT 10
        """)
        dtcs = cursor.fetchall()
        
        if dtcs:
            print(f"✅ Found {len(dtcs)} active DTCs (Command Center should display these):")
            for dtc in dtcs[:5]:
                print(f"   [{dtc['severity']}] {dtc['truck_id']}: {dtc['dtc_code']} - {dtc['component']} - {dtc['description']}")
            if len(dtcs) > 5:
                print(f"   ... and {len(dtcs)-5} more")
        else:
            print("⚠️ No active DTCs found")
            
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("="*60)
    print("🔧 FIXING MISSING TABLES - FUEL ANALYTICS")
    print("="*60)
    
    try:
        create_daily_truck_metrics()
        create_trip_data()
        create_fleet_summary()
        check_dtc_display()
        
        print("\n" + "="*60)
        print("✅ ALL TABLES CREATED AND POPULATED!")
        print("="*60)
        print("\n📋 NEXT STEPS:")
        print("1. Cost/Mile should now work (uses daily_truck_metrics)")
        print("2. Utilization should now work (uses daily_truck_metrics)")
        print("3. Command Center needs code fix to display DTCs")
        print("4. Loss Analysis needs data quality improvement (75% missing RPM)")
        print("\n💡 To update daily metrics, run:")
        print("   python fix_missing_tables.py")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
