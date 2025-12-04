"""
MySQL Database Service - Direct Query from fuel_metrics table
Replaces CSV reading with direct MySQL queries for better performance and historical analysis

🔧 FIX v3.9.2: All queries now use SQLAlchemy connection pooling
- pool_pre_ping=True: Check connection health before use
- pool_recycle=3600: Recycle connections after 1 hour
- pool_size=10: Maintain 10 connections in pool
- max_overflow=5: Allow 5 additional connections under load
"""

import pymysql
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import logging
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

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
        BASELINE_MPG = 6.5

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


def get_sqlalchemy_engine():
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
def get_db_connection():
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

    🆕 v3.8.0: Added 24h averages for MPG and idle consumption
    - avg_mpg_24h: Average MPG when MOVING over last 24h
    - avg_idle_gph_24h: Average idle GPH when STOPPED over last 24h
    """
    query = text(
        """
        SELECT 
            t1.truck_id,
            t1.timestamp_utc,
            t1.data_age_min,
            t1.truck_status,
            t1.estimated_liters,
            t1.estimated_gallons,
            t1.estimated_pct,
            t1.sensor_pct,
            t1.sensor_liters,
            t1.sensor_gallons,
            t1.sensor_ema_pct,
            t1.ecu_level_pct,
            t1.model_level_pct,
            t1.confidence_indicator,
            t1.consumption_lph,
            t1.consumption_gph,
            t1.idle_method,
            t1.idle_mode,
            t1.idle_gph,
            t1.mpg_current,
            t1.speed_mph,
            t1.rpm,
            t1.hdop,
            t1.altitude_ft,
            t1.coolant_temp_f,
            t1.odometer_mi,
            t1.odom_delta_mi,
            t1.drift_pct,
            t1.drift_warning,
            t1.anchor_detected,
            t1.anchor_type,
            t1.static_anchors_total,
            t1.micro_anchors_total,
            t1.refuel_events_total,
            t1.refuel_gallons,
            t1.flags,
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

    Returns: List of dicts matching RefuelEvent model:
        - truck_id: str
        - timestamp: datetime
        - date: str (YYYY-MM-DD)
        - time: str (HH:MM:SS)
        - gallons: float
        - liters: float
        - fuel_level_after: float (optional)
    """

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
            MIN_REFUEL_GAL = 40  # Minimum 40 gal to count as real refuel (~$140)

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


def get_fleet_summary() -> Dict[str, Any]:
    """
    Get fleet-wide statistics
    Replaces: get_fleet_summary() in database.py

    🔧 FIX v3.9.2: Now uses SQLAlchemy connection pooling
    """
    query = text(
        """
        SELECT 
            COUNT(DISTINCT truck_id) as total_trucks,
            SUM(CASE WHEN truck_status != 'OFFLINE' THEN 1 ELSE 0 END) as active_trucks,
            SUM(CASE WHEN truck_status = 'OFFLINE' THEN 1 ELSE 0 END) as offline_trucks,
            AVG(estimated_pct) as avg_fuel_level,
            AVG(mpg_current) as avg_mpg,
            AVG(consumption_lph) as avg_consumption,
            SUM(CASE WHEN drift_warning = 'YES' THEN 1 ELSE 0 END) as trucks_with_drift
        FROM (
            SELECT t1.*
            FROM fuel_metrics t1
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_time
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
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
            AVG(mpg_current) as avg_mpg,
            MAX(mpg_current) as max_mpg,
            MIN(mpg_current) as min_mpg,
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


def get_kpi_summary(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.8.1: Optimized KPI calculation using single MySQL query

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


def get_loss_analysis(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.9.0: Loss Analysis by Root Cause

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
        "baseline_mpg": 6.5,
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


def get_driver_scorecard(days_back: int = 7) -> Dict[str, Any]:
    """
    🆕 v3.10.0: Comprehensive Driver Scorecard System

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
            
            -- Distance
            SUM(CASE WHEN odom_delta_mi > 0 AND odom_delta_mi < 10 THEN odom_delta_mi ELSE 0 END) as total_miles
            
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
        GROUP BY truck_id
        HAVING total_records > 10
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

            return {
                "period_days": days_back,
                "driver_count": len(drivers),
                "fleet_avg": {
                    "mpg": round(fleet_mpg_avg, 2),
                    "idle_pct": round(
                        (
                            (fleet_idle_avg / (total_records / len(results))) * 100
                            if results
                            else 0
                        ),
                        1,
                    ),
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


def get_enhanced_kpis(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.10.0: Enhanced KPI Dashboard with Fleet Health Index

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
            
            -- MPG analysis
            AVG(CASE WHEN mpg_current > 3.5 AND mpg_current < 12 THEN mpg_current END) as avg_mpg,
            
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
            total_miles = float(result[7] or 0)

            # MPG analysis
            avg_mpg = float(result[6] or BASELINE_MPG)

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
                            total_cost / days_back if days_back > 0 else total_cost, 2
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
                            total_miles / days_back if days_back > 0 else total_miles, 1
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
            "baseline_mpg": 6.5,
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


def get_enhanced_loss_analysis(days_back: int = 1) -> Dict[str, Any]:
    """
    🆕 v3.10.0: Enhanced Loss Analysis with Root Cause Intelligence

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

                total_miles = float(row[18] or 0)
                total_records = int(row[19] or 1)

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
        "baseline_mpg": 6.5,
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


def get_advanced_refuel_analytics(days_back: int = 7) -> Dict[str, Any]:
    """
    🆕 v3.10.3: World-Class Refuel Analytics Dashboard

    Provides comprehensive refuel intelligence:
    1. Refuel Events Timeline with precise gallons calculation
    2. Refuel Patterns Analysis (by truck, day of week, time of day)
    3. Cost Analysis & Fuel Purchase Tracking
    4. Anomaly Detection (partial fills, overfills, suspicious patterns)
    5. Station/Location Inference
    6. Tank Efficiency Analysis
    """
    FUEL_PRICE = FUEL.PRICE_PER_GALLON

    # Query 1: All refuel events with detailed metrics
    refuel_query = text(
        """
        SELECT 
            fm.truck_id,
            fm.timestamp_utc,
            fm.refuel_gallons,
            fm.estimated_pct as fuel_after_pct,
            fm.estimated_gallons as fuel_after_gal,
            fm.sensor_pct as sensor_after_pct,
            fm.truck_status,
            fm.speed_mph,
            fm.odometer_mi,
            fm.altitude_ft,
            -- Get previous record for fuel_before calculation
            LAG(fm.estimated_pct) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as fuel_before_pct,
            LAG(fm.estimated_gallons) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as fuel_before_gal,
            LAG(fm.sensor_pct) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as sensor_before_pct,
            LAG(fm.timestamp_utc) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as prev_timestamp,
            LAG(fm.odometer_mi) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as prev_odometer
        FROM fuel_metrics fm
        WHERE fm.timestamp_utc > NOW() - INTERVAL :days_back DAY
          AND fm.refuel_gallons > 0
        ORDER BY fm.timestamp_utc DESC
    """
    )

    # Query 2: Summary statistics per truck
    summary_query = text(
        """
        SELECT 
            truck_id,
            COUNT(*) as refuel_count,
            SUM(refuel_gallons) as total_gallons,
            AVG(refuel_gallons) as avg_gallons,
            MIN(refuel_gallons) as min_gallons,
            MAX(refuel_gallons) as max_gallons,
            AVG(estimated_pct) as avg_fuel_level_after
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
          AND refuel_gallons > 0
        GROUP BY truck_id
        ORDER BY total_gallons DESC
    """
    )

    # Query 3: Pattern analysis (hour of day, day of week)
    pattern_query = text(
        """
        SELECT 
            HOUR(timestamp_utc) as hour_of_day,
            DAYOFWEEK(timestamp_utc) as day_of_week,
            COUNT(*) as refuel_count,
            SUM(refuel_gallons) as total_gallons
        FROM fuel_metrics
        WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
          AND refuel_gallons > 0
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

            # Process refuel events - CONSOLIDATE BY DAY
            # 🔧 v3.10.13: Consolidate all refuel records from same day as ONE refuel
            # This fixes false positives from sensor oscillations throughout the day
            refuel_events = []
            anomalies = []
            total_gallons = 0
            total_cost = 0

            # First pass: collect all events per truck PER DAY
            truck_day_refuels = {}  # (truck_id, date) -> list of (timestamp, row)
            for row in refuel_results:
                truck_id = row[0]
                timestamp = row[1]
                day_key = (
                    truck_id,
                    timestamp.strftime("%Y-%m-%d") if timestamp else "unknown",
                )
                if day_key not in truck_day_refuels:
                    truck_day_refuels[day_key] = []
                truck_day_refuels[day_key].append((timestamp, row))

            # Second pass: take the LARGEST single refuel from each day
            # This represents the actual fuel purchase, not oscillation artifacts

            for (truck_id, date_str), day_records in truck_day_refuels.items():
                # Sort by timestamp
                day_records.sort(key=lambda x: x[0])

                # Find the record with the LARGEST refuel_gallons for this day
                # This is most likely the actual refuel event
                best_record = max(day_records, key=lambda x: float(x[1][2] or 0))
                best_ts, best_row = best_record

                # Use the largest single refuel amount (not sum)
                refuel_gallons_val = float(best_row[2] or 0)

                # 🔧 v3.10.13: Skip amounts below 40 gal (~$140) - likely sensor noise
                if refuel_gallons_val < 40:
                    continue

                # Get fuel levels from the best record
                fuel_after_pct = float(best_row[3] or 0)

                # 🔧 v3.12.0: Lowered threshold from 55% to 40% to capture partial refuels
                # A real refuel should result in fuel > 40% (allows emergency/partial fills)
                if fuel_after_pct < 40:
                    continue

                # Cap at reasonable max
                total_group_gallons = min(refuel_gallons_val, 200.0)

                fuel_after_gal = float(best_row[4] or 0)
                sensor_after_pct = float(best_row[5] or 0)
                truck_status = best_row[6]
                speed_mph = float(best_row[7] or 0)
                odometer = float(best_row[8] or 0)
                altitude = float(best_row[9] or 0)
                fuel_before_pct = float(best_row[10] or 0)
                fuel_before_gal = float(
                    best_row[11] or 0
                )  # 🆕 v3.10.15: Add fuel_before in gallons
                prev_timestamp = best_row[13]
                prev_odometer = float(best_row[14] or 0)

                # Calculate derived metrics
                cost = total_group_gallons * FUEL_PRICE
                total_gallons += total_group_gallons
                total_cost += cost

                # Miles since last record
                miles_since_last = (
                    max(0, odometer - prev_odometer) if prev_odometer else 0
                )

                # Time since last reading
                if prev_timestamp and best_ts:
                    time_gap_minutes = (best_ts - prev_timestamp).total_seconds() / 60
                else:
                    time_gap_minutes = 0

                # Calculate fill type
                if fuel_after_pct >= 95:
                    fill_type = "LLENO COMPLETO"
                elif fuel_after_pct >= 80:
                    fill_type = "LLENO PARCIAL"
                elif total_group_gallons < 50:
                    fill_type = "RECARGA PEQUEÑA"
                else:
                    fill_type = "RECARGA NORMAL"

                # Detect anomalies
                anomaly_flags = []
                if fuel_after_pct > 100:
                    anomaly_flags.append("SOBRE-LLENADO")
                if speed_mph > 5:
                    anomaly_flags.append("RECARGA EN MOVIMIENTO")
                if total_group_gallons > 180:
                    anomaly_flags.append("CANTIDAD MUY GRANDE")
                if sensor_after_pct and abs(sensor_after_pct - fuel_after_pct) > 15:
                    anomaly_flags.append("DISCREPANCIA SENSOR")

                event = {
                    "truck_id": truck_id,
                    "timestamp": (
                        best_ts.strftime("%Y-%m-%d %H:%M:%S") if best_ts else None
                    ),
                    "date": date_str,
                    "time": best_ts.strftime("%H:%M") if best_ts else None,
                    "gallons": round(total_group_gallons, 1),
                    "liters": round(total_group_gallons * 3.78541, 1),
                    "cost_usd": round(cost, 2),
                    "fuel_before_pct": (
                        round(fuel_before_pct, 1) if fuel_before_pct else None
                    ),
                    "fuel_after_pct": round(fuel_after_pct, 1),
                    "fuel_before_gal": (
                        round(fuel_before_gal, 1) if fuel_before_gal else None
                    ),
                    "fuel_after_gal": (
                        round(fuel_after_gal, 1) if fuel_after_gal else None
                    ),
                    "fuel_added_pct": (
                        round(fuel_after_pct - fuel_before_pct, 1)
                        if fuel_before_pct
                        else None
                    ),
                    "sensor_pct": (
                        round(sensor_after_pct, 1) if sensor_after_pct else None
                    ),
                    "fill_type": fill_type,
                    "miles_since_last": round(miles_since_last, 1),
                    "time_gap_minutes": round(time_gap_minutes, 0),
                    "altitude_ft": round(altitude, 0),
                    "anomalies": anomaly_flags,
                    "has_anomaly": len(anomaly_flags) > 0,
                    "consolidated_from": len(day_records),  # Records this day
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
                                "ALTA"
                                if "SOBRE-LLENADO" in anomaly_flags
                                or "RECARGA EN MOVIMIENTO" in anomaly_flags
                                else "MEDIA"
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


def get_fuel_theft_analysis(days_back: int = 7) -> Dict[str, Any]:
    """
    🆕 v3.10.5: IMPROVED Fuel Theft & Drain Detection System

    Only flags TRUE anomalies - not sensor issues or normal consumption!

    Detects:
    1. FUEL THEFT: Sudden large drops (>25 gal) in <30 min while parked
    2. SIPHONING: Large drops (>15 gal) overnight with no miles

    IMPORTANT: Filters out:
    - Sensor disconnections (NULL readings)
    - Offline periods
    - Normal consumption
    """
    FUEL_PRICE = FUEL.PRICE_PER_GALLON

    # Much stricter thresholds to avoid false positives
    THEFT_MIN_GALLONS = 15.0  # At least 15 gal drop to flag
    THEFT_MIN_PCT = 8.0  # At least 8% drop
    THEFT_MAX_TIME_MIN = 120  # Drop must happen in <2 hours
    THEFT_MAX_MILES = 3.0  # Max 3 miles driven during drop
    SIPHON_MIN_GALLONS = 20.0  # Overnight siphoning threshold
    IDLE_CONSUMPTION_GPH = 1.2  # Conservative idle consumption estimate

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
            LAG(truck_status) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_status
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

                # If current is 0% and previous had valid sensor with >20%,
                # this is likely a sensor disconnect to 0, not theft
                if (
                    est_pct == 0
                    and prev_sensor_pct is not None
                    and float(prev_sensor_pct) > 20
                ):
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

                # Check time of day
                hour = timestamp.hour if timestamp else 12
                is_night = hour < 6 or hour > 22
                if is_night:
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
                    "unexplained_loss_gallons": round(unexplained_loss, 1),
                    "fuel_drop_pct": round(fuel_drop_pct, 1),
                    "fuel_before_pct": round(prev_pct, 1),
                    "fuel_after_pct": round(est_pct, 1),
                    "estimated_loss_usd": round(unexplained_loss * FUEL_PRICE, 2),
                    "time_gap_minutes": round(time_gap_min, 0),
                    "miles_driven": round(miles_driven, 1),
                    "expected_consumption_gal": round(expected_total, 1),
                    "is_night": is_night,
                }
                theft_events.append(theft_event)
                total_loss_gal += unexplained_loss

                # Track per truck
                if truck_id not in truck_patterns:
                    truck_patterns[truck_id] = {
                        "event_count": 0,
                        "total_loss_gal": 0,
                        "highest_confidence": 0,
                    }
                truck_patterns[truck_id]["event_count"] += 1
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

            return {
                "period_days": days_back,
                "fuel_price_per_gal": FUEL_PRICE,
                "detection_thresholds": {
                    "min_gallons": THEFT_MIN_GALLONS,
                    "min_pct": THEFT_MIN_PCT,
                    "max_time_minutes": THEFT_MAX_TIME_MIN,
                },
                "summary": {
                    "total_events": len(theft_events),
                    "high_confidence_events": len(
                        [e for e in theft_events if e["confidence_pct"] >= 85]
                    ),
                    "total_suspected_loss_gallons": round(total_loss_gal, 1),
                    "total_suspected_loss_usd": round(total_loss_gal * FUEL_PRICE, 2),
                    "trucks_affected": len(trucks_at_risk),
                },
                "trucks_at_risk": trucks_at_risk[:20],
                "events": theft_events[:30],
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
    BASELINE_MPG = 6.5

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


def get_cost_attribution_report(days_back: int = 30) -> Dict:
    """
    Generate detailed cost attribution report for fleet fuel expenses.

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
    BASELINE_MPG = 6.5
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
