"""
Enhanced Database Service - Hybrid CSV + MySQL approach
Uses existing MySQL tables (sensors, units_map) + CSV for latest computed metrics
"""

import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import logging
import os
import glob
from pathlib import Path
import pymysql.cursors

# Import connection pool manager
from database_pool import get_db_connection

logger = logging.getLogger(__name__)

# CSV Directory
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_reports"


def get_raw_sensor_history(
    truck_id: str, hours_back: int = 48, sensor_type: str = "fuel_lvl"
) -> pd.DataFrame:
    """
    Get RAW sensor data history from MySQL sensors table
    NEW FEATURE: Access historical sensor readings

    Args:
        truck_id: Truck ID (e.g., 'DO9356')
        hours_back: Hours of history
        sensor_type: 'fuel_lvl', 'fuel_rate', 'rpm', 'obd_speed', etc.
    """
    # Get unit ID from units_map
    unit_query = "SELECT unit FROM units_map WHERE beyondId = %s LIMIT 1"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute(unit_query, [truck_id])
            result = cursor.fetchone()

            if not result:
                logger.warning(f"Truck {truck_id} not found in units_map")
                return pd.DataFrame()

            unit_id = result["unit"]

            # Get sensor history
            cutoff_epoch = int(
                (datetime.now() - timedelta(hours=hours_back)).timestamp()
            )

            sensor_query = """
                SELECT 
                    FROM_UNIXTIME(m) as timestamp_utc,
                    m as epoch,
                    value,
                    p as sensor_name
                FROM sensors
                WHERE unit = %s
                  AND p = %s
                  AND m >= %s
                ORDER BY m DESC
            """

            cursor.execute(sensor_query, [unit_id, sensor_type, cutoff_epoch])
            results = cursor.fetchall()

            if results:
                df = pd.DataFrame(results)
                df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
                df["truck_id"] = truck_id
                return df
            else:
                return pd.DataFrame()

    except Exception as e:
        logger.error(f"Error getting sensor history for {truck_id}: {e}")
        return pd.DataFrame()


def get_fuel_consumption_trend(truck_id: str, hours_back: int = 48) -> Dict[str, Any]:
    """
    NEW FEATURE: Analyze fuel consumption trend from raw sensor data
    Shows actual fuel level changes over time
    """
    df = get_raw_sensor_history(truck_id, hours_back, "fuel_lvl")

    if df.empty:
        return {
            "truck_id": truck_id,
            "error": "No sensor data available",
            "data_points": 0,
        }

    # Calculate consumption rate
    df = df.sort_values("timestamp_utc")
    df["fuel_delta"] = df["value"].diff()
    df["time_delta_hours"] = df["timestamp_utc"].diff().dt.total_seconds() / 3600
    df["consumption_rate"] = (
        -df["fuel_delta"] / df["time_delta_hours"]
    )  # negative because fuel decreases

    # Filter out refuels (large positive changes)
    df_consumption = df[df["fuel_delta"] < 5].copy()  # Skip refuels

    return {
        "truck_id": truck_id,
        "hours_analyzed": hours_back,
        "data_points": len(df),
        "avg_fuel_level": float(df["value"].mean()),
        "min_fuel_level": float(df["value"].min()),
        "max_fuel_level": float(df["value"].max()),
        "avg_consumption_rate": (
            float(df_consumption["consumption_rate"].mean())
            if len(df_consumption) > 0
            else None
        ),
        "timeline": (
            df[["timestamp_utc", "value"]].to_dict("records") if len(df) < 500 else None
        ),
    }


def get_fleet_sensor_status() -> List[Dict[str, Any]]:
    """
    NEW FEATURE: Check sensor health for entire fleet
    Identifies trucks with sensor issues (like DO9356 with 0.0%)
    """
    query = """
        SELECT 
            um.beyondId as truck_id,
            um.unit,
            MAX(s.m) as last_report_epoch,
            FROM_UNIXTIME(MAX(s.m)) as last_report_time,
            AVG(CASE WHEN s.p = 'fuel_lvl' THEN s.value END) as avg_fuel_lvl,
            MIN(CASE WHEN s.p = 'fuel_lvl' THEN s.value END) as min_fuel_lvl,
            MAX(CASE WHEN s.p = 'fuel_lvl' THEN s.value END) as max_fuel_lvl,
            COUNT(CASE WHEN s.p = 'fuel_lvl' THEN 1 END) as fuel_readings
        FROM units_map um
        LEFT JOIN sensors s ON um.unit = s.unit AND s.m >= UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
        GROUP BY um.beyondId, um.unit
        HAVING fuel_readings > 0
        ORDER BY truck_id
    """

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute(query)
            results = cursor.fetchall()

            # Classify sensor health
            for row in results:
                if row["last_report_time"]:
                    row["last_report_time"] = row["last_report_time"].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                # Detect sensor issues
                if row["avg_fuel_lvl"] == 0 and row["min_fuel_lvl"] == 0:
                    row["sensor_status"] = "FAILED"
                    row["issue"] = "Sensor reporting 0.0 consistently"
                elif row["max_fuel_lvl"] == row["min_fuel_lvl"]:
                    row["sensor_status"] = "STUCK"
                    row["issue"] = "Sensor reading not changing"
                elif row["fuel_readings"] < 10:
                    row["sensor_status"] = "SPARSE"
                    row["issue"] = "Very few readings in 24h"
                else:
                    row["sensor_status"] = "HEALTHY"
                    row["issue"] = None

            return results

    except Exception as e:
        logger.error(f"Error getting fleet sensor status: {e}")
        return []


def get_truck_units_map() -> Dict[str, int]:
    """Get mapping of truck_id -> unit_id"""
    query = "SELECT beyondId as truck_id, unit FROM units_map"

    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn)
            return dict(zip(df["truck_id"], df["unit"]))
    except Exception as e:
        logger.error(f"Error getting units map: {e}")
        return {}


def get_latest_truck_data_from_csv(hours_back: int = 24) -> pd.DataFrame:
    """
    Get latest truck data from CSV files (existing functionality)
    This remains unchanged - CSVs still work as before
    """
    csv_files = glob.glob(str(CSV_DIR / "fuel_report_*.csv"))

    if not csv_files:
        logger.warning(f"No CSV files found in {CSV_DIR}")
        return pd.DataFrame()

    latest_data = []
    # 🔧 FIX: Use UTC-aware datetime for proper comparison with UTC timestamps in CSV
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)

            if df.empty:
                continue

            # 🔧 FIX: Parse timestamps as UTC-aware to match CSV format
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
            df_recent = df[df["timestamp_utc"] > cutoff_time]

            if not df_recent.empty:
                latest_row = df_recent.iloc[-1]

                # Extract truck_id from filename
                truck_id = Path(csv_file).stem.split("_")[2]
                latest_row["truck_id"] = truck_id

                latest_data.append(latest_row)

        except Exception as e:
            logger.error(f"Error reading {csv_file}: {e}")

    if latest_data:
        return pd.DataFrame(latest_data)
    else:
        return pd.DataFrame()


def get_refuel_history_from_csv(
    truck_id: Optional[str] = None, days_back: int = 7
) -> List[Dict[str, Any]]:
    """
    Get refuel history from CSV files (existing functionality)
    This remains unchanged
    """
    if truck_id:
        csv_pattern = f"fuel_report_{truck_id}_*.csv"
    else:
        csv_pattern = "fuel_report_*.csv"

    csv_files = glob.glob(str(CSV_DIR / csv_pattern))
    cutoff_time = datetime.now() - timedelta(days=days_back)

    all_refuels = []
    seen_timestamps = set()

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)

            if df.empty or "refuel_events_total" not in df.columns:
                continue

            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
            df_refuels = df[
                (df["refuel_events_total"] > 0) & (df["timestamp_utc"] > cutoff_time)
            ].copy()

            if not df_refuels.empty:
                truck_id_from_file = Path(csv_file).stem.split("_")[2]

                for _, row in df_refuels.iterrows():
                    timestamp_key = f"{truck_id_from_file}_{row['timestamp_utc'].strftime('%Y-%m-%d %H:%M')}"

                    if timestamp_key not in seen_timestamps:
                        seen_timestamps.add(timestamp_key)

                        all_refuels.append(
                            {
                                "truck_id": truck_id_from_file,
                                "timestamp_utc": row["timestamp_utc"].strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "refuel_gallons": float(row.get("refuel_gallons", 0)),
                                "fuel_level_before_pct": float(
                                    row.get("estimated_pct", 0)
                                ),
                                "status": row.get("truck_status", "UNKNOWN"),
                                "odometer_mi": (
                                    float(row.get("odometer_mi", 0))
                                    if pd.notna(row.get("odometer_mi"))
                                    else None
                                ),
                            }
                        )

        except Exception as e:
            logger.error(f"Error reading refuels from {csv_file}: {e}")

    return sorted(all_refuels, key=lambda x: x["timestamp_utc"], reverse=True)


def get_fleet_summary_from_csv() -> Dict[str, Any]:
    """
    Get fleet summary from CSV files (existing functionality)
    This remains unchanged
    """
    df = get_latest_truck_data_from_csv(hours_back=24)

    if df.empty:
        return {
            "total_trucks": 0,
            "active_trucks": 0,
            "offline_trucks": 0,
            "avg_fuel_level": 0,
            "avg_mpg": 0,
            "trucks_with_drift": 0,
        }

    return {
        "total_trucks": len(df),
        "active_trucks": len(df[df["truck_status"] != "OFFLINE"]),
        "offline_trucks": len(df[df["truck_status"] == "OFFLINE"]),
        "avg_fuel_level": float(df["estimated_pct"].mean()),
        "avg_mpg": (
            float(df[df["mpg_current"] > 0]["mpg_current"].mean())
            if "mpg_current" in df.columns
            else 0
        ),
        "trucks_with_drift": (
            len(df[df["drift_warning"] == "YES"])
            if "drift_warning" in df.columns
            else 0
        ),
    }


# Aliases to match existing API
get_latest_truck_data = get_latest_truck_data_from_csv
get_refuel_history = get_refuel_history_from_csv
get_fleet_summary = get_fleet_summary_from_csv


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🧪 Testing Enhanced Database Service\n")
    print("=" * 60)

    # Test 1: Existing functionality (CSV)
    print("\n1️⃣  Testing CSV-based functions (EXISTING):")
    df = get_latest_truck_data(hours_back=24)
    print(f"   ✅ Found {len(df)} trucks from CSVs")

    # Test 2: New MySQL sensor history
    print("\n2️⃣  Testing MySQL sensor history (NEW):")
    if not df.empty:
        truck_id = df.iloc[0]["truck_id"]
        sensor_df = get_raw_sensor_history(truck_id, hours_back=48)
        print(f"   ✅ Found {len(sensor_df)} sensor readings for {truck_id}")

    # Test 3: Fuel consumption trend
    print("\n3️⃣  Testing fuel consumption trend (NEW):")
    trend = get_fuel_consumption_trend("DO9356", hours_back=48)
    print(
        f"   ✅ Trend analysis: {trend['data_points']} points, avg={trend.get('avg_fuel_level', 'N/A')}"
    )

    # Test 4: Fleet sensor health
    print("\n4️⃣  Testing fleet sensor health check (NEW):")
    fleet_health = get_fleet_sensor_status()
    print(f"   ✅ Analyzed {len(fleet_health)} trucks")

    failed_sensors = [t for t in fleet_health if t["sensor_status"] == "FAILED"]
    if failed_sensors:
        print(f"   ⚠️  Found {len(failed_sensors)} trucks with failed sensors:")
        for truck in failed_sensors[:5]:
            print(f"      - {truck['truck_id']}: {truck['issue']}")

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
