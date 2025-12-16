"""
MySQL Database Service - Direct Query from fuel_metrics table
Replaces CSV reading with direct MySQL queries for better performance and historical analysis

🔧 FIX v3.9.2: All queries now use SQLAlchemy connection pooling
🆕 v5.4.2: Now uses centralized get_allowed_trucks() from config.py
- pool_pre_ping=True: Check connection health before use
- pool_recycle=3600: Recycle connections after 1 hour
- pool_size=10: Maintain 10 connections in pool
- max_overflow=5: Allow 5 additional connections under load
"""

import pymysql
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Generator
from contextlib import contextmanager
import logging
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# 🆕 v5.4.2: Centralized truck filtering
try:
    from config import get_allowed_trucks

    CENTRALIZED_TRUCKS = True
except ImportError:
    logger.warning("⚠️ Could not import get_allowed_trucks from config")
    CENTRALIZED_TRUCKS = False

    def get_allowed_trucks():
        # Fallback - will be replaced when config.py is available
        return set()


# 🆕 v3.12.22: Memory cache for performance optimization
try:
    from memory_cache import cached, cache, invalidate_fleet_cache

    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False
    cache = None
    invalidate_fleet_cache = lambda: 0

    # Dummy decorator if cache not available
    def cached(ttl_seconds=30, key_prefix=""):
        def decorator(func):
            return func

        return decorator


# 🔧 FIX v3.12.23: Removed duplicate logger declaration (was on line 43)
# Logger already declared on line 23

# 🔧 FIX v3.9.2: Import centralized config
# Add parent directory to path to import config from root
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
try:
    from config import FUEL, DATABASE as DB_CONFIG
except ImportError:
    # Fallback if config not available
    logger.warning("Could not import config module, using defaults")

    class FUEL:
        PRICE_PER_GALLON = 3.50
        BASELINE_MPG = 5.7

    class DB_CONFIG:
        HOST = "localhost"
        PORT = 3306
        USER = "fuel_admin"
        PASSWORD = "FuelCopilot2025!"
        DATABASE = "fuel_copilot"
        CHARSET = "utf8mb4"
        POOL_SIZE = 10
        MAX_OVERFLOW = 5
        POOL_RECYCLE = 3600


# MySQL Configuration - from centralized config
MYSQL_CONFIG = {
    "host": DB_CONFIG.HOST,
    "port": DB_CONFIG.PORT,
    "user": DB_CONFIG.USER,
    "password": DB_CONFIG.PASSWORD,
    "database": DB_CONFIG.DATABASE,
    "charset": DB_CONFIG.CHARSET,
}

# Separate config for dict cursor (used in non-pandas queries)
MYSQL_CONFIG_DICT = {
    **MYSQL_CONFIG,
    "cursorclass": pymysql.cursors.DictCursor,
}

# 🔧 FIX v3.9.2: Enhanced SQLAlchemy connection pooling
_engine = None


def get_sqlalchemy_engine() -> Engine:
    """
    Get or create SQLAlchemy engine with connection pooling.

    🔧 FIX v3.9.2: Enhanced pooling configuration
    - pool_size=10: Base pool size
    - max_overflow=5: Extra connections under load
    - pool_recycle=3600: Recycle after 1 hour
    - pool_pre_ping=True: Health check before use
    """
    global _engine
    if _engine is None:
        connection_string = (
            f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@"
            f"{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
            f"?charset={MYSQL_CONFIG['charset']}"
        )
        _engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=10,  # 🔧 FIX v3.9.2: Increased from default (5)
            max_overflow=5,  # 🔧 FIX v3.9.2: Allow burst capacity
            pool_pre_ping=True,  # Health check connections
            pool_recycle=3600,  # Recycle after 1 hour
            echo=False,  # Disable SQL logging in production
        )
        logger.info(
            "✅ SQLAlchemy engine created with connection pooling (10+5 connections)"
        )
    return _engine


@contextmanager
def get_db_connection() -> Generator[Connection, None, None]:
    """
    Context manager for MySQL connections.

    🔧 FIX v3.9.2: Now uses SQLAlchemy pooled connections
    """
    engine = get_sqlalchemy_engine()
    conn = engine.connect()
    try:
        yield conn
    except Exception as e:
        logger.error(f"MySQL connection error: {e}")
        raise
    finally:
        conn.close()


def get_latest_truck_data(hours_back: int = 24) -> pd.DataFrame:
    """
    Get latest record for each truck from last N hours
    Replaces: CSV reading in database.py

    Returns DataFrame with same structure as CSV data

    🔧 v3.12.14: Added altitude_ft, coolant_temp_f, consumption_lph for truck details
    Real columns: speed_mph, estimated_pct, estimated_liters, sensor_pct,
    sensor_liters, rpm, drift_pct, idle_mode, refuel_gallons, etc.
    """
    query = text(
        """
        SELECT 
            t1.truck_id,
            t1.timestamp_utc,
            t1.truck_status,
            t1.latitude,
            t1.longitude,
            t1.speed_mph,
            t1.estimated_liters,
            t1.estimated_pct,
            t1.sensor_pct,
            t1.sensor_liters,
            t1.consumption_gph,
            t1.idle_method,
            t1.mpg_current,
            t1.rpm,
            t1.odometer_mi,
            t1.anchor_type,
            t1.anchor_detected,
            t1.refuel_gallons,
            t1.refuel_events_total,
            t1.data_age_min,
            t1.idle_mode,
            t1.drift_pct,
            t1.drift_warning,
            t1.flags,
            t1.altitude_ft,
            t1.coolant_temp_f,
            -- 🆕 v5.7.6: Diagnostic fields for Sensor Health dashboard
            t1.battery_voltage,
            t1.sats,
            t1.pwr_int,
            t1.gps_quality,
            t1.dtc,
            t1.dtc_code,
            t1.terrain_factor,
            t1.idle_hours_ecu,
            -- 🆕 v3.12.14: Consumption in LPH (GPH * 3.78541)
            ROUND(t1.consumption_gph * 3.78541, 2) as consumption_lph,
            -- 🆕 24h averages for stable metrics
            mpg_avg.avg_mpg_24h,
            mpg_avg.mpg_readings_24h,
            idle_avg.avg_idle_gph_24h,
            idle_avg.idle_readings_24h
        FROM fuel_metrics t1
        INNER JOIN (
            SELECT truck_id, MAX(timestamp_utc) as max_time
            FROM fuel_metrics
            WHERE timestamp_utc > NOW() - INTERVAL :hours_back HOUR
            GROUP BY truck_id
        ) t2 ON t1.truck_id = t2.truck_id AND t1.timestamp_utc = t2.max_time
        -- 🆕 Join with 24h MPG averages (MOVING trucks only)
        LEFT JOIN (
            SELECT 
                truck_id,
                AVG(mpg_current) as avg_mpg_24h,
                COUNT(*) as mpg_readings_24h
            FROM fuel_metrics
            WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
              AND truck_status = 'MOVING'
              AND mpg_current > 3.5 AND mpg_current < 12
            GROUP BY truck_id
        ) mpg_avg ON t1.truck_id = mpg_avg.truck_id
        -- 🆕 Join with 24h idle averages (STOPPED trucks with motor on)
        LEFT JOIN (
            SELECT 
                truck_id,
                AVG(consumption_gph) as avg_idle_gph_24h,
                COUNT(*) as idle_readings_24h
            FROM fuel_metrics
            WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
              AND truck_status = 'STOPPED'
              AND idle_method != 'NOT_IDLE'
              AND consumption_gph > 0.1 AND consumption_gph < 5.0
            GROUP BY truck_id
        ) idle_avg ON t1.truck_id = idle_avg.truck_id
        ORDER BY t1.truck_id
    """
    )

    try:
        # ✅ FIX: Use SQLAlchemy engine for pandas compatibility with positional params
        engine = get_sqlalchemy_engine()
        df = pd.read_sql_query(query, engine, params={"hours_back": hours_back})

        # Convert timestamp column explicitly
        if "timestamp_utc" in df.columns and not df.empty:
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")

        logger.info(f"Retrieved {len(df)} trucks from MySQL")
        return df

    except Exception as e:
        logger.error(f"Error getting latest truck data: {e}")
        return pd.DataFrame()


def get_truck_history(truck_id: str, hours_back: int = 168) -> pd.DataFrame:
    """
    Get historical data for specific truck
    Args:
        truck_id: Truck identifier (e.g., 'DO9356')
        hours_back: Hours of history to retrieve (default 7 days = 168 hours)
    """
    query = text(
        """
        SELECT *
        FROM fuel_metrics
        WHERE truck_id = :truck_id
          AND timestamp_utc > NOW() - INTERVAL :hours_back HOUR
        ORDER BY timestamp_utc DESC
    """
    )

    try:
        # ✅ FIX: Use SQLAlchemy engine for pandas compatibility
        engine = get_sqlalchemy_engine()
        df = pd.read_sql_query(
            query, engine, params={"truck_id": truck_id, "hours_back": hours_back}
        )

        if "timestamp_utc" in df.columns:
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])

        return df

    except Exception as e:
        logger.error(f"Error getting truck history for {truck_id}: {e}")
        return pd.DataFrame()


def get_refuel_history(
    truck_id: Optional[str] = None, days_back: int = 7
) -> List[Dict[str, Any]]:
    """
    Get refuel events from last N days
    Replaces: get_refuel_history() in database.py

    🔧 FIX v3.9.2: Now uses SQLAlchemy connection pooling
    🔧 FIX v3.10.13: Consolidate BY DAY - one refuel per truck per day
                     Minimum 40 gal threshold to filter sensor noise
    🔧 FIX v3.12.21: Also read from refuel_events table (where detected refuels are saved)

    Returns: List of dicts matching RefuelEvent model:
        - truck_id: str
        - timestamp: datetime
        - date: str (YYYY-MM-DD)
        - time: str (HH:MM:SS)
        - gallons: float
        - liters: float
        - fuel_level_after: float (optional)
    """

    # First, try to get from refuel_events table (where detected refuels are saved)
    refuel_events_query = text(
        """
        SELECT 
            truck_id,
            timestamp_utc,
            gallons_added as refuel_gallons,
            fuel_after as fuel_level_after_pct,
            fuel_before as fuel_level_before_pct,
            refuel_type,
            confidence
        FROM refuel_events
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        {truck_filter}
        ORDER BY timestamp_utc DESC
    """.format(
            truck_filter="AND truck_id = :truck_id" if truck_id else ""
        )
    )

    params = {"days_back": days_back}
    if truck_id:
        params["truck_id"] = truck_id

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(refuel_events_query, params)
            refuel_events_rows = result.mappings().all()

            if refuel_events_rows:
                logger.info(
                    f"Found {len(refuel_events_rows)} refuels in refuel_events table"
                )

                consolidated_results = []
                for row in refuel_events_rows:
                    ts = row["timestamp_utc"]
                    if isinstance(ts, str):
                        ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

                    gallons = float(row.get("refuel_gallons", 0) or 0)
                    fuel_after = float(row.get("fuel_level_after_pct", 0) or 0)
                    fuel_before = float(row.get("fuel_level_before_pct", 0) or 0)

                    # Convert fuel_after from gallons to percentage if needed
                    # The refuel_events table stores actual percentage values
                    if fuel_after > 100:
                        # It's in gallons, convert to percentage assuming 200 gal tank
                        fuel_after_pct = (fuel_after / 200) * 100
                    else:
                        fuel_after_pct = fuel_after

                    refuel_event = {
                        "truck_id": row["truck_id"],
                        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "date": ts.strftime("%Y-%m-%d"),
                        "time": ts.strftime("%H:%M:%S"),
                        "gallons": round(gallons, 1),
                        "liters": round(gallons * 3.78541, 1),
                        "fuel_level_after": (
                            round(fuel_after_pct, 1) if fuel_after_pct > 0 else None
                        ),
                        "fuel_level_before": (
                            round(fuel_before, 1) if fuel_before > 0 else None
                        ),
                        "source": "refuel_events",
                    }
                    consolidated_results.append(refuel_event)

                return consolidated_results

    except Exception as e:
        logger.warning(f"Could not read from refuel_events table: {e}")

    # Fallback: read from fuel_metrics table
    if truck_id:
        query = text(
            """
            SELECT 
                truck_id,
                timestamp_utc,
                refuel_gallons,
                estimated_pct as fuel_level_after_pct,
                estimated_liters as fuel_level_after_liters,
                estimated_gallons as fuel_level_after_gallons,
                truck_status as status,
                odometer_mi
            FROM fuel_metrics
            WHERE truck_id = :truck_id
              AND refuel_gallons > 0
              AND timestamp_utc > NOW() - INTERVAL :days_back DAY
            ORDER BY timestamp_utc ASC
        """
        )
        params = {"truck_id": truck_id, "days_back": days_back}
    else:
        query = text(
            """
            SELECT 
                truck_id,
                timestamp_utc,
                refuel_gallons,
                estimated_pct as fuel_level_after_pct,
                estimated_liters as fuel_level_after_liters,
                estimated_gallons as fuel_level_after_gallons,
                truck_status as status,
                odometer_mi
            FROM fuel_metrics
            WHERE refuel_gallons > 0
              AND timestamp_utc > NOW() - INTERVAL :days_back DAY
            ORDER BY timestamp_utc ASC
        """
        )
        params = {"days_back": days_back}

    try:
        # 🔧 FIX v3.9.2: Use SQLAlchemy pooled connection
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(query, params)
            results = result.mappings().all()

            if not results:
                return []

            # 🔧 v3.10.13: Consolidate BY DAY - one refuel per truck per day
            # Group records by (truck_id, date)
            truck_day_records = {}
            for row in results:
                tid = row["truck_id"]
                timestamp_utc = row["timestamp_utc"]
                if isinstance(timestamp_utc, datetime):
                    ts = timestamp_utc
                else:
                    ts = datetime.strptime(str(timestamp_utc), "%Y-%m-%d %H:%M:%S")

                date_str = ts.strftime("%Y-%m-%d")
                key = (tid, date_str)
                if key not in truck_day_records:
                    truck_day_records[key] = []
                truck_day_records[key].append((ts, row))

            # Process each day: take the LARGEST single refuel
            consolidated_results = []
            # 🔧 FIX v5.6.1: Was 40, now 10 to match detection threshold in wialon_sync_enhanced.py
            # This was causing ~30% of detected refuels to be filtered out in queries!
            MIN_REFUEL_GAL = 10

            for (tid, date_str), day_records in truck_day_records.items():
                # Find the record with largest refuel_gallons
                best_ts, best_row = max(
                    day_records, key=lambda x: float(x[1].get("refuel_gallons", 0))
                )

                max_gallons = float(best_row.get("refuel_gallons", 0))

                # Skip if below minimum threshold
                if max_gallons < MIN_REFUEL_GAL:
                    continue

                fuel_level_after_pct = (
                    float(best_row.get("fuel_level_after_pct", 0))
                    if best_row.get("fuel_level_after_pct")
                    else 0
                )

                # 🔧 v3.12.0: Lowered threshold from 55% to 40% to capture partial refuels
                # A real refuel should result in fuel > 40% (allows emergency/partial fills)
                if fuel_level_after_pct < 40:
                    continue

                # Cap at reasonable max
                total_gallons = min(max_gallons, 200.0)

                fuel_level_after_gallons = (
                    float(best_row.get("fuel_level_after_gallons", 0))
                    if best_row.get("fuel_level_after_gallons")
                    else 0
                )

                # Estimate fuel_before
                if fuel_level_after_gallons > 0 and fuel_level_after_pct > 0:
                    fuel_before_gal = max(0, fuel_level_after_gallons - total_gallons)
                    fuel_level_before = (
                        fuel_before_gal / fuel_level_after_gallons
                    ) * fuel_level_after_pct
                else:
                    fuel_level_before = None

                timestamp_str = best_ts.strftime("%Y-%m-%d %H:%M:%S")

                refuel_event = {
                    "truck_id": tid,
                    "timestamp": timestamp_str,
                    "date": date_str,
                    "time": best_ts.strftime("%H:%M:%S"),
                    "gallons": round(total_gallons, 1),
                    "liters": round(total_gallons * 3.78541, 1),
                    "fuel_level_after": (
                        fuel_level_after_pct if fuel_level_after_pct > 0 else None
                    ),
                    "fuel_level_before": (
                        round(fuel_level_before, 1) if fuel_level_before else None
                    ),
                    "consolidated_from": len(day_records),
                }
                consolidated_results.append(refuel_event)

            # Sort by timestamp descending (most recent first)
            consolidated_results.sort(key=lambda x: x["timestamp"], reverse=True)

            logger.info(
                f"Retrieved {len(consolidated_results)} refuel events (consolidated from {len(results)} raw records)"
            )
            return consolidated_results

    except Exception as e:
        logger.error(f"Error getting refuel history: {e}")
        return []


@cached(ttl_seconds=30, key_prefix="get_fleet_summary")
def get_fleet_summary() -> Dict[str, Any]:
    """
    Get fleet-wide statistics
    Replaces: get_fleet_summary() in database.py

    🔧 FIX v3.9.2: Now uses SQLAlchemy connection pooling
    🆕 v3.12.22: Cached for 30 seconds
    🆕 v5.4.2: Now uses centralized get_allowed_trucks() from config.py
    """
    # 🆕 v5.4.2: Use centralized truck filtering
    allowed_trucks = list(get_allowed_trucks())

    if not allowed_trucks:
        logger.warning("⚠️ No allowed trucks found, using empty list")
        return _empty_fleet_summary()

    query = text(
        f"""
        SELECT 
            COUNT(DISTINCT truck_id) as total_trucks,
            SUM(CASE WHEN truck_status != 'OFFLINE' THEN 1 ELSE 0 END) as active_trucks,
            SUM(CASE WHEN truck_status = 'OFFLINE' THEN 1 ELSE 0 END) as offline_trucks,
            AVG(estimated_pct) as avg_fuel_level,
            AVG(CASE WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
            AVG(consumption_lph) as avg_consumption,
            SUM(CASE WHEN drift_warning = 'YES' THEN 1 ELSE 0 END) as trucks_with_drift
        FROM (
            SELECT t1.*
            FROM fuel_metrics t1
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_time
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
                  AND truck_id IN ({','.join(f"'{t}'" for t in allowed_trucks)})
                GROUP BY truck_id
            ) t2 ON t1.truck_id = t2.truck_id AND t1.timestamp_utc = t2.max_time
        ) latest
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(query).fetchone()

            if result:
                return {
                    "total_trucks": result[0] or 0,
                    "active_trucks": result[1] or 0,
                    "offline_trucks": result[2] or 0,
                    "avg_fuel_level": float(result[3] or 0),
                    "avg_mpg": float(result[4] or 0),
                    "avg_consumption": float(result[5] or 0),
                    "trucks_with_drift": result[6] or 0,
                }
            return _empty_fleet_summary()

    except Exception as e:
        logger.error(f"Error getting fleet summary: {e}")
        return _empty_fleet_summary()


def _empty_fleet_summary() -> Dict[str, Any]:
    """Return empty fleet summary response"""
    return {
        "total_trucks": 0,
        "active_trucks": 0,
        "offline_trucks": 0,
        "avg_fuel_level": 0,
        "avg_mpg": 0,
        "avg_consumption": 0,
        "trucks_with_drift": 0,
    }


def get_truck_efficiency_stats(truck_id: str, days_back: int = 30) -> Dict[str, Any]:
    """
    Get efficiency statistics for specific truck over time period
    New feature enabled by historical data

    🔧 FIX v3.9.2: Now uses SQLAlchemy connection pooling
    """
    query = text(
        """
        SELECT 
            AVG(CASE WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
            MAX(CASE WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as max_mpg,
            MIN(CASE WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as min_mpg,
            AVG(consumption_lph) as avg_consumption,
            AVG(CASE WHEN truck_status = 'MOVING' THEN speed_mph END) as avg_speed,
            SUM(CASE WHEN idle_method != 'NOT_IDLE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as idle_percentage,
            AVG(drift_pct) as avg_drift,
            MAX(drift_pct) as max_drift,
            COUNT(*) as total_records,
            SUM(refuel_events_total) as total_refuels,
            SUM(refuel_gallons) as total_fuel_added
        FROM fuel_metrics
        WHERE truck_id = :truck_id
          AND timestamp_utc > NOW() - INTERVAL :days_back DAY
          AND mpg_current > 0
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(
                query, {"truck_id": truck_id, "days_back": days_back}
            ).fetchone()

            if result:
                return {
                    "avg_mpg": float(result[0] or 0),
                    "max_mpg": float(result[1] or 0),
                    "min_mpg": float(result[2] or 0),
                    "avg_consumption": float(result[3] or 0),
                    "avg_speed": float(result[4] or 0),
                    "idle_percentage": float(result[5] or 0),
                    "avg_drift": float(result[6] or 0),
                    "max_drift": float(result[7] or 0),
                    "total_records": result[8] or 0,
                    "total_refuels": result[9] or 0,
                    "total_fuel_added": float(result[10] or 0),
                }
            else:
                return {}

    except Exception as e:
        logger.error(f"Error getting efficiency stats for {truck_id}: {e}")
        return {}


def get_fuel_rate_analysis(truck_id: str, hours_back: int = 48) -> pd.DataFrame:
    """
    Get fuel consumption rate over time for analysis
    Example use case: "muéstrame fuel_rate promedio de últimas 48hrs"
    """
    query = text(
        """
        SELECT 
            timestamp_utc,
            consumption_lph,
            consumption_gph,
            mpg_current,
            speed_mph,
            rpm,
            truck_status,
            idle_method
        FROM fuel_metrics
        WHERE truck_id = :truck_id
          AND timestamp_utc > NOW() - INTERVAL :hours_back HOUR
        ORDER BY timestamp_utc ASC
    """
    )

    try:
        # ✅ FIX: Use SQLAlchemy engine for pandas compatibility
        engine = get_sqlalchemy_engine()
        df = pd.read_sql_query(
            query, engine, params={"truck_id": truck_id, "hours_back": hours_back}
        )

        if "timestamp_utc" in df.columns:
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])

        return df

    except Exception as e:
        logger.error(f"Error getting fuel rate analysis for {truck_id}: {e}")
        return pd.DataFrame()


@cached(ttl_seconds=60, key_prefix="get_kpi_summary")
def get_kpi_summary(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.8.1: Optimized KPI calculation using single MySQL query
    🆕 v3.12.22: Cached for 60 seconds

    Calculates fleet KPIs directly from MySQL for better performance:
    - Total fuel consumed (excluding OFFLINE status)
    - Idle waste (STOPPED status only)
    - Fleet average MPG (weighted by readings count)
    - Total distance from odometer deltas

    Args:
        days_back: Number of days to analyze (1=today, 7=week, 30=month)

    Returns:
        Dict with KPI metrics
    """
    query = text(
        """
        SELECT 
            -- Total records and trucks
            COUNT(*) as total_records,
            COUNT(DISTINCT truck_id) as truck_count,
            
            -- Weighted MPG (only MOVING with valid MPG between 3.5-12)
            SUM(CASE 
                WHEN truck_status = 'MOVING' 
                AND mpg_current > 3.5 AND mpg_current < 12 
                THEN mpg_current 
                ELSE 0 
            END) as mpg_sum,
            SUM(CASE 
                WHEN truck_status = 'MOVING' 
                AND mpg_current > 3.5 AND mpg_current < 12 
                THEN 1 
                ELSE 0 
            END) as mpg_count,
            
            -- Idle consumption (STOPPED with motor on)
            SUM(CASE 
                WHEN truck_status = 'STOPPED' 
                AND consumption_gph > 0.1 AND consumption_gph < 5.0
                THEN consumption_gph 
                ELSE 0 
            END) as idle_gph_sum,
            SUM(CASE 
                WHEN truck_status = 'STOPPED' 
                AND consumption_gph > 0.1 AND consumption_gph < 5.0
                THEN 1 
                ELSE 0 
            END) as idle_count,
            
            -- Moving consumption (for distance calculation)
            SUM(CASE 
                WHEN truck_status = 'MOVING' 
                AND consumption_gph > 0.5 AND consumption_gph < 20.0
                THEN consumption_gph 
                ELSE 0 
            END) as moving_gph_sum,
            SUM(CASE 
                WHEN truck_status = 'MOVING' 
                AND consumption_gph > 0.5 AND consumption_gph < 20.0
                THEN 1 
                ELSE 0 
            END) as moving_count,
            
            -- Total consumption (MOVING + STOPPED, excluding OFFLINE noise)
            SUM(CASE 
                WHEN truck_status IN ('MOVING', 'STOPPED') 
                AND consumption_gph > 0.05 
                THEN consumption_gph 
                ELSE 0 
            END) as consumption_gph_sum,
            SUM(CASE 
                WHEN truck_status IN ('MOVING', 'STOPPED') 
                AND consumption_gph > 0.05 
                THEN 1 
                ELSE 0 
            END) as consumption_count
            
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
    """
    )

    # 🔧 FIX v3.9.2: Use centralized config
    fuel_price_per_gal = FUEL.PRICE_PER_GALLON

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(query, {"days_back": days_back}).fetchone()

            if not result:
                return _empty_kpi_response(fuel_price_per_gal)

            # Extract values
            total_records = result[0] or 0
            truck_count = result[1] or 0
            mpg_sum = float(result[2] or 0)
            mpg_count = int(result[3] or 0)
            idle_gph_sum = float(result[4] or 0)
            idle_count = int(result[5] or 0)
            moving_gph_sum = float(result[6] or 0)
            moving_count = int(result[7] or 0)
            consumption_gph_sum = float(result[8] or 0)
            consumption_count = int(result[9] or 0)

            # Calculate weighted averages
            fleet_avg_mpg = mpg_sum / mpg_count if mpg_count > 0 else 0
            avg_idle_gph = idle_gph_sum / idle_count if idle_count > 0 else 0
            avg_moving_gph = moving_gph_sum / moving_count if moving_count > 0 else 0
            avg_consumption_gph = (
                consumption_gph_sum / consumption_count if consumption_count > 0 else 0
            )

            # Each record represents ~1 minute interval
            record_interval_hours = 1 / 60  # 1 minute = 1/60 hour

            # Moving fuel consumed
            moving_fuel_gal = moving_count * record_interval_hours * avg_moving_gph

            # Total fuel = all consumption (moving + idle)
            total_fuel_gal = (
                consumption_count * record_interval_hours * avg_consumption_gph
            )

            # Idle waste = idle_count * interval * avg_idle
            total_idle_gal = idle_count * record_interval_hours * avg_idle_gph

            # 🔧 FIX: Distance = moving fuel consumed * MPG
            # This is more accurate than odometer which has noise
            total_distance_mi = (
                moving_fuel_gal * fleet_avg_mpg if fleet_avg_mpg > 0 else 0
            )

            kpi_data = {
                "total_fuel_consumed_gal": round(total_fuel_gal, 2),
                "total_fuel_cost_usd": round(total_fuel_gal * fuel_price_per_gal, 2),
                "total_idle_waste_gal": round(total_idle_gal, 2),
                "total_idle_cost_usd": round(total_idle_gal * fuel_price_per_gal, 2),
                "avg_fuel_price_per_gal": fuel_price_per_gal,
                "total_distance_mi": round(total_distance_mi, 2),
                "fleet_avg_mpg": round(fleet_avg_mpg, 2),
                # Additional context
                "period_days": days_back,
                "truck_count": truck_count,
                "total_records": total_records,
                "avg_idle_gph": round(avg_idle_gph, 3),
            }

            logger.info(
                f"✅ KPIs calculated from MySQL: {truck_count} trucks, {total_records} records, {days_back}d period"
            )
            return kpi_data

    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")
        return _empty_kpi_response(fuel_price_per_gal)


def _empty_kpi_response(fuel_price: float) -> Dict[str, Any]:
    """Return empty KPI response"""
    return {
        "total_fuel_consumed_gal": 0,
        "total_fuel_cost_usd": 0,
        "total_idle_waste_gal": 0,
        "total_idle_cost_usd": 0,
        "avg_fuel_price_per_gal": fuel_price,
        "total_distance_mi": 0,
        "fleet_avg_mpg": 0,
        "period_days": 0,
        "truck_count": 0,
        "total_records": 0,
        "avg_idle_gph": 0,
    }


@cached(ttl_seconds=60, key_prefix="get_loss_analysis")
def get_loss_analysis(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.9.0: Loss Analysis by Root Cause
    🔧 v3.15.0: Added 60-second cache for performance

    Classifies fuel consumption losses into 3 categories:
    1. EXCESSIVE IDLE (~50%): Speed < 5 mph with engine running
    2. HIGH ALTITUDE (~25%): Altitude > 3000 ft affects efficiency
    3. MECHANICAL/DRIVING (~25%): Catch-all for other inefficiencies

    Args:
        days_back: Number of days to analyze (1, 7, or 30)

    Returns:
        Dict with loss breakdown by cause, totals, and per-truck details
    """
    # 🔧 FIX v3.9.2: Use centralized config for baseline values
    BASELINE_MPG = FUEL.BASELINE_MPG
    FUEL_PRICE = FUEL.PRICE_PER_GALLON

    query = text(
        """
        SELECT 
            truck_id,
            -- Classify each record by root cause
            SUM(CASE 
                WHEN truck_status = 'STOPPED' AND consumption_gph > 0.1 
                THEN consumption_gph 
                ELSE 0 
            END) as idle_consumption_sum,
            SUM(CASE 
                WHEN truck_status = 'STOPPED' AND consumption_gph > 0.1 
                THEN 1 ELSE 0 
            END) as idle_records,
            
            -- High altitude (> 3000 ft while moving)
            SUM(CASE 
                WHEN truck_status = 'MOVING' AND altitude_ft > 3000 
                AND mpg_current > 0 AND mpg_current < :baseline_mpg
                THEN (:baseline_mpg - mpg_current) / :baseline_mpg * consumption_gph
                ELSE 0 
            END) as altitude_loss_sum,
            SUM(CASE 
                WHEN truck_status = 'MOVING' AND altitude_ft > 3000 
                THEN 1 ELSE 0 
            END) as altitude_records,
            
            -- Moving stats for efficiency calculation
            SUM(CASE 
                WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12
                THEN mpg_current ELSE 0 
            END) as mpg_sum,
            SUM(CASE 
                WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12
                THEN 1 ELSE 0 
            END) as mpg_count,
            SUM(CASE 
                WHEN truck_status = 'MOVING' AND consumption_gph > 0.5
                THEN consumption_gph ELSE 0 
            END) as moving_consumption_sum,
            SUM(CASE 
                WHEN truck_status = 'MOVING' AND consumption_gph > 0.5
                THEN 1 ELSE 0 
            END) as moving_records,
            
            -- Average metrics
            AVG(CASE WHEN altitude_ft > 0 THEN altitude_ft END) as avg_altitude,
            AVG(CASE WHEN speed_mph > 0 THEN speed_mph END) as avg_speed,
            AVG(CASE WHEN rpm > 0 THEN rpm END) as avg_rpm
            
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        GROUP BY truck_id
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            results = conn.execute(
                query, {"days_back": days_back, "baseline_mpg": BASELINE_MPG}
            ).fetchall()

            if not results:
                return _empty_loss_response(days_back, FUEL_PRICE)

            # Process each truck
            trucks_analysis = []
            totals: Dict[str, float] = {
                "idle_loss_gal": 0.0,
                "altitude_loss_gal": 0.0,
                "mechanical_loss_gal": 0.0,
                "total_loss_gal": 0.0,
            }

            record_interval = 1 / 60  # 1 minute per record

            for row in results:
                truck_id = row[0]

                # Idle loss
                idle_sum = float(row[1] or 0)
                idle_records = int(row[2] or 0)
                idle_loss_gal = (
                    idle_records
                    * record_interval
                    * (idle_sum / idle_records if idle_records > 0 else 0)
                )

                # Altitude loss
                altitude_loss_sum = float(row[3] or 0)
                altitude_records = int(row[4] or 0)
                altitude_loss_gal = (
                    altitude_records
                    * record_interval
                    * (
                        altitude_loss_sum / altitude_records
                        if altitude_records > 0
                        else 0
                    )
                )

                # Calculate actual vs expected consumption
                mpg_sum = float(row[5] or 0)
                mpg_count = int(row[6] or 0)
                actual_mpg = mpg_sum / mpg_count if mpg_count > 0 else BASELINE_MPG

                moving_consumption_sum = float(row[7] or 0)
                moving_records = int(row[8] or 0)
                moving_fuel = (
                    moving_records
                    * record_interval
                    * (
                        moving_consumption_sum / moving_records
                        if moving_records > 0
                        else 0
                    )
                )

                # Expected fuel at baseline MPG
                distance_traveled = moving_fuel * actual_mpg if actual_mpg > 0 else 0
                expected_fuel = (
                    distance_traveled / BASELINE_MPG if BASELINE_MPG > 0 else 0
                )

                # Mechanical/driving loss = actual - expected - idle - altitude
                total_actual = moving_fuel + idle_loss_gal
                total_excess = max(0, total_actual - expected_fuel)
                mechanical_loss_gal = max(
                    0, total_excess - idle_loss_gal - altitude_loss_gal
                )

                # Classify truck efficiency
                if actual_mpg >= BASELINE_MPG:
                    classification = "ALTA"
                    efficiency_status = "En Rango"
                elif actual_mpg >= BASELINE_MPG * 0.85:
                    classification = "EN_RANGO"
                    efficiency_status = "Esperado"
                else:
                    classification = "BAJA"
                    efficiency_status = "Anómala"

                # Determine probable cause
                if (
                    idle_loss_gal > altitude_loss_gal
                    and idle_loss_gal > mechanical_loss_gal
                ):
                    probable_cause = "RALENTÍ EXCESIVO"
                elif altitude_loss_gal > mechanical_loss_gal:
                    probable_cause = "ALTA ALTITUD"
                elif mechanical_loss_gal > 0:
                    probable_cause = "FALLA MECÁNICA/CONDUCCIÓN"
                else:
                    probable_cause = "N/A"

                avg_altitude = float(row[9] or 0)
                avg_speed = float(row[10] or 0)
                avg_rpm = float(row[11] or 0)

                truck_analysis = {
                    "truck_id": truck_id,
                    "classification": classification,
                    "efficiency_status": efficiency_status,
                    "probable_cause": probable_cause,
                    "actual_mpg": round(actual_mpg, 2),
                    "baseline_mpg": BASELINE_MPG,
                    "idle_loss_gal": round(idle_loss_gal, 2),
                    "altitude_loss_gal": round(altitude_loss_gal, 2),
                    "mechanical_loss_gal": round(mechanical_loss_gal, 2),
                    "total_loss_gal": round(
                        idle_loss_gal + altitude_loss_gal + mechanical_loss_gal, 2
                    ),
                    "idle_loss_usd": round(idle_loss_gal * FUEL_PRICE, 2),
                    "altitude_loss_usd": round(altitude_loss_gal * FUEL_PRICE, 2),
                    "mechanical_loss_usd": round(mechanical_loss_gal * FUEL_PRICE, 2),
                    "total_loss_usd": round(
                        (idle_loss_gal + altitude_loss_gal + mechanical_loss_gal)
                        * FUEL_PRICE,
                        2,
                    ),
                    "avg_altitude_ft": round(avg_altitude, 0),
                    "avg_speed_mph": round(avg_speed, 1),
                    "avg_rpm": round(avg_rpm, 0),
                }

                trucks_analysis.append(truck_analysis)

                # Accumulate totals
                totals["idle_loss_gal"] += idle_loss_gal
                totals["altitude_loss_gal"] += altitude_loss_gal
                totals["mechanical_loss_gal"] += mechanical_loss_gal

            totals["total_loss_gal"] = (
                totals["idle_loss_gal"]
                + totals["altitude_loss_gal"]
                + totals["mechanical_loss_gal"]
            )

            # Sort by total loss descending
            trucks_analysis.sort(key=lambda x: x["total_loss_gal"], reverse=True)

            # Calculate percentages
            total = totals["total_loss_gal"] if totals["total_loss_gal"] > 0 else 1

            response = {
                "period_days": days_back,
                "truck_count": len(trucks_analysis),
                "fuel_price_per_gal": FUEL_PRICE,
                "baseline_mpg": BASELINE_MPG,
                "summary": {
                    "total_loss_gal": round(totals["total_loss_gal"], 2),
                    "total_loss_usd": round(totals["total_loss_gal"] * FUEL_PRICE, 2),
                    "by_cause": {
                        "idle": {
                            "gallons": round(totals["idle_loss_gal"], 2),
                            "usd": round(totals["idle_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                totals["idle_loss_gal"] / total * 100, 1
                            ),
                        },
                        "altitude": {
                            "gallons": round(totals["altitude_loss_gal"], 2),
                            "usd": round(totals["altitude_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                totals["altitude_loss_gal"] / total * 100, 1
                            ),
                        },
                        "mechanical": {
                            "gallons": round(totals["mechanical_loss_gal"], 2),
                            "usd": round(totals["mechanical_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                totals["mechanical_loss_gal"] / total * 100, 1
                            ),
                        },
                    },
                },
                "trucks": trucks_analysis,
            }

            logger.info(
                f"✅ Loss analysis: {len(trucks_analysis)} trucks, ${response['summary']['total_loss_usd']} total loss"
            )
            return response

    except Exception as e:
        logger.error(f"Error in loss analysis: {e}")
        return _empty_loss_response(days_back, FUEL_PRICE)


def _empty_loss_response(days: int, price: float) -> Dict[str, Any]:
    """Return empty loss analysis response"""
    return {
        "period_days": days,
        "truck_count": 0,
        "fuel_price_per_gal": price,
        "baseline_mpg": 5.7,
        "summary": {
            "total_loss_gal": 0,
            "total_loss_usd": 0,
            "by_cause": {
                "idle": {"gallons": 0, "usd": 0, "percentage": 0},
                "altitude": {"gallons": 0, "usd": 0, "percentage": 0},
                "mechanical": {"gallons": 0, "usd": 0, "percentage": 0},
            },
        },
        "trucks": [],
    }


# =============================================================================
# 🚀 ANALYTICS v3.10.0: World-Class Fleet Intelligence
# =============================================================================


@cached(ttl_seconds=60, key_prefix="get_driver_scorecard")
def get_driver_scorecard(days_back: int = 7) -> Dict[str, Any]:
    """
    🆕 v3.10.0: Comprehensive Driver Scorecard System
    🆕 v3.12.22: Cached for 60 seconds

    Calculates multi-dimensional driver scores based on:
    1. Speed Optimization (0-100): % time at optimal speed (55-65 mph)
    2. RPM Discipline (0-100): % time at efficient RPM (1200-1600)
    3. Idle Management (0-100): Inverse of idle time vs fleet avg
    4. Fuel Consistency (0-100): Low variability = better consistency
    5. MPG Performance (0-100): Actual MPG vs baseline

    Returns ranking with overall score and breakdown per driver/truck
    """
    BASELINE_MPG = FUEL.BASELINE_MPG
    OPTIMAL_SPEED_MIN = 55.0
    OPTIMAL_SPEED_MAX = 65.0
    OPTIMAL_RPM_MIN = 1200
    OPTIMAL_RPM_MAX = 1600

    query = text(
        """
        SELECT 
            truck_id,
            
            -- Speed Analysis
            COUNT(CASE WHEN truck_status = 'MOVING' AND speed_mph BETWEEN :speed_min AND :speed_max THEN 1 END) as optimal_speed_count,
            COUNT(CASE WHEN truck_status = 'MOVING' AND speed_mph > 5 THEN 1 END) as total_moving_count,
            AVG(CASE WHEN truck_status = 'MOVING' THEN speed_mph END) as avg_speed,
            MAX(CASE WHEN truck_status = 'MOVING' THEN speed_mph END) as max_speed,
            
            -- RPM Analysis  
            COUNT(CASE WHEN rpm BETWEEN :rpm_min AND :rpm_max THEN 1 END) as optimal_rpm_count,
            COUNT(CASE WHEN rpm > 0 THEN 1 END) as total_rpm_count,
            AVG(CASE WHEN rpm > 0 THEN rpm END) as avg_rpm,
            
            -- Idle Analysis
            COUNT(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN 1 END) as idle_count,
            SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph ELSE 0 END) as idle_consumption_sum,
            
            -- Fuel Consistency
            AVG(CASE WHEN consumption_gph > 0 THEN consumption_gph END) as avg_consumption,
            STDDEV(CASE WHEN consumption_gph > 0 THEN consumption_gph END) as consumption_stddev,
            
            -- MPG Performance
            AVG(CASE WHEN mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
            MAX(CASE WHEN mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as best_mpg,
            MIN(CASE WHEN mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as worst_mpg,
            
            -- Total Records
            COUNT(*) as total_records,
            
            -- Distance (use odom_delta_mi sum for accurate mileage)
            -- 🔧 v6.2.1: Increased delta limit from 10 to 50 miles (trucks at 60mph can do 5mi in 5min intervals)
            SUM(CASE WHEN odom_delta_mi > 0 AND odom_delta_mi < 50 THEN odom_delta_mi ELSE 0 END) as total_miles
            
        FROM fuel_metrics
        WHERE timestamp_utc > UTC_TIMESTAMP() - INTERVAL :days_back DAY
        GROUP BY truck_id
        HAVING total_records > 5
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            results = conn.execute(
                query,
                {
                    "days_back": days_back,
                    "speed_min": OPTIMAL_SPEED_MIN,
                    "speed_max": OPTIMAL_SPEED_MAX,
                    "rpm_min": OPTIMAL_RPM_MIN,
                    "rpm_max": OPTIMAL_RPM_MAX,
                },
            ).fetchall()

            if not results:
                return {"period_days": days_back, "drivers": [], "fleet_avg": {}}

            # Calculate fleet averages for comparison
            fleet_idle_avg = sum(r[8] for r in results) / len(results) if results else 0
            fleet_mpg_avg = (
                sum(r[12] or 0 for r in results) / len([r for r in results if r[12]])
                if results
                else BASELINE_MPG
            )

            drivers = []
            for row in results:
                truck_id = row[0]

                # 1. Speed Optimization Score (0-100)
                optimal_speed = int(row[1] or 0)
                total_moving = int(row[2] or 1)
                speed_score = (
                    min(100, (optimal_speed / max(total_moving, 1)) * 100)
                    if total_moving > 0
                    else 50
                )

                # 2. RPM Discipline Score (0-100)
                optimal_rpm = int(row[5] or 0)
                total_rpm = int(row[6] or 1)
                rpm_score = (
                    min(100, (optimal_rpm / max(total_rpm, 1)) * 100)
                    if total_rpm > 0
                    else 50
                )

                # 3. Idle Management Score (0-100) - Lower idle = better score
                idle_count = int(row[8] or 0)
                total_records = int(row[15] or 1)
                idle_pct = (
                    (idle_count / total_records) * 100 if total_records > 0 else 0
                )
                fleet_idle_pct = (
                    (fleet_idle_avg / total_records) * 100 if total_records > 0 else 10
                )
                # Score: 100 if no idle, 0 if 2x fleet average
                idle_score = max(
                    0, min(100, 100 - (idle_pct / max(fleet_idle_pct * 2, 1)) * 100)
                )

                # 4. Fuel Consistency Score (0-100) - Lower variability = better
                avg_consumption = float(row[10] or 1)
                consumption_stddev = float(row[11] or 0)
                cv = (
                    (consumption_stddev / avg_consumption) if avg_consumption > 0 else 0
                )
                # CV of 0 = 100 points, CV of 0.5+ = 0 points
                consistency_score = max(0, min(100, 100 - (cv * 200)))

                # 5. MPG Performance Score (0-100)
                avg_mpg = float(row[12] or BASELINE_MPG)
                # Score based on % of baseline achieved: 100% = 100 points, 70% = 0 points
                mpg_ratio = avg_mpg / BASELINE_MPG if BASELINE_MPG > 0 else 1
                mpg_score = max(0, min(100, (mpg_ratio - 0.7) / 0.3 * 100))

                # Overall Score (weighted average)
                weights = {
                    "speed": 0.15,
                    "rpm": 0.15,
                    "idle": 0.30,
                    "consistency": 0.10,
                    "mpg": 0.30,
                }
                overall_score = (
                    speed_score * weights["speed"]
                    + rpm_score * weights["rpm"]
                    + idle_score * weights["idle"]
                    + consistency_score * weights["consistency"]
                    + mpg_score * weights["mpg"]
                )

                # Grade assignment
                if overall_score >= 90:
                    grade = "A+"
                elif overall_score >= 80:
                    grade = "A"
                elif overall_score >= 70:
                    grade = "B"
                elif overall_score >= 60:
                    grade = "C"
                else:
                    grade = "D"

                drivers.append(
                    {
                        "truck_id": truck_id,
                        "overall_score": round(overall_score, 1),
                        "grade": grade,
                        "scores": {
                            "speed_optimization": round(speed_score, 1),
                            "rpm_discipline": round(rpm_score, 1),
                            "idle_management": round(idle_score, 1),
                            "fuel_consistency": round(consistency_score, 1),
                            "mpg_performance": round(mpg_score, 1),
                        },
                        "metrics": {
                            "avg_speed_mph": round(float(row[3] or 0), 1),
                            "max_speed_mph": round(float(row[4] or 0), 1),
                            "avg_rpm": round(float(row[7] or 0), 0),
                            "idle_pct": round(idle_pct, 1),
                            "avg_mpg": round(avg_mpg, 2),
                            "best_mpg": round(float(row[13] or 0), 2),
                            "worst_mpg": round(float(row[14] or 0), 2),
                            "total_miles": round(float(row[16] or 0), 1),
                        },
                    }
                )

            # 🔧 FIX v3.10.2: Filter out drivers with 0 miles (no activity)
            drivers = [d for d in drivers if d["metrics"]["total_miles"] > 1]

            # Sort by overall score descending
            drivers.sort(key=lambda x: x["overall_score"], reverse=True)

            # Add rank
            for i, driver in enumerate(drivers, 1):
                driver["rank"] = i

            # 🔧 v6.2.1: Calculate fleet idle % correctly
            # fleet_idle_avg = sum of all idle_counts
            # We need to divide by total of all records across all trucks
            total_fleet_records = (
                sum(int(r[15] or 0) for r in results) if results else 1
            )
            fleet_idle_pct_correct = (
                (fleet_idle_avg / max(total_fleet_records, 1)) * 100 if results else 0
            )

            return {
                "period_days": days_back,
                "driver_count": len(drivers),
                "fleet_avg": {
                    "mpg": round(fleet_mpg_avg, 2),
                    "idle_pct": round(
                        min(fleet_idle_pct_correct, 100), 1
                    ),  # Cap at 100%
                    "baseline_mpg": BASELINE_MPG,
                },
                "drivers": drivers,
                "weights": weights,
            }

    except Exception as e:
        logger.error(f"Error in driver scorecard: {e}")
        return {
            "period_days": days_back,
            "drivers": [],
            "fleet_avg": {},
            "error": str(e),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVER SCORE HISTORY v1.1.0
# ═══════════════════════════════════════════════════════════════════════════════


def ensure_driver_score_history_table() -> bool:
    """Create driver_score_history table if not exists"""
    create_sql = """
    CREATE TABLE IF NOT EXISTS driver_score_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        truck_id VARCHAR(50) NOT NULL,
        record_date DATE NOT NULL,
        overall_score DECIMAL(5,1) NOT NULL,
        grade VARCHAR(5) NOT NULL,
        speed_score DECIMAL(5,1),
        rpm_score DECIMAL(5,1),
        idle_score DECIMAL(5,1),
        consistency_score DECIMAL(5,1),
        mpg_score DECIMAL(5,1),
        avg_mpg DECIMAL(5,2),
        total_miles DECIMAL(10,1),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY idx_truck_date (truck_id, record_date),
        INDEX idx_record_date (record_date),
        INDEX idx_truck_id (truck_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()
        logger.info("✅ driver_score_history table ready")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Could not create driver_score_history table: {e}")
        return False


def save_driver_score_history(
    drivers: List[Dict[str, Any]], record_date: Optional[str] = None
) -> int:
    """
    Save daily driver scores to history table for trend analysis.

    Args:
        drivers: List of driver dicts from get_driver_scorecard
        record_date: Date string YYYY-MM-DD, defaults to today

    Returns:
        Number of records saved
    """
    if not drivers:
        return 0

    ensure_driver_score_history_table()

    if record_date is None:
        record_date = datetime.now().strftime("%Y-%m-%d")

    insert_sql = """
    INSERT INTO driver_score_history 
        (truck_id, record_date, overall_score, grade, speed_score, rpm_score, 
         idle_score, consistency_score, mpg_score, avg_mpg, total_miles)
    VALUES 
        (:truck_id, :record_date, :overall_score, :grade, :speed_score, :rpm_score,
         :idle_score, :consistency_score, :mpg_score, :avg_mpg, :total_miles)
    ON DUPLICATE KEY UPDATE
        overall_score = VALUES(overall_score),
        grade = VALUES(grade),
        speed_score = VALUES(speed_score),
        rpm_score = VALUES(rpm_score),
        idle_score = VALUES(idle_score),
        consistency_score = VALUES(consistency_score),
        mpg_score = VALUES(mpg_score),
        avg_mpg = VALUES(avg_mpg),
        total_miles = VALUES(total_miles)
    """

    try:
        engine = get_sqlalchemy_engine()
        saved = 0
        with engine.connect() as conn:
            for driver in drivers:
                scores = driver.get("scores", {})
                metrics = driver.get("metrics", {})
                conn.execute(
                    text(insert_sql),
                    {
                        "truck_id": driver.get("truck_id"),
                        "record_date": record_date,
                        "overall_score": driver.get("overall_score", 0),
                        "grade": driver.get("grade", "N/A"),
                        "speed_score": scores.get("speed_optimization", 0),
                        "rpm_score": scores.get("rpm_discipline", 0),
                        "idle_score": scores.get("idle_management", 0),
                        "consistency_score": scores.get("fuel_consistency", 0),
                        "mpg_score": scores.get("mpg_performance", 0),
                        "avg_mpg": metrics.get("avg_mpg", 0),
                        "total_miles": metrics.get("total_miles", 0),
                    },
                )
                saved += 1
            conn.commit()
        logger.info(f"✅ Saved {saved} driver score history records for {record_date}")
        return saved
    except Exception as e:
        logger.error(f"❌ Error saving driver score history: {e}")
        return 0


def get_driver_score_history(
    truck_id: str, days_back: int = 30
) -> List[Dict[str, Any]]:
    """
    Get historical scores for a specific driver/truck.

    Args:
        truck_id: Truck identifier
        days_back: Number of days of history to retrieve

    Returns:
        List of historical score records, newest first
    """
    query = text(
        """
        SELECT 
            truck_id,
            record_date,
            overall_score,
            grade,
            speed_score,
            rpm_score,
            idle_score,
            consistency_score,
            mpg_score,
            avg_mpg,
            total_miles
        FROM driver_score_history
        WHERE truck_id = :truck_id
          AND record_date >= DATE_SUB(CURDATE(), INTERVAL :days_back DAY)
        ORDER BY record_date DESC
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            results = conn.execute(
                query,
                {
                    "truck_id": truck_id,
                    "days_back": days_back,
                },
            ).fetchall()

            history = []
            for row in results:
                history.append(
                    {
                        "truck_id": row[0],
                        "date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                        "overall_score": float(row[2]) if row[2] else 0,
                        "grade": row[3],
                        "scores": {
                            "speed_optimization": float(row[4]) if row[4] else 0,
                            "rpm_discipline": float(row[5]) if row[5] else 0,
                            "idle_management": float(row[6]) if row[6] else 0,
                            "fuel_consistency": float(row[7]) if row[7] else 0,
                            "mpg_performance": float(row[8]) if row[8] else 0,
                        },
                        "avg_mpg": float(row[9]) if row[9] else 0,
                        "total_miles": float(row[10]) if row[10] else 0,
                    }
                )
            return history
    except Exception as e:
        logger.error(f"Error getting driver score history: {e}")
        return []


def get_driver_score_trend(truck_id: str, days_back: int = 30) -> Dict[str, Any]:
    """
    Analyze score trend for a driver - is performance improving or declining?

    Returns:
        Dict with trend analysis including direction, rate of change, and insight
    """
    history = get_driver_score_history(truck_id, days_back)

    if len(history) < 2:
        return {
            "truck_id": truck_id,
            "trend": "insufficient_data",
            "data_points": len(history),
            "message": "Need at least 2 days of history for trend analysis",
        }

    # Calculate trend (simple linear regression)
    scores = [h["overall_score"] for h in reversed(history)]  # Oldest first
    n = len(scores)

    # Calculate slope using least squares
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n

    numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator != 0 else 0

    # Determine trend direction and strength
    if slope > 1.0:
        trend = "improving_fast"
        direction = "↑↑"
        color = "green"
    elif slope > 0.2:
        trend = "improving"
        direction = "↑"
        color = "green"
    elif slope < -1.0:
        trend = "declining_fast"
        direction = "↓↓"
        color = "red"
    elif slope < -0.2:
        trend = "declining"
        direction = "↓"
        color = "red"
    else:
        trend = "stable"
        direction = "→"
        color = "yellow"

    # Calculate improvement percentage
    first_week_avg = sum(scores[:7]) / min(7, len(scores))
    last_week_avg = sum(scores[-7:]) / min(7, len(scores))
    improvement_pct = (
        ((last_week_avg - first_week_avg) / first_week_avg * 100)
        if first_week_avg > 0
        else 0
    )

    # Generate insight
    current_score = scores[-1]
    if trend in ["improving", "improving_fast"]:
        insight = f"Great progress! Score improved by {abs(improvement_pct):.1f}% over {days_back} days."
    elif trend in ["declining", "declining_fast"]:
        insight = f"Attention needed. Score dropped {abs(improvement_pct):.1f}% over {days_back} days."
    else:
        insight = f"Consistent performance at {current_score:.0f} points."

    return {
        "truck_id": truck_id,
        "trend": trend,
        "trend_direction": direction,
        "trend_color": color,
        "slope_per_day": round(slope, 2),
        "improvement_pct": round(improvement_pct, 1),
        "data_points": n,
        "current_score": current_score,
        "first_score": scores[0],
        "insight": insight,
        "history_summary": {
            "best_score": max(scores),
            "worst_score": min(scores),
            "avg_score": round(sum(scores) / n, 1),
        },
    }


@cached(ttl_seconds=60, key_prefix="get_enhanced_kpis")
def get_enhanced_kpis(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.10.0: Enhanced KPI Dashboard with Fleet Health Index
    🔧 v3.15.0: Added 60-second cache for performance

    Provides comprehensive financial intelligence:
    - Fleet Health Index (composite score)
    - Fuel cost breakdown by category
    - ROI and cost-per-mile analysis
    - Savings opportunity matrix
    - Trend analysis and predictions
    """
    FUEL_PRICE = FUEL.PRICE_PER_GALLON
    BASELINE_MPG = FUEL.BASELINE_MPG

    query = text(
        """
        SELECT 
            -- Counts
            COUNT(DISTINCT truck_id) as truck_count,
            COUNT(*) as total_records,
            
            -- Moving consumption
            SUM(CASE WHEN truck_status = 'MOVING' AND consumption_gph > 0.5 THEN consumption_gph ELSE 0 END) as moving_gph_sum,
            COUNT(CASE WHEN truck_status = 'MOVING' AND consumption_gph > 0.5 THEN 1 END) as moving_count,
            
            -- Idle consumption  
            SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.1 THEN consumption_gph ELSE 0 END) as idle_gph_sum,
            COUNT(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.1 THEN 1 END) as idle_count,
            
            -- MPG analysis (ONLY from MOVING trucks - v4.2 fix)
            AVG(CASE WHEN truck_status = 'MOVING' AND mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
            
            -- Distance
            SUM(CASE WHEN odom_delta_mi > 0 AND odom_delta_mi < 10 THEN odom_delta_mi ELSE 0 END) as total_miles,
            
            -- Altitude impact (high altitude = >3000ft)
            COUNT(CASE WHEN altitude_ft > 3000 AND truck_status = 'MOVING' THEN 1 END) as high_altitude_count,
            COUNT(CASE WHEN truck_status = 'MOVING' THEN 1 END) as total_moving_for_altitude,
            
            -- RPM inefficiency (>1800 RPM = inefficient)
            COUNT(CASE WHEN rpm > 1800 AND truck_status = 'MOVING' THEN 1 END) as high_rpm_count,
            COUNT(CASE WHEN rpm > 0 AND truck_status = 'MOVING' THEN 1 END) as total_rpm_count,
            
            -- Speed issues (>70 mph = fuel waste)
            COUNT(CASE WHEN speed_mph > 70 AND truck_status = 'MOVING' THEN 1 END) as overspeeding_count
            
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(query, {"days_back": days_back}).fetchone()

            if not result:
                return _empty_enhanced_kpis(days_back, FUEL_PRICE)

            truck_count = int(result[0] or 0)
            total_records = int(result[1] or 0)

            # Calculate fuel consumed (convert GPH counts to gallons)
            # Each record = 1 minute, so gallons = GPH_sum * (count/60)
            record_interval = 1 / 60  # 1 minute per record

            moving_gph_sum = float(result[2] or 0)
            moving_count = int(result[3] or 0)
            moving_gallons = (
                moving_count
                * record_interval
                * (moving_gph_sum / moving_count if moving_count > 0 else 0)
            )

            idle_gph_sum = float(result[4] or 0)
            idle_count = int(result[5] or 0)
            idle_gallons = (
                idle_count
                * record_interval
                * (idle_gph_sum / idle_count if idle_count > 0 else 0)
            )

            total_gallons = moving_gallons + idle_gallons

            # MPG analysis
            avg_mpg = float(result[6] or BASELINE_MPG)

            # 🔧 v3.15.2: Calculate total_miles from odometer OR from fuel/MPG
            # odom_delta_mi is often NULL/0 due to sensor issues
            odom_miles = float(result[7] or 0)

            # If no odometer data, estimate miles from: miles = gallons × MPG
            if odom_miles < 1 and avg_mpg > 0 and moving_gallons > 0:
                total_miles = moving_gallons * avg_mpg
                logger.info(
                    f"📏 Estimated miles from fuel: {moving_gallons:.1f} gal × {avg_mpg:.1f} MPG = {total_miles:.1f} mi"
                )
            else:
                total_miles = odom_miles

            # Calculate cost breakdown
            moving_cost = moving_gallons * FUEL_PRICE
            idle_cost = idle_gallons * FUEL_PRICE
            total_cost = total_gallons * FUEL_PRICE

            # Calculate potential savings
            # If fleet achieved baseline MPG, how much would be saved?
            expected_gallons_at_baseline = (
                total_miles / BASELINE_MPG if BASELINE_MPG > 0 else total_gallons
            )
            mpg_savings_potential = max(
                0, (moving_gallons - expected_gallons_at_baseline) * FUEL_PRICE
            )

            # Idle savings (if idle was reduced by 50%)
            idle_savings_potential = idle_cost * 0.5

            total_savings_potential = mpg_savings_potential + idle_savings_potential

            # Fleet Health Index (0-100)
            # Components: MPG ratio (40%), idle % (30%), high RPM % (15%), overspeeding % (15%)
            mpg_ratio = avg_mpg / BASELINE_MPG if BASELINE_MPG > 0 else 1
            mpg_health = min(100, mpg_ratio * 100)

            idle_pct = (idle_count / total_records * 100) if total_records > 0 else 0
            idle_health = max(0, 100 - idle_pct * 5)  # 20% idle = 0 health

            high_rpm_pct = (int(result[10] or 0) / max(int(result[11] or 1), 1)) * 100
            rpm_health = max(0, 100 - high_rpm_pct * 2)  # 50% high RPM = 0 health

            overspeeding_pct = (
                int(result[12] or 0) / max(int(result[9] or 1), 1)
            ) * 100
            speed_health = max(
                0, 100 - overspeeding_pct * 5
            )  # 20% overspeeding = 0 health

            fleet_health_index = (
                mpg_health * 0.40
                + idle_health * 0.30
                + rpm_health * 0.15
                + speed_health * 0.15
            )

            # High altitude impact
            high_alt_count = int(result[8] or 0)
            total_moving_alt = int(result[9] or 1)
            high_altitude_pct = (
                (high_alt_count / total_moving_alt * 100) if total_moving_alt > 0 else 0
            )

            # Projections (multiply by working days)
            if days_back == 1:
                monthly_multiplier = 22  # Working days per month
                annual_multiplier = 260  # Working days per year
            elif days_back == 7:
                monthly_multiplier = 4.3  # Weeks per month
                annual_multiplier = 52  # Weeks per year
            else:
                monthly_multiplier = 1
                annual_multiplier = 12

            return {
                "period_days": days_back,
                "truck_count": truck_count,
                "fuel_price_per_gal": FUEL_PRICE,
                "fleet_health": {
                    "index": round(fleet_health_index, 1),
                    "grade": (
                        "A"
                        if fleet_health_index >= 80
                        else (
                            "B"
                            if fleet_health_index >= 60
                            else "C" if fleet_health_index >= 40 else "D"
                        )
                    ),
                    "components": {
                        "mpg_health": round(mpg_health, 1),
                        "idle_health": round(idle_health, 1),
                        "rpm_health": round(rpm_health, 1),
                        "speed_health": round(speed_health, 1),
                    },
                },
                "fuel_consumption": {
                    "total_gallons": round(total_gallons, 2),
                    "moving_gallons": round(moving_gallons, 2),
                    "idle_gallons": round(idle_gallons, 2),
                    "idle_percentage": round(
                        (
                            (idle_gallons / total_gallons * 100)
                            if total_gallons > 0
                            else 0
                        ),
                        1,
                    ),
                },
                "costs": {
                    "total_cost": round(total_cost, 2),
                    "moving_cost": round(moving_cost, 2),
                    "idle_cost": round(idle_cost, 2),
                    "cost_per_mile": round(
                        (total_cost / total_miles) if total_miles > 0 else 0, 3
                    ),
                    "cost_per_truck": round(
                        (total_cost / truck_count) if truck_count > 0 else 0, 2
                    ),
                },
                "efficiency": {
                    "avg_mpg": round(avg_mpg, 2),
                    "baseline_mpg": BASELINE_MPG,
                    "mpg_gap": round(BASELINE_MPG - avg_mpg, 2),
                    "mpg_achievement_pct": round(mpg_ratio * 100, 1),
                    "total_miles": round(total_miles, 1),
                },
                "inefficiency_breakdown": {
                    "idle_pct": round(idle_pct, 1),
                    "high_rpm_pct": round(high_rpm_pct, 1),
                    "overspeeding_pct": round(overspeeding_pct, 1),
                    "high_altitude_pct": round(high_altitude_pct, 1),
                },
                "savings_potential": {
                    "from_mpg_improvement": round(mpg_savings_potential, 2),
                    "from_idle_reduction": round(idle_savings_potential, 2),
                    "total_potential": round(total_savings_potential, 2),
                    "potential_pct": round(
                        (
                            (total_savings_potential / total_cost * 100)
                            if total_cost > 0
                            else 0
                        ),
                        1,
                    ),
                },
                "projections": {
                    "daily": {
                        "cost": round(
                            (total_cost / days_back if days_back > 0 else total_cost),
                            2,
                        ),
                        "gallons": round(
                            (
                                total_gallons / days_back
                                if days_back > 0
                                else total_gallons
                            ),
                            2,
                        ),
                        "miles": round(
                            (total_miles / days_back if days_back > 0 else total_miles),
                            1,
                        ),
                    },
                    "monthly": {
                        "cost": round(
                            (
                                (total_cost / days_back * monthly_multiplier)
                                if days_back > 0
                                else 0
                            ),
                            2,
                        ),
                        "gallons": round(
                            (
                                (total_gallons / days_back * monthly_multiplier)
                                if days_back > 0
                                else 0
                            ),
                            2,
                        ),
                        "savings_potential": round(
                            (
                                (
                                    total_savings_potential
                                    / days_back
                                    * monthly_multiplier
                                )
                                if days_back > 0
                                else 0
                            ),
                            2,
                        ),
                    },
                    "annual": {
                        "cost": round(
                            (
                                (total_cost / days_back * annual_multiplier)
                                if days_back > 0
                                else 0
                            ),
                            2,
                        ),
                        "gallons": round(
                            (
                                (total_gallons / days_back * annual_multiplier)
                                if days_back > 0
                                else 0
                            ),
                            2,
                        ),
                        "savings_potential": round(
                            (
                                (
                                    total_savings_potential
                                    / days_back
                                    * annual_multiplier
                                )
                                if days_back > 0
                                else 0
                            ),
                            2,
                        ),
                    },
                },
            }

    except Exception as e:
        logger.error(f"Error in enhanced KPIs: {e}")
        return _empty_enhanced_kpis(days_back, FUEL_PRICE)


def _empty_enhanced_kpis(days: int, price: float) -> Dict[str, Any]:
    """Return empty enhanced KPI response"""
    return {
        "period_days": days,
        "truck_count": 0,
        "fuel_price_per_gal": price,
        "fleet_health": {"index": 0, "grade": "N/A", "components": {}},
        "fuel_consumption": {
            "total_gallons": 0,
            "moving_gallons": 0,
            "idle_gallons": 0,
            "idle_percentage": 0,
        },
        "costs": {
            "total_cost": 0,
            "moving_cost": 0,
            "idle_cost": 0,
            "cost_per_mile": 0,
            "cost_per_truck": 0,
        },
        "efficiency": {
            "avg_mpg": 0,
            "baseline_mpg": 5.7,
            "mpg_gap": 0,
            "mpg_achievement_pct": 0,
            "total_miles": 0,
        },
        "inefficiency_breakdown": {
            "idle_pct": 0,
            "high_rpm_pct": 0,
            "overspeeding_pct": 0,
            "high_altitude_pct": 0,
        },
        "savings_potential": {
            "from_mpg_improvement": 0,
            "from_idle_reduction": 0,
            "total_potential": 0,
            "potential_pct": 0,
        },
        "projections": {"daily": {}, "monthly": {}, "annual": {}},
    }


@cached(ttl_seconds=60, key_prefix="get_enhanced_loss_analysis")
def get_enhanced_loss_analysis(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.10.0: Enhanced Loss Analysis with Root Cause Intelligence
    🆕 v3.12.22: Cached for 60 seconds

    Provides detailed breakdown of fuel losses:
    1. EXCESSIVE IDLE (~50%): Detailed by time patterns, locations
    2. HIGH ALTITUDE (~25%): Route-based analysis, impact quantification
    3. MECHANICAL/DRIVING (~25%):
       - RPM abuse analysis
       - Speed profile analysis
       - Consumption anomalies
       - Coolant temperature issues

    Includes actionable insights with priority and expected ROI
    """
    BASELINE_MPG = FUEL.BASELINE_MPG
    FUEL_PRICE = FUEL.PRICE_PER_GALLON

    query = text(
        """
        SELECT 
            truck_id,
            
            -- Idle Analysis
            COUNT(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN 1 END) as idle_count,
            SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph ELSE 0 END) as idle_gph_sum,
            AVG(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph END) as avg_idle_gph,
            
            -- High Altitude Analysis (>3000 ft)
            COUNT(CASE WHEN altitude_ft > 3000 AND truck_status = 'MOVING' THEN 1 END) as high_alt_count,
            AVG(CASE WHEN altitude_ft > 3000 AND truck_status = 'MOVING' THEN altitude_ft END) as avg_high_altitude,
            SUM(CASE WHEN altitude_ft > 3000 AND truck_status = 'MOVING' THEN consumption_gph ELSE 0 END) as high_alt_consumption,
            
            -- RPM Abuse (>1800 RPM)
            COUNT(CASE WHEN rpm > 1800 AND truck_status = 'MOVING' THEN 1 END) as high_rpm_count,
            SUM(CASE WHEN rpm > 1800 AND truck_status = 'MOVING' THEN consumption_gph ELSE 0 END) as high_rpm_consumption,
            AVG(CASE WHEN rpm > 1800 THEN rpm END) as avg_high_rpm,
            
            -- Overspeeding (>70 mph)
            COUNT(CASE WHEN speed_mph > 70 AND truck_status = 'MOVING' THEN 1 END) as overspeed_count,
            SUM(CASE WHEN speed_mph > 70 AND truck_status = 'MOVING' THEN consumption_gph ELSE 0 END) as overspeed_consumption,
            AVG(CASE WHEN speed_mph > 70 THEN speed_mph END) as avg_overspeed,
            
            -- Coolant Temperature Issues (>220F = overheating)
            COUNT(CASE WHEN coolant_temp_f > 220 THEN 1 END) as overheat_count,
            AVG(CASE WHEN coolant_temp_f > 0 THEN coolant_temp_f END) as avg_coolant_temp,
            
            -- Overall Moving Stats
            COUNT(CASE WHEN truck_status = 'MOVING' THEN 1 END) as moving_count,
            SUM(CASE WHEN truck_status = 'MOVING' THEN consumption_gph ELSE 0 END) as moving_consumption_sum,
            AVG(CASE WHEN mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
            
            -- Distance
            SUM(CASE WHEN odom_delta_mi > 0 AND odom_delta_mi < 10 THEN odom_delta_mi ELSE 0 END) as total_miles,
            
            -- Total records
            COUNT(*) as total_records
            
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        GROUP BY truck_id
        HAVING total_records > 30
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            results = conn.execute(query, {"days_back": days_back}).fetchall()

            if not results:
                return _empty_enhanced_loss_analysis(days_back, FUEL_PRICE)

            record_interval = 1 / 60  # 1 minute per record

            trucks_analysis = []
            totals = {
                "idle_loss_gal": 0,
                "altitude_loss_gal": 0,
                "rpm_loss_gal": 0,
                "speed_loss_gal": 0,
                "thermal_loss_gal": 0,
                "total_loss_gal": 0,
            }

            for row in results:
                truck_id = row[0]

                # Parse row data
                idle_count = int(row[1] or 0)
                idle_gph_sum = float(row[2] or 0)
                avg_idle_gph = float(row[3] or 0.8)

                high_alt_count = int(row[4] or 0)
                avg_high_alt = float(row[5] or 0)
                high_alt_consumption = float(row[6] or 0)

                high_rpm_count = int(row[7] or 0)
                high_rpm_consumption = float(row[8] or 0)
                avg_high_rpm = float(row[9] or 0)

                overspeed_count = int(row[10] or 0)
                overspeed_consumption = float(row[11] or 0)
                avg_overspeed = float(row[12] or 0)

                overheat_count = int(row[13] or 0)
                avg_coolant = float(row[14] or 0)

                moving_count = int(row[15] or 0)
                moving_consumption_sum = float(row[16] or 0)
                avg_mpg = float(row[17] or BASELINE_MPG)

                odom_miles = float(row[18] or 0)
                total_records = int(row[19] or 1)

                # 🔧 v3.15.3: Calculate total_miles from odometer OR from fuel/MPG
                # odom_delta_mi is often NULL/0 due to sensor issues
                moving_gallons = moving_consumption_sum * record_interval
                if odom_miles < 1 and avg_mpg > 0 and moving_gallons > 0:
                    total_miles = moving_gallons * avg_mpg
                    logger.debug(
                        f"📏 [{truck_id}] Estimated miles: {moving_gallons:.1f} gal × {avg_mpg:.1f} MPG = {total_miles:.1f} mi"
                    )
                else:
                    total_miles = odom_miles

                # Calculate losses in gallons
                # 1. Idle Loss
                idle_loss = (
                    idle_count
                    * record_interval
                    * (idle_gph_sum / idle_count if idle_count > 0 else 0)
                )

                # 2. Altitude Loss (estimated 10% efficiency drop per 1000ft above 3000)
                if high_alt_count > 0 and avg_high_alt > 3000:
                    altitude_penalty = min(
                        0.20, (avg_high_alt - 3000) / 10000
                    )  # Max 20% penalty
                    altitude_loss = (
                        high_alt_count
                        * record_interval
                        * (high_alt_consumption / high_alt_count)
                        * altitude_penalty
                    )
                else:
                    altitude_loss = 0

                # 3. RPM Abuse Loss (high RPM wastes ~15% more fuel)
                if high_rpm_count > 0:
                    rpm_penalty = 0.15  # 15% waste at high RPM
                    rpm_loss = (
                        high_rpm_count
                        * record_interval
                        * (high_rpm_consumption / high_rpm_count)
                        * rpm_penalty
                    )
                else:
                    rpm_loss = 0

                # 4. Speed Loss (every mph over 65 = ~2% efficiency loss)
                if overspeed_count > 0:
                    speed_over = avg_overspeed - 65 if avg_overspeed > 65 else 0
                    speed_penalty = min(0.20, speed_over * 0.02)  # Max 20% penalty
                    speed_loss = (
                        overspeed_count
                        * record_interval
                        * (overspeed_consumption / overspeed_count)
                        * speed_penalty
                    )
                else:
                    speed_loss = 0

                # 5. Thermal Loss (overheating = inefficiency)
                if overheat_count > 0:
                    thermal_penalty = 0.10  # 10% efficiency loss when overheating
                    # Estimate consumption during overheat
                    avg_consumption = (
                        moving_consumption_sum / moving_count if moving_count > 0 else 3
                    )
                    thermal_loss = (
                        overheat_count
                        * record_interval
                        * avg_consumption
                        * thermal_penalty
                    )
                else:
                    thermal_loss = 0

                # Total loss for truck
                total_loss = (
                    idle_loss + altitude_loss + rpm_loss + speed_loss + thermal_loss
                )

                # Determine primary cause
                losses_dict: Dict[str, float] = {
                    "RALENTÍ EXCESIVO": float(idle_loss),
                    "ALTA ALTITUD": float(altitude_loss),
                    "RPM ELEVADAS": float(rpm_loss),
                    "EXCESO VELOCIDAD": float(speed_loss),
                    "SOBRECALENTAMIENTO": float(thermal_loss),
                }
                primary_cause = (
                    max(losses_dict.keys(), key=lambda k: losses_dict[k])
                    if total_loss > 0
                    else "N/A"
                )

                # Severity assessment
                if total_loss > 10:
                    severity = "CRÍTICA"
                elif total_loss > 5:
                    severity = "ALTA"
                elif total_loss > 2:
                    severity = "MEDIA"
                else:
                    severity = "BAJA"

                trucks_analysis.append(
                    {
                        "truck_id": truck_id,
                        "severity": severity,
                        "primary_cause": primary_cause,
                        "avg_mpg": round(avg_mpg, 2),
                        "mpg_vs_baseline": round(avg_mpg - BASELINE_MPG, 2),
                        "total_miles": round(total_miles, 1),
                        "losses": {
                            "idle": {
                                "gallons": round(idle_loss, 2),
                                "usd": round(idle_loss * FUEL_PRICE, 2),
                                "minutes": idle_count,
                                "avg_gph": round(avg_idle_gph, 2),
                            },
                            "altitude": {
                                "gallons": round(altitude_loss, 2),
                                "usd": round(altitude_loss * FUEL_PRICE, 2),
                                "minutes_at_high_alt": high_alt_count,
                                "avg_altitude_ft": round(avg_high_alt, 0),
                            },
                            "rpm": {
                                "gallons": round(rpm_loss, 2),
                                "usd": round(rpm_loss * FUEL_PRICE, 2),
                                "minutes_high_rpm": high_rpm_count,
                                "avg_rpm": round(avg_high_rpm, 0),
                            },
                            "speed": {
                                "gallons": round(speed_loss, 2),
                                "usd": round(speed_loss * FUEL_PRICE, 2),
                                "minutes_overspeeding": overspeed_count,
                                "avg_overspeed_mph": round(avg_overspeed, 1),
                            },
                            "thermal": {
                                "gallons": round(thermal_loss, 2),
                                "usd": round(thermal_loss * FUEL_PRICE, 2),
                                "overheat_events": overheat_count,
                                "avg_coolant_f": round(avg_coolant, 1),
                            },
                        },
                        "total_loss": {
                            "gallons": round(total_loss, 2),
                            "usd": round(total_loss * FUEL_PRICE, 2),
                        },
                    }
                )

                # Accumulate totals
                totals["idle_loss_gal"] += idle_loss
                totals["altitude_loss_gal"] += altitude_loss
                totals["rpm_loss_gal"] += rpm_loss
                totals["speed_loss_gal"] += speed_loss
                totals["thermal_loss_gal"] += thermal_loss
                totals["total_loss_gal"] += total_loss

            # Sort by total loss descending
            trucks_analysis.sort(key=lambda x: x["total_loss"]["gallons"], reverse=True)

            # Calculate percentages for summary
            total_loss_gal = totals["total_loss_gal"]

            # Generate actionable insights
            insights = []

            if totals["idle_loss_gal"] > 2:
                insights.append(
                    {
                        "priority": "ALTA",
                        "category": "RALENTÍ",
                        "finding": f"La flota pierde {round(totals['idle_loss_gal'], 1)} galones en ralentí excesivo",
                        "recommendation": "Implementar política de apagado de motor después de 5 minutos parado",
                        "potential_savings_usd": round(
                            totals["idle_loss_gal"] * FUEL_PRICE * 0.5, 2
                        ),
                        "roi_timeline": "Inmediato",
                    }
                )

            if totals["rpm_loss_gal"] > 1:
                insights.append(
                    {
                        "priority": "MEDIA",
                        "category": "RPM",
                        "finding": f"Revoluciones excesivas causan pérdida de {round(totals['rpm_loss_gal'], 1)} galones",
                        "recommendation": "Capacitar conductores en uso óptimo de marchas (1200-1600 RPM)",
                        "potential_savings_usd": round(
                            totals["rpm_loss_gal"] * FUEL_PRICE * 0.7, 2
                        ),
                        "roi_timeline": "30 días",
                    }
                )

            if totals["speed_loss_gal"] > 1:
                insights.append(
                    {
                        "priority": "MEDIA",
                        "category": "VELOCIDAD",
                        "finding": f"Exceso de velocidad genera pérdida de {round(totals['speed_loss_gal'], 1)} galones",
                        "recommendation": "Establecer límite de 65 mph y monitorear con alertas",
                        "potential_savings_usd": round(
                            totals["speed_loss_gal"] * FUEL_PRICE * 0.8, 2
                        ),
                        "roi_timeline": "Inmediato",
                    }
                )

            if totals["thermal_loss_gal"] > 0.5:
                insights.append(
                    {
                        "priority": "ALTA",
                        "category": "MECÁNICO",
                        "finding": f"Problemas de temperatura detectados - {totals['thermal_loss_gal']:.1f} gal perdidos",
                        "recommendation": "Inspección urgente del sistema de enfriamiento",
                        "potential_savings_usd": round(
                            totals["thermal_loss_gal"] * FUEL_PRICE + 200, 2
                        ),
                        "roi_timeline": "Urgente - previene daño mayor",
                    }
                )

            return {
                "period_days": days_back,
                "truck_count": len(trucks_analysis),
                "fuel_price_per_gal": FUEL_PRICE,
                "baseline_mpg": BASELINE_MPG,
                "summary": {
                    "total_loss": {
                        "gallons": round(total_loss_gal, 2),
                        "usd": round(total_loss_gal * FUEL_PRICE, 2),
                    },
                    "by_cause": {
                        "idle": {
                            "gallons": round(totals["idle_loss_gal"], 2),
                            "usd": round(totals["idle_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                (
                                    (totals["idle_loss_gal"] / total_loss_gal * 100)
                                    if total_loss_gal > 0
                                    else 0
                                ),
                                1,
                            ),
                        },
                        "altitude": {
                            "gallons": round(totals["altitude_loss_gal"], 2),
                            "usd": round(totals["altitude_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                (
                                    (totals["altitude_loss_gal"] / total_loss_gal * 100)
                                    if total_loss_gal > 0
                                    else 0
                                ),
                                1,
                            ),
                        },
                        "rpm": {
                            "gallons": round(totals["rpm_loss_gal"], 2),
                            "usd": round(totals["rpm_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                (
                                    (totals["rpm_loss_gal"] / total_loss_gal * 100)
                                    if total_loss_gal > 0
                                    else 0
                                ),
                                1,
                            ),
                        },
                        "speed": {
                            "gallons": round(totals["speed_loss_gal"], 2),
                            "usd": round(totals["speed_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                (
                                    (totals["speed_loss_gal"] / total_loss_gal * 100)
                                    if total_loss_gal > 0
                                    else 0
                                ),
                                1,
                            ),
                        },
                        "thermal": {
                            "gallons": round(totals["thermal_loss_gal"], 2),
                            "usd": round(totals["thermal_loss_gal"] * FUEL_PRICE, 2),
                            "percentage": round(
                                (
                                    (totals["thermal_loss_gal"] / total_loss_gal * 100)
                                    if total_loss_gal > 0
                                    else 0
                                ),
                                1,
                            ),
                        },
                    },
                },
                "insights": insights,
                "trucks": trucks_analysis,
            }

    except Exception as e:
        logger.error(f"Error in enhanced loss analysis: {e}")
        return _empty_enhanced_loss_analysis(days_back, FUEL_PRICE)


def _empty_enhanced_loss_analysis(days: int, price: float) -> Dict[str, Any]:
    """Return empty enhanced loss analysis response"""
    return {
        "period_days": days,
        "truck_count": 0,
        "fuel_price_per_gal": price,
        "baseline_mpg": 5.7,
        "summary": {
            "total_loss": {"gallons": 0, "usd": 0},
            "by_cause": {
                "idle": {"gallons": 0, "usd": 0, "percentage": 0},
                "altitude": {"gallons": 0, "usd": 0, "percentage": 0},
                "rpm": {"gallons": 0, "usd": 0, "percentage": 0},
                "speed": {"gallons": 0, "usd": 0, "percentage": 0},
                "thermal": {"gallons": 0, "usd": 0, "percentage": 0},
            },
        },
        "insights": [],
        "trucks": [],
    }


def test_connection() -> bool:
    """
    Test MySQL connection

    🔧 FIX v3.9.2: Now uses SQLAlchemy connection pooling
    """
    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) as count FROM fuel_metrics")
            ).fetchone()
            count = result[0] if result else 0
            logger.info(
                f"✅ MySQL connected (pooled) - {count} records in fuel_metrics"
            )
            return True
    except Exception as e:
        logger.error(f"❌ MySQL connection test failed: {e}")
        return False


# =============================================================================
# 🆕 v3.10.3: ADVANCED REFUEL ANALYTICS & THEFT DETECTION
# =============================================================================


@cached(ttl_seconds=120, key_prefix="get_advanced_refuel_analytics")
def get_advanced_refuel_analytics(days_back: int = 7) -> Dict[str, Any]:
    """
    🆕 v3.10.3: World-Class Refuel Analytics Dashboard
    🔧 v3.12.25: Now reads from refuel_events table (where wialon_sync saves detected refuels)
    🔧 v3.15.0: Added 120-second cache for performance

    Provides comprehensive refuel intelligence:
    1. Refuel Events Timeline with precise gallons calculation
    2. Refuel Patterns Analysis (by truck, day of week, time of day)
    3. Cost Analysis & Fuel Purchase Tracking
    4. Anomaly Detection (partial fills, overfills, suspicious patterns)
    5. Station/Location Inference
    6. Tank Efficiency Analysis
    """
    FUEL_PRICE = FUEL.PRICE_PER_GALLON

    # 🔧 v3.12.25: Query from refuel_events table (where detected refuels are saved)
    # This table is populated by wialon_sync_service when it detects refuel events
    refuel_query = text(
        """
        SELECT 
            truck_id,
            timestamp_utc,
            gallons_added as refuel_gallons,
            fuel_after,
            fuel_before,
            refuel_type,
            confidence
        FROM refuel_events
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        ORDER BY timestamp_utc DESC
    """
    )

    # Query 2: Summary statistics per truck from refuel_events
    summary_query = text(
        """
        SELECT 
            truck_id,
            COUNT(*) as refuel_count,
            SUM(gallons_added) as total_gallons,
            AVG(gallons_added) as avg_gallons,
            MIN(gallons_added) as min_gallons,
            MAX(gallons_added) as max_gallons,
            AVG(fuel_after) as avg_fuel_level_after
        FROM refuel_events
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        GROUP BY truck_id
        ORDER BY total_gallons DESC
    """
    )

    # Query 3: Pattern analysis (hour of day, day of week) from refuel_events
    pattern_query = text(
        """
        SELECT 
            HOUR(timestamp_utc) as hour_of_day,
            DAYOFWEEK(timestamp_utc) as day_of_week,
            COUNT(*) as refuel_count,
            SUM(gallons_added) as total_gallons
        FROM refuel_events
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        GROUP BY HOUR(timestamp_utc), DAYOFWEEK(timestamp_utc)
        ORDER BY hour_of_day
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            # Execute all queries
            refuel_results = conn.execute(
                refuel_query, {"days_back": days_back}
            ).fetchall()
            summary_results = conn.execute(
                summary_query, {"days_back": days_back}
            ).fetchall()
            pattern_results = conn.execute(
                pattern_query, {"days_back": days_back}
            ).fetchall()

            if not refuel_results:
                return _empty_advanced_refuel_analytics(days_back, FUEL_PRICE)

            # 🔧 v3.12.25: Process events directly from refuel_events table
            # No need for complex consolidation - wialon_sync already does this
            refuel_events = []
            anomalies = []
            total_gallons = 0
            total_cost = 0

            for row in refuel_results:
                truck_id = row[0]
                timestamp = row[1]
                refuel_gallons = float(row[2] or 0)
                fuel_after_pct = float(row[3] or 0)
                fuel_before_pct = float(row[4] or 0)
                refuel_type = row[5] or "NORMAL"
                confidence = float(row[6] or 0)

                # Calculate derived metrics
                cost = refuel_gallons * FUEL_PRICE
                total_gallons += refuel_gallons
                total_cost += cost

                # Calculate fill type based on fuel_after percentage
                if fuel_after_pct >= 95:
                    fill_type = "LLENO COMPLETO"
                elif fuel_after_pct >= 80:
                    fill_type = "LLENO PARCIAL"
                elif refuel_gallons < 50:
                    fill_type = "RECARGA PEQUEÑA"
                else:
                    fill_type = "RECARGA NORMAL"

                # Detect anomalies
                anomaly_flags = []
                if fuel_after_pct > 100:
                    anomaly_flags.append("SOBRE-LLENADO")
                if refuel_gallons > 180:
                    anomaly_flags.append("CANTIDAD MUY GRANDE")
                if confidence < 0.8:
                    anomaly_flags.append("BAJA CONFIANZA")

                date_str = timestamp.strftime("%Y-%m-%d") if timestamp else ""
                time_str = timestamp.strftime("%H:%M") if timestamp else ""

                event = {
                    "truck_id": truck_id,
                    "timestamp": (
                        timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else None
                    ),
                    "date": date_str,
                    "time": time_str,
                    "gallons": round(refuel_gallons, 1),
                    "liters": round(refuel_gallons * 3.78541, 1),
                    "cost_usd": round(cost, 2),
                    "fuel_before_pct": (
                        round(fuel_before_pct, 1) if fuel_before_pct else None
                    ),
                    "fuel_after_pct": round(fuel_after_pct, 1),
                    "fuel_before_gal": None,  # Not available in refuel_events
                    "fuel_after_gal": None,  # Not available in refuel_events
                    "fuel_added_pct": (
                        round(fuel_after_pct - fuel_before_pct, 1)
                        if fuel_before_pct
                        else None
                    ),
                    "sensor_pct": None,  # Not available in refuel_events
                    "fill_type": fill_type,
                    "refuel_type": refuel_type,
                    "confidence": round(confidence, 2),
                    "miles_since_last": 0,  # Not tracked in refuel_events
                    "time_gap_minutes": 0,  # Not tracked in refuel_events
                    "altitude_ft": 0,  # Not tracked in refuel_events
                    "anomalies": anomaly_flags,
                    "has_anomaly": len(anomaly_flags) > 0,
                    "consolidated_from": 1,
                }
                refuel_events.append(event)

                if anomaly_flags:
                    anomalies.append(
                        {
                            "truck_id": truck_id,
                            "timestamp": event["timestamp"],
                            "gallons": event["gallons"],
                            "flags": anomaly_flags,
                            "severity": (
                                "ALTA" if "SOBRE-LLENADO" in anomaly_flags else "MEDIA"
                            ),
                        }
                    )

            # Process truck summaries FROM CONSOLIDATED EVENTS (not raw SQL)
            # Build summaries from the consolidated refuel_events
            truck_stats = {}  # truck_id -> {gallons: [], fuel_after: []}
            for event in refuel_events:
                tid = event["truck_id"]
                if tid not in truck_stats:
                    truck_stats[tid] = {"gallons": [], "fuel_after": []}
                truck_stats[tid]["gallons"].append(event["gallons"])
                if event.get("fuel_after_pct"):
                    truck_stats[tid]["fuel_after"].append(event["fuel_after_pct"])

            truck_summaries = []
            for tid, stats in truck_stats.items():
                gals = stats["gallons"]
                fuel_afters = stats["fuel_after"]
                truck_summaries.append(
                    {
                        "truck_id": tid,
                        "refuel_count": len(gals),
                        "total_gallons": round(sum(gals), 1),
                        "total_cost_usd": round(sum(gals) * FUEL_PRICE, 2),
                        "avg_gallons": round(sum(gals) / len(gals), 1) if gals else 0,
                        "min_gallons": round(min(gals), 1) if gals else 0,
                        "max_gallons": round(max(gals), 1) if gals else 0,
                        "avg_fuel_level_after": (
                            round(sum(fuel_afters) / len(fuel_afters), 1)
                            if fuel_afters
                            else 0
                        ),
                    }
                )
            # Sort by total gallons descending
            truck_summaries.sort(key=lambda x: x["total_gallons"], reverse=True)

            # Process patterns
            hourly_pattern = [0] * 24
            daily_pattern = [0] * 7  # Mon=0, Sun=6

            for row in pattern_results:
                hour = int(row[0])
                dow = int(row[1]) - 1  # MySQL DAYOFWEEK is 1-indexed, Sunday=1
                count = int(row[2])
                gallons = float(row[3] or 0)

                if 0 <= hour < 24:
                    hourly_pattern[hour] += count
                if 0 <= dow < 7:
                    daily_pattern[dow] += count

            # Calculate insights
            insights = []

            # Peak refuel times
            peak_hour = hourly_pattern.index(max(hourly_pattern))
            insights.append(
                {
                    "type": "PATRÓN HORARIO",
                    "finding": f"La mayoría de recargas ocurren a las {peak_hour}:00 hrs",
                    "recommendation": "Considerar negociar descuentos por volumen en estaciones cercanas para ese horario",
                }
            )

            # Average fill analysis
            avg_gallons_per_refuel = (
                total_gallons / len(refuel_events) if refuel_events else 0
            )
            if avg_gallons_per_refuel < 50:
                insights.append(
                    {
                        "type": "EFICIENCIA",
                        "finding": f"Promedio de {avg_gallons_per_refuel:.0f} gal/recarga es bajo",
                        "recommendation": "Llenar tanques más completos reduce paradas y tiempo perdido",
                    }
                )

            return {
                "period_days": days_back,
                "fuel_price_per_gal": FUEL_PRICE,
                "summary": {
                    "total_refuels": len(refuel_events),
                    "total_gallons": round(total_gallons, 1),
                    "total_liters": round(total_gallons * 3.78541, 1),
                    "total_cost_usd": round(total_cost, 2),
                    "avg_gallons_per_refuel": round(avg_gallons_per_refuel, 1),
                    "trucks_with_refuels": len(truck_summaries),
                    "anomaly_count": len(anomalies),
                },
                "patterns": {
                    "hourly": hourly_pattern,
                    "daily": daily_pattern,
                    "peak_hour": peak_hour,
                    "busiest_day": [
                        "Domingo",
                        "Lunes",
                        "Martes",
                        "Miércoles",
                        "Jueves",
                        "Viernes",
                        "Sábado",
                    ][daily_pattern.index(max(daily_pattern))],
                },
                "by_truck": truck_summaries,
                "events": refuel_events[:100],  # Limit to last 100
                "anomalies": anomalies,
                "insights": insights,
            }

    except Exception as e:
        logger.error(f"Error in advanced refuel analytics: {e}")
        return _empty_advanced_refuel_analytics(days_back, FUEL_PRICE)


def _empty_advanced_refuel_analytics(days: int, price: float) -> Dict[str, Any]:
    """Return empty advanced refuel analytics response"""
    return {
        "period_days": days,
        "fuel_price_per_gal": price,
        "summary": {
            "total_refuels": 0,
            "total_gallons": 0,
            "total_liters": 0,
            "total_cost_usd": 0,
            "avg_gallons_per_refuel": 0,
            "trucks_with_refuels": 0,
            "anomaly_count": 0,
        },
        "patterns": {
            "hourly": [0] * 24,
            "daily": [0] * 7,
            "peak_hour": 0,
            "busiest_day": "N/A",
        },
        "by_truck": [],
        "events": [],
        "anomalies": [],
        "insights": [],
    }


@cached(ttl_seconds=120, key_prefix="get_fuel_theft_analysis")
def get_fuel_theft_analysis(days_back: int = 7) -> Dict[str, Any]:
    """
    🆕 v3.12.27: IMPROVED Fuel Theft & Drain Detection System with SENSOR ISSUE detection
    🔧 v3.15.0: Added 120-second cache for performance

    Now differentiates between:
    - THEFT: Fuel drop that doesn't recover
    - SENSOR_ISSUE: Fuel drop that recovers quickly (sensor glitch)

    Detects:
    1. FUEL THEFT: Sudden large drops (>25 gal) in <30 min while parked, NO recovery
    2. SIPHONING: Large drops (>15 gal) overnight with no miles, NO recovery
    3. SENSOR_ISSUE: Drop that recovers within 15 minutes = sensor glitch

    IMPORTANT: Filters out:
    - Sensor disconnections (NULL readings)
    - Offline periods
    - Normal consumption
    - Drops that recover (now classified as SENSOR_ISSUE)
    """
    FUEL_PRICE = FUEL.PRICE_PER_GALLON

    # Much stricter thresholds to avoid false positives
    THEFT_MIN_GALLONS = 15.0  # At least 15 gal drop to flag
    THEFT_MIN_PCT = 8.0  # At least 8% drop
    THEFT_MAX_TIME_MIN = 120  # Drop must happen in <2 hours
    THEFT_MAX_MILES = 3.0  # Max 3 miles driven during drop
    SIPHON_MIN_GALLONS = 20.0  # Overnight siphoning threshold
    IDLE_CONSUMPTION_GPH = 1.2  # Conservative idle consumption estimate

    # 🆕 v4.0.0: Recovery detection thresholds - INCREASED based on real data analysis
    # Analysis of MR7679, FF7702 etc showed recoveries taking 20-25 minutes
    RECOVERY_WINDOW_MINUTES = 30  # Check for recovery within 30 min (was 15)
    RECOVERY_TOLERANCE_PCT = (
        15.0  # If fuel recovers to within 15% of original = sensor issue (was 10%)
    )

    # 🆕 First query: Get all fuel readings with LEAD to check recovery
    query = text(
        """
        SELECT 
            truck_id,
            timestamp_utc,
            estimated_pct,
            estimated_gallons,
            sensor_pct,
            sensor_gallons,
            truck_status,
            speed_mph,
            rpm,
            odometer_mi,
            consumption_gph,
            refuel_gallons,
            LAG(estimated_pct) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_pct,
            LAG(estimated_gallons) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_gal,
            LAG(sensor_pct) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_sensor_pct,
            LAG(sensor_gallons) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_sensor_gal,
            LAG(timestamp_utc) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_ts,
            LAG(odometer_mi) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_odo,
            LAG(truck_status) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_status,
            LEAD(estimated_pct, 1) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as next_pct_1,
            LEAD(estimated_pct, 2) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as next_pct_2,
            LEAD(estimated_pct, 3) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as next_pct_3,
            LEAD(timestamp_utc, 1) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as next_ts_1,
            LEAD(timestamp_utc, 2) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as next_ts_2,
            LEAD(timestamp_utc, 3) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as next_ts_3
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
          AND estimated_gallons IS NOT NULL
        ORDER BY truck_id, timestamp_utc
    """
    )

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            results = conn.execute(query, {"days_back": days_back}).fetchall()

            if not results:
                return _empty_theft_analysis(days_back, FUEL_PRICE)

            theft_events = []
            truck_patterns = {}  # Track patterns per truck
            total_loss_gal = 0

            for row in results:
                truck_id = row[0]
                timestamp = row[1]
                est_pct = float(row[2] or 0)
                est_gal = float(row[3] or 0)
                sensor_pct = row[4]  # Can be NULL
                sensor_gal = row[5]  # Can be NULL
                truck_status = row[6]
                refuel_gallons = float(row[11] or 0)

                prev_pct = float(row[12] or 0)
                prev_gal = float(row[13] or 0)
                prev_sensor_pct = row[14]  # Can be NULL
                prev_sensor_gal = row[15]  # Can be NULL
                prev_ts = row[16]
                prev_odo = float(row[17] or 0)
                prev_status = row[18]
                odometer = float(row[9] or 0)

                # Skip refuel events - not theft
                if refuel_gallons and refuel_gallons > 0:
                    continue

                # Skip if no valid previous data
                if not prev_pct or not prev_gal or prev_gal <= 0:
                    continue

                # ============================================
                # SENSOR QUALITY FILTERS
                # ============================================
                # If BOTH current and previous have sensor=NULL, skip (no reliable data)
                both_null = (sensor_pct is None) and (prev_sensor_pct is None)
                if both_null:
                    continue

                # 🆕 v4.0.0: IMPROVED - If current reading drops to near-zero (<5%)
                # from a normal level (>20%), this is almost always a sensor disconnect/failure
                # Real thieves don't drain tanks to exactly 0%
                if (
                    est_pct <= 5  # Near zero (was == 0, now <= 5)
                    and prev_pct > 20  # Previous was normal
                ):
                    logger.debug(
                        f"🔧 {truck_id}: Skipping drop to {est_pct}% from {prev_pct}% - likely sensor disconnect"
                    )
                    continue

                # Also skip if sensor reading is exactly 0 (NULL/disconnect indicator)
                if sensor_pct is not None and float(sensor_pct) == 0 and prev_pct > 20:
                    logger.debug(
                        f"🔧 {truck_id}: Skipping sensor=0% event - sensor disconnect"
                    )
                    continue
                # ============================================

                # Calculate metrics
                fuel_drop_gal = prev_gal - est_gal
                fuel_drop_pct = prev_pct - est_pct

                # Skip if fuel INCREASED (not a drop)
                if fuel_drop_gal <= 0:
                    continue

                # Calculate time and distance
                if prev_ts and timestamp:
                    time_gap_min = (timestamp - prev_ts).total_seconds() / 60
                    time_gap_hours = time_gap_min / 60
                else:
                    continue  # Can't evaluate without time

                # Filter out rapid oscillations (dual tank sensors)
                # If change happens in under 30 seconds, it's definitely not theft
                if time_gap_min < 0.5:
                    continue  # Too fast = sensor glitch/alternation

                # Minimum time for theft detection - need at least 2 minutes
                if time_gap_min < 2 and unexplained_loss < 50:
                    continue  # Very fast drops need to be very large to flag

                miles_driven = max(0, odometer - prev_odo) if prev_odo else 0

                # Calculate EXPECTED consumption for this period
                expected_driving_consumption = miles_driven / 6.0  # Conservative 6 MPG
                expected_idle_consumption = time_gap_hours * IDLE_CONSUMPTION_GPH
                expected_total = (
                    expected_driving_consumption + expected_idle_consumption
                )

                # UNEXPLAINED loss = actual drop minus what we'd expect
                unexplained_loss = fuel_drop_gal - expected_total

                # Only flag if UNEXPLAINED loss exceeds threshold
                if unexplained_loss < THEFT_MIN_GALLONS:
                    continue  # Normal consumption, not theft

                # Additional filters to reduce false positives
                if fuel_drop_pct < THEFT_MIN_PCT:
                    continue  # Small percentage drop, likely sensor noise

                # Sanity check: sensor/estimate should be consistent
                if sensor_pct is not None and abs(float(sensor_pct) - est_pct) > 15:
                    continue  # Data quality issue

                # THEFT CLASSIFICATION - BE VERY STRICT
                theft_type = None
                confidence = 0

                # KEY: If truck moved ANY distance, it's consumption not theft
                if miles_driven > 0.5:
                    continue  # Truck moved = consumption, not theft

                # If there's a large gap (>30 min), odometer might not reflect actual miles
                # during the gap. Require larger drop to flag.
                large_gap = time_gap_min > 30
                min_drop_for_theft = (
                    40 if large_gap else 25
                )  # Higher threshold for gaps

                # Type 1: RAPID THEFT - Large drop while COMPLETELY stationary
                if (
                    time_gap_min <= THEFT_MAX_TIME_MIN
                    and miles_driven <= 0.5
                    and unexplained_loss >= min_drop_for_theft
                ):
                    theft_type = "ROBO RÁPIDO"
                    confidence = 95 if not large_gap else 80  # Lower confidence if gap

                # Type 2: OVERNIGHT SIPHONING - stationary overnight
                elif (
                    time_gap_hours >= 4
                    and time_gap_hours <= 12
                    and unexplained_loss >= max(SIPHON_MIN_GALLONS, min_drop_for_theft)
                    and miles_driven <= 0.5
                ):
                    hour = timestamp.hour if timestamp else 12
                    if hour < 8 or hour > 20:
                        theft_type = "SIFÓN NOCTURNO"
                        confidence = 85
                    else:
                        theft_type = "PÉRDIDA SOSPECHOSA"
                        confidence = 70

                # Type 3: ANOMALY - must be stationary with large confirmed drop
                elif (
                    unexplained_loss >= 50  # Very large drop only
                    and miles_driven <= 0.5
                    and time_gap_hours <= 6
                ):
                    theft_type = "ANOMALÍA GRAVE"
                    confidence = 75

                if not theft_type:
                    continue

                # 🆕 v3.12.27: CHECK FOR RECOVERY - If fuel recovers, it's a SENSOR ISSUE not theft
                # Look at the next 3 readings to see if fuel recovered
                next_pct_1 = float(row[19] or 0) if row[19] else None
                next_pct_2 = float(row[20] or 0) if row[20] else None
                next_pct_3 = float(row[21] or 0) if row[21] else None
                next_ts_1 = row[22]
                next_ts_2 = row[23]
                next_ts_3 = row[24]

                recovered = False
                recovery_to_pct = None
                recovery_time_min = None

                # Check each of the next readings for recovery
                for next_pct, next_ts in [
                    (next_pct_1, next_ts_1),
                    (next_pct_2, next_ts_2),
                    (next_pct_3, next_ts_3),
                ]:
                    if next_pct is None or next_ts is None:
                        continue

                    # Time since the drop
                    time_since_drop = (
                        (next_ts - timestamp).total_seconds() / 60 if timestamp else 999
                    )

                    # If within recovery window and fuel recovered close to original level
                    if time_since_drop <= RECOVERY_WINDOW_MINUTES:
                        recovery_gap = abs(prev_pct - next_pct)
                        if recovery_gap <= RECOVERY_TOLERANCE_PCT:
                            # Fuel recovered! This is a sensor issue, not theft
                            recovered = True
                            recovery_to_pct = next_pct
                            recovery_time_min = time_since_drop
                            break

                # 🆕 If recovered, classify as SENSOR ISSUE instead of theft
                if recovered:
                    theft_type = "PROBLEMA DE SENSOR"
                    confidence = 30  # Low confidence since it's not actual theft
                    logger.info(
                        f"🔧 {truck_id}: Drop of {fuel_drop_pct:.1f}% RECOVERED to {recovery_to_pct:.1f}% "
                        f"in {recovery_time_min:.0f} min - classifying as SENSOR ISSUE"
                    )

                # Check time of day
                hour = timestamp.hour if timestamp else 12
                is_night = hour < 6 or hour > 22
                if is_night and not recovered:
                    confidence = min(100, confidence + 5)

                # Create event record
                theft_event = {
                    "truck_id": truck_id,
                    "timestamp": (
                        timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else None
                    ),
                    "date": timestamp.strftime("%Y-%m-%d") if timestamp else None,
                    "time": timestamp.strftime("%H:%M") if timestamp else None,
                    "theft_type": theft_type,
                    "confidence_pct": confidence,
                    "fuel_drop_gallons": round(fuel_drop_gal, 1),
                    "unexplained_loss_gallons": (
                        round(unexplained_loss, 1) if not recovered else 0
                    ),
                    "fuel_drop_pct": round(fuel_drop_pct, 1),
                    "fuel_before_pct": round(prev_pct, 1),
                    "fuel_after_pct": round(est_pct, 1),
                    "estimated_loss_usd": (
                        round(unexplained_loss * FUEL_PRICE, 2) if not recovered else 0
                    ),
                    "time_gap_minutes": round(time_gap_min, 0),
                    "miles_driven": round(miles_driven, 1),
                    "expected_consumption_gal": round(expected_total, 1),
                    "is_night": is_night,
                    "recovered": recovered,  # 🆕 Flag for recovery
                    "recovery_to_pct": (
                        round(recovery_to_pct, 1) if recovery_to_pct else None
                    ),
                    "recovery_time_min": (
                        round(recovery_time_min, 0) if recovery_time_min else None
                    ),
                }
                theft_events.append(theft_event)

                # 🆕 Only count loss if NOT recovered (sensor issues don't count as loss)
                if not recovered:
                    total_loss_gal += unexplained_loss

                # Track per truck (but mark sensor issues separately)
                if truck_id not in truck_patterns:
                    truck_patterns[truck_id] = {
                        "event_count": 0,
                        "sensor_issue_count": 0,
                        "total_loss_gal": 0,
                        "highest_confidence": 0,
                    }
                truck_patterns[truck_id]["event_count"] += 1
                if recovered:
                    truck_patterns[truck_id]["sensor_issue_count"] = (
                        truck_patterns[truck_id].get("sensor_issue_count", 0) + 1
                    )
                else:
                    truck_patterns[truck_id]["total_loss_gal"] += unexplained_loss
                    truck_patterns[truck_id]["highest_confidence"] = max(
                        truck_patterns[truck_id]["highest_confidence"], confidence
                    )

            # Build trucks_at_risk list
            trucks_at_risk = []
            for truck_id, data in truck_patterns.items():
                risk_level = (
                    "CRÍTICO"
                    if data["highest_confidence"] >= 90
                    else (
                        "ALTO"
                        if data["highest_confidence"] >= 75
                        else "MEDIO" if data["highest_confidence"] >= 60 else "BAJO"
                    )
                )
                trucks_at_risk.append(
                    {
                        "truck_id": truck_id,
                        "event_count": data["event_count"],
                        "total_loss_gallons": round(data["total_loss_gal"], 1),
                        "total_loss_usd": round(data["total_loss_gal"] * FUEL_PRICE, 2),
                        "highest_confidence": data["highest_confidence"],
                        "risk_level": risk_level,
                    }
                )

            # Sort by severity
            trucks_at_risk.sort(
                key=lambda x: (x["highest_confidence"], x["total_loss_gallons"]),
                reverse=True,
            )
            theft_events.sort(key=lambda x: x["confidence_pct"], reverse=True)

            # Generate insights
            insights = []

            if len(theft_events) == 0:
                insights.append(
                    {
                        "priority": "INFO",
                        "type": "SIN ALERTAS",
                        "finding": "No se detectaron eventos de robo o pérdida sospechosa",
                        "recommendation": "El sistema está monitoreando. Continúe operaciones normales.",
                    }
                )
            else:
                if total_loss_gal >= 50:
                    insights.append(
                        {
                            "priority": "CRÍTICA",
                            "type": "PÉRDIDA SIGNIFICATIVA",
                            "finding": f"Pérdida inexplicable: {round(total_loss_gal, 0)} gal (${round(total_loss_gal * FUEL_PRICE, 0)})",
                            "recommendation": "Revisar cámaras, verificar cerraduras de tanque",
                        }
                    )

                high_conf_events = [
                    e for e in theft_events if e["confidence_pct"] >= 85
                ]
                if high_conf_events:
                    insights.append(
                        {
                            "priority": "ALTA",
                            "type": "EVENTOS CRÍTICOS",
                            "finding": f"{len(high_conf_events)} evento(s) con alta confianza detectados",
                            "recommendation": "Investigar inmediatamente",
                        }
                    )

                night_events = [e for e in theft_events if e.get("is_night")]
                if len(night_events) > len(theft_events) * 0.6:
                    insights.append(
                        {
                            "priority": "ALTA",
                            "type": "PATRÓN NOCTURNO",
                            "finding": f"{len(night_events)} de {len(theft_events)} eventos de noche",
                            "recommendation": "Mejorar seguridad nocturna",
                        }
                    )

            # 🆕 Separate real theft events from sensor issues
            real_theft_events = [
                e for e in theft_events if not e.get("recovered", False)
            ]
            sensor_issue_events = [e for e in theft_events if e.get("recovered", False)]

            return {
                "period_days": days_back,
                "fuel_price_per_gal": FUEL_PRICE,
                "detection_thresholds": {
                    "min_gallons": THEFT_MIN_GALLONS,
                    "min_pct": THEFT_MIN_PCT,
                    "max_time_minutes": THEFT_MAX_TIME_MIN,
                },
                "summary": {
                    "total_events": len(real_theft_events),  # Only count real theft
                    "sensor_issue_events": len(
                        sensor_issue_events
                    ),  # 🆕 Separate count
                    "high_confidence_events": len(
                        [e for e in real_theft_events if e["confidence_pct"] >= 85]
                    ),
                    "total_suspected_loss_gallons": round(total_loss_gal, 1),
                    "total_suspected_loss_usd": round(total_loss_gal * FUEL_PRICE, 2),
                    "trucks_affected": len(
                        [t for t in trucks_at_risk if t["total_loss_gallons"] > 0]
                    ),
                },
                "trucks_at_risk": [
                    t for t in trucks_at_risk[:20] if t["total_loss_gallons"] > 0
                ],
                "events": theft_events[
                    :30
                ],  # Include all for display, frontend will filter
                "sensor_issues": sensor_issue_events[
                    :20
                ],  # 🆕 Separate list for sensor issues
                "insights": insights,
            }

    except Exception as e:
        logger.error(f"Error in fuel theft analysis: {e}")
        return _empty_theft_analysis(days_back, FUEL_PRICE)


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 ROUTE EFFICIENCY & COST ATTRIBUTION FUNCTIONS (v3.12.0)
# ═══════════════════════════════════════════════════════════════════════════════


def get_route_efficiency_analysis(
    truck_id: Optional[str] = None, days_back: int = 7
) -> Dict:
    """
    Analyze route efficiency comparing actual vs expected fuel consumption.

    This helps identify:
    - Routes with poor fuel economy
    - Driver behavior issues on specific routes
    - Vehicle performance problems

    Args:
        truck_id: Optional specific truck to analyze
        days_back: Days of history to analyze

    Returns:
        Dict with route efficiency metrics and recommendations
    """
    engine = get_sqlalchemy_engine()
    FUEL_PRICE = 3.50
    BASELINE_MPG = 5.7

    try:
        with engine.connect() as conn:
            # Get trip segments (periods of movement between stops)
            truck_filter = f"AND truck_id = '{truck_id}'" if truck_id else ""

            query = text(
                f"""
                WITH trip_data AS (
                    SELECT 
                        truck_id,
                        DATE(timestamp_utc) as trip_date,
                        MIN(timestamp_utc) as start_time,
                        MAX(timestamp_utc) as end_time,
                        SUM(CASE WHEN truck_status = 'MOVING' THEN 1 ELSE 0 END) as moving_records,
                        AVG(CASE WHEN truck_status = 'MOVING' AND mpg_current > 0 THEN mpg_current END) as avg_mpg,
                        AVG(CASE WHEN truck_status = 'MOVING' THEN speed_mph END) as avg_speed,
                        MAX(odometer_mi) - MIN(odometer_mi) as miles_traveled,
                        AVG(altitude_ft) as avg_altitude,
                        SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.5 THEN 1 ELSE 0 END) as idle_periods,
                        AVG(CASE WHEN truck_status = 'STOPPED' THEN consumption_gph END) as avg_idle_gph
                    FROM fuel_metrics
                    WHERE timestamp_utc > NOW() - INTERVAL :days DAY
                    {truck_filter}
                    GROUP BY truck_id, DATE(timestamp_utc)
                    HAVING SUM(CASE WHEN truck_status = 'MOVING' THEN 1 ELSE 0 END) > 10
                )
                SELECT * FROM trip_data
                ORDER BY truck_id, trip_date DESC
            """
            )

            result = conn.execute(query, {"days": days_back})
            rows = result.fetchall()

            if not rows:
                return {
                    "period_days": days_back,
                    "truck_id": truck_id,
                    "total_trips": 0,
                    "efficiency_analysis": [],
                    "recommendations": [],
                    "summary": {
                        "avg_mpg": 0,
                        "total_miles": 0,
                        "total_fuel_gallons": 0,
                        "efficiency_score": 0,
                    },
                }

            trips = []
            total_miles = 0
            total_fuel = 0
            mpg_values = []

            for row in rows:
                tid = row[0]
                trip_date = row[1]
                avg_mpg = float(row[5] or 0)
                avg_speed = float(row[6] or 0)
                miles = float(row[7] or 0)
                avg_altitude = float(row[8] or 0)
                idle_periods = int(row[9] or 0)
                avg_idle = float(row[10] or 0)

                if miles <= 0:
                    continue

                # Calculate expected vs actual fuel
                expected_fuel = miles / BASELINE_MPG
                actual_fuel = miles / avg_mpg if avg_mpg > 0 else expected_fuel * 1.5
                fuel_variance = actual_fuel - expected_fuel
                variance_pct = (
                    (fuel_variance / expected_fuel * 100) if expected_fuel > 0 else 0
                )

                # Efficiency score (100 = baseline, >100 = better, <100 = worse)
                efficiency_score = (BASELINE_MPG / avg_mpg * 100) if avg_mpg > 0 else 50

                # Cost analysis
                actual_cost = actual_fuel * FUEL_PRICE
                expected_cost = expected_fuel * FUEL_PRICE
                cost_variance = actual_cost - expected_cost

                # Altitude impact estimate (3% penalty per 1000ft above 3000ft)
                altitude_penalty = max(0, (avg_altitude - 3000) / 1000 * 0.03)

                trips.append(
                    {
                        "truck_id": tid,
                        "date": str(trip_date),
                        "miles": round(miles, 1),
                        "avg_mpg": round(avg_mpg, 2) if avg_mpg > 0 else None,
                        "avg_speed_mph": round(avg_speed, 1),
                        "avg_altitude_ft": round(avg_altitude, 0),
                        "idle_periods": idle_periods,
                        "avg_idle_gph": round(avg_idle, 2) if avg_idle > 0 else None,
                        "expected_fuel_gal": round(expected_fuel, 1),
                        "actual_fuel_gal": round(actual_fuel, 1),
                        "fuel_variance_gal": round(fuel_variance, 1),
                        "variance_pct": round(variance_pct, 1),
                        "efficiency_score": round(efficiency_score, 0),
                        "actual_cost": round(actual_cost, 2),
                        "expected_cost": round(expected_cost, 2),
                        "cost_variance": round(cost_variance, 2),
                        "altitude_impact_pct": round(altitude_penalty * 100, 1),
                    }
                )

                total_miles += miles
                total_fuel += actual_fuel
                if avg_mpg > 0:
                    mpg_values.append(avg_mpg)

            # Generate recommendations
            recommendations = []

            # Check for consistently low MPG
            avg_fleet_mpg = sum(mpg_values) / len(mpg_values) if mpg_values else 0
            if avg_fleet_mpg < BASELINE_MPG * 0.85:
                recommendations.append(
                    {
                        "priority": "HIGH",
                        "type": "LOW_MPG",
                        "finding": f"Average MPG ({avg_fleet_mpg:.1f}) is {((BASELINE_MPG - avg_fleet_mpg) / BASELINE_MPG * 100):.0f}% below baseline",
                        "action": "Schedule maintenance check for engine, tires, and fuel system",
                        "estimated_monthly_savings": round(
                            (BASELINE_MPG - avg_fleet_mpg) * 100 * FUEL_PRICE, 0
                        ),
                    }
                )

            # Check for high idle
            high_idle_trips = [t for t in trips if (t.get("idle_periods") or 0) > 5]
            if len(high_idle_trips) > len(trips) * 0.3:
                recommendations.append(
                    {
                        "priority": "MEDIUM",
                        "type": "EXCESSIVE_IDLE",
                        "finding": f"{len(high_idle_trips)} trips with excessive idle periods",
                        "action": "Coach drivers on reducing idle time; consider APU installation",
                        "estimated_monthly_savings": round(
                            len(high_idle_trips) * 2 * FUEL_PRICE, 0
                        ),
                    }
                )

            # Check for speed efficiency
            fast_trips = [t for t in trips if (t.get("avg_speed_mph") or 0) > 70]
            if fast_trips:
                recommendations.append(
                    {
                        "priority": "MEDIUM",
                        "type": "HIGH_SPEED",
                        "finding": f"{len(fast_trips)} trips with avg speed >70 mph",
                        "action": "Optimal cruising speed is 55-65 mph for best fuel economy",
                        "estimated_monthly_savings": round(
                            len(fast_trips) * 5 * FUEL_PRICE, 0
                        ),
                    }
                )

            return {
                "period_days": days_back,
                "truck_id": truck_id,
                "total_trips": len(trips),
                "efficiency_analysis": trips[:50],  # Limit to recent 50
                "recommendations": recommendations,
                "summary": {
                    "avg_mpg": round(avg_fleet_mpg, 2),
                    "total_miles": round(total_miles, 0),
                    "total_fuel_gallons": round(total_fuel, 0),
                    "total_cost": round(total_fuel * FUEL_PRICE, 2),
                    "efficiency_score": round(
                        (
                            (BASELINE_MPG / avg_fleet_mpg * 100)
                            if avg_fleet_mpg > 0
                            else 50
                        ),
                        0,
                    ),
                    "baseline_mpg": BASELINE_MPG,
                },
            }

    except Exception as e:
        logger.error(f"Error in route efficiency analysis: {e}")
        return {
            "period_days": days_back,
            "truck_id": truck_id,
            "total_trips": 0,
            "efficiency_analysis": [],
            "recommendations": [],
            "summary": {
                "avg_mpg": 0,
                "total_miles": 0,
                "total_fuel_gallons": 0,
                "efficiency_score": 0,
            },
            "error": str(e),
        }


def get_inefficiency_causes(truck_id: str, days_back: int = 30) -> Dict:
    """
    🆕 v3.14.1: Analyze REAL causes of fuel inefficiency using ALL sensor data.

    Uses actual sensor readings to attribute inefficiency to specific causes:

    - High Speed Driving (>65 mph): Aerodynamic drag increases exponentially
    - High RPM Operation (>1600): More fuel per rotation
    - High Engine Load (>80%): Heavy loads consume more fuel
    - Excessive Idle: Fuel burned with no miles
    - Low Oil Pressure: Mechanical issues affecting efficiency
    - High Oil Temperature: Engine stress indicator

    Returns breakdown with percentages, MPG impact, and cost attribution.
    """
    engine = get_sqlalchemy_engine()
    FUEL_PRICE = 3.50
    BASELINE_MPG = 5.7
    OPTIMAL_SPEED_MAX = 65.0  # MPH
    OPTIMAL_RPM_MAX = 1600
    OPTIMAL_LOAD_MAX = 80  # %
    LOW_OIL_PRESSURE = 35  # PSI
    HIGH_OIL_TEMP = 240  # °F

    try:
        with engine.connect() as conn:
            query = text(
                """
                SELECT 
                    -- Total counts for percentages
                    COUNT(CASE WHEN truck_status = 'MOVING' THEN 1 END) as total_moving,
                    COUNT(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN 1 END) as total_idle,
                    
                    -- High speed analysis (>65 mph)
                    COUNT(CASE WHEN truck_status = 'MOVING' AND speed_mph > :speed_max THEN 1 END) as high_speed_count,
                    AVG(CASE WHEN truck_status = 'MOVING' AND speed_mph > :speed_max THEN speed_mph END) as avg_high_speed,
                    AVG(CASE WHEN truck_status = 'MOVING' AND speed_mph > :speed_max THEN mpg_current END) as mpg_at_high_speed,
                    
                    -- High RPM analysis (>1600)
                    COUNT(CASE WHEN rpm > :rpm_max THEN 1 END) as high_rpm_count,
                    AVG(CASE WHEN rpm > :rpm_max THEN rpm END) as avg_high_rpm,
                    AVG(CASE WHEN rpm > :rpm_max THEN mpg_current END) as mpg_at_high_rpm,
                    
                    -- Normal operation for comparison
                    AVG(CASE WHEN truck_status = 'MOVING' AND speed_mph BETWEEN 55 AND 65 THEN mpg_current END) as mpg_at_optimal_speed,
                    AVG(CASE WHEN rpm BETWEEN 1200 AND 1600 THEN mpg_current END) as mpg_at_optimal_rpm,
                    
                    -- Overall MPG and consumption
                    AVG(CASE WHEN mpg_current > 3 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
                    SUM(CASE WHEN consumption_gph > 0 THEN consumption_gph / 60.0 END) as total_fuel_approx,
                    MAX(odometer_mi) - MIN(odometer_mi) as total_miles,
                    
                    -- Idle consumption
                    SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph / 60.0 END) as idle_fuel,
                    
                    -- 🆕 Engine Load analysis (>80%)
                    COUNT(CASE WHEN engine_load_pct > :load_max THEN 1 END) as high_load_count,
                    AVG(CASE WHEN engine_load_pct > :load_max THEN engine_load_pct END) as avg_high_load,
                    AVG(CASE WHEN engine_load_pct > :load_max THEN mpg_current END) as mpg_at_high_load,
                    AVG(CASE WHEN engine_load_pct BETWEEN 30 AND 60 THEN mpg_current END) as mpg_at_optimal_load,
                    
                    -- 🆕 Oil Pressure analysis (<35 PSI)
                    COUNT(CASE WHEN oil_pressure_psi < :low_oil_pressure AND oil_pressure_psi > 0 THEN 1 END) as low_oil_pressure_count,
                    AVG(CASE WHEN oil_pressure_psi < :low_oil_pressure AND oil_pressure_psi > 0 THEN oil_pressure_psi END) as avg_low_oil_pressure,
                    MIN(CASE WHEN oil_pressure_psi > 0 THEN oil_pressure_psi END) as min_oil_pressure,
                    AVG(oil_pressure_psi) as avg_oil_pressure,
                    COUNT(CASE WHEN oil_pressure_psi IS NOT NULL AND oil_pressure_psi > 0 THEN 1 END) as oil_pressure_readings,
                    
                    -- 🆕 Oil Temperature analysis (>240°F)
                    COUNT(CASE WHEN oil_temp_f > :high_oil_temp THEN 1 END) as high_oil_temp_count,
                    AVG(CASE WHEN oil_temp_f > :high_oil_temp THEN oil_temp_f END) as avg_high_oil_temp,
                    MAX(oil_temp_f) as max_oil_temp,
                    AVG(oil_temp_f) as avg_oil_temp,
                    COUNT(CASE WHEN oil_temp_f IS NOT NULL AND oil_temp_f > 0 THEN 1 END) as oil_temp_readings
                    
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL :days DAY
                AND (:truck_id IS NULL OR truck_id = :truck_id)
            """
            )

            result = conn.execute(
                query,
                {
                    "days": days_back,
                    "truck_id": truck_id if truck_id != "fleet" else None,
                    "speed_max": OPTIMAL_SPEED_MAX,
                    "rpm_max": OPTIMAL_RPM_MAX,
                    "load_max": OPTIMAL_LOAD_MAX,
                    "low_oil_pressure": LOW_OIL_PRESSURE,
                    "high_oil_temp": HIGH_OIL_TEMP,
                },
            ).fetchone()

            if not result or not result[0]:
                return {"error": "No data found", "causes": []}

            # Basic metrics
            total_moving = int(result[0] or 1)
            total_idle = int(result[1] or 0)
            high_speed_count = int(result[2] or 0)
            avg_high_speed = float(result[3] or 70)
            mpg_at_high_speed = float(result[4] or 5.0)
            high_rpm_count = int(result[5] or 0)
            avg_high_rpm = float(result[6] or 1800)
            mpg_at_high_rpm = float(result[7] or 5.5)
            mpg_at_optimal_speed = float(result[8] or BASELINE_MPG)
            mpg_at_optimal_rpm = float(result[9] or BASELINE_MPG)
            avg_mpg = float(result[10] or BASELINE_MPG)
            total_fuel = float(result[11] or 0)
            total_miles = float(result[12] or 0)
            idle_fuel = float(result[13] or 0)

            # 🆕 Engine Load metrics
            high_load_count = int(result[14] or 0)
            avg_high_load = float(result[15] or 85)
            mpg_at_high_load = float(result[16] or 4.5)
            mpg_at_optimal_load = float(result[17] or BASELINE_MPG)

            # 🆕 Oil Pressure metrics
            low_oil_pressure_count = int(result[18] or 0)
            avg_low_oil_pressure = float(result[19] or 30)
            min_oil_pressure = float(result[20] or 0)
            avg_oil_pressure = float(result[21] or 0)
            oil_pressure_readings = int(result[22] or 0)

            # 🆕 Oil Temperature metrics
            high_oil_temp_count = int(result[23] or 0)
            avg_high_oil_temp = float(result[24] or 250)
            max_oil_temp = float(result[25] or 0)
            avg_oil_temp = float(result[26] or 0)
            oil_temp_readings = int(result[27] or 0)

            # Calculate inefficiency causes with REAL data
            causes = []

            # 1. High Speed Impact
            if high_speed_count > 0 and total_moving > 0:
                high_speed_pct = (high_speed_count / total_moving) * 100
                mpg_loss_speed = max(0, mpg_at_optimal_speed - mpg_at_high_speed)
                high_speed_miles_est = total_miles * (high_speed_pct / 100)
                extra_gal_speed = (
                    (high_speed_miles_est / mpg_at_high_speed)
                    - (high_speed_miles_est / mpg_at_optimal_speed)
                    if mpg_at_high_speed > 0 and mpg_at_optimal_speed > 0
                    else 0
                )
                extra_gal_speed = max(0, extra_gal_speed)

                causes.append(
                    {
                        "cause": "high_speed",
                        "icon": "🏎️",
                        "label": "High Speed Driving",
                        "label_es": "Conducción a Alta Velocidad",
                        "description": f"Driving above 65 mph ({high_speed_pct:.0f}% of time, avg {avg_high_speed:.0f} mph)",
                        "description_es": f"Conduciendo sobre 65 mph ({high_speed_pct:.0f}% del tiempo, prom {avg_high_speed:.0f} mph)",
                        "pct_of_time": round(high_speed_pct, 1),
                        "mpg_impact": round(mpg_loss_speed, 2),
                        "mpg_at_issue": round(mpg_at_high_speed, 2),
                        "mpg_at_optimal": round(mpg_at_optimal_speed, 2),
                        "extra_gallons": round(extra_gal_speed, 1),
                        "extra_cost": round(extra_gal_speed * FUEL_PRICE, 2),
                        "data_points": high_speed_count,
                        "recommendation": "Reduce cruising speed to 62-65 mph to improve aerodynamics",
                        "recommendation_es": "Reducir velocidad de crucero a 62-65 mph para mejorar aerodinámica",
                        "source": "speed_sensor",
                    }
                )

            # 2. High RPM Impact
            if high_rpm_count > 0 and total_moving > 0:
                high_rpm_pct = (high_rpm_count / total_moving) * 100
                mpg_loss_rpm = max(0, mpg_at_optimal_rpm - mpg_at_high_rpm)
                high_rpm_fuel_est = total_fuel * (high_rpm_pct / 100)
                optimal_fuel_at_same_pct = (
                    high_rpm_fuel_est * (mpg_at_high_rpm / mpg_at_optimal_rpm)
                    if mpg_at_optimal_rpm > 0
                    else high_rpm_fuel_est
                )
                extra_gal_rpm = high_rpm_fuel_est - optimal_fuel_at_same_pct
                extra_gal_rpm = max(0, extra_gal_rpm)

                causes.append(
                    {
                        "cause": "high_rpm",
                        "icon": "⚡",
                        "label": "High RPM Operation",
                        "label_es": "Operación a RPM Alta",
                        "description": f"Engine above 1600 RPM ({high_rpm_pct:.0f}% of time, avg {avg_high_rpm:.0f} RPM)",
                        "description_es": f"Motor sobre 1600 RPM ({high_rpm_pct:.0f}% del tiempo, prom {avg_high_rpm:.0f} RPM)",
                        "pct_of_time": round(high_rpm_pct, 1),
                        "mpg_impact": round(mpg_loss_rpm, 2),
                        "mpg_at_issue": round(mpg_at_high_rpm, 2),
                        "mpg_at_optimal": round(mpg_at_optimal_rpm, 2),
                        "extra_gallons": round(extra_gal_rpm, 1),
                        "extra_cost": round(extra_gal_rpm * FUEL_PRICE, 2),
                        "data_points": high_rpm_count,
                        "recommendation": "Upshift earlier, use cruise control in sweet spot (1200-1500 RPM)",
                        "recommendation_es": "Subir de marcha antes, usar control crucero en zona óptima (1200-1500 RPM)",
                        "source": "rpm_sensor",
                    }
                )

            # 3. 🆕 High Engine Load Impact
            if high_load_count > 0 and total_moving > 0 and mpg_at_high_load > 0:
                high_load_pct = (high_load_count / total_moving) * 100
                mpg_loss_load = (
                    max(0, mpg_at_optimal_load - mpg_at_high_load)
                    if mpg_at_optimal_load
                    else 0
                )
                high_load_miles_est = total_miles * (high_load_pct / 100)
                extra_gal_load = (
                    (high_load_miles_est / mpg_at_high_load)
                    - (high_load_miles_est / mpg_at_optimal_load)
                    if mpg_at_high_load > 0 and mpg_at_optimal_load > 0
                    else 0
                )
                extra_gal_load = max(0, extra_gal_load)

                causes.append(
                    {
                        "cause": "high_engine_load",
                        "icon": "⚙️",
                        "label": "High Engine Load",
                        "label_es": "Carga de Motor Alta",
                        "description": f"Engine load above 80% ({high_load_count} events, avg {avg_high_load:.0f}%)",
                        "description_es": f"Carga del motor sobre 80% ({high_load_count} eventos, prom {avg_high_load:.0f}%)",
                        "pct_of_time": round(high_load_pct, 1),
                        "mpg_impact": round(mpg_loss_load, 2),
                        "mpg_at_issue": round(mpg_at_high_load, 2),
                        "mpg_at_optimal": (
                            round(mpg_at_optimal_load, 2)
                            if mpg_at_optimal_load
                            else None
                        ),
                        "extra_gallons": round(extra_gal_load, 1),
                        "extra_cost": round(extra_gal_load * FUEL_PRICE, 2),
                        "data_points": high_load_count,
                        "recommendation": "Avoid overloading, consider route optimization for hills",
                        "recommendation_es": "Evitar sobrecarga, optimizar rutas para evitar pendientes",
                        "source": "engine_load_sensor",
                    }
                )

            # 4. Idle Impact
            if total_idle > 0 and idle_fuel > 0:
                idle_pct = (
                    (total_idle / (total_moving + total_idle)) * 100
                    if (total_moving + total_idle) > 0
                    else 0
                )

                causes.append(
                    {
                        "cause": "excessive_idle",
                        "icon": "⏸️",
                        "label": "Excessive Idling",
                        "label_es": "Ralentí Excesivo",
                        "description": f"Engine running without moving ({idle_pct:.0f}% of time)",
                        "description_es": f"Motor encendido sin moverse ({idle_pct:.0f}% del tiempo)",
                        "pct_of_time": round(idle_pct, 1),
                        "mpg_impact": 0,
                        "extra_gallons": round(idle_fuel, 1),
                        "extra_cost": round(idle_fuel * FUEL_PRICE, 2),
                        "data_points": total_idle,
                        "recommendation": "Turn off engine when stopped for >2 minutes, consider APU for sleeper",
                        "recommendation_es": "Apagar motor si parado >2 min, considerar APU para dormir",
                        "source": "truck_status",
                    }
                )

            # 5. 🆕 Low Oil Pressure (Mechanical Issue)
            # Use total readings as base to get realistic percentage
            total_readings = total_moving + total_idle
            if low_oil_pressure_count > 0 and total_readings > 0:
                # Calculate % based on ALL readings, not just oil pressure readings
                low_oil_pct = (low_oil_pressure_count / total_readings) * 100
                # Cap the percentage at a reasonable max (can't be >50% low pressure realistically)
                low_oil_pct = min(low_oil_pct, 25.0)
                # Low oil pressure causes ~3-5% efficiency loss due to increased friction
                estimated_mpg_loss = (
                    avg_mpg * 0.04
                )  # 4% efficiency loss estimate (more conservative)
                low_oil_miles_est = total_miles * (low_oil_pct / 100)
                extra_gal_oil = (
                    low_oil_miles_est / (avg_mpg - estimated_mpg_loss)
                    - low_oil_miles_est / avg_mpg
                    if avg_mpg > estimated_mpg_loss
                    else 0
                )
                extra_gal_oil = max(
                    0, min(extra_gal_oil, total_fuel * 0.10)
                )  # Cap at 10% of total fuel

                causes.append(
                    {
                        "cause": "low_oil_pressure",
                        "icon": "🛢️",
                        "label": "Low Oil Pressure Events",
                        "label_es": "Eventos de Presión de Aceite Baja",
                        "description": f"Oil pressure below 35 PSI ({low_oil_pressure_count} events, min {min_oil_pressure:.0f} PSI)",
                        "description_es": f"Presión de aceite bajo 35 PSI ({low_oil_pressure_count} eventos, mín {min_oil_pressure:.0f} PSI)",
                        "pct_of_time": round(low_oil_pct, 1),
                        "mpg_impact": round(estimated_mpg_loss, 2),
                        "current_avg": round(avg_oil_pressure, 1),
                        "min_recorded": round(min_oil_pressure, 1),
                        "extra_gallons": round(extra_gal_oil, 1),
                        "extra_cost": round(extra_gal_oil * FUEL_PRICE, 2),
                        "data_points": low_oil_pressure_count,
                        "recommendation": "⚠️ MECHANICAL: Check oil level, oil pump, and for leaks. Low pressure increases friction and fuel consumption.",
                        "recommendation_es": "⚠️ MECÁNICO: Revisar nivel de aceite, bomba y fugas. Presión baja aumenta fricción y consumo.",
                        "source": "oil_pressure_sensor",
                        "severity": "warning",
                    }
                )

            # 6. 🆕 High Oil Temperature (Engine Stress)
            if high_oil_temp_count > 0 and total_readings > 0:
                # Calculate % based on ALL readings
                high_oil_temp_pct = (high_oil_temp_count / total_readings) * 100
                # Cap at reasonable max
                high_oil_temp_pct = min(high_oil_temp_pct, 20.0)
                # High oil temp causes ~3-5% efficiency loss
                estimated_mpg_loss = avg_mpg * 0.04
                high_temp_miles_est = total_miles * (high_oil_temp_pct / 100)
                extra_gal_temp = (
                    high_temp_miles_est / (avg_mpg - estimated_mpg_loss)
                    - high_temp_miles_est / avg_mpg
                    if avg_mpg > estimated_mpg_loss
                    else 0
                )
                extra_gal_temp = max(
                    0, min(extra_gal_temp, total_fuel * 0.08)
                )  # Cap at 8% of total fuel

                causes.append(
                    {
                        "cause": "high_oil_temp",
                        "icon": "🌡️",
                        "label": "High Oil Temperature",
                        "label_es": "Temperatura de Aceite Alta",
                        "description": f"Oil temp above 240°F ({high_oil_temp_count} events, max {max_oil_temp:.0f}°F)",
                        "description_es": f"Temp. aceite sobre 240°F ({high_oil_temp_count} eventos, máx {max_oil_temp:.0f}°F)",
                        "pct_of_time": round(high_oil_temp_pct, 1),
                        "mpg_impact": round(estimated_mpg_loss, 2),
                        "current_avg": round(avg_oil_temp, 1),
                        "max_recorded": round(max_oil_temp, 1),
                        "extra_gallons": round(extra_gal_temp, 1),
                        "extra_cost": round(extra_gal_temp * FUEL_PRICE, 2),
                        "data_points": high_oil_temp_count,
                        "recommendation": "⚠️ MECHANICAL: Check oil cooler, coolant system. Hot oil loses viscosity and increases wear.",
                        "recommendation_es": "⚠️ MECÁNICO: Revisar enfriador de aceite y sistema de refrigeración. Aceite caliente pierde viscosidad.",
                        "source": "oil_temp_sensor",
                        "severity": "warning",
                    }
                )

            # Calculate total attribution
            total_extra_cost = sum(c.get("extra_cost", 0) for c in causes)

            # Sort by impact (cost)
            causes.sort(key=lambda x: x.get("extra_cost", 0), reverse=True)

            # Add percentage of total inefficiency
            for cause in causes:
                cause["pct_of_inefficiency"] = round(
                    (
                        (cause["extra_cost"] / total_extra_cost * 100)
                        if total_extra_cost > 0
                        else 0
                    ),
                    1,
                )

            # 🆕 Sensor coverage info
            sensor_coverage = {
                "speed_rpm": {"available": True, "readings": total_moving},
                "engine_load": {
                    "available": high_load_count > 0 or mpg_at_optimal_load is not None,
                    "readings": high_load_count,
                },
                "oil_pressure": {
                    "available": oil_pressure_readings > 0,
                    "readings": oil_pressure_readings,
                    "avg_psi": round(avg_oil_pressure, 1) if avg_oil_pressure else None,
                },
                "oil_temp": {
                    "available": oil_temp_readings > 0,
                    "readings": oil_temp_readings,
                    "avg_f": round(avg_oil_temp, 1) if avg_oil_temp else None,
                },
            }

            return {
                "truck_id": truck_id,
                "period_days": days_back,
                "total_miles": round(total_miles, 0),
                "avg_mpg": round(avg_mpg, 2),
                "baseline_mpg": BASELINE_MPG,
                "total_inefficiency_cost": round(total_extra_cost, 2),
                "causes": causes,
                "data_quality": {
                    "total_readings": total_moving + total_idle,
                    "moving_readings": total_moving,
                    "idle_readings": total_idle,
                },
                "sensor_coverage": sensor_coverage,
            }

    except Exception as e:
        logger.error(f"Error analyzing inefficiency causes: {e}")
        return {"error": str(e), "causes": []}


@cached(ttl_seconds=300, key_prefix="get_cost_attribution_report")
def get_cost_attribution_report(days_back: int = 30) -> Dict:
    """
    Generate detailed cost attribution report for fleet fuel expenses.
    🔧 v3.15.0: Added 5-minute cache for performance (heavy report)

    Breaks down costs by:
    - Per-truck consumption
    - Driving vs idling
    - Efficiency losses
    - Waste categories

    Args:
        days_back: Days of history to analyze

    Returns:
        Dict with comprehensive cost breakdown and savings opportunities
    """
    engine = get_sqlalchemy_engine()
    FUEL_PRICE = 3.50
    BASELINE_MPG = 5.7
    BASELINE_IDLE_GPH = 0.8

    try:
        with engine.connect() as conn:
            # Get per-truck statistics
            query = text(
                """
                SELECT 
                    truck_id,
                    COUNT(*) as total_readings,
                    SUM(CASE WHEN truck_status = 'MOVING' THEN 1 ELSE 0 END) as moving_readings,
                    SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN 1 ELSE 0 END) as idle_readings,
                    AVG(CASE WHEN truck_status = 'MOVING' AND mpg_current > 2 THEN mpg_current END) as avg_mpg,
                    AVG(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph END) as avg_idle_gph,
                    MAX(odometer_mi) - MIN(odometer_mi) as total_miles,
                    SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph / 60.0 END) as total_idle_gallons_approx
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL :days DAY
                GROUP BY truck_id
                HAVING COUNT(*) > 100
                ORDER BY total_miles DESC
            """
            )

            result = conn.execute(query, {"days": days_back})
            rows = result.fetchall()

            truck_costs = []
            fleet_totals = {
                "total_miles": 0,
                "total_driving_fuel": 0,
                "total_idle_fuel": 0,
                "total_cost": 0,
                "efficiency_loss_gal": 0,
                "idle_waste_gal": 0,
            }

            for row in rows:
                tid = row[0]
                avg_mpg = float(row[4] or BASELINE_MPG)
                avg_idle = float(row[5] or BASELINE_IDLE_GPH)
                miles = float(row[6] or 0)
                idle_gal_approx = float(row[7] or 0)

                # 🔧 Sanity check: max reasonable miles in period
                # At 70mph average, 10hrs/day driving = 700 miles/day max
                max_reasonable_miles = days_back * 800  # 800 miles/day is very generous
                if miles > max_reasonable_miles:
                    logger.warning(
                        f"[{tid}] Unrealistic miles: {miles:.0f} (max {max_reasonable_miles}), skipping"
                    )
                    continue

                if miles <= 0:
                    continue

                # Calculate driving fuel
                driving_fuel = miles / avg_mpg if avg_mpg > 0 else miles / BASELINE_MPG
                expected_driving_fuel = miles / BASELINE_MPG
                driving_efficiency_loss = driving_fuel - expected_driving_fuel

                # Calculate idle fuel (estimate from readings)
                idle_fuel = idle_gal_approx
                expected_idle_fuel = (
                    idle_fuel * (BASELINE_IDLE_GPH / avg_idle)
                    if avg_idle > 0
                    else idle_fuel
                )
                idle_waste = (
                    idle_fuel - expected_idle_fuel if expected_idle_fuel > 0 else 0
                )

                # Total costs
                total_fuel = driving_fuel + idle_fuel
                total_cost = total_fuel * FUEL_PRICE

                # Waste breakdown
                efficiency_loss_cost = max(0, driving_efficiency_loss) * FUEL_PRICE
                idle_waste_cost = max(0, idle_waste) * FUEL_PRICE

                truck_costs.append(
                    {
                        "truck_id": tid,
                        "total_miles": round(miles, 0),
                        "avg_mpg": round(avg_mpg, 2),
                        "avg_idle_gph": round(avg_idle, 2),
                        "driving_fuel_gal": round(driving_fuel, 1),
                        "idle_fuel_gal": round(idle_fuel, 1),
                        "total_fuel_gal": round(total_fuel, 1),
                        "total_fuel_cost": round(total_cost, 2),
                        "efficiency_score": round(
                            (BASELINE_MPG / avg_mpg * 100) if avg_mpg > 0 else 50, 0
                        ),
                        # 🆕 Flattened structure for frontend compatibility
                        "driving_cost": round(driving_fuel * FUEL_PRICE, 2),
                        "idle_cost": round(idle_fuel * FUEL_PRICE, 2),
                        "waste_cost": round(efficiency_loss_cost + idle_waste_cost, 2),
                        "efficiency_loss": round(efficiency_loss_cost, 2),
                        "cost_per_mile": (
                            round(total_cost / miles, 3) if miles > 0 else 0
                        ),
                        # Keep nested breakdown for backward compatibility
                        "cost_breakdown": {
                            "driving_cost": round(driving_fuel * FUEL_PRICE, 2),
                            "idle_cost": round(idle_fuel * FUEL_PRICE, 2),
                            "efficiency_loss": round(efficiency_loss_cost, 2),
                            "idle_waste": round(idle_waste_cost, 2),
                        },
                    }
                )

                # Accumulate fleet totals
                fleet_totals["total_miles"] += miles
                fleet_totals["total_driving_fuel"] += driving_fuel
                fleet_totals["total_idle_fuel"] += idle_fuel
                fleet_totals["total_cost"] += total_cost
                fleet_totals["efficiency_loss_gal"] += max(0, driving_efficiency_loss)
                fleet_totals["idle_waste_gal"] += max(0, idle_waste)

            # Calculate savings opportunities
            savings_opportunities = []

            # MPG improvement opportunity
            if fleet_totals["efficiency_loss_gal"] > 0:
                savings_opportunities.append(
                    {
                        "category": "Efficiency Improvement",
                        "potential_savings": round(
                            fleet_totals["efficiency_loss_gal"] * FUEL_PRICE, 0
                        ),
                        "recommendation": "Bring all trucks to baseline MPG through maintenance and training",
                    }
                )

            # Idle reduction opportunity
            if fleet_totals["idle_waste_gal"] > 0:
                savings_opportunities.append(
                    {
                        "category": "Idle Reduction",
                        "potential_savings": round(
                            fleet_totals["idle_waste_gal"] * FUEL_PRICE, 0
                        ),
                        "recommendation": "Reduce idle time through driver coaching and APU installation",
                    }
                )

            # Calculate totals for frontend
            total_driving_cost = fleet_totals["total_driving_fuel"] * FUEL_PRICE
            total_idle_cost = fleet_totals["total_idle_fuel"] * FUEL_PRICE
            total_waste_cost = (
                fleet_totals["efficiency_loss_gal"] + fleet_totals["idle_waste_gal"]
            ) * FUEL_PRICE

            return {
                "period_days": days_back,
                # 🆕 Frontend-expected fields
                "total_fleet_cost": round(fleet_totals["total_cost"], 2),
                "total_driving_cost": round(total_driving_cost, 2),
                "total_idle_cost": round(total_idle_cost, 2),
                "total_waste_cost": round(total_waste_cost, 2),
                "by_truck": truck_costs[:50],  # Top 50 trucks
                "savings_opportunities": savings_opportunities,
                "insights": [
                    {
                        "type": "efficiency",
                        "finding": f"Fleet averages ${round(fleet_totals['total_cost'] / fleet_totals['total_miles'], 2) if fleet_totals['total_miles'] > 0 else 0:.2f}/mile",
                        "recommendation": "Focus on trucks with highest cost per mile for improvements",
                    }
                ],
                # Legacy fields for backward compatibility
                "fuel_price_per_gal": FUEL_PRICE,
                "baseline_mpg": BASELINE_MPG,
                "baseline_idle_gph": BASELINE_IDLE_GPH,
                "fleet_summary": {
                    "total_trucks": len(truck_costs),
                    "total_miles": round(fleet_totals["total_miles"], 0),
                    "total_fuel_gal": round(
                        fleet_totals["total_driving_fuel"]
                        + fleet_totals["total_idle_fuel"],
                        0,
                    ),
                    "total_cost": round(fleet_totals["total_cost"], 2),
                    "cost_per_mile": (
                        round(
                            fleet_totals["total_cost"] / fleet_totals["total_miles"], 3
                        )
                        if fleet_totals["total_miles"] > 0
                        else 0
                    ),
                },
            }

    except Exception as e:
        logger.error(f"Error in cost attribution report: {e}")
        return {
            "period_days": days_back,
            "error": str(e),
            "fleet_summary": {},
            "truck_breakdown": [],
            "savings_opportunities": [],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 GEOFENCING FUNCTIONS (v3.12.0)
# ═══════════════════════════════════════════════════════════════════════════════


# Predefined geofence zones (can be expanded via config file or database)
GEOFENCE_ZONES = {
    "HOME_BASE": {
        "name": "Home Base",
        "type": "CIRCLE",
        "lat": 40.7128,  # Example: NYC
        "lon": -74.0060,
        "radius_miles": 5.0,
        "alert_on_exit": True,
        "alert_on_enter": False,
    },
    "FUEL_STATION_1": {
        "name": "Main Fuel Station",
        "type": "CIRCLE",
        "lat": 40.7589,
        "lon": -73.9851,
        "radius_miles": 0.5,
        "alert_on_exit": False,
        "alert_on_enter": True,
    },
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates in miles.
    Uses Haversine formula for great-circle distance.
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def check_geofence_status(
    truck_id: str, latitude: float, longitude: float, zones: Optional[Dict] = None
) -> List[Dict]:
    """
    Check if a truck is inside any geofence zones.

    Args:
        truck_id: Truck identifier
        latitude: Current GPS latitude
        longitude: Current GPS longitude
        zones: Optional custom zones dict (uses GEOFENCE_ZONES if not provided)

    Returns:
        List of zones the truck is currently inside
    """
    if zones is None:
        zones = GEOFENCE_ZONES

    inside_zones = []

    for zone_id, zone in zones.items():
        if zone["type"] == "CIRCLE":
            distance = haversine_distance(latitude, longitude, zone["lat"], zone["lon"])

            if distance <= zone["radius_miles"]:
                inside_zones.append(
                    {
                        "zone_id": zone_id,
                        "zone_name": zone["name"],
                        "distance_miles": round(distance, 2),
                        "radius_miles": zone["radius_miles"],
                    }
                )

    return inside_zones


def get_geofence_events(
    truck_id: Optional[str] = None, hours_back: int = 24, zones: Optional[Dict] = None
) -> Dict:
    """
    Analyze geofence entry/exit events for trucks.

    This function tracks when trucks enter or exit defined zones
    by analyzing GPS history.

    Args:
        truck_id: Optional specific truck to analyze
        hours_back: Hours of history to analyze
        zones: Optional custom zones dict

    Returns:
        Dict with geofence events and statistics
    """
    engine = get_sqlalchemy_engine()

    if zones is None:
        zones = GEOFENCE_ZONES

    try:
        with engine.connect() as conn:
            # Get GPS history
            truck_filter = f"AND truck_id = '{truck_id}'" if truck_id else ""

            query = text(
                f"""
                SELECT 
                    truck_id,
                    timestamp_utc,
                    latitude,
                    longitude,
                    truck_status,
                    speed_mph
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL :hours HOUR
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
                {truck_filter}
                ORDER BY truck_id, timestamp_utc
            """
            )

            result = conn.execute(query, {"hours": hours_back})
            rows = result.fetchall()

            if not rows:
                return {
                    "period_hours": hours_back,
                    "truck_id": truck_id,
                    "total_events": 0,
                    "events": [],
                    "zone_summary": {},
                }

            # Track zone transitions
            events = []
            zone_summary = {
                zone_id: {"entries": 0, "exits": 0, "time_inside_min": 0}
                for zone_id in zones
            }
            truck_zone_state: Dict[str, Dict[str, bool]] = (
                {}
            )  # truck_id -> {zone_id: inside}
            truck_zone_entry_time: Dict[str, Dict[str, datetime]] = (
                {}
            )  # For time tracking

            for row in rows:
                tid = row[0]
                timestamp = row[1]
                lat = float(row[2])
                lon = float(row[3])
                status = row[4]
                speed = float(row[5] or 0)

                # Initialize truck state if needed
                if tid not in truck_zone_state:
                    truck_zone_state[tid] = {}
                    truck_zone_entry_time[tid] = {}

                # Check each zone
                for zone_id, zone in zones.items():
                    if zone["type"] == "CIRCLE":
                        distance = haversine_distance(
                            lat, lon, zone["lat"], zone["lon"]
                        )
                        is_inside = distance <= zone["radius_miles"]
                        was_inside = truck_zone_state[tid].get(zone_id, False)

                        # Detect transitions
                        if is_inside and not was_inside:
                            # ENTRY event
                            if zone.get("alert_on_enter", False):
                                events.append(
                                    {
                                        "truck_id": tid,
                                        "zone_id": zone_id,
                                        "zone_name": zone["name"],
                                        "event_type": "ENTRY",
                                        "timestamp": (
                                            timestamp.isoformat() if timestamp else None
                                        ),
                                        "latitude": lat,
                                        "longitude": lon,
                                        "distance_miles": round(distance, 2),
                                        "speed_mph": speed,
                                    }
                                )
                            zone_summary[zone_id]["entries"] += 1
                            truck_zone_entry_time[tid][zone_id] = timestamp

                        elif not is_inside and was_inside:
                            # EXIT event
                            if zone.get("alert_on_exit", False):
                                events.append(
                                    {
                                        "truck_id": tid,
                                        "zone_id": zone_id,
                                        "zone_name": zone["name"],
                                        "event_type": "EXIT",
                                        "timestamp": (
                                            timestamp.isoformat() if timestamp else None
                                        ),
                                        "latitude": lat,
                                        "longitude": lon,
                                        "distance_miles": round(distance, 2),
                                        "speed_mph": speed,
                                    }
                                )
                            zone_summary[zone_id]["exits"] += 1

                            # Calculate time inside
                            if (
                                tid in truck_zone_entry_time
                                and zone_id in truck_zone_entry_time[tid]
                            ):
                                entry_time = truck_zone_entry_time[tid][zone_id]
                                if entry_time and timestamp:
                                    time_inside = (
                                        timestamp - entry_time
                                    ).total_seconds() / 60
                                    zone_summary[zone_id][
                                        "time_inside_min"
                                    ] += time_inside

                        truck_zone_state[tid][zone_id] = is_inside

            # Round time values
            for zone_id in zone_summary:
                zone_summary[zone_id]["time_inside_min"] = round(
                    zone_summary[zone_id]["time_inside_min"], 0
                )

            return {
                "period_hours": hours_back,
                "truck_id": truck_id,
                "total_events": len(events),
                "events": events[-100:],  # Last 100 events
                "zone_summary": zone_summary,
                "zones_monitored": list(zones.keys()),
            }

    except Exception as e:
        logger.error(f"Error in geofence analysis: {e}")
        return {
            "period_hours": hours_back,
            "truck_id": truck_id,
            "total_events": 0,
            "events": [],
            "zone_summary": {},
            "error": str(e),
        }


def get_truck_location_history(truck_id: str, hours_back: int = 24) -> List[Dict]:
    """
    Get GPS location history for a truck (for map visualization).

    Args:
        truck_id: Truck identifier
        hours_back: Hours of history to retrieve

    Returns:
        List of location points with timestamps
    """
    engine = get_sqlalchemy_engine()

    try:
        with engine.connect() as conn:
            query = text(
                """
                SELECT 
                    timestamp_utc,
                    latitude,
                    longitude,
                    truck_status,
                    speed_mph,
                    estimated_pct as fuel_pct
                FROM fuel_metrics
                WHERE truck_id = :truck_id
                AND timestamp_utc > NOW() - INTERVAL :hours HOUR
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
                ORDER BY timestamp_utc
            """
            )

            result = conn.execute(query, {"truck_id": truck_id, "hours": hours_back})
            rows = result.fetchall()

            locations = []
            for row in rows:
                locations.append(
                    {
                        "timestamp": row[0].isoformat() if row[0] else None,
                        "latitude": float(row[1]),
                        "longitude": float(row[2]),
                        "status": row[3],
                        "speed_mph": float(row[4] or 0),
                        "fuel_pct": float(row[5] or 0),
                    }
                )

            return locations

    except Exception as e:
        logger.error(f"Error getting location history for {truck_id}: {e}")
        return []


def _empty_theft_analysis(days: int, price: float) -> Dict[str, Any]:
    """Return empty theft analysis response"""
    return {
        "period_days": days,
        "fuel_price_per_gal": price,
        "detection_thresholds": {"min_gallons": 5.0, "min_pct": 3.0},
        "summary": {
            "total_events": 0,
            "high_confidence_events": 0,
            "total_suspected_loss_gallons": 0,
            "total_suspected_loss_usd": 0,
            "trucks_affected": 0,
        },
        "trucks_at_risk": [],
        "events": [],
        "insights": [],
    }


if __name__ == "__main__":
    # Test the connection and queries
    logging.basicConfig(level=logging.INFO)

    print("Testing MySQL connection...")
    if test_connection():
        print("\n1. Testing latest truck data...")
        df = get_latest_truck_data(hours_back=24)
        print(f"   Found {len(df)} trucks")

        if not df.empty:
            truck_id = df.iloc[0]["truck_id"]
            print(f"\n2. Testing history for {truck_id}...")
            history = get_truck_history(truck_id, hours_back=168)
            print(f"   Found {len(history)} records")

            print(f"\n3. Testing refuel history...")
            refuels = get_refuel_history(days_back=7)
            print(f"   Found {len(refuels)} refuel events")

            print(f"\n4. Testing fleet summary...")
            summary = get_fleet_summary()
            print(f"   {summary}")

            print(f"\n5. Testing efficiency stats for {truck_id}...")
            stats = get_truck_efficiency_stats(truck_id, days_back=30)
            print(f"   {stats}")


# NOTE: Engine health monitoring functions were moved to engine_health_router.py
# which implements them directly with inline queries for better maintainability.


def get_inefficiency_by_truck(days_back: int = 30, sort_by: str = "total_cost") -> Dict:
    """
    🆕 v3.12.33: Get inefficiency breakdown BY TRUCK with all causes.

    Returns each truck with their specific inefficiency causes and costs,
    sorted by the specified metric.

    Args:
        days_back: Days of history to analyze
        sort_by: Sort metric - 'total_cost', 'high_load', 'idle', 'high_speed', 'low_mpg'

    Returns:
        Dict with fleet summary and per-truck breakdown
    """
    engine = get_sqlalchemy_engine()
    FUEL_PRICE = 3.50
    BASELINE_MPG = 5.7
    BASELINE_IDLE_GPH = 0.8
    OPTIMAL_SPEED_MAX = 65.0
    OPTIMAL_RPM_MAX = 1600
    OPTIMAL_LOAD_MAX = 80
    LOW_OIL_PRESSURE = 35
    HIGH_OIL_TEMP = 240

    try:
        with engine.connect() as conn:
            # 🔧 FIX v3.14.3: Filter invalid odometer readings (< 1000) and calculate actual days
            query = text(
                """
                SELECT 
                    truck_id,
                    
                    -- Basic metrics
                    COUNT(*) as total_readings,
                    COUNT(CASE WHEN truck_status = 'MOVING' THEN 1 END) as moving_readings,
                    COUNT(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN 1 END) as idle_readings,
                    -- 🔧 FIX: Only use valid odometer readings (> 1000 mi) to avoid sensor noise
                    MAX(CASE WHEN odometer_mi > 1000 THEN odometer_mi END) - MIN(CASE WHEN odometer_mi > 1000 THEN odometer_mi END) as total_miles,
                    AVG(CASE WHEN mpg_current > 3 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
                    -- 🆕 Actual days of data for this truck
                    DATEDIFF(MAX(timestamp_utc), MIN(timestamp_utc)) as actual_days,
                    MAX(CASE WHEN odometer_mi > 1000 THEN odometer_mi END) as current_odometer,
                    
                    -- High Speed (>65 mph)
                    COUNT(CASE WHEN truck_status = 'MOVING' AND speed_mph > :speed_max THEN 1 END) as high_speed_count,
                    AVG(CASE WHEN truck_status = 'MOVING' AND speed_mph > :speed_max THEN speed_mph END) as avg_high_speed,
                    AVG(CASE WHEN truck_status = 'MOVING' AND speed_mph > :speed_max THEN mpg_current END) as mpg_at_high_speed,
                    AVG(CASE WHEN truck_status = 'MOVING' AND speed_mph BETWEEN 55 AND 65 THEN mpg_current END) as mpg_at_optimal_speed,
                    
                    -- High RPM (>1600)
                    COUNT(CASE WHEN rpm > :rpm_max THEN 1 END) as high_rpm_count,
                    AVG(CASE WHEN rpm > :rpm_max THEN rpm END) as avg_high_rpm,
                    AVG(CASE WHEN rpm > :rpm_max THEN mpg_current END) as mpg_at_high_rpm,
                    AVG(CASE WHEN rpm BETWEEN 1200 AND 1600 THEN mpg_current END) as mpg_at_optimal_rpm,
                    
                    -- High Engine Load (>80%)
                    COUNT(CASE WHEN engine_load_pct > :load_max THEN 1 END) as high_load_count,
                    AVG(CASE WHEN engine_load_pct > :load_max THEN engine_load_pct END) as avg_high_load,
                    AVG(CASE WHEN engine_load_pct > :load_max THEN mpg_current END) as mpg_at_high_load,
                    AVG(CASE WHEN engine_load_pct BETWEEN 30 AND 60 THEN mpg_current END) as mpg_at_optimal_load,
                    
                    -- Idle
                    SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph / 60.0 END) as idle_fuel_gal,
                    AVG(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph END) as avg_idle_gph,
                    
                    -- Low Oil Pressure (<35 PSI)
                    COUNT(CASE WHEN oil_pressure_psi < :low_oil_psi AND oil_pressure_psi > 0 THEN 1 END) as low_oil_count,
                    MIN(CASE WHEN oil_pressure_psi > 0 THEN oil_pressure_psi END) as min_oil_psi,
                    
                    -- High Oil Temp (>240°F)
                    COUNT(CASE WHEN oil_temp_f > :high_oil_temp THEN 1 END) as high_oil_temp_count,
                    MAX(oil_temp_f) as max_oil_temp
                    
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL :days DAY
                GROUP BY truck_id
                HAVING COUNT(*) > 100
                ORDER BY truck_id
            """
            )

            result = conn.execute(
                query,
                {
                    "days": days_back,
                    "speed_max": OPTIMAL_SPEED_MAX,
                    "rpm_max": OPTIMAL_RPM_MAX,
                    "load_max": OPTIMAL_LOAD_MAX,
                    "low_oil_psi": LOW_OIL_PRESSURE,
                    "high_oil_temp": HIGH_OIL_TEMP,
                },
            )

            trucks_data = []
            fleet_totals = {
                "total_cost": 0.0,
                "high_load_cost": 0.0,
                "high_speed_cost": 0.0,
                "high_rpm_cost": 0.0,
                "idle_cost": 0.0,
                "low_oil_cost": 0.0,
                "high_temp_cost": 0.0,
            }

            for row in result:
                truck_id = row[0]
                total_readings = int(row[1] or 0)
                moving_readings = int(row[2] or 0)
                idle_readings = int(row[3] or 0)
                total_miles = float(row[4] or 0)
                avg_mpg = float(row[5] or BASELINE_MPG)
                # 🆕 v3.14.3: New fields for actual period and odometer
                actual_days = int(row[6] or 1)  # Avoid division by zero
                current_odometer = float(row[7] or 0)

                if total_miles <= 0 or moving_readings == 0:
                    continue

                # 🔧 Sanity check: if miles seem unreasonable for the period, cap it
                max_reasonable_miles = actual_days * 800  # Max 800 mi/day
                if total_miles > max_reasonable_miles and actual_days > 0:
                    total_miles = max_reasonable_miles

                # High Speed calculations (indices shifted by +2)
                high_speed_count = int(row[8] or 0)
                avg_high_speed = float(row[9] or 70)
                mpg_at_high_speed = float(row[10] or avg_mpg)
                mpg_at_optimal_speed = float(row[11] or avg_mpg)

                high_speed_pct = (
                    (high_speed_count / moving_readings * 100)
                    if moving_readings > 0
                    else 0
                )
                high_speed_miles = total_miles * (high_speed_pct / 100)
                high_speed_extra_gal = 0
                if (
                    mpg_at_high_speed > 0
                    and mpg_at_optimal_speed > 0
                    and high_speed_miles > 0
                ):
                    high_speed_extra_gal = max(
                        0,
                        (high_speed_miles / mpg_at_high_speed)
                        - (high_speed_miles / mpg_at_optimal_speed),
                    )
                high_speed_cost = high_speed_extra_gal * FUEL_PRICE

                # High RPM calculations (indices +2 for new fields)
                high_rpm_count = int(row[12] or 0)
                avg_high_rpm = float(row[13] or 1700)
                mpg_at_high_rpm = float(row[14] or avg_mpg)
                mpg_at_optimal_rpm = float(row[15] or avg_mpg)

                high_rpm_pct = (
                    (high_rpm_count / moving_readings * 100)
                    if moving_readings > 0
                    else 0
                )
                high_rpm_miles = total_miles * (high_rpm_pct / 100)
                high_rpm_extra_gal = 0
                if (
                    mpg_at_high_rpm > 0
                    and mpg_at_optimal_rpm > 0
                    and high_rpm_miles > 0
                ):
                    high_rpm_extra_gal = max(
                        0,
                        (high_rpm_miles / mpg_at_high_rpm)
                        - (high_rpm_miles / mpg_at_optimal_rpm),
                    )
                high_rpm_cost = high_rpm_extra_gal * FUEL_PRICE

                # High Engine Load calculations (indices +2 for new fields)
                high_load_count = int(row[16] or 0)
                avg_high_load = float(row[17] or 90)
                mpg_at_high_load = float(row[18] or avg_mpg)
                mpg_at_optimal_load = float(row[19] or avg_mpg)

                high_load_pct = (
                    (high_load_count / moving_readings * 100)
                    if moving_readings > 0
                    else 0
                )
                high_load_miles = total_miles * (high_load_pct / 100)
                high_load_extra_gal = 0
                if (
                    mpg_at_high_load > 0
                    and mpg_at_optimal_load > 0
                    and high_load_miles > 0
                ):
                    high_load_extra_gal = max(
                        0,
                        (high_load_miles / mpg_at_high_load)
                        - (high_load_miles / mpg_at_optimal_load),
                    )
                high_load_cost = high_load_extra_gal * FUEL_PRICE

                # Idle calculations (indices +2 for new fields)
                idle_fuel_gal = float(row[20] or 0)
                avg_idle_gph = float(row[21] or BASELINE_IDLE_GPH)

                # Calculate idle "waste" (anything above baseline idle rate)
                idle_waste_gal = 0
                if avg_idle_gph > BASELINE_IDLE_GPH and idle_fuel_gal > 0:
                    waste_ratio = (avg_idle_gph - BASELINE_IDLE_GPH) / avg_idle_gph
                    idle_waste_gal = idle_fuel_gal * waste_ratio
                idle_cost = idle_waste_gal * FUEL_PRICE

                # Low Oil Pressure (mechanical issue indicator) (indices +2)
                low_oil_count = int(row[22] or 0)
                min_oil_psi = float(row[23] or 35)

                low_oil_pct = (
                    (low_oil_count / total_readings * 100) if total_readings > 0 else 0
                )
                # Estimate 5% efficiency loss during low oil pressure events
                low_oil_miles = total_miles * (low_oil_pct / 100)
                low_oil_extra_gal = (
                    (low_oil_miles / (avg_mpg * 0.95) - low_oil_miles / avg_mpg)
                    if avg_mpg > 0
                    else 0
                )
                low_oil_extra_gal = max(0, low_oil_extra_gal)
                low_oil_cost = low_oil_extra_gal * FUEL_PRICE

                # High Oil Temp (engine stress) (indices +2)
                high_oil_temp_count = int(row[24] or 0)
                max_oil_temp = float(row[25] or 200)

                high_temp_pct = (
                    (high_oil_temp_count / total_readings * 100)
                    if total_readings > 0
                    else 0
                )
                # Estimate 4% efficiency loss during high temp
                high_temp_miles = total_miles * (high_temp_pct / 100)
                high_temp_extra_gal = (
                    (high_temp_miles / (avg_mpg * 0.96) - high_temp_miles / avg_mpg)
                    if avg_mpg > 0
                    else 0
                )
                high_temp_extra_gal = max(0, high_temp_extra_gal)
                high_temp_cost = high_temp_extra_gal * FUEL_PRICE

                # Total cost for this truck
                total_truck_cost = (
                    high_load_cost
                    + high_speed_cost
                    + high_rpm_cost
                    + idle_cost
                    + low_oil_cost
                    + high_temp_cost
                )

                # MPG vs baseline efficiency
                mpg_vs_baseline = (
                    ((avg_mpg - BASELINE_MPG) / BASELINE_MPG * 100)
                    if BASELINE_MPG > 0
                    else 0
                )

                truck_data = {
                    "truck_id": truck_id,
                    "total_miles": round(total_miles, 0),
                    "current_odometer": round(current_odometer, 0),
                    "actual_days": actual_days,  # 🆕 v3.14.3: Real days of data
                    "avg_mpg": round(avg_mpg, 2),
                    "mpg_vs_baseline": round(mpg_vs_baseline, 1),
                    "total_readings": total_readings,
                    "total_inefficiency_cost": round(total_truck_cost, 2),
                    "causes": {
                        "high_engine_load": {
                            "events": high_load_count,
                            "pct_of_time": round(high_load_pct, 1),
                            "avg_load": round(avg_high_load, 0),
                            "extra_gallons": round(high_load_extra_gal, 1),
                            "extra_cost": round(high_load_cost, 2),
                        },
                        "high_speed": {
                            "events": high_speed_count,
                            "pct_of_time": round(high_speed_pct, 1),
                            "avg_speed": round(avg_high_speed, 0),
                            "extra_gallons": round(high_speed_extra_gal, 1),
                            "extra_cost": round(high_speed_cost, 2),
                        },
                        "high_rpm": {
                            "events": high_rpm_count,
                            "pct_of_time": round(high_rpm_pct, 1),
                            "avg_rpm": round(avg_high_rpm, 0),
                            "extra_gallons": round(high_rpm_extra_gal, 1),
                            "extra_cost": round(high_rpm_cost, 2),
                        },
                        "excessive_idle": {
                            "events": idle_readings,
                            "total_gallons": round(idle_fuel_gal, 1),
                            "waste_gallons": round(idle_waste_gal, 1),
                            "avg_gph": round(avg_idle_gph, 2),
                            "extra_cost": round(idle_cost, 2),
                        },
                        "low_oil_pressure": {
                            "events": low_oil_count,
                            "pct_of_time": round(low_oil_pct, 1),
                            "min_psi": round(min_oil_psi, 0),
                            "extra_gallons": round(low_oil_extra_gal, 1),
                            "extra_cost": round(low_oil_cost, 2),
                            "severity": "warning" if low_oil_count > 100 else "info",
                        },
                        "high_oil_temp": {
                            "events": high_oil_temp_count,
                            "pct_of_time": round(high_temp_pct, 1),
                            "max_temp_f": round(max_oil_temp, 0),
                            "extra_gallons": round(high_temp_extra_gal, 1),
                            "extra_cost": round(high_temp_cost, 2),
                            "severity": (
                                "warning" if high_oil_temp_count > 50 else "info"
                            ),
                        },
                    },
                    "top_issue": None,  # Will be set below
                }

                # Determine top issue for this truck
                cause_costs = [
                    ("high_engine_load", high_load_cost),
                    ("high_speed", high_speed_cost),
                    ("high_rpm", high_rpm_cost),
                    ("excessive_idle", idle_cost),
                    ("low_oil_pressure", low_oil_cost),
                    ("high_oil_temp", high_temp_cost),
                ]
                top_cause = max(cause_costs, key=lambda x: x[1])
                truck_data["top_issue"] = top_cause[0] if top_cause[1] > 0 else None

                trucks_data.append(truck_data)

                # Aggregate fleet totals
                fleet_totals["total_cost"] += total_truck_cost
                fleet_totals["high_load_cost"] += high_load_cost
                fleet_totals["high_speed_cost"] += high_speed_cost
                fleet_totals["high_rpm_cost"] += high_rpm_cost
                fleet_totals["idle_cost"] += idle_cost
                fleet_totals["low_oil_cost"] += low_oil_cost
                fleet_totals["high_temp_cost"] += high_temp_cost

            # Sort trucks by the specified metric
            sort_key_map = {
                "total_cost": lambda x: x["total_inefficiency_cost"],
                "high_load": lambda x: x["causes"]["high_engine_load"]["extra_cost"],
                "high_speed": lambda x: x["causes"]["high_speed"]["extra_cost"],
                "idle": lambda x: x["causes"]["excessive_idle"]["extra_cost"],
                "low_mpg": lambda x: -x["avg_mpg"],  # Lower MPG = worse
                "high_rpm": lambda x: x["causes"]["high_rpm"]["extra_cost"],
            }

            sort_func = sort_key_map.get(sort_by, sort_key_map["total_cost"])
            trucks_data.sort(key=sort_func, reverse=True)

            # 🆕 v3.14.3: Calculate actual data period across all trucks
            actual_data_days = (
                max([t.get("actual_days", 1) for t in trucks_data])
                if trucks_data
                else 0
            )

            return {
                "period_days_requested": days_back,
                "period_days_actual": actual_data_days,  # 🆕 Real days of data available
                "truck_count": len(trucks_data),
                "sort_by": sort_by,
                "note": (
                    f"Data available for {actual_data_days} days (requested {days_back})"
                    if actual_data_days < days_back
                    else None
                ),
                "fleet_summary": {
                    "total_inefficiency_cost": round(fleet_totals["total_cost"], 2),
                    "by_cause": {
                        "high_engine_load": round(fleet_totals["high_load_cost"], 2),
                        "high_speed": round(fleet_totals["high_speed_cost"], 2),
                        "high_rpm": round(fleet_totals["high_rpm_cost"], 2),
                        "excessive_idle": round(fleet_totals["idle_cost"], 2),
                        "low_oil_pressure": round(fleet_totals["low_oil_cost"], 2),
                        "high_oil_temp": round(fleet_totals["high_temp_cost"], 2),
                    },
                    "top_fleet_issue": max(
                        [
                            ("high_engine_load", fleet_totals["high_load_cost"]),
                            ("high_speed", fleet_totals["high_speed_cost"]),
                            ("high_rpm", fleet_totals["high_rpm_cost"]),
                            ("excessive_idle", fleet_totals["idle_cost"]),
                            ("low_oil_pressure", fleet_totals["low_oil_cost"]),
                            ("high_oil_temp", fleet_totals["high_temp_cost"]),
                        ],
                        key=lambda x: x[1],
                    )[0],
                },
                "trucks": trucks_data,
            }

    except Exception as e:
        logger.error(f"Error in get_inefficiency_by_truck: {e}")
        return {
            "period_days": days_back,
            "truck_count": 0,
            "sort_by": sort_by,
            "fleet_summary": {"total_inefficiency_cost": 0, "by_cause": {}},
            "trucks": [],
            "error": str(e),
        }
