"""
CSV Reporter Module - Extracted from fuel_copilot_v2_1_fixed.py

Handles CSV and MySQL data persistence for fuel metrics.

Author: Fuel Copilot Team
Version: 3.5.0
Date: November 26, 2025
"""

import os
import csv
import logging
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo
from enum import Enum

logger = logging.getLogger(__name__)

# Constants
LITERS_TO_GALLONS = 1 / 3.78541
CSV_REPORTS_DIR = "data/csv_reports"


def ensure_directories():
    """Create necessary directories if they don't exist"""
    dirs = [CSV_REPORTS_DIR, "data/analysis_plots"]
    for directory in dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"📁 Created directory: {directory}")


def _bool_to_yesno(value) -> str:
    """Convert Python boolean to MySQL ENUM('YES','NO')"""
    if value is None:
        return "NO"
    return "YES" if value else "NO"


class TruckStatus(Enum):
    """Truck status enum"""

    MOVING = "MOVING"
    STOPPED = "STOPPED"
    PARKED = "PARKED"
    OFFLINE = "OFFLINE"


class CSVReporter:
    """CSV reporter for fuel copilot data with MySQL dual-write"""

    # CSV Headers
    HEADERS = [
        "timestamp_utc",
        "data_age_min",
        "truck_status",
        "estimated_liters",
        "estimated_gallons",
        "estimated_pct",
        "sensor_pct",
        "sensor_liters",
        "sensor_gallons",
        "sensor_ema_pct",
        "ecu_level_pct",
        "model_level_pct",
        "confidence_indicator",
        "consumption_lph",
        "consumption_gph",
        "idle_method",
        "idle_mode",
        "mpg_current",
        "speed_mph",
        "rpm",
        "hdop",
        "altitude_ft",
        "coolant_temp_f",
        "odometer_mi",
        "odom_delta_mi",
        "drift_pct",
        "drift_warning",
        "anchor_detected",
        "anchor_type",
        "static_anchors_total",
        "micro_anchors_total",
        "refuel_events_total",
        "refuel_gallons",
        "flags",
    ]

    def __init__(self, truck_id: str):
        self.truck_id = truck_id
        self.csv_file = None
        self.csv_writer = None
        self.current_date = None
        self._initialize_csv()

    def _initialize_csv(self):
        """Initialize CSV file with headers"""
        today = datetime.now().date()

        if self.current_date != today:
            if self.csv_file:
                self.csv_file.close()

            ensure_directories()

            filename = os.path.join(
                CSV_REPORTS_DIR, f"fuel_report_{self.truck_id}_{today}.csv"
            )
            file_exists = os.path.exists(filename)

            self.csv_file = open(filename, "a", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.current_date = today

            if not file_exists:
                self.csv_writer.writerow(self.HEADERS)
                self.csv_file.flush()
                logger.info(f"📊 CSV Report initialized: {filename}")

    def write_row(
        self,
        timestamp: datetime,
        data_age_min: float,
        truck_status,
        estimate: Optional[Dict],
        sensors: Dict,
        odom_delta: float,
        drift_pct: float,
        drift_warning: bool,
        anchor_detected: bool,
        anchor_type,
        anchor_stats: Dict,
        flags: Dict,
        ema_pct: Optional[float],
        tanks_config,
        truck_id: str,
        mpg_current: Optional[float] = None,
        refuel_gallons: float = 0.0,
        idle_method: str = "NOT_IDLE",
        idle_mode: str = "ENGINE_OFF",
        epoch_time: int = 0,
    ):
        """Write a data row to CSV and MySQL"""
        self._initialize_csv()

        drift_pct = drift_pct if drift_pct is not None else 0.0
        timestamp_est = timestamp.astimezone(ZoneInfo("America/New_York"))

        # Get capacity for calculations
        capacity = tanks_config.get_capacity(truck_id) if tanks_config else 757.0

        # Build confidence indicator
        if sensors.get("fuel_lvl") is None:
            confidence = "SIN SENSOR"
        elif drift_pct is not None and abs(drift_pct) > 10.0:
            confidence = "SOSPECHOSO"
        else:
            confidence = "OK"

        # Handle truck_status as string or enum
        status_value = (
            truck_status.value if hasattr(truck_status, "value") else str(truck_status)
        )

        # Handle anchor_type as string or enum
        anchor_type_str = ""
        if anchor_type:
            anchor_type_str = (
                anchor_type.value if hasattr(anchor_type, "value") else str(anchor_type)
            )

        row = [
            timestamp_est.strftime("%Y-%m-%d %H:%M:%S"),
            f"{data_age_min:.1f}",
            status_value,
            f"{estimate['level_liters']:.2f}" if estimate else "",
            f"{estimate['level_liters'] * LITERS_TO_GALLONS:.2f}" if estimate else "",
            f"{estimate['level_pct']:.2f}" if estimate else "",
            (
                f"{sensors.get('fuel_lvl'):.2f}"
                if sensors.get("fuel_lvl") is not None
                else ""
            ),
            (
                f"{capacity * sensors.get('fuel_lvl') / 100.0:.2f}"
                if sensors.get("fuel_lvl") is not None
                else ""
            ),
            (
                f"{capacity * sensors.get('fuel_lvl') / 100.0 * LITERS_TO_GALLONS:.2f}"
                if sensors.get("fuel_lvl") is not None
                else ""
            ),
            f"{ema_pct:.2f}" if ema_pct is not None else "",
            f"{ema_pct:.2f}" if ema_pct is not None else "",
            f"{estimate['level_pct']:.2f}" if estimate else "",
            confidence,
            f"{estimate['consumption_lph']:.2f}" if estimate else "",
            f"{estimate['consumption_lph'] * 0.264172:.2f}" if estimate else "",
            idle_method,
            idle_mode,
            f"{mpg_current:.2f}" if mpg_current is not None else "",
            (
                f"{sensors.get('obd_speed'):.1f}"
                if sensors.get("obd_speed") is not None
                else ""
            ),
            f"{sensors.get('rpm'):.0f}" if sensors.get("rpm") is not None else "",
            f"{sensors.get('hdop'):.2f}" if sensors.get("hdop") is not None else "",
            (
                f"{sensors.get('altitude'):.1f}"
                if sensors.get("altitude") is not None
                else ""
            ),
            (
                f"{sensors.get('cool_temp'):.1f}"
                if sensors.get("cool_temp") is not None
                else ""
            ),
            f"{sensors.get('odom'):.1f}" if sensors.get("odom") is not None else "",
            f"{odom_delta:.3f}",
            f"{drift_pct:.2f}",
            "YES" if drift_warning else "NO",
            "YES" if anchor_detected else "NO",
            anchor_type_str,
            anchor_stats.get("static_anchors", 0),
            anchor_stats.get("micro_anchors", 0),
            anchor_stats.get("refuel_events", 0),
            f"{refuel_gallons:.1f}" if refuel_gallons > 0 else "",
            "|".join([k for k, v in (flags or {}).items() if v]),
        ]

        if self.csv_writer:
            self.csv_writer.writerow(row)
            self.csv_file.flush()

        # MySQL dual-write
        self._write_to_mysql(
            truck_id,
            timestamp,
            data_age_min,
            status_value,
            estimate,
            sensors,
            odom_delta,
            drift_pct,
            drift_warning,
            anchor_detected,
            anchor_type_str,
            anchor_stats,
            ema_pct,
            tanks_config,
            mpg_current,
            refuel_gallons,
            idle_method,
            idle_mode,
            epoch_time,
            confidence,
        )

    def _write_to_mysql(
        self,
        truck_id,
        timestamp,
        data_age_min,
        truck_status,
        estimate,
        sensors,
        odom_delta,
        drift_pct,
        drift_warning,
        anchor_detected,
        anchor_type,
        anchor_stats,
        ema_pct,
        tanks_config,
        mpg_current,
        refuel_gallons,
        idle_method,
        idle_mode,
        epoch_time,
        confidence,
    ):
        """Write to MySQL database"""
        try:
            from bulk_mysql_handler import save_to_mysql_bulk

            capacity = tanks_config.get_capacity(truck_id) if tanks_config else 757.0

            # Convert PARKED to OFFLINE for MySQL compatibility
            mysql_status = truck_status if truck_status != "PARKED" else "OFFLINE"

            # Convert timestamp
            timestamp_local = timestamp.astimezone(ZoneInfo("America/New_York"))
            timestamp_naive = timestamp_local.replace(tzinfo=None)

            mysql_data = {
                "timestamp_utc": timestamp_naive,
                "epoch_time": epoch_time,
                "data_age_min": data_age_min,
                "truck_status": mysql_status,
                "estimated_liters": estimate["level_liters"] if estimate else None,
                "estimated_gallons": (
                    estimate["level_liters"] * LITERS_TO_GALLONS if estimate else None
                ),
                "estimated_pct": estimate["level_pct"] if estimate else None,
                "sensor_pct": sensors.get("fuel_lvl"),
                "sensor_liters": (
                    capacity * sensors.get("fuel_lvl") / 100.0
                    if sensors.get("fuel_lvl") is not None
                    else None
                ),
                "sensor_gallons": (
                    capacity * sensors.get("fuel_lvl") / 100.0 * LITERS_TO_GALLONS
                    if sensors.get("fuel_lvl") is not None
                    else None
                ),
                "sensor_ema_pct": ema_pct,
                "ecu_level_pct": ema_pct,
                "model_level_pct": estimate["level_pct"] if estimate else None,
                "confidence_indicator": confidence,
                "consumption_lph": estimate["consumption_lph"] if estimate else None,
                "consumption_gph": (
                    estimate["consumption_lph"] * 0.264172 if estimate else None
                ),
                "idle_method": idle_method,
                "idle_mode": idle_mode,
                "mpg_current": mpg_current,
                "speed_mph": sensors.get("obd_speed"),
                "rpm": sensors.get("rpm"),
                "hdop": sensors.get("hdop"),
                "altitude_ft": sensors.get("altitude"),
                "coolant_temp_f": sensors.get("cool_temp"),
                "odometer_mi": sensors.get("odom"),
                "odom_delta_mi": odom_delta,
                "drift_pct": drift_pct,
                "drift_warning": drift_warning,
                "anchor_detected": anchor_detected,
                "anchor_type": anchor_type,
                "static_anchors_total": anchor_stats.get("static_anchors", 0),
                "micro_anchors_total": anchor_stats.get("micro_anchors", 0),
                "refuel_events_total": anchor_stats.get("refuel_events", 0),
                "refuel_gallons": refuel_gallons if refuel_gallons > 0 else None,
                "flags": "",
            }

            save_to_mysql_bulk(truck_id, mysql_data)

        except ImportError:
            pass  # MySQL not available
        except Exception as e:
            logger.warning(f"[{truck_id}] MySQL write failed: {e}")

    def close(self):
        """Close CSV file"""
        if self.csv_file:
            self.csv_file.close()
            logger.info(f"📊 CSV Report closed for {self.truck_id}")
