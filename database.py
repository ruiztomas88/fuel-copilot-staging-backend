"""
Database connection and query utilities for FastAPI backend
Hybrid MySQL + CSV with automatic fallback
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages access to MySQL (primary) and CSV reports (fallback)"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.csv_dir = self.base_dir / "data" / "csv_reports"
        self.states_dir = self.base_dir / "data" / "estimator_states"

        # 🔧 MySQL Enabled for High Performance
        # The dashboard will now read directly from the local MySQL database
        # populated by fuel_copilot_v2_1_fixed.py
        self.mysql_available = True
        logger.info("🚀 MySQL enabled - using high-performance database mode")

        # Import MySQL functions if available
        if self.mysql_available:
            try:
                try:
                    from .database_mysql import (
                        get_latest_truck_data,
                        get_truck_history as mysql_get_truck_history,
                        get_refuel_history as mysql_get_refuel_history,
                        get_fleet_summary as mysql_get_fleet_summary,
                    )
                except ImportError:
                    from database_mysql import (
                        get_latest_truck_data,
                        get_truck_history as mysql_get_truck_history,
                        get_refuel_history as mysql_get_refuel_history,
                        get_fleet_summary as mysql_get_fleet_summary,
                    )

                self.mysql_get_latest = get_latest_truck_data
                self.mysql_get_history = mysql_get_truck_history
                self.mysql_get_refuels = mysql_get_refuel_history
                self.mysql_get_fleet_summary = mysql_get_fleet_summary
                logger.info("✅ MySQL functions loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to import MySQL functions: {e}")
                self.mysql_available = False

    def _check_mysql_connection(self) -> bool:
        """Check if MySQL is available"""
        try:
            try:
                from .database_mysql import test_connection
            except ImportError:
                from database_mysql import test_connection

            return test_connection()
        except Exception as e:
            logger.info(f"MySQL not available, using CSV fallback: {e}")
            return False

    def get_latest_csv_for_truck(self, truck_id: str) -> Optional[Path]:
        """Find the most recent CSV file for a truck"""
        pattern = f"fuel_report_{truck_id}_*.csv"
        matching_files = list(self.csv_dir.glob(pattern))

        if not matching_files:
            return None

        # Sort by modification time, most recent first
        matching_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return matching_files[0]

    def load_truck_data(self, truck_id: str) -> Optional[pd.DataFrame]:
        """Load the latest CSV data for a truck"""
        csv_path = self.get_latest_csv_for_truck(truck_id)
        if not csv_path or not csv_path.exists():
            return None

        try:
            df = pd.read_csv(csv_path)
            # Ensure timestamp is datetime
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df
        except Exception as e:
            print(f"Error loading CSV for {truck_id}: {e}")
            return None

    def get_truck_latest_record(self, truck_id: str) -> Optional[Dict]:
        """Get the most recent record for a truck (MySQL first, then CSV fallback)"""

        # Try MySQL first
        if self.mysql_available:
            try:
                df = self.mysql_get_latest(hours_back=24)
                if not df.empty:
                    truck_data = df[df["truck_id"] == truck_id]
                    if not truck_data.empty:
                        latest = truck_data.iloc[0].to_dict()
                        # Convert timestamp to ISO format if present
                        if "timestamp_utc" in latest and isinstance(
                            latest["timestamp_utc"], pd.Timestamp
                        ):
                            latest["timestamp"] = latest["timestamp_utc"].isoformat()
                        logger.info(f"✅ MySQL data retrieved for {truck_id}")
                        return latest
            except Exception as e:
                logger.warning(f"MySQL query failed for {truck_id}, using CSV: {e}")

        # Fallback to CSV
        logger.info(f"⚠️ Using CSV fallback for {truck_id}")
        df = self.load_truck_data(truck_id)
        if df is None or df.empty:
            return None

        # Get last row as dict
        latest = df.iloc[-1].to_dict()

        # Convert timestamp to ISO format if present
        if "timestamp" in latest and isinstance(latest["timestamp"], pd.Timestamp):
            latest["timestamp"] = latest["timestamp"].isoformat()

        return latest

    def get_all_trucks(self) -> List[str]:
        """Get list of all trucks (MySQL first, then CSV fallback)"""

        # Try MySQL first
        if self.mysql_available:
            try:
                # 🔧 FIX v3.11.1: Query truck IDs directly from fuel_metrics
                try:
                    from database_mysql import get_sqlalchemy_engine
                except ImportError:
                    from .database_mysql import get_sqlalchemy_engine
                
                from sqlalchemy import text
                
                engine = get_sqlalchemy_engine()
                with engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT DISTINCT truck_id 
                        FROM fuel_metrics 
                        WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
                        ORDER BY truck_id
                    """))
                    trucks = [row[0] for row in result]
                    logger.info(f"✅ Found {len(trucks)} trucks in MySQL")
                    return trucks
            except Exception as e:
                logger.warning(f"MySQL query failed, using CSV: {e}")

        # Fallback to CSV
        logger.info("⚠️ Using CSV fallback for truck list")
        if not self.csv_dir.exists():
            return []

        trucks = set()
        for csv_file in self.csv_dir.glob("fuel_report_*.csv"):
            # Extract truck_id from filename: fuel_report_{TRUCK_ID}_{DATE}.csv
            parts = csv_file.stem.split("_")
            if len(parts) >= 3:
                truck_id = parts[2]
                trucks.add(truck_id)

        return sorted(list(trucks))

    def get_fleet_summary(self) -> Dict:
        """Get summary statistics for entire fleet (MySQL first, then CSV fallback)"""

        # Try MySQL first for real-time data
        if self.mysql_available:
            try:
                # 🔧 FIX v3.11.0: Use direct MySQL fleet summary function
                mysql_summary = self.mysql_get_fleet_summary()
                if mysql_summary and mysql_summary.get('total_trucks', 0) > 0:
                    logger.info(
                        f"✅ Using MySQL for fleet summary - {mysql_summary['total_trucks']} trucks found"
                    )
                    # Enrich with missing fields required by FleetSummary model
                    mysql_summary['data_source'] = 'MySQL'
                    mysql_summary['critical_count'] = 0  # TODO: implement health calculation
                    mysql_summary['warning_count'] = 0
                    mysql_summary['healthy_count'] = mysql_summary['total_trucks']
                    mysql_summary['avg_idle_gph'] = mysql_summary.get('avg_consumption', 0)
                    
                    # 🔧 FIX v3.11.2: Populate truck_details for dashboard table
                    truck_details = self._get_truck_details_from_mysql()
                    mysql_summary['truck_details'] = truck_details
                    mysql_summary['timestamp'] = datetime.now()
                    return mysql_summary
            except Exception as e:
                logger.warning(f"MySQL fleet summary failed, using CSV: {e}")
    
    def _get_truck_details_from_mysql(self) -> List[Dict]:
        """Get individual truck details for fleet summary table"""
        try:
            from sqlalchemy import text
            try:
                from database_mysql import get_sqlalchemy_engine
            except ImportError:
                from .database_mysql import get_sqlalchemy_engine
            
            engine = get_sqlalchemy_engine()
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        t1.truck_id,
                        t1.truck_status,
                        t1.estimated_pct as fuel_level,
                        t1.sensor_pct,
                        t1.drift_pct,
                        t1.mpg_current,
                        t1.consumption_gph as idle_gph,
                        t1.speed_mph,
                        t1.timestamp_utc
                    FROM fuel_metrics t1
                    INNER JOIN (
                        SELECT truck_id, MAX(timestamp_utc) as max_time
                        FROM fuel_metrics
                        WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
                        GROUP BY truck_id
                    ) t2 ON t1.truck_id = t2.truck_id AND t1.timestamp_utc = t2.max_time
                    ORDER BY t1.truck_id
                """))
                
                trucks = []
                for row in result:
                    trucks.append({
                        'truck_id': row[0],
                        'status': row[1],
                        'fuel_level': round(row[2], 1) if row[2] else 0,
                        'sensor_pct': round(row[3], 1) if row[3] else 0,
                        'drift': round(row[4], 1) if row[4] else 0,
                        'mpg': round(row[5], 1) if row[5] else 0,
                        'idle_gph': round(row[6], 2) if row[6] else 0,
                        'speed': round(row[7], 1) if row[7] else 0,
                        'last_update': row[8].isoformat() if row[8] else None
                    })
                return trucks
        except Exception as e:
            logger.error(f"Error getting truck details: {e}")
            return []

        # Fallback to CSV
        logger.info("⚠️ Using CSV fallback for fleet summary")
        trucks = self.get_all_trucks()

        total_trucks = len(trucks)
        active_trucks = 0
        total_mpg = 0
        total_idle_gph = 0
        mpg_count = 0
        idle_count = 0
        offline_trucks = 0
        critical_count = 0  # health_score < 50
        warning_count = 0  # 50 <= health_score < 75
        healthy_count = 0  # health_score >= 75

        truck_details = []

        for truck_id in trucks:
            record = self.get_truck_latest_record(truck_id)
            if not record:
                # No data available - count as offline
                offline_trucks += 1
                continue

            # Calculate health score
            health_score = self._calculate_health_score(record)

            # Count by health status
            if health_score < 50:
                critical_count += 1
            elif health_score < 75:
                warning_count += 1
            else:
                healthy_count += 1

            # Check if truck is online (data less than 60 minutes old)
            try:
                ts_val = record.get("timestamp_utc") or record.get("timestamp")
                if not ts_val:
                    # No timestamp - count as offline
                    offline_trucks += 1
                    continue
                timestamp = pd.to_datetime(ts_val)
                age_minutes = (datetime.now() - timestamp).total_seconds() / 60

                # Data is recent (< 60 minutes)
                if age_minutes <= 60:
                    # 🔧 FIX: Use truck_status from CSV (already calculated by fuel_copilot)
                    # The CSV has the authoritative status from Kalman processing
                    truck_status = record.get("truck_status", "OFFLINE")

                    # Validate status value
                    if truck_status not in ["MOVING", "STOPPED", "OFFLINE"]:
                        truck_status = "OFFLINE"

                    # ✅ FIX: Count active trucks AFTER determining status (motor encendido)
                    if truck_status != "OFFLINE":
                        active_trucks += 1
                    else:
                        offline_trucks += 1

                    # Get consumption_gph from record for idle calculations
                    consumption_gph = record.get("consumption_gph")

                    # ✅ FIX: Accumulate MPG (only for MOVING trucks with valid MPG)
                    if (
                        truck_status == "MOVING"
                        and "mpg_current" in record
                        and pd.notna(record["mpg_current"])
                        and record["mpg_current"] > 0
                    ):
                        total_mpg += record["mpg_current"]
                        mpg_count += 1

                    # ✅ FIX: Accumulate idle (only for STOPPED trucks with consumption_gph > 0.01)
                    # Don't accumulate for OFFLINE (motor apagado) or MOVING
                    if (
                        truck_status == "STOPPED"
                        and pd.notna(consumption_gph)
                        and consumption_gph > 0.01
                    ):
                        total_idle_gph += consumption_gph
                        idle_count += 1

                    # Get values and convert NaN to None
                    # MPG only for MOVING trucks
                    mpg_val = (
                        record.get("mpg_current") if truck_status == "MOVING" else None
                    )
                    # Idle GPH for STOPPED trucks (motor encendido) with consumption > 0.01
                    consumption_gph_val = record.get("consumption_gph")
                    if (
                        truck_status == "STOPPED"  # Only STOPPED (not OFFLINE)
                        and pd.notna(consumption_gph_val)
                        and consumption_gph_val > 0.01
                    ):
                        idle_val = consumption_gph_val
                    else:
                        idle_val = None
                    fuel_val = record.get("fuel_L")
                    estimated_pct = record.get("estimated_pct")
                    estimated_liters = record.get("estimated_liters")
                    sensor_pct = record.get("sensor_pct")
                    sensor_liters = record.get("sensor_liters")
                    drift_pct = record.get("drift_pct")
                    speed_mph = record.get("speed_mph")

                    # Event fields for Actions column
                    refuel_gallons = record.get("refuel_gallons")
                    anchor_detected = record.get("anchor_detected")
                    anchor_type = record.get("anchor_type")
                    idle_method = record.get("idle_method")

                    # Calculate health score and category for this truck
                    health_score = self._calculate_health_score(record)
                    if health_score < 50:
                        health_category = "critical"
                    elif health_score < 75:
                        health_category = "warning"
                    else:
                        health_category = "healthy"

                    truck_details.append(
                        {
                            "truck_id": truck_id,
                            "mpg": (
                                None if pd.isna(mpg_val) else round(float(mpg_val), 2)
                            ),
                            "idle_gph": (
                                None if pd.isna(idle_val) else round(float(idle_val), 2)
                            ),
                            "fuel_L": (
                                None if pd.isna(fuel_val) else round(float(fuel_val), 1)
                            ),
                            "status": (
                                truck_status
                                if truck_status in ["MOVING", "STOPPED"]
                                else "OFFLINE"
                            ),
                            "estimated_pct": (
                                None
                                if pd.isna(estimated_pct)
                                else round(float(estimated_pct), 1)
                            ),
                            "estimated_gallons": (
                                None
                                if pd.isna(estimated_liters)
                                else round(float(estimated_liters) * 0.264172, 1)
                            ),
                            "sensor_pct": (
                                None
                                if pd.isna(sensor_pct)
                                else round(float(sensor_pct), 1)
                            ),
                            "sensor_gallons": (
                                None
                                if pd.isna(sensor_liters)
                                else round(float(sensor_liters) * 0.264172, 1)
                            ),
                            "drift_pct": (
                                None
                                if pd.isna(drift_pct)
                                else round(float(drift_pct), 1)
                            ),
                            "speed_mph": (
                                None
                                if pd.isna(speed_mph)
                                else round(float(speed_mph), 1)
                            ),
                            "health_score": health_score,
                            "health_category": health_category,
                            # Event fields for Actions
                            "refuel_gallons": (
                                None
                                if pd.isna(refuel_gallons) or refuel_gallons == 0
                                else round(float(refuel_gallons), 1)
                            ),
                            "anchor_detected": (
                                str(anchor_detected)
                                if pd.notna(anchor_detected)
                                else None
                            ),
                            "anchor_type": (
                                str(anchor_type) if pd.notna(anchor_type) else None
                            ),
                            "idle_method": (
                                str(idle_method) if pd.notna(idle_method) else None
                            ),
                        }
                    )
                else:
                    offline_trucks += 1

            except Exception as e:
                print(f"Error processing {truck_id}: {e}")
                continue

        return {
            "total_trucks": total_trucks,
            "active_trucks": active_trucks,
            "offline_trucks": offline_trucks,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "healthy_count": healthy_count,
            "avg_mpg": round(total_mpg / mpg_count, 2) if mpg_count > 0 else 0,
            "avg_idle_gph": (
                round(total_idle_gph / idle_count, 2) if idle_count > 0 else 0
            ),
            "truck_details": truck_details,
            "timestamp": datetime.now().isoformat(),
        }

    def _process_fleet_data(self, df: pd.DataFrame, source: str = "mysql") -> Dict:
        """Process fleet data from DataFrame (works for both MySQL and CSV)"""
        total_trucks = len(df)
        active_trucks = 0
        total_mpg = 0
        total_idle_gph = 0
        mpg_count = 0
        idle_count = 0
        offline_trucks = 0
        critical_count = 0
        warning_count = 0
        healthy_count = 0
        truck_details = []

        for _, row in df.iterrows():
            record = row.to_dict()
            truck_id = record.get("truck_id")

            if not truck_id:
                continue

            # Calculate health score
            health_score = self._calculate_health_score(record)

            # Count by health status
            if health_score < 50:
                critical_count += 1
            elif health_score < 75:
                warning_count += 1
            else:
                healthy_count += 1

            # Check if truck is online
            try:
                ts_val = record.get("timestamp_utc") or record.get("timestamp")
                if not ts_val:
                    offline_trucks += 1
                    continue

                # FIX: Robust timezone handling
                timestamp = pd.to_datetime(ts_val)
                if timestamp.tzinfo is None:
                    # The database stores timestamps in server local time (EST/EDT) despite the column name 'timestamp_utc'
                    # We must localize to America/New_York first, then convert to UTC
                    timestamp = timestamp.tz_localize("America/New_York").tz_convert(
                        "UTC"
                    )

                now_utc = pd.Timestamp.now(tz="UTC")
                age_minutes = (now_utc - timestamp).total_seconds() / 60

                # Data is recent (< 60 minutes)
                if age_minutes <= 60:
                    rpm = record.get("rpm")
                    speed_mph = record.get("speed_mph")
                    consumption_gph = record.get("consumption_gph")

                    # FIX: Trust the truck_status from the database/engine first
                    # The engine (fuel_copilot) has superior logic for status determination
                    db_status = record.get("truck_status")

                    if db_status and db_status in ["MOVING", "STOPPED", "OFFLINE"]:
                        truck_status = db_status
                    else:
                        # ✨ STRICT Fallback logic (v3.1.1) - only if status is missing
                        # MOVING:  speed > 5 mph (engine implied ON) OR (speed > 0 AND rpm > 0)
                        # STOPPED: speed = 0 AND rpm > 0
                        # OFFLINE: rpm = 0 or rpm = None (AND speed < 5)

                        # 🆕 ROBUSTNESS FIX: Check speed first
                        if pd.notna(speed_mph) and speed_mph > 5.0:
                            truck_status = "MOVING"
                        elif pd.isna(rpm) or rpm <= 0:
                            truck_status = "OFFLINE"  # Engine OFF
                        else:
                            # Engine ON (rpm > 0) - check movement
                            if pd.notna(speed_mph) and speed_mph > 0:
                                truck_status = "MOVING"  # speed > 0 AND rpm > 0
                            else:
                                truck_status = "STOPPED"  # speed = 0 AND rpm > 0                    # Count active trucks (motor encendido)
                    if truck_status != "OFFLINE":
                        active_trucks += 1
                    else:
                        offline_trucks += 1

                    # ✅ FIX: Accumulate MPG (only for MOVING trucks with valid MPG)
                    if truck_status == "MOVING":
                        mpg_current = record.get("mpg_current")
                        if pd.notna(mpg_current) and mpg_current > 0:
                            total_mpg += mpg_current
                            mpg_count += 1

                    # ✅ FIX: Accumulate idle (only for STOPPED trucks, not OFFLINE or MOVING)
                    if (
                        truck_status == "STOPPED"
                        and pd.notna(consumption_gph)
                        and consumption_gph > 0.01
                    ):
                        total_idle_gph += consumption_gph
                        idle_count += 1

                    # 🆕 v3.8.0: Prepare truck detail with 24h averages for stable metrics
                    # MPG: Use avg_mpg_24h if available (more stable), otherwise current
                    avg_mpg_24h = record.get("avg_mpg_24h")
                    mpg_readings_24h = record.get("mpg_readings_24h", 0)
                    mpg_val = None
                    if truck_status == "MOVING":
                        # Prefer 24h average if we have enough readings
                        if (
                            pd.notna(avg_mpg_24h)
                            and mpg_readings_24h
                            and mpg_readings_24h >= 5
                        ):
                            mpg_val = avg_mpg_24h
                        else:
                            mpg_val = record.get("mpg_current")

                    # 🆕 Idle GPH: Use avg_idle_gph_24h (more stable than instant value)
                    avg_idle_gph_24h = record.get("avg_idle_gph_24h")
                    idle_readings_24h = record.get("idle_readings_24h", 0)
                    idle_val = None
                    if truck_status == "STOPPED":
                        # Prefer 24h average if we have enough readings
                        if (
                            pd.notna(avg_idle_gph_24h)
                            and idle_readings_24h
                            and idle_readings_24h >= 3
                        ):
                            idle_val = avg_idle_gph_24h
                        elif pd.notna(consumption_gph) and consumption_gph > 0.01:
                            # Fallback to current instant value
                            idle_val = consumption_gph

                    estimated_pct = record.get("estimated_pct")
                    estimated_liters = record.get("estimated_liters")
                    sensor_pct = record.get("sensor_pct")
                    sensor_liters = record.get("sensor_liters")
                    drift_pct = record.get("drift_pct")
                    refuel_gallons = record.get("refuel_gallons")
                    anchor_detected = record.get("anchor_detected")
                    anchor_type = record.get("anchor_type")
                    idle_method = record.get("idle_method")

                    if health_score < 50:
                        health_category = "critical"
                    elif health_score < 75:
                        health_category = "warning"
                    else:
                        health_category = "healthy"

                    truck_details.append(
                        {
                            "truck_id": truck_id,
                            "mpg": (
                                None if pd.isna(mpg_val) else round(float(mpg_val), 2)
                            ),
                            "idle_gph": (
                                None if pd.isna(idle_val) else round(float(idle_val), 2)
                            ),
                            "fuel_L": (
                                None
                                if pd.isna(estimated_liters)
                                else round(float(estimated_liters), 1)
                            ),
                            "status": truck_status,  # 🔧 FIX: Pass all statuses (MOVING, STOPPED, OFFLINE, PARKED)
                            "estimated_pct": (
                                None
                                if pd.isna(estimated_pct)
                                else round(float(estimated_pct), 1)
                            ),
                            "estimated_gallons": (
                                None
                                if pd.isna(estimated_liters)
                                else round(float(estimated_liters) * 0.264172, 1)
                            ),
                            "sensor_pct": (
                                None
                                if pd.isna(sensor_pct)
                                else round(float(sensor_pct), 1)
                            ),
                            "sensor_gallons": (
                                None
                                if pd.isna(sensor_liters)
                                else round(float(sensor_liters) * 0.264172, 1)
                            ),
                            "drift_pct": (
                                None
                                if pd.isna(drift_pct)
                                else round(float(drift_pct), 1)
                            ),
                            "speed_mph": (
                                None
                                if pd.isna(speed_mph)
                                else round(float(speed_mph), 1)
                            ),
                            "health_score": health_score,
                            "health_category": health_category,
                            "refuel_gallons": (
                                None
                                if pd.isna(refuel_gallons) or refuel_gallons == 0
                                else round(float(refuel_gallons), 1)
                            ),
                            "anchor_detected": (
                                str(anchor_detected)
                                if pd.notna(anchor_detected)
                                else None
                            ),
                            "anchor_type": (
                                str(anchor_type) if pd.notna(anchor_type) else None
                            ),
                            "idle_method": (
                                str(idle_method) if pd.notna(idle_method) else None
                            ),
                        }
                    )
                else:
                    # 🔧 FIX v3.9.0: Data is stale (> 60 minutes), but STILL show truck as OFFLINE
                    offline_trucks += 1

                    # Extract last known values for display
                    estimated_pct = record.get("estimated_pct")
                    estimated_liters = record.get("estimated_liters")
                    sensor_pct = record.get("sensor_pct")
                    sensor_liters = record.get("sensor_liters")
                    drift_pct = record.get("drift_pct")

                    truck_details.append(
                        {
                            "truck_id": truck_id,
                            "mpg": None,  # No valid MPG for offline
                            "idle_gph": None,  # No idle for offline
                            "fuel_L": (
                                None
                                if pd.isna(estimated_liters)
                                else round(float(estimated_liters), 1)
                            ),
                            "status": "OFFLINE",  # Force OFFLINE for stale data
                            "estimated_pct": (
                                None
                                if pd.isna(estimated_pct)
                                else round(float(estimated_pct), 1)
                            ),
                            "estimated_gallons": (
                                None
                                if pd.isna(estimated_liters)
                                else round(float(estimated_liters) * 0.264172, 1)
                            ),
                            "sensor_pct": (
                                None
                                if pd.isna(sensor_pct)
                                else round(float(sensor_pct), 1)
                            ),
                            "sensor_gallons": (
                                None
                                if pd.isna(sensor_liters)
                                else round(float(sensor_liters) * 0.264172, 1)
                            ),
                            "drift_pct": (
                                None
                                if pd.isna(drift_pct)
                                else round(float(drift_pct), 1)
                            ),
                            "speed_mph": None,
                            "health_score": health_score,
                            "health_category": (
                                "critical"
                                if health_score < 50
                                else "warning" if health_score < 75 else "healthy"
                            ),
                            "refuel_gallons": None,
                            "anchor_detected": None,
                            "anchor_type": None,
                            "idle_method": None,
                        }
                    )

            except Exception as e:
                logger.error(f"Error processing truck {truck_id}: {e}")
                continue

        return {
            "total_trucks": total_trucks,
            "active_trucks": active_trucks,
            "offline_trucks": offline_trucks,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "healthy_count": healthy_count,
            "avg_mpg": round(total_mpg / mpg_count, 2) if mpg_count > 0 else 0,
            "avg_idle_gph": (
                round(total_idle_gph / idle_count, 2) if idle_count > 0 else 0
            ),
            "truck_details": truck_details,
            "timestamp": datetime.now().isoformat(),
            "data_source": source,
        }

    def _calculate_health_score(self, record: Dict) -> int:
        """Calculate health score from record data (matches fuel_copilot logic)"""
        health = 100.0

        # 1. Sensor availability (-25 points)
        truck_status = str(record.get("truck_status", "")).upper()
        rpm = record.get("rpm")
        engine_off = pd.isna(rpm) or rpm == 0
        flags = str(record.get("flags", ""))
        waiting_for_fuel = "NO_FUEL_LVL" in flags

        sensor_pct = record.get("sensor_pct")
        if (
            pd.isna(sensor_pct)
            and truck_status != "OFFLINE"
            and not engine_off
            and not waiting_for_fuel
        ):
            health -= 25

        # 2. Data freshness (-20 or -10 points)
        try:
            ts_val = record.get("timestamp_utc") or record.get("timestamp")
            if ts_val:
                timestamp = pd.to_datetime(ts_val)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.tz_localize("UTC")

                now_utc = pd.Timestamp.now(tz="UTC")
                age_minutes = (now_utc - timestamp).total_seconds() / 60

                if age_minutes > 240:  # > 4 hours
                    health -= 20
                elif age_minutes > 120:  # > 2 hours
                    health -= 10
        except:
            pass

        # 3. Drift penalty (-30, -20, or -10 points)
        drift = record.get("drift_pct")
        if pd.notna(drift):
            try:
                drift_val = (
                    float(drift)
                    if not isinstance(drift, str) or drift.strip() not in ["", "N/A"]
                    else None
                )
                if drift_val is not None:
                    if abs(drift_val) > 15:
                        health -= 30
                    elif abs(drift_val) > 10:
                        health -= 20
                    elif abs(drift_val) > 5:
                        health -= 10
            except (ValueError, TypeError):
                pass

        return max(0, min(100, int(health)))

    def get_truck_history(self, truck_id: str, hours: int = 24) -> List[Dict]:
        """Get historical data for a truck (MySQL first, then CSV fallback)"""

        # Try MySQL first
        if self.mysql_available:
            try:
                df = self.mysql_get_history(truck_id, hours_back=hours)
                if not df.empty:
                    records = df.to_dict("records")
                    # Convert timestamps
                    for record in records:
                        if "timestamp_utc" in record and isinstance(
                            record["timestamp_utc"], pd.Timestamp
                        ):
                            record["timestamp"] = record["timestamp_utc"].isoformat()
                    logger.info(
                        f"✅ Retrieved {len(records)} history records from MySQL for {truck_id}"
                    )
                    return records
            except Exception as e:
                logger.warning(
                    f"MySQL history query failed for {truck_id}, using CSV: {e}"
                )

        # Fallback to CSV
        logger.info(f"⚠️ Using CSV fallback for {truck_id} history")
        df = self.load_truck_data(truck_id)
        if df is None or df.empty:
            return []

        # Filter last N hours
        cutoff = datetime.now() - timedelta(hours=hours)
        timestamp_col = (
            "timestamp_utc" if "timestamp_utc" in df.columns else "timestamp"
        )
        if timestamp_col in df.columns:
            df = df[df[timestamp_col] >= cutoff]

        # Convert to list of dicts
        records = df.to_dict("records")

        # Convert timestamps
        for record in records:
            for ts_col in ["timestamp_utc", "timestamp"]:
                if ts_col in record and isinstance(record[ts_col], pd.Timestamp):
                    record[ts_col] = record[ts_col].isoformat()

        return records

    def get_efficiency_rankings(self) -> List[Dict]:
        """
        Get efficiency rankings for all trucks

        🔧 v3.8.1 Fixes:
        - Changed idle_consumption_gph → consumption_gph (correct field)
        - Added cap on idle_score to prevent infinity (max 200%)
        - Uses 24h averages when available for more stable metrics
        """
        trucks = self.get_all_trucks()
        rankings = []

        for truck_id in trucks:
            record = self.get_truck_latest_record(truck_id)
            if not record:
                continue

            # Check if online
            try:
                ts_val = record.get("timestamp_utc") or record.get("timestamp")
                if not ts_val:
                    continue
                timestamp = pd.to_datetime(ts_val)
                age_minutes = (datetime.now() - timestamp).total_seconds() / 60

                if age_minutes > 60:  # Changed from 5 to 60 minutes for more trucks
                    continue  # Skip offline trucks

                # 🔧 FIX: Use correct field and prefer 24h averages
                mpg = record.get("avg_mpg_24h") or record.get("mpg_current", 0)
                # 🔧 FIX: Use consumption_gph (correct field) or avg_idle_gph_24h
                idle_gph = record.get("avg_idle_gph_24h") or record.get(
                    "consumption_gph", 0
                )

                # Get truck status to determine if idle_gph is relevant
                truck_status = record.get("truck_status", "OFFLINE")

                # Convert NaN to None for JSON serialization
                mpg_val = None if pd.isna(mpg) else round(float(mpg), 2)
                idle_val = None if pd.isna(idle_gph) else round(float(idle_gph), 2)

                # Calculate efficiency score (higher MPG = better, lower idle = better)
                # Normalize: MPG target ~6.5, idle target ~0.8
                mpg_score = (mpg / 6.5) * 100 if mpg > 0 and not pd.isna(mpg) else 0

                # 🔧 FIX: Cap idle_score at 200% to prevent infinity
                if idle_gph > 0 and not pd.isna(idle_gph):
                    idle_score = min((0.8 / idle_gph) * 100, 200)  # Cap at 200%
                else:
                    idle_score = 100  # Default if no idle data

                overall_score = mpg_score * 0.6 + idle_score * 0.4

                rankings.append(
                    {
                        "truck_id": truck_id,
                        "mpg": mpg_val,
                        "idle_gph": idle_val,
                        "status": truck_status,
                        "overall_score": (
                            None
                            if pd.isna(overall_score)
                            else round(float(overall_score), 1)
                        ),
                        "mpg_score": (
                            None if pd.isna(mpg_score) else round(float(mpg_score), 1)
                        ),
                        "idle_score": (
                            None if pd.isna(idle_score) else round(float(idle_score), 1)
                        ),
                    }
                )

            except Exception as e:
                print(f"Error calculating efficiency for {truck_id}: {e}")
                continue

        # Sort by overall_score descending
        rankings.sort(key=lambda x: x.get("overall_score") or 0, reverse=True)

        return rankings

    def get_refuel_history(self, truck_id: str, days: int = 30) -> List[Dict]:
        """Get refuel events history for a truck (MySQL first, then CSV fallback)"""

        # Try MySQL first
        if self.mysql_available:
            try:
                refuels = self.mysql_get_refuels(truck_id=truck_id, days_back=days)
                if refuels:
                    # MySQL function already returns correctly formatted data
                    # DEFENSIVE: Ensure all refuels have truck_id
                    for refuel in refuels:
                        if "truck_id" not in refuel or not refuel["truck_id"]:
                            refuel["truck_id"] = truck_id
                            logger.warning(
                                f"⚠️ Added missing truck_id to refuel for {truck_id}"
                            )

                    logger.info(
                        f"✅ Retrieved {len(refuels)} refuel events from MySQL for {truck_id}"
                    )
                    return refuels
            except Exception as e:
                logger.error(
                    f"❌ MySQL refuel query failed for {truck_id}, using CSV: {e}"
                )

        # Fallback to CSV
        logger.info(f"⚠️ Using CSV fallback for {truck_id} refuels")
        refuels = []
        seen_timestamps = set()  # Para deduplicar refuels
        end_date = datetime.now().date()

        for i in range(days):
            date = end_date - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            csv_file = self.csv_dir / f"fuel_report_{truck_id}_{date_str}.csv"

            if csv_file.exists():
                try:
                    df = pd.read_csv(csv_file, on_bad_lines="skip", engine="python")
                    if df.empty:
                        continue

                    # Check if we have the refuel_gallons column
                    if "refuel_gallons" in df.columns:
                        refuel_rows = df[
                            df["refuel_gallons"].notna() & (df["refuel_gallons"] > 0)
                        ]

                        for _, row in refuel_rows.iterrows():
                            try:
                                timestamp = pd.to_datetime(row["timestamp_utc"])
                                gallons = float(row["refuel_gallons"])

                                # Crear clave única: fecha + hora (sin segundos) para deduplicar
                                timestamp_key = timestamp.strftime("%Y-%m-%d %H:%M")

                                # Skip si ya procesamos este refuel
                                if timestamp_key in seen_timestamps:
                                    continue

                                seen_timestamps.add(timestamp_key)

                                estimated_pct = row.get("estimated_pct")
                                if pd.notna(estimated_pct):
                                    estimated_pct = float(estimated_pct)
                                else:
                                    estimated_pct = None

                                refuels.append(
                                    {
                                        "truck_id": truck_id,
                                        "timestamp": timestamp.isoformat(),
                                        "date": timestamp.strftime("%Y-%m-%d"),
                                        "time": timestamp.strftime("%H:%M:%S"),
                                        "gallons": round(gallons, 2),
                                        "liters": round(
                                            gallons * 3.78541, 2
                                        ),  # FIX: gallons to liters
                                        "fuel_level_after": (
                                            round(estimated_pct, 1)
                                            if estimated_pct
                                            else None
                                        ),
                                    }
                                )
                            except Exception as e:
                                print(f"Error parsing refuel row: {e}")
                                continue

                except Exception as e:
                    print(f"Error reading CSV {csv_file}: {e}")
                    continue

        # Sort by timestamp descending (most recent first)
        refuels.sort(key=lambda x: x["timestamp"], reverse=True)
        return refuels

    def get_all_refuels(self, days: int = 7) -> List[Dict]:
        """Get all refuel events for the entire fleet"""
        all_refuels = []
        trucks = self.get_all_trucks()

        for truck_id in trucks:
            truck_refuels = self.get_refuel_history(truck_id, days)
            # Add truck_id to each refuel event
            for refuel in truck_refuels:
                refuel["truck_id"] = truck_id
                all_refuels.append(refuel)

        # Sort by timestamp descending (most recent first)
        all_refuels.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_refuels

    def get_alerts(self) -> List[Dict]:
        """Get active alerts for fleet"""
        trucks = self.get_all_trucks()
        alerts = []

        for truck_id in trucks:
            record = self.get_truck_latest_record(truck_id)
            if not record:
                continue

            try:
                ts_val = record.get("timestamp_utc") or record.get("timestamp")
                if not ts_val:
                    continue
                timestamp = pd.to_datetime(ts_val)
                age_minutes = (datetime.now() - timestamp).total_seconds() / 60

                # Offline alert
                if age_minutes > 5:
                    alerts.append(
                        {
                            "truck_id": truck_id,
                            "type": "offline",
                            "severity": "warning",
                            "message": f"Truck offline for {int(age_minutes)} minutes",
                            "timestamp": timestamp.isoformat(),
                        }
                    )
                    continue

                # High idle alert
                # 🔧 FIX v3.9.1: Use correct field consumption_gph (not idle_consumption_gph)
                idle_gph = record.get("consumption_gph", 0)
                if idle_gph and idle_gph > 1.5:
                    alerts.append(
                        {
                            "truck_id": truck_id,
                            "type": "high_idle",
                            "severity": "warning",
                            "message": f"High idle consumption: {idle_gph:.2f} GPH",
                            "timestamp": timestamp.isoformat(),
                        }
                    )

                # Low MPG alert
                mpg = record.get("mpg_current", 0)
                if mpg > 0 and mpg < 5.0:
                    alerts.append(
                        {
                            "truck_id": truck_id,
                            "type": "low_mpg",
                            "severity": "warning",
                            "message": f"Low MPG: {mpg:.2f}",
                            "timestamp": timestamp.isoformat(),
                        }
                    )

                # Low fuel alert
                # 🔧 FIX v3.9.1: Use correct field estimated_pct (not fuel_percent)
                fuel_percent = record.get("estimated_pct", 100)
                if fuel_percent and fuel_percent < 15:
                    alerts.append(
                        {
                            "truck_id": truck_id,
                            "type": "low_fuel",
                            "severity": "critical",
                            "message": f"Low fuel: {fuel_percent:.1f}%",
                            "timestamp": timestamp.isoformat(),
                        }
                    )

            except Exception as e:
                print(f"Error checking alerts for {truck_id}: {e}")
                continue

        # Sort by severity (critical first) then by timestamp
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(
            key=lambda x: (severity_order.get(x["severity"], 3), x["timestamp"]),
            reverse=True,
        )

        return alerts


# Singleton instance
db = DatabaseManager()
