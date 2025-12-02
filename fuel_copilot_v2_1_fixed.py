"""
Fuel Copilot v3.11.6 - Production-Grade Fleet Fuel Monitoring
Real-time Fuel Level Estimation with Kalman Filter

CORE FEATURES:
- Kalman Filter for fuel level estimation
- Static Anchor Detection (truck stopped 30-45s)
- Micro Anchor Detection (stable cruise 3-6 min)
- Gap-Aware Refuel Detection - v3.11.2: Detects refuels during engine-off gaps
- Refuel Deduplication (30-min cooldown) - v3.11.1: Prevents duplicate detections
- Consecutive Refuel Summing - v3.11.5: Multi-jump refuels aggregated as single event
- Database Persistence - v3.11.5: Refuels saved to refuel_events table
- Anti-Noise Filter - v3.11.6: Rejects false positives from sensor glitches
- Fuel Theft Detection (sudden drops >10% while stopped)
- MPG Tracking with EMA smoothing
- Idle Consumption with temperature adjustment
- Multi-source consumption: ECU, Kalman delta, RPM-based, fallback
- Multi-Tenant Support (carrier_id) - v3.10.8
- State Persistence with Freshness Validation - v3.11.0

ARCHITECTURE:
- Predict phase: fuel_rate sensor -> consumption estimation
- Update phase: Static/Micro anchors calibrate filter
- Adaptive noise: Speed, altitude, acceleration detection
- Emergency reset: Auto-resync on extreme drift (>30%, >2h gap)
- State files: Saved every 60s, validated for freshness on load

DATA FLOW:
Wialon DB -> WialonReader -> Kalman Filter -> CSV/MySQL Reporter -> Dashboard

CHANGELOG v3.11.6:
- NEW: Anti-noise filter for refuel detection (NQ6975 false positive fix)
- NEW: Validates "before" level isn't anomalously low (sensor glitch)
- NEW: Compares reference vs recent history - rejects if >25% deviation
- NEW: recent_fuel_history tracking per truck (last 5 valid readings)
- FIX: Sensor drops like 45%→2.8%→45% no longer trigger false refuels

CHANGELOG v3.11.5:
- NEW: save_refuel_to_db() - Insert refuel events into refuel_events table
- NEW: Consecutive refuel summing - detect multi-jump refuels (RR3094 scenario)
- NEW: pending_refuels buffer - accumulates jumps within 10 min window
- NEW: finalize_pending_refuel() - sums accumulated gallons before DB insert
- FIX: Refuels now properly saved to MySQL for dashboard queries
- FIX: Single 171 gal refuel no longer detected as 105 gal (first jump only)

CHANGELOG v3.11.4:
- FIX: CRITICAL TIMEZONE BUG - timestamp_utc was actually EST, 5 hours off!
- FIX: Wialon measure_datetime is CST, not UTC as assumed
- FIX: Now using epoch_time (always correct) to generate true UTC timestamps
- FIX: Dashboard should now show correct "X minutes ago" values

CHANGELOG v3.11.3:
- FIX: CRITICAL - Added missing apply_refuel_reset() method to FuelEstimator
- FIX: System was crashing on every refuel detection
- FIX: All trucks stuck at 5+ hours old data due to this error
- FIX: Method properly resets Kalman filter state after refuel

CHANGELOG v3.11.2:
- NEW: Gap-Aware Refuel Detection - industry standard logic
- FIX: Trucks turn off engine during refueling (safety requirement)
- FIX: Data gaps (5-120 min) + fuel increase = automatic refuel detection
- NEW: MIN_REFUEL_GAP_MINUTES = 5, MAX_REFUEL_GAP_MINUTES = 120
- FIX: Always compare against LAST KNOWN level before gap from MySQL

CHANGELOG v3.11.1:
- FIX: Refuel deduplication - same refuel was logged 20+ times
- NEW: 30-minute cooldown between refuel detections per truck
- NEW: last_refuel_times tracking dictionary
- FIX: Refuel alerts and logging only fire once per actual refuel

CHANGELOG v3.11.0:
- FIX: Stale status bug - trucks showing OFFLINE when actually MOVING
- NEW: State persistence with 2-hour freshness validation
- NEW: Automatic cleanup of stale state files on startup
- NEW: Save estimator states every 60 seconds
- NEW: Save states on shutdown/crash for fast recovery

CHANGELOG v3.10.8:
- NEW: Multi-tenant support with carrier_id from tanks.yaml
- NEW: carrier_id stored in MySQL for filtering by customer
- NEW: carriers table with customer metadata

CHANGELOG v3.10.7:
- FIX: MPG delta_hours now uses actual timestamps instead of POLL_INTERVAL
- FIX: max_mpg reduced from 20.0 to 9.0 (realistic for Class 8 trucks)
- FIX: min_miles increased from 3.0 to 10.0 for MPG accuracy
- FIX: min_fuel_gal increased from 0.5 to 1.5 for MPG accuracy
- FIX: EMA alpha changed from 0.6 to 0.4 (more smoothing)
- FIX: refuel_jump_threshold_pct increased from 10% to 15%
- NEW: Fuel theft detection (drops >10% while stopped)

For full changelog, see: docs/CHANGELOG.md
"""

import os
import sys
import time
import logging
import csv
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# 🚀 v3.1.0: Import modules
from wialon_reader import WialonReader, WialonConfig, TRUCK_CONFIG, TRUCK_UNIT_MAPPING
from mpg_engine import MPGState, update_mpg_state, MPGConfig
from idle_engine import (
    calculate_idle_consumption,
    IdleConfig,
    detect_idle_mode,
)

# 🚀 v3.6.0: Observability
from observability import (
    get_metrics,
    get_health_checker,
    ObservabilityServer,
    HealthCheckResult,
    HealthStatus,
)

# 🆕 v3.8.0: Alert Service for refuel notifications
from alert_service import get_alert_manager

# Initialize logger
logger = logging.getLogger(__name__)

# 🔧 FIX v3.9.4: Use INFO level in production (was DEBUG)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# 🆕 v3.9.7: Separate refuel logger for audit trail
refuel_logger = logging.getLogger("refuel_audit")
refuel_handler = logging.FileHandler("logs/refuel_events.log")
refuel_handler.setFormatter(logging.Formatter("%(asctime)s [REFUEL] %(message)s"))
refuel_logger.addHandler(refuel_handler)
refuel_logger.setLevel(logging.INFO)


# INLINE TanksConfig - simple version (no LUT needed)
class TanksConfig:
    """Simple tank configuration handler - reads from tanks.yaml via TRUCK_CONFIG"""

    def __init__(self, yaml_file: str = "tanks.yaml"):
        # Use TRUCK_CONFIG from wialon_reader (single source of truth)
        self.trucks = TRUCK_CONFIG
        if not self.trucks:
            logger.warning(f"⚠️ No truck configuration loaded from tanks.yaml")
        # 🔧 FIX v3.9.7: Cache capacity lookups for performance
        self._capacity_cache: Dict[str, float] = {}
        self._refuel_factor_cache: Dict[str, float] = {}

    def get_capacity(self, truck_id: str) -> float:
        """Get tank capacity in liters for a truck (cached)"""
        if truck_id not in self._capacity_cache:
            truck_data = self.trucks.get(truck_id, {})
            self._capacity_cache[truck_id] = truck_data.get(
                "capacity_liters", 757.08
            )  # default 200 gal
        return self._capacity_cache[truck_id]

    def get_refuel_factor(self, truck_id: str, default_factor: float = 1.0) -> float:
        """Get refuel correction factor for a truck (cached)"""
        cache_key = f"{truck_id}_{default_factor}"
        if cache_key not in self._refuel_factor_cache:
            truck_data = self.trucks.get(truck_id, {})
            self._refuel_factor_cache[cache_key] = truck_data.get(
                "refuel_factor", default_factor
            )
        return self._refuel_factor_cache[cache_key]

    # 🆕 v3.10.8: Get carrier_id for multi-tenant support
    def get_carrier_id(self, truck_id: str, default: str = "skylord") -> str:
        """Get carrier_id for a truck from tanks.yaml"""
        truck_data = self.trucks.get(truck_id, {})
        return truck_data.get("carrier_id", default)


# 🆕 MPG PERSISTENCE HELPERS
def save_mpg_states(mpg_states: Dict[str, MPGState]):
    """Save MPG states to JSON file to survive restarts"""
    try:
        data = {}
        for truck_id, state in mpg_states.items():
            data[truck_id] = {
                "distance_accum": state.distance_accum,
                "fuel_accum_gal": state.fuel_accum_gal,
                "mpg_current": state.mpg_current,
                "window_count": state.window_count,
                # 🆕 New fields for delta calculation
                "last_fuel_lvl_pct": state.last_fuel_lvl_pct,
                "last_odometer_mi": state.last_odometer_mi,
                "last_timestamp": state.last_timestamp,
                "fuel_source_stats": getattr(
                    state, "fuel_source_stats", {"sensor": 0, "fallback": 0}
                ),
            }

        with open("data/mpg_states.json", "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"❌ Failed to save MPG states: {e}")


# ============================================================================
# 🆕 v3.11.0: ESTIMATOR STATE PERSISTENCE - FIX FOR STALE STATUS BUG
# ============================================================================
ESTIMATOR_STATES_DIR = "data/estimator_states"


def save_estimator_state(
    truck_id: str, estimator: "FuelEstimator", mpg_state: Optional["MPGState"] = None
):
    """
    Save estimator state to JSON file for persistence across restarts.

    🔧 v3.11.0: Added proper state persistence to prevent stale status bug
    where trucks show OFFLINE in dashboard despite being MOVING in Wialon.
    """
    try:
        os.makedirs(ESTIMATOR_STATES_DIR, exist_ok=True)
        filepath = os.path.join(ESTIMATOR_STATES_DIR, f"{truck_id}_state.json")

        state_data = {
            "truck_id": truck_id,
            "initialized": estimator.initialized,
            "level_liters": estimator.level_liters,
            "level_pct": estimator.level_pct,
            "consumption_lph": estimator.consumption_lph,
            "drift_pct": estimator.drift_pct,
            "P": estimator.P,
            "L": estimator.L,
            "P_L": estimator.P_L,
            "last_fuel_lvl_pct": estimator.last_fuel_lvl_pct,
            # 🔑 CRITICAL: Save timestamp in ISO format for freshness check
            "last_timestamp": datetime.now(timezone.utc).isoformat(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        # Include MPG state if available
        if mpg_state:
            state_data["mpg_current"] = mpg_state.mpg_current
            state_data["mpg_distance_accum"] = mpg_state.distance_accum
            state_data["mpg_fuel_accum_gal"] = mpg_state.fuel_accum_gal

        with open(filepath, "w") as f:
            json.dump(state_data, f, indent=2)

    except Exception as e:
        logger.error(f"[{truck_id}] ❌ Failed to save estimator state: {e}")


def load_estimator_state(truck_id: str) -> Optional[Dict]:
    """
    Load estimator state from JSON file.

    🔧 v3.11.0: Added FRESHNESS CHECK - reject states older than 2 hours
    to prevent stale status bug.

    Returns:
        Dict with state data if valid and fresh, None if stale/missing/invalid
    """
    try:
        filepath = os.path.join(ESTIMATOR_STATES_DIR, f"{truck_id}_state.json")

        if not os.path.exists(filepath):
            return None

        with open(filepath, "r") as f:
            state_data = json.load(f)

        # 🔑 CRITICAL: Check freshness - reject states older than 2 hours
        last_timestamp_str = state_data.get("last_timestamp") or state_data.get(
            "saved_at"
        )
        if last_timestamp_str:
            try:
                last_timestamp = datetime.fromisoformat(
                    last_timestamp_str.replace("Z", "+00:00")
                )
                if last_timestamp.tzinfo is None:
                    last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)

                age_hours = (
                    datetime.now(timezone.utc) - last_timestamp
                ).total_seconds() / 3600

                # STALE STATE DETECTION
                MAX_STATE_AGE_HOURS = 2.0
                if age_hours > MAX_STATE_AGE_HOURS:
                    logger.warning(
                        f"[{truck_id}] ⚠️ STALE STATE DETECTED: {age_hours:.1f}h old "
                        f"(max {MAX_STATE_AGE_HOURS}h) - will reset to fresh sensor data"
                    )
                    # Delete the stale file to prevent future issues
                    try:
                        os.remove(filepath)
                        logger.info(f"[{truck_id}] 🗑️ Deleted stale state file")
                    except Exception:
                        pass
                    return None

                logger.debug(f"[{truck_id}] ✅ State file fresh ({age_hours:.1f}h old)")

            except (ValueError, TypeError) as e:
                logger.warning(f"[{truck_id}] Could not parse timestamp: {e}")
                return None
        else:
            # No timestamp = stale state
            logger.warning(
                f"[{truck_id}] State file has no timestamp - treating as stale"
            )
            return None

        return state_data

    except json.JSONDecodeError as e:
        logger.warning(f"[{truck_id}] Invalid JSON in state file: {e}")
        return None
    except Exception as e:
        logger.error(f"[{truck_id}] ❌ Failed to load estimator state: {e}")
        return None


def restore_estimator_from_state(estimator: "FuelEstimator", state_data: Dict) -> bool:
    """
    Restore estimator state from saved data.

    Returns True if restoration successful, False otherwise.
    """
    try:
        estimator.initialized = state_data.get("initialized", False)

        if estimator.initialized:
            estimator.level_liters = state_data.get("level_liters", 0.0)
            estimator.level_pct = state_data.get("level_pct", 0.0)
            estimator.consumption_lph = state_data.get("consumption_lph", 0.0)
            estimator.drift_pct = state_data.get("drift_pct", 0.0)
            estimator.P = state_data.get("P", 1.0)
            estimator.L = state_data.get("L", estimator.level_liters)
            estimator.P_L = state_data.get("P_L", 20.0)
            estimator.last_fuel_lvl_pct = state_data.get("last_fuel_lvl_pct")

            # Set last_update_time to now (we're resuming)
            estimator.last_update_time = datetime.now(timezone.utc)

            logger.info(
                f"[{estimator.truck_id}] ♻️ Restored state: "
                f"{estimator.level_pct:.1f}%, drift={estimator.drift_pct:.1f}%"
            )
            return True

    except Exception as e:
        logger.error(f"[{estimator.truck_id}] ❌ Failed to restore state: {e}")

    return False


def cleanup_stale_estimator_states(max_age_hours: float = 24.0):
    """
    🆕 v3.11.0: Cleanup stale state files on startup.

    Removes state files older than max_age_hours to prevent
    accumulation of stale data.
    """
    try:
        if not os.path.exists(ESTIMATOR_STATES_DIR):
            return

        cleaned_count = 0
        for filename in os.listdir(ESTIMATOR_STATES_DIR):
            if not filename.endswith("_state.json"):
                continue

            filepath = os.path.join(ESTIMATOR_STATES_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    state_data = json.load(f)

                timestamp_str = state_data.get("last_timestamp") or state_data.get(
                    "saved_at"
                )
                if timestamp_str:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)

                    age_hours = (
                        datetime.now(timezone.utc) - timestamp
                    ).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        os.remove(filepath)
                        truck_id = filename.replace("_state.json", "")
                        logger.info(
                            f"[{truck_id}] 🗑️ Cleaned stale state ({age_hours:.1f}h old)"
                        )
                        cleaned_count += 1

            except Exception as e:
                logger.debug(f"Could not check {filename}: {e}")

        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned {cleaned_count} stale state files")

    except Exception as e:
        logger.error(f"❌ Error during state cleanup: {e}")


def load_mpg_states() -> Dict[str, MPGState]:
    """Load MPG states from JSON file"""
    states = {}
    try:
        if os.path.exists("data/mpg_states.json"):
            with open("data/mpg_states.json", "r") as f:
                data = json.load(f)

            for truck_id, state_data in data.items():
                state = MPGState()
                state.distance_accum = state_data.get("distance_accum", 0.0)
                state.fuel_accum_gal = state_data.get("fuel_accum_gal", 0.0)
                state.mpg_current = state_data.get("mpg_current")
                state.window_count = state_data.get("window_count", 0)
                # 🆕 New fields for delta calculation
                state.last_fuel_lvl_pct = state_data.get("last_fuel_lvl_pct")
                state.last_odometer_mi = state_data.get("last_odometer_mi")
                state.last_timestamp = state_data.get("last_timestamp")
                state.fuel_source_stats = state_data.get(
                    "fuel_source_stats", {"sensor": 0, "fallback": 0}
                )
                states[truck_id] = state

            logger.info(f"♻️ Loaded MPG states for {len(states)} trucks")
    except Exception as e:
        logger.error(f"❌ Failed to load MPG states: {e}")
    return states


# Sensor normalizer not needed - using direct ECU % values
class SensorNormalizer:
    """Dummy class - ECU values already normalized (0-100%)"""

    def normalize_fuel_level(self, value):
        """Pass-through - ECU already provides 0-100%"""
        return value

    def normalize_fuel_rate(self, value):
        """Pass-through - rate values used as-is"""
        return value


# 🆕 v2.2 IMPORTS - Executive Edition
# State persistence: usando funciones inline (ver STATE PERSISTENCE HELPERS)
STATE_PERSISTENCE_AVAILABLE = True

# 🔧 FIX v3.9.4: Use importlib.util.find_spec for optional module detection
import importlib.util

CHART_GENERATOR_AVAILABLE = importlib.util.find_spec("fuel_chart_generator") is not None
if not CHART_GENERATOR_AVAILABLE:
    print("⚠️  Chart generator module not found - PNG charts won't be generated")

ALERT_SYSTEM_AVAILABLE = importlib.util.find_spec("alert_system") is not None
if not ALERT_SYSTEM_AVAILABLE:
    print("⚠️  Alert system module not found - Alerts won't be sent")

# ============================================================================
# CONFIGURATION
# ============================================================================
# Load environment variables from .env file if present
from dotenv import load_dotenv

load_dotenv()

# Database Configuration - SECURE: No defaults for sensitive data
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Validate required environment variables
if not all([DB_HOST, DB_NAME, DB_USER, DB_PASS]):
    raise ValueError(
        "❌ SECURITY ERROR: Missing required database credentials!\n"
        "Please create a .env file with: DB_HOST, DB_NAME, DB_USER, DB_PASS\n"
        "See .env.example for template."
    )
# Directory Configuration for organized file storage
CSV_REPORTS_DIR = "data/csv_reports"
ANALYSIS_PLOTS_DIR = "data/analysis_plots"


def ensure_directories():
    """Create necessary directories if they don't exist"""
    for directory in [CSV_REPORTS_DIR, ANALYSIS_PLOTS_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Created directory: {directory}")


# SMTP / Alert configuration (use environment variables)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_TO = os.getenv("ALERT_TO", "ops@example.com")
COOLDOWN_MIN = int(os.getenv("COOLDOWN_MIN", "30"))  # Configurable cooldown in minutes
# Cooldown tracker for alerts (per truck)
last_alert_time: Dict[str, datetime] = {}


def send_email_alert(
    truck_id: str, drift_pct: float, details: str, is_anchor: bool = False
):
    """Send a simple email alert using SMTP. Credentials come from env vars.
    Behavior:
    - Enforces a 30-minute cooldown per truck to avoid alert spam.
    - If SMTP credentials are missing, logs the intended alert and registers a cooldown.
    """
    # Cooldown: do not send more than one alert per truck within 30 minutes
    try:
        now = datetime.now(timezone.utc)
        cooldown_min = 30
        last = last_alert_time.get(truck_id)
        if last is not None:
            delta_min = (now - last).total_seconds() / 60.0
            if delta_min < cooldown_min:
                logger.info(
                    f"Cooldown activo para {truck_id} ({delta_min:.1f} min) - saltando alerta"
                )
                return
    except Exception:
        # If any issue computing cooldown, fall through and attempt send
        pass
    if not SMTP_USER or not SMTP_PASS:
        logger.warning(
            "SMTP credentials not provided; will NOT send email alert, but logging intention"
        )
        logger.info(
            f"[ALERT INTENT] {truck_id} drift={drift_pct:.1f}% details={details}"
        )
        # register last alert time to avoid repeated logs
        last_alert_time[truck_id] = datetime.now(timezone.utc)
        return
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_TO
    subject = f"[ALERTA ROBO] {truck_id} ({drift_pct:.1f}%)"
    if is_anchor:
        subject += " - Durante Anchor!"
    msg["Subject"] = subject
    body = f"Se detectó drift {drift_pct:.1f}% en {truck_id}.\n\nDetalles:\n{details}"
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        logger.info(
            f"📧 Alert sent for {truck_id} (drift {drift_pct:.1f}%) to {ALERT_TO}"
        )
        last_alert_time[truck_id] = datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Failed to send alert email for {truck_id}: {e}")


# 🆕 MULTI-TRUCK CONFIGURATION
# ⚠️ DEPRECATED: TRUCKS dict removed - now loaded from tanks.yaml
# This alias provides backward compatibility for any code still referencing TRUCKS
TRUCKS = TRUCK_CONFIG  # Alias to TRUCK_CONFIG from wialon_reader.py
# Common configuration for all trucks
COMMON_CONFIG = {
    # Idle consumption
    "idle_rate_lph": 2.0,
    # Kalman parameters - OPTIMIZED for filtering sensor noise
    # Q_r = process noise (modelo de consumo) - bajo porque GPH es preciso
    # Q_L = measurement noise (sensor) - alto porque tiene slosh/aceleración/pendiente
    "Q_r": 0.1,  # Was 46.68 - too high, assumed model was imprecise
    "Q_L_moving": 4.0,  # High noise when moving (slosh, acceleration)
    "Q_L_static": 1.0,  # Lower noise when stopped (sensor more reliable)
    "Q_L": 4.0,  # Default (legacy compatibility)
    # Thresholds
    "unreal_threshold_lph": 80.93,
    "hdop_max": 2.0,
    "aged_alert_min": 30,  # Alert at 30 min
    "aged_critical_min": 120,  # OFFLINE at 120 min (2 hours)
    # Extended for trucks with slow transmission (JC9352, JC1282, NQ6975)
    # Safe to keep even when all trucks update to 60s intervals
    # EMA filter
    "ema_alpha": 0.1,
    # Fallback
    "fallback_max_gap_min": 10,
    "fallback_clamp_pct": 0.01,
    # Drift protection
    "max_drift_pct": 7.5,  # Increased from 5.0 based on P95=7.17% real data
    "reset_on_startup": True,
    # ANCHOR PARAMETERS
    "anchor_static_min_duration_s": 30,
    "anchor_static_max_duration_s": 45,
    "anchor_static_speed_max": 0.5,
    "anchor_static_rpm_min": 1,
    "anchor_static_hdop_max": 1.5,
    "anchor_static_alt_delta_max": 35,
    "anchor_static_fuel_var_max": 0.25,
    "anchor_static_drift_min": 0.3,  # Only apply if drift >= 0.3% (avoid unnecessary adjustments)
    "anchor_static_drift_min_post_gap": 0.1,  # 🆕 OPTION 3: More aggressive after gaps (0.1% vs 0.3%)
    "anchor_micro_min_duration_s": 90,  # Minimum 90 seconds window
    "anchor_micro_max_duration_s": 360,
    "anchor_micro_speed_min": 30,
    "anchor_micro_speed_std_factor": 0.15,  # Dynamic: max(5, 0.15 * mean_speed)
    "anchor_micro_hdop_good": 1.5,  # HDOP <= 1.5 adds to quality score
    "anchor_micro_hdop_max": 2.5,  # HDOP > 2.5 rejects anchor
    "anchor_micro_alt_delta_max": 150,  # Max altitude change (relaxed for highway with rolling terrain)
    "anchor_micro_slope_max_pct": 2.0,  # Max 2% slope (delta_alt/delta_dist)
    "anchor_micro_fuel_var_max": 0.5,  # Max fuel variance
    "anchor_micro_quality_threshold": 0.4,  # Minimum quality score to accept anchor
    "anchor_micro_drift_min": 0.5,  # Only apply if drift >= 0.5% (50% of time drift < 1%)
    "anchor_micro_drift_min_post_gap": 0.2,  # 🆕 OPTION 3: More aggressive after gaps (0.2% vs 0.5%)
    "anchor_micro_adjustment_max_pct": 0.15,
    # 🆕 MODERATE DRIFT CORRECTION: Activate aggressive anchoring for persistent moderate drift
    "drift_moderate_threshold": 5.0,  # Drift >= 5% triggers monitoring
    "drift_moderate_duration_min": 10.0,  # If persists >10 min → aggressive anchoring (3 cycles)
    # 🔧 v3.10.7: Increased from 10.0 to 15.0 to reduce false positive refuels
    # Sensor noise can cause 10% swings; real refuels are typically 30-60% jumps
    "refuel_jump_threshold_pct": 15.0,
    # 🆕 v3.0.7-REFUEL-FIX: Corrección empírica por no-linealidad de tanques
    # Sistema sobreestima ~10% porque tanques no son perfectamente lineales
    # Factor 0.90 ajusta: 100 gal (raw) → 90 gal (real)
    "refuel_volume_factor": 0.90,
    # 🆕 v3.0.9-TUNING (ChatGPT): Idle fallback configurable
    # 0.8 GPH es más realista para flota moderna (Cummins X15, Detroit DD15)
    # Motores ECO: 0.6-0.8 GPH | Motores viejos/DPF regen: 1.0-1.2 GPH
    "idle_fallback_gph": 0.8,
    "thermal_correction_threshold_f": 20.0,
    "thermal_correction_coeff": 0.00046,
    "thermal_correction_max_factor": 0.10,
    "temp_valid_min": 140,
    "temp_valid_max": 220,
    "temp_baseline": 190,
    # STOPPED DETECTION
    "stopped_odom_threshold_mi": 0.01,
    "stopped_speed_max": 1.0,
    # LEANDRO IMPROVEMENTS
    "fuel_drop_max_pct_per_min": 5.0,  # Increased from 3.0 to handle noisy sensors (e.g., FM3679)
}
# Polling interval - OPTIMIZED for real-time dashboard updates
POLL_INTERVAL = 15  # seconds - 4x faster updates for near real-time display
# Sensors to read
SENSORS = [
    "fuel_lvl",
    "fuel_rate",
    "obd_speed",
    "rpm",
    "hdop",
    "altitude",
    "cool_temp",
    "odom",
    "course",
]
# Unit conversion
GPH_TO_LPH = 3.78541
LITERS_TO_GALLONS = 1 / 3.78541  # ~0.264172


# ============================================================================
# ENUMS
# ============================================================================
class AnchorType(Enum):
    """Types of anchors"""

    NONE = "NONE"  # No anchor detected
    STATIC = "STATIC"  # Truck stopped
    MICRO = "MICRO"  # Stable cruise
    REFUEL = "REFUEL"  # Refueling event


class TruckStatus(Enum):
    """Truck status"""

    MOVING = "MOVING"
    STOPPED = "STOPPED"  # Engine ON, parked (idle consumption)
    PARKED = "PARKED"  # Engine OFF, recently (< 30 min)
    OFFLINE = "OFFLINE"  # No data > 30 min OR engine OFF > 30 min


# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class SensorReading:
    """Single sensor reading with timestamp"""

    timestamp: datetime
    fuel_lvl: Optional[float] = None
    fuel_rate: Optional[float] = None
    speed: Optional[float] = None
    rpm: Optional[float] = None
    hdop: Optional[float] = None
    altitude: Optional[float] = None
    cool_temp: Optional[float] = None
    odom: Optional[float] = None


@dataclass
class AnchorEvent:
    """Anchor detection event"""

    timestamp: datetime
    anchor_type: AnchorType
    fuel_level_pct: float
    fuel_level_liters: float
    duration_s: Optional[float] = None
    thermal_correction_applied: bool = False
    thermal_delta_f: Optional[float] = None
    drift_before_pct: Optional[float] = None
    drift_after_pct: Optional[float] = None
    gallons_added: Optional[float] = None  # For refuel events
    details: Optional[Dict] = None


@dataclass
class TruckHealthScore:
    """Health score and diagnostics for a truck"""

    truck_id: str
    health_score: float  # 0-100
    status: str  # EXCELLENT / GOOD / WARNING / CRITICAL
    issues: List[str]

    # Diagnostic flags
    sensor_frozen: bool = False
    sensor_noisy: bool = False
    sensor_disconnected: bool = False
    high_drift: bool = False
    old_data: bool = False
    gps_poor: bool = False

    # Stats for diagnostics
    drift_current: Optional[float] = None
    data_age_minutes: Optional[float] = None
    sensor_variance_24h: Optional[float] = None
    last_sensor_change: Optional[float] = None


# ============================================================================
# ANCHOR DETECTOR - Kalman Calibration via Stable Conditions
# ============================================================================
class AnchorDetector:
    """
    Detects stable conditions (anchors) for Kalman filter calibration.

    Two types of anchors:
    1. STATIC: Truck stopped with engine idling (speed<0.5, rpm>500)
    2. MICRO: Stable cruise (steady speed, stable fuel level)
    """

    def __init__(self, config: Dict):
        self.config = config
        self.static_start_time: Optional[datetime] = None
        self.static_fuel_readings: List[float] = []
        self.cruise_readings: List[Dict] = []  # For micro anchor
        self.last_anchor_time: Optional[datetime] = None
        self.anchor_cooldown_s = 60  # Base minimum time between anchors

        # 🔧 FIX v3.9.4: Adaptive cooldown based on drift history
        self.recent_drift_values: List[float] = []  # Last N drift values
        self.max_drift_history = 20  # Keep last 20 readings

    def _get_adaptive_cooldown(self) -> float:
        """
        🔧 FIX v3.9.4: Calculate adaptive cooldown based on drift history.

        - Low avg drift (< 2%): Short cooldown (30s) - truck is stable
        - Medium drift (2-5%): Normal cooldown (60s)
        - High drift (> 5%): Long cooldown (90-120s) - noisy conditions

        This reduces spurious anchors in noisy conditions while allowing
        faster calibration when the truck is stable.
        """
        if len(self.recent_drift_values) < 3:
            return self.anchor_cooldown_s  # Use base cooldown if not enough data

        import numpy as np

        avg_drift = np.mean([abs(d) for d in self.recent_drift_values])

        if avg_drift < 2.0:
            return float(max(30, self.anchor_cooldown_s - 30))  # 30s minimum
        elif avg_drift < 5.0:
            return float(self.anchor_cooldown_s)  # 60s base
        else:
            # High drift: longer cooldown to avoid chasing noise
            return float(min(120, self.anchor_cooldown_s + avg_drift * 6))

    def _record_drift(self, drift_pct: float):
        """Record drift value for adaptive cooldown calculation"""
        self.recent_drift_values.append(drift_pct)
        if len(self.recent_drift_values) > self.max_drift_history:
            self.recent_drift_values.pop(0)

    def check_static_anchor(
        self,
        timestamp: datetime,
        speed: Optional[float],
        rpm: Optional[float],
        fuel_pct: Optional[float],
        hdop: Optional[float] = None,
        drift_pct: float = 0.0,
    ) -> Optional[Dict]:
        """
        Check if conditions meet STATIC anchor criteria:
        - Speed < 0.5 mph (truck stopped)
        - RPM > 500 (engine idling)
        - HDOP < 1.5 (good GPS)
        - Duration 30-45 seconds
        - Drift above threshold (worth calibrating)
        """
        # Validate inputs
        if speed is None or rpm is None or fuel_pct is None:
            self._reset_static()
            return None

        speed_max = self.config.get("anchor_static_speed_max", 0.5)
        rpm_min = self.config.get("anchor_static_rpm_min", 500)
        hdop_max = self.config.get("anchor_static_hdop_max", 1.5)
        min_duration = self.config.get("anchor_static_min_duration_s", 30)
        max_duration = self.config.get("anchor_static_max_duration_s", 45)
        drift_min = self.config.get("anchor_static_drift_min", 0.3)

        # Check static conditions
        is_static = (
            speed <= speed_max and rpm >= rpm_min and (hdop is None or hdop <= hdop_max)
        )

        if not is_static:
            self._reset_static()
            return None

        # Start tracking if not already
        if self.static_start_time is None:
            self.static_start_time = timestamp
            self.static_fuel_readings = [fuel_pct]
            logger.debug(
                f"🔍 STATIC: Started tracking - speed={speed:.2f}, rpm={rpm}, fuel={fuel_pct:.1f}%"
            )
            return None

        # Accumulate readings
        self.static_fuel_readings.append(fuel_pct)

        # Check duration
        duration = (timestamp - self.static_start_time).total_seconds()

        if duration < min_duration:
            return None

        # Log that we're past duration threshold
        logger.debug(
            f"🔍 STATIC CHECK: duration={duration:.0f}s >= {min_duration}s, drift={drift_pct:.2f}%"
        )

        # 🔧 FIX v3.9.4: Use adaptive cooldown
        self._record_drift(drift_pct)
        adaptive_cooldown = self._get_adaptive_cooldown()

        # Check cooldown
        if self.last_anchor_time:
            cooldown = (timestamp - self.last_anchor_time).total_seconds()
            if cooldown < adaptive_cooldown:
                return None

        # Check fuel variance (should be stable)
        if len(self.static_fuel_readings) >= 2:
            import numpy as np

            fuel_var = np.var(self.static_fuel_readings)
            fuel_var_max = self.config.get("anchor_static_fuel_var_max", 0.25)
            if fuel_var > fuel_var_max:
                self._reset_static()
                return None

        # Check if drift is worth calibrating
        if abs(drift_pct) < drift_min:
            # Drift too small - log as candidate but don't calibrate
            logger.info(
                f"📍 STATIC CANDIDATE: {duration:.0f}s stationary, fuel stable, drift={drift_pct:.2f}% (threshold={drift_min}%, no calibration needed)"
            )
            if duration > max_duration:
                self._reset_static()
            return None

        # STATIC ANCHOR DETECTED!
        import numpy as np

        median_fuel = np.median(self.static_fuel_readings)

        self.last_anchor_time = timestamp
        self._reset_static()

        return {
            "type": AnchorType.STATIC,
            "timestamp": timestamp,
            "fuel_pct": median_fuel,
            "duration_s": duration,
            "num_readings": len(self.static_fuel_readings),
            "drift_pct": drift_pct,
        }

    def check_micro_anchor(
        self,
        timestamp: datetime,
        speed: Optional[float],
        fuel_pct: Optional[float],
        hdop: Optional[float] = None,
        altitude_ft: Optional[float] = None,
        drift_pct: float = 0.0,
    ) -> Optional[Dict]:
        """
        Check if conditions meet MICRO anchor (stable cruise):
        - Speed > 30 mph (highway cruise)
        - Speed std < 15% of mean (stable)
        - Fuel variance < 0.5 (stable reading)
        - Duration 90-360 seconds
        - HDOP < 2.5
        """
        if speed is None or fuel_pct is None:
            self._reset_cruise()
            return None

        speed_min = self.config.get("anchor_micro_speed_min", 30)
        hdop_max = self.config.get("anchor_micro_hdop_max", 2.5)
        min_duration = self.config.get("anchor_micro_min_duration_s", 90)
        max_duration = self.config.get("anchor_micro_max_duration_s", 360)
        drift_min = self.config.get("anchor_micro_drift_min", 0.5)

        # Check basic cruise conditions
        is_cruising = speed >= speed_min and (hdop is None or hdop <= hdop_max)

        if not is_cruising:
            self._reset_cruise()
            return None

        # Add reading
        self.cruise_readings.append(
            {
                "timestamp": timestamp,
                "speed": speed,
                "fuel_pct": fuel_pct,
                "altitude_ft": altitude_ft,
            }
        )

        # Keep window manageable
        if len(self.cruise_readings) > 30:
            self.cruise_readings = self.cruise_readings[-25:]

        if len(self.cruise_readings) < 5:
            return None

        # Calculate duration
        start_time = self.cruise_readings[0]["timestamp"]
        duration = (timestamp - start_time).total_seconds()

        if duration < min_duration:
            return None

        # Check cooldown
        if self.last_anchor_time:
            cooldown = (timestamp - self.last_anchor_time).total_seconds()
            if cooldown < self.anchor_cooldown_s * 2:  # Longer cooldown for micro
                return None

        import numpy as np

        speeds = [r["speed"] for r in self.cruise_readings]
        fuels = [r["fuel_pct"] for r in self.cruise_readings]

        # Check speed stability
        speed_mean = np.mean(speeds)
        speed_std = np.std(speeds)
        speed_std_factor = self.config.get("anchor_micro_speed_std_factor", 0.15)
        max_speed_std = max(5.0, speed_std_factor * speed_mean)

        if speed_std > max_speed_std:
            return None

        # Check fuel stability
        fuel_var = np.var(fuels)
        fuel_var_max = self.config.get("anchor_micro_fuel_var_max", 0.5)

        if fuel_var > fuel_var_max:
            return None

        # Check altitude change if available
        alts = [r["altitude_ft"] for r in self.cruise_readings if r.get("altitude_ft")]
        if len(alts) >= 2:
            alt_delta = abs(max(alts) - min(alts))
            alt_delta_max = self.config.get("anchor_micro_alt_delta_max", 150)
            if alt_delta > alt_delta_max:
                return None

        # Check if drift is worth calibrating
        if abs(drift_pct) < drift_min:
            # Drift too small - log as candidate but don't calibrate
            logger.info(
                f"📍 MICRO CANDIDATE: {duration:.0f}s cruise (speed={speed_mean:.0f}mph), drift={drift_pct:.2f}% (threshold={drift_min}%, no calibration needed)"
            )
            if duration > max_duration:
                self._reset_cruise()
            return None

        # MICRO ANCHOR DETECTED!
        median_fuel = np.median(fuels)

        self.last_anchor_time = timestamp
        self._reset_cruise()

        return {
            "type": AnchorType.MICRO,
            "timestamp": timestamp,
            "fuel_pct": median_fuel,
            "duration_s": duration,
            "num_readings": len(self.cruise_readings),
            "speed_mean": speed_mean,
            "speed_std": speed_std,
            "fuel_variance": fuel_var,
            "drift_pct": drift_pct,
        }

    def _reset_static(self):
        self.static_start_time = None
        self.static_fuel_readings = []

    def _reset_cruise(self):
        self.cruise_readings = []


# NOTE: TRUCK_UNIT_MAPPING is now imported from wialon_reader.py
# This eliminates duplication - tanks.yaml is the single source of truth


# ============================================================================
# MYSQL WRITER (NEW - Parallel to CSV)
# ============================================================================
def _bool_to_yesno(value) -> str:
    """Convert Python boolean to MySQL ENUM('YES','NO')"""
    if value is None:
        return "NO"
    return "YES" if value else "NO"


def get_last_fuel_level_from_mysql(truck_id: str) -> Optional[Dict]:
    """
    🆕 v3.9.8: Get the last recorded fuel level from MySQL for refuel detection
    Returns dict with sensor_pct, estimated_pct, timestamp_utc or None if not found

    CRITICAL for refuel detection after system restarts/gaps
    """
    try:
        import pymysql

        conn = pymysql.connect(
            host="localhost",
            user="fuel_admin",
            password="FuelCopilot2025!",
            database="fuel_copilot",
            connect_timeout=5,
        )
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT sensor_pct, estimated_pct, timestamp_utc
            FROM fuel_metrics 
            WHERE truck_id = %s 
            AND sensor_pct IS NOT NULL
            ORDER BY timestamp_utc DESC 
            LIMIT 1
        """,
            (truck_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "sensor_pct": float(row[0]) if row[0] else None,
                "estimated_pct": float(row[1]) if row[1] else None,
                "timestamp_utc": row[2],
            }
        return None

    except Exception as e:
        logger.debug(f"[{truck_id}] Could not get last fuel level from MySQL: {e}")
        return None


# Cache for last known fuel levels (to avoid repeated DB queries)
_last_fuel_cache: Dict[str, Dict] = {}
_last_fuel_cache_time: Dict[str, datetime] = {}


def get_last_fuel_level_cached(truck_id: str) -> Optional[Dict]:
    """
    🆕 v3.9.8: Get last fuel level with caching to avoid hammering MySQL
    Cache expires after 5 minutes (forces refresh)
    """
    global _last_fuel_cache, _last_fuel_cache_time

    now = datetime.now(timezone.utc)
    cache_ttl_seconds = 300  # 5 minutes

    # Check if cached value is still valid
    if truck_id in _last_fuel_cache:
        cache_time = _last_fuel_cache_time.get(truck_id)
        if cache_time and (now - cache_time).total_seconds() < cache_ttl_seconds:
            return _last_fuel_cache[truck_id]

    # Fetch from MySQL
    result = get_last_fuel_level_from_mysql(truck_id)
    if result:
        _last_fuel_cache[truck_id] = result
        _last_fuel_cache_time[truck_id] = now

    return result


def update_fuel_cache_after_write(
    truck_id: str, sensor_pct: float, estimated_pct: float
):
    """
    🆕 v3.9.8: Update cache after writing to MySQL to keep it fresh
    """
    global _last_fuel_cache, _last_fuel_cache_time

    _last_fuel_cache[truck_id] = {
        "sensor_pct": sensor_pct,
        "estimated_pct": estimated_pct,
        "timestamp_utc": datetime.now(timezone.utc),
    }
    _last_fuel_cache_time[truck_id] = datetime.now(timezone.utc)


# ============================================================================
# 🆕 v3.11.5: REFUEL DATABASE PERSISTENCE
# ============================================================================

# Global buffer for consecutive refuel detection
# Structure: {truck_id: {"start_pct": float, "end_pct": float, "gallons": float,
#                        "start_time": datetime, "last_jump_time": datetime}}
_pending_refuels: Dict[str, Dict] = {}
CONSECUTIVE_REFUEL_WINDOW_MINUTES = 10  # Jumps within 10 min are same refuel event

# 🆕 v3.11.6: ANTI-NOISE FILTER - Recent fuel history per truck
# Stores last N valid readings to detect sensor glitches
# Structure: {truck_id: [fuel_pct, fuel_pct, ...]}  (most recent last)
_recent_fuel_history: Dict[str, List[float]] = {}
FUEL_HISTORY_SIZE = 5  # Keep last 5 readings
NOISE_DEVIATION_THRESHOLD = (
    25.0  # If reference deviates >25% from history median, it's noise
)


def update_fuel_history(truck_id: str, fuel_pct: float):
    """
    🆕 v3.11.6: Track recent fuel readings for noise detection.
    Only add valid readings (not None, between 0-100).
    """
    global _recent_fuel_history

    if fuel_pct is None or fuel_pct < 0 or fuel_pct > 100:
        return

    if truck_id not in _recent_fuel_history:
        _recent_fuel_history[truck_id] = []

    _recent_fuel_history[truck_id].append(fuel_pct)

    # Keep only last N readings
    if len(_recent_fuel_history[truck_id]) > FUEL_HISTORY_SIZE:
        _recent_fuel_history[truck_id] = _recent_fuel_history[truck_id][
            -FUEL_HISTORY_SIZE:
        ]


def is_reference_valid(truck_id: str, reference_pct: float) -> tuple[bool, str]:
    """
    🆕 v3.11.6: Check if reference fuel level is valid (not a sensor glitch).

    Returns (is_valid, reason) tuple.

    Example scenario (NQ6975 false positive):
    - History: [48%, 45%, 47%, 46%, 35%]  (median ~46%)
    - Reference: 2.8%  ← This is clearly a glitch (deviates 43% from median)
    - Current: 45.6%
    - Without filter: Detected as refuel (+42.8%)
    - With filter: Rejected as noise (reference 2.8% is invalid)
    """
    global _recent_fuel_history

    if truck_id not in _recent_fuel_history:
        return True, "no_history"

    history = _recent_fuel_history[truck_id]
    if len(history) < 3:
        return True, "insufficient_history"

    # Calculate median of recent history
    sorted_history = sorted(history)
    mid = len(sorted_history) // 2
    if len(sorted_history) % 2 == 0:
        median = (sorted_history[mid - 1] + sorted_history[mid]) / 2
    else:
        median = sorted_history[mid]

    # Check if reference deviates too much from median
    deviation = abs(reference_pct - median)

    if deviation > NOISE_DEVIATION_THRESHOLD:
        return (
            False,
            f"noise_detected(ref={reference_pct:.1f}%, median={median:.1f}%, dev={deviation:.1f}%)",
        )

    return True, "valid"


def save_refuel_to_db(
    truck_id: str,
    gallons_added: float,
    fuel_before_pct: float,
    fuel_after_pct: float,
    timestamp: datetime,
    carrier_id: str = "skylord",
    location_lat: Optional[float] = None,
    location_lon: Optional[float] = None,
) -> bool:
    """
    🆕 v3.11.5: Save refuel event to refuel_events table in MySQL.

    This function is called after a refuel is detected (including consecutive
    refuel summing) to persist the event for dashboard queries.

    Returns True if saved successfully, False otherwise.
    """
    try:
        from bulk_mysql_handler import get_local_session
        from sqlalchemy import text

        session = get_local_session()
        if not session:
            logger.warning(f"[{truck_id}] Failed to get MySQL session for refuel save")
            return False

        try:
            # Insert into refuel_events table
            query = text(
                """
                INSERT INTO refuel_events 
                (truck_id, carrier_id, timestamp, fuel_before, fuel_after, amount, 
                 location_lat, location_lon, confidence, is_valid)
                VALUES 
                (:truck_id, :carrier_id, :timestamp, :fuel_before, :fuel_after, :amount,
                 :location_lat, :location_lon, :confidence, :is_valid)
            """
            )

            session.execute(
                query,
                {
                    "truck_id": truck_id,
                    "carrier_id": carrier_id,
                    "timestamp": timestamp,
                    "fuel_before": fuel_before_pct,
                    "fuel_after": fuel_after_pct,
                    "amount": gallons_added,
                    "location_lat": location_lat,
                    "location_lon": location_lon,
                    "confidence": 1.0,
                    "is_valid": 1,
                },
            )
            session.commit()

            logger.info(
                f"[{truck_id}] 💾 Refuel saved to DB: {gallons_added:.1f} gal "
                f"({fuel_before_pct:.1f}% → {fuel_after_pct:.1f}%)"
            )
            return True

        except Exception as e:
            session.rollback()
            logger.warning(f"[{truck_id}] Failed to save refuel to DB: {e}")
            return False
        finally:
            session.close()

    except ImportError as e:
        logger.warning(f"[{truck_id}] MySQL not available for refuel save: {e}")
        return False
    except Exception as e:
        logger.warning(f"[{truck_id}] Unexpected error saving refuel: {e}")
        return False


def add_pending_refuel(
    truck_id: str,
    gallons: float,
    before_pct: float,
    after_pct: float,
    timestamp: datetime,
    tanks_config,
) -> Optional[Dict]:
    """
    🆕 v3.11.5: Add a refuel jump to the pending buffer for consecutive detection.

    When a truck refuels, the sensor may report multiple jumps as fuel sloshes/settles:
    - Jump 1: 20% → 80% (+60%)
    - Jump 2: 80% → 96% (+16%)  ← within 10 min = same refuel event
    - Jump 3: 96% → 100% (+4%) ← within 10 min = same refuel event

    This function accumulates all jumps and returns the finalized event when:
    1. A new refuel starts (>10 min since last jump), or
    2. finalize_pending_refuel() is called explicitly

    Returns: Dict with finalized refuel data if a previous refuel was completed, else None
    """
    global _pending_refuels

    now = datetime.now(timezone.utc)
    carrier_id = tanks_config.get_carrier_id(truck_id)

    # Check if there's a pending refuel for this truck
    if truck_id in _pending_refuels:
        pending = _pending_refuels[truck_id]
        time_since_last_jump = (now - pending["last_jump_time"]).total_seconds() / 60

        # If within window, accumulate this jump
        if time_since_last_jump <= CONSECUTIVE_REFUEL_WINDOW_MINUTES:
            pending["gallons"] += gallons
            pending["end_pct"] = after_pct
            pending["last_jump_time"] = now
            logger.info(
                f"[{truck_id}] 📊 Consecutive refuel detected: +{gallons:.1f} gal "
                f"(total: {pending['gallons']:.1f} gal, {pending['start_pct']:.1f}% → {after_pct:.1f}%)"
            )
            return None
        else:
            # Time window expired - finalize previous refuel and start new one
            finalized = finalize_pending_refuel(truck_id, tanks_config)

            # Start new pending refuel
            _pending_refuels[truck_id] = {
                "start_pct": before_pct,
                "end_pct": after_pct,
                "gallons": gallons,
                "start_time": timestamp,
                "last_jump_time": now,
                "carrier_id": carrier_id,
            }
            return finalized
    else:
        # No pending refuel - start new one
        _pending_refuels[truck_id] = {
            "start_pct": before_pct,
            "end_pct": after_pct,
            "gallons": gallons,
            "start_time": timestamp,
            "last_jump_time": now,
            "carrier_id": carrier_id,
        }
        return None


def finalize_pending_refuel(truck_id: str, tanks_config) -> Optional[Dict]:
    """
    🆕 v3.11.5: Finalize a pending refuel and save to database.

    Called when:
    1. A new refuel starts (previous one completed)
    2. Periodically to flush stale pending refuels

    Returns: Dict with refuel data if finalized, else None
    """
    global _pending_refuels

    if truck_id not in _pending_refuels:
        return None

    pending = _pending_refuels.pop(truck_id)

    # Save to database
    save_refuel_to_db(
        truck_id=truck_id,
        gallons_added=pending["gallons"],
        fuel_before_pct=pending["start_pct"],
        fuel_after_pct=pending["end_pct"],
        timestamp=pending["start_time"],
        carrier_id=pending.get("carrier_id", "skylord"),
    )

    return {
        "truck_id": truck_id,
        "gallons": pending["gallons"],
        "start_pct": pending["start_pct"],
        "end_pct": pending["end_pct"],
        "timestamp": pending["start_time"],
    }


def flush_stale_pending_refuels(tanks_config, max_age_minutes: int = 15):
    """
    🆕 v3.11.5: Finalize any pending refuels that haven't seen activity.

    Called periodically to ensure refuels don't stay pending forever.
    """
    global _pending_refuels

    now = datetime.now(timezone.utc)
    stale_trucks = []

    for truck_id, pending in _pending_refuels.items():
        age_minutes = (now - pending["last_jump_time"]).total_seconds() / 60
        if age_minutes > max_age_minutes:
            stale_trucks.append(truck_id)

    for truck_id in stale_trucks:
        finalize_pending_refuel(truck_id, tanks_config)
        logger.debug(f"[{truck_id}] Flushed stale pending refuel")


def save_to_mysql(truck_id: str, row_data: Dict) -> bool:
    """
    Save metrics to MySQL database (parallel to CSV)
    Returns True if successful, False otherwise (fallback to CSV only)

    DEPRECATED: Use save_to_mysql_bulk() for better performance
    This function kept for backward compatibility
    """
    try:
        from tools.database_models import get_session, FuelMetrics

        session = get_session()
        if not session:
            return False

        try:
            # Create FuelMetrics record
            record = FuelMetrics(
                truck_id=truck_id,
                timestamp_utc=row_data.get("timestamp_utc"),
                data_age_min=row_data.get("data_age_min"),
                truck_status=row_data.get("truck_status"),
                estimated_liters=row_data.get("estimated_liters"),
                estimated_gallons=row_data.get("estimated_gallons"),
                estimated_pct=row_data.get("estimated_pct"),
                sensor_pct=row_data.get("sensor_pct"),
                sensor_liters=row_data.get("sensor_liters"),
                sensor_gallons=row_data.get("sensor_gallons"),
                sensor_ema_pct=row_data.get("sensor_ema_pct"),
                ecu_level_pct=row_data.get("ecu_level_pct"),
                model_level_pct=row_data.get("model_level_pct"),
                confidence_indicator=row_data.get("confidence_indicator"),
                consumption_lph=row_data.get("consumption_lph"),
                consumption_gph=row_data.get("consumption_gph"),
                idle_method=row_data.get("idle_method"),
                idle_mode=row_data.get("idle_mode"),
                mpg_current=row_data.get("mpg_current"),
                speed_mph=row_data.get("speed_mph"),
                rpm=row_data.get("rpm"),
                hdop=row_data.get("hdop"),
                altitude_ft=row_data.get("altitude_ft"),
                coolant_temp_f=row_data.get("coolant_temp_f"),
                odometer_mi=row_data.get("odometer_mi"),
                odom_delta_mi=row_data.get("odom_delta_mi"),
                drift_pct=row_data.get("drift_pct"),
                drift_warning=_bool_to_yesno(row_data.get("drift_warning")),
                anchor_detected=_bool_to_yesno(row_data.get("anchor_detected")),
                anchor_type=row_data.get("anchor_type"),
                static_anchors_total=row_data.get("static_anchors_total"),
                micro_anchors_total=row_data.get("micro_anchors_total"),
                refuel_events_total=row_data.get("refuel_events_total"),
                refuel_gallons=row_data.get("refuel_gallons"),
                flags=row_data.get("flags"),
            )

            session.add(record)
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.warning(f"[{truck_id}] MySQL save failed: {e}")
            return False
        finally:
            session.close()

    except ImportError:
        # MySQL models not available, skip silently
        return False
    except Exception as e:
        logger.warning(f"[{truck_id}] MySQL connection failed: {e}")
        return False


def save_to_mysql_bulk(truck_id: str, row_data: Dict) -> bool:
    """
    Save metrics to MySQL using bulk inserts (better performance)
    Accumulates records and commits in batches instead of individual commits

    Performance: 39 commits/cycle → 1-2 commits/cycle

    Returns True if record queued successfully, False if error
    """
    try:
        from bulk_mysql_handler import save_to_mysql_bulk as bulk_save

        result = bulk_save(truck_id, row_data)

        # 🆕 v3.9.8: Update fuel cache after successful write for refuel detection
        if result:
            sensor_pct = row_data.get("sensor_pct")
            estimated_pct = row_data.get("estimated_pct")
            if sensor_pct is not None:
                update_fuel_cache_after_write(
                    truck_id, sensor_pct, estimated_pct or 0.0
                )

        return result
    except Exception as e:
        logger.warning(
            f"[{truck_id}] Bulk MySQL save failed, falling back to individual: {e}"
        )
        return save_to_mysql(truck_id, row_data)


# ============================================================================
# CSV REPORTER
# ============================================================================
class CSVReporter:
    """CSV reporter for fuel copilot data"""

    def __init__(self, truck_id: str):
        self.truck_id = truck_id
        self.csv_file = None
        self.csv_writer = None
        self.current_date = None
        self._initialize_csv()

    def _initialize_csv(self):
        """Initialize CSV file with headers"""
        # Use local timezone (EST/EDT) for file naming to match business day
        today = datetime.now().date()
        # Check if we need a new file (new day)
        if self.current_date != today:
            # Close previous file if open
            if self.csv_file:
                self.csv_file.close()
            # Ensure directories exist
            ensure_directories()
            # Create new file in csv_reports directory
            filename = os.path.join(
                CSV_REPORTS_DIR, f"fuel_report_{self.truck_id}_{today}.csv"
            )
            file_exists = os.path.exists(filename)
            self.csv_file = open(filename, "a", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.current_date = today
            print(f"📁 CSV report file: {filename}")
            # Write headers if new file
            if not file_exists:
                headers = [
                    "timestamp_utc",
                    "data_age_min",
                    "truck_status",  # 🆕 MOVING/STOPPED/OFFLINE
                    "estimated_liters",
                    "estimated_gallons",  # 🆕 Gallons
                    "estimated_pct",
                    "sensor_pct",  # 🆕 Sensor in % directly
                    "sensor_liters",  # 🆕 Sensor in L
                    "sensor_gallons",  # 🆕 Sensor in Gallons
                    "sensor_ema_pct",
                    "ecu_level_pct",  # 🆕 ECU level (sensor_ema_pct)
                    "model_level_pct",  # 🆕 Model level (estimated_pct)
                    "confidence_indicator",  # 🆕 OK/SOSPECHOSO/SIN SENSOR
                    "consumption_lph",
                    "consumption_gph",  # 🆕 Gallons Per Hour (for idle monitoring)
                    "idle_method",  # 🆕 IDLE calculation method (SENSOR_FUEL_RATE/CALCULATED_DELTA/FALLBACK_CONSENSUS/NOT_IDLE)
                    "idle_mode",  # 🆕 v3.0.6: Auto-detected mode (NORMAL/REEFER_ACTIVE/HIGH_LOAD/REEFER_CONTINUOUS/ENGINE_OFF)
                    "mpg_current",  # 🆕 v3.0.7-BETA: Miles Per Gallon (⚠️ VALIDAR 7 días antes de confiar 100%)
                    "speed_mph",
                    "rpm",
                    "hdop",
                    "altitude_ft",
                    "coolant_temp_f",
                    "odometer_mi",
                    "odom_delta_mi",  # 🆕 Odometer change
                    "drift_pct",
                    "drift_warning",
                    "anchor_detected",
                    "anchor_type",
                    "static_anchors_total",
                    "micro_anchors_total",
                    "refuel_events_total",
                    "refuel_gallons",  # 🆕 Gallons added in last refuel
                    "flags",
                ]
                self.csv_writer.writerow(headers)
                self.csv_file.flush()
                logger.info(f"📊 CSV Report initialized: {filename}")

    def write_row(
        self,
        timestamp: datetime,
        data_age_min: float,
        truck_status: TruckStatus,  # 🆕
        estimate: Optional[Dict],
        sensors: Dict,
        odom_delta: float,  # 🆕
        drift_pct: float,
        drift_warning: bool,
        anchor_detected: bool,
        anchor_type: Optional[str],
        anchor_stats: Dict,
        flags: Dict,
        ema_pct: Optional[float],
        tanks_config: TanksConfig,  # NEW
        truck_id: str,  # NEW
        mpg_current: Optional[float] = None,  # 🆕 MPG
        refuel_gallons: float = 0.0,  # 🆕 Gallons added in refuel
        idle_method: str = "NOT_IDLE",  # 🆕 IDLE calculation method
        idle_mode: str = "ENGINE_OFF",  # 🆕 v3.0.6: Auto-detected mode
        epoch_time: int = 0,  # 🆕 Epoch time from Wialon
    ):
        """Write a data row to CSV"""
        # Check if we need a new file (new day)
        self._initialize_csv()
        # Default drift_pct to 0.0 if None for formatting
        drift_pct = drift_pct if drift_pct is not None else 0.0
        # Convert UTC timestamp to EST for business hours alignment
        timestamp_est = timestamp.astimezone(ZoneInfo("America/New_York"))
        row = [
            timestamp_est.strftime("%Y-%m-%d %H:%M:%S"),
            f"{data_age_min:.1f}",
            truck_status.value,  # 🆕
            f"{estimate['level_liters']:.2f}" if estimate else "",
            (
                f"{estimate['level_liters'] * LITERS_TO_GALLONS:.2f}"
                if estimate
                else ""
            ),  # 🆕 Gallons
            f"{estimate['level_pct']:.2f}" if estimate else "",
            (
                f"{sensors.get('fuel_lvl'):.2f}"
                if sensors.get("fuel_lvl") is not None
                else ""
            ),  # 🆕 % directly
            (
                f"{tanks_config.get_capacity(truck_id) * sensors.get('fuel_lvl') / 100.0:.2f}"
                if sensors.get("fuel_lvl") is not None
                else ""
            ),  # 🆕 L direct (no LUT)
            (
                f"{tanks_config.get_capacity(truck_id) * sensors.get('fuel_lvl') / 100.0 * LITERS_TO_GALLONS:.2f}"
                if sensors.get("fuel_lvl") is not None
                else ""
            ),  # 🆕 Gallons direct (no LUT)
            f"{ema_pct:.2f}" if ema_pct is not None else "",
            f"{ema_pct:.2f}" if ema_pct is not None else "",  # ecu_level_pct
            f"{estimate['level_pct']:.2f}" if estimate else "",  # model_level_pct
            (  # confidence_indicator - FIXED with parentheses
                "SIN SENSOR"
                if "fuel_lvl" not in sensors or sensors.get("fuel_lvl") is None
                else (
                    "SOSPECHOSO"
                    if (drift_pct is not None and drift_pct > 10.0)
                    or (drift_pct is None and "fuel_lvl" in sensors)
                    else "OK"
                )
            ),
            f"{estimate['consumption_lph']:.2f}" if estimate else "",
            (
                f"{estimate['consumption_lph'] * 0.264172:.2f}" if estimate else ""
            ),  # 🆕 Convert L/h to gal/h
            idle_method,  # 🆕 IDLE calculation method
            idle_mode,  # 🆕 v3.0.6: Auto-detected mode
            f"{mpg_current:.2f}" if mpg_current is not None else "",  # 🆕 MPG
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
            f"{odom_delta:.3f}",  # 🆕
            f"{drift_pct:.2f}",
            "YES" if drift_warning else "NO",
            "YES" if anchor_detected else "NO",
            anchor_type if anchor_type else "",
            anchor_stats["static_anchors"],
            anchor_stats["micro_anchors"],
            anchor_stats["refuel_events"],
            f"{refuel_gallons:.1f}" if refuel_gallons > 0 else "",  # 🆕 Gallons added
            "|".join([k for k, v in flags.items() if v]),
        ]
        # Write and flush to CSV
        if self.csv_writer is None or self.csv_file is None:
            logger.error("CSV writer not initialized - skipping write")
            return
        self.csv_writer.writerow(row)
        self.csv_file.flush()

        # 🆕 ALSO save to MySQL (parallel write with CSV fallback)
        mysql_save_success = False
        try:
            # 🔧 FIX: Convert PARKED → OFFLINE for MySQL compatibility
            # MySQL ENUM only has MOVING/STOPPED/OFFLINE, not PARKED yet
            # PARKED (engine off >30min) maps better to OFFLINE than STOPPED
            mysql_truck_status = (
                truck_status.value if truck_status.value != "PARKED" else "OFFLINE"
            )

            # 🔧 v3.11.4 TIMEZONE FIX: Use epoch_time as source of truth
            # Wialon's measure_datetime is in CST, which caused 5-6 hour offsets
            # epoch_time is always correct (Unix timestamp = UTC)
            # Convert epoch directly to UTC datetime for MySQL
            from datetime import datetime, timezone

            timestamp_utc_real = datetime.fromtimestamp(epoch_time, tz=timezone.utc)
            timestamp_naive = timestamp_utc_real.replace(
                tzinfo=None
            )  # MySQL datetime has no tz

            mysql_data = {
                # 🆕 v3.10.8: carrier_id for multi-tenant support
                "carrier_id": tanks_config.get_carrier_id(truck_id),
                "timestamp_utc": timestamp_naive,  # 🔧 v3.11.4: Now ACTUALLY UTC from epoch!
                "epoch_time": epoch_time,  # 🆕 Store raw epoch for consistency
                "data_age_min": data_age_min,
                "truck_status": mysql_truck_status,
                "estimated_liters": estimate["level_liters"] if estimate else None,
                "estimated_gallons": (
                    estimate["level_liters"] * LITERS_TO_GALLONS if estimate else None
                ),
                "estimated_pct": estimate["level_pct"] if estimate else None,
                "sensor_pct": sensors.get("fuel_lvl"),
                "sensor_liters": (
                    tanks_config.get_capacity(truck_id)
                    * sensors.get("fuel_lvl")
                    / 100.0
                    if sensors.get("fuel_lvl") is not None
                    else None
                ),
                "sensor_gallons": (
                    tanks_config.get_capacity(truck_id)
                    * sensors.get("fuel_lvl")
                    / 100.0
                    * LITERS_TO_GALLONS
                    if sensors.get("fuel_lvl") is not None
                    else None
                ),
                "sensor_ema_pct": ema_pct,
                "ecu_level_pct": ema_pct,
                "model_level_pct": estimate["level_pct"] if estimate else None,
                "confidence_indicator": (
                    "SIN SENSOR"
                    if "fuel_lvl" not in sensors or sensors.get("fuel_lvl") is None
                    else (
                        "SOSPECHOSO"
                        if (drift_pct is not None and drift_pct > 10.0)
                        or (drift_pct is None and "fuel_lvl" in sensors)
                        else "OK"
                    )
                ),
                # 🔧 FIX: Cap consumption to realistic max (50 L/h = 13.2 GPH)
                # Prevents sensor glitches like 120 L/h from being saved
                "consumption_lph": (
                    min(estimate["consumption_lph"], 50.0)
                    if estimate and estimate["consumption_lph"]
                    else None
                ),
                "consumption_gph": (
                    min(estimate["consumption_lph"] * 0.264172, 13.2)
                    if estimate and estimate["consumption_lph"]
                    else None
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
                "static_anchors_total": anchor_stats["static_anchors"],
                "micro_anchors_total": anchor_stats["micro_anchors"],
                "refuel_events_total": anchor_stats["refuel_events"],
                "refuel_gallons": refuel_gallons if refuel_gallons > 0 else None,
                "flags": "|".join([k for k, v in flags.items() if v]),
            }
            # 🚀 USE BULK INSERT FOR BETTER PERFORMANCE (39 commits → 1-2 commits/cycle)
            mysql_save_success = save_to_mysql_bulk(truck_id, mysql_data)
            if not mysql_save_success:
                logger.warning(f"[{truck_id}] ⚠️ MySQL save failed, data in CSV only")
        except Exception as e:
            logger.error(f"[{truck_id}] ❌ MySQL save error: {e}")

    def close(self):
        """Close CSV file"""
        if self.csv_file:
            self.csv_file.close()
            logger.info("📊 CSV Report closed")


# ============================================================================
# HEALTH SCORE & DIAGNOSTICS
# ============================================================================


def calculate_health_score(
    truck_id: str,
    drift_pct: Optional[float],
    data_age_min: Optional[float],
    sensor_readings: List[float],
    is_moving: bool,
    has_fuel_sensor: bool,
    hdop: Optional[float] = None,
    truck_status: Optional[TruckStatus] = None,
    rpm: Optional[float] = None,
) -> TruckHealthScore:
    """
    Calculate health score (0-100) and diagnostics for a truck

    Health Score Breakdown:
    - 100: Perfect (sensor good, low drift, fresh data, GPS good)
    - 75-99: Good (minor issues)
    - 50-74: Warning (needs attention)
    - 0-49: Critical (urgent action required)
    """

    health = 100.0
    issues = []

    # Diagnostic flags
    sensor_frozen = False
    sensor_noisy = False
    sensor_disconnected = False
    high_drift = False
    old_data = False
    gps_poor = False

    # 1. Check sensor availability (25 points)
    # 🆕 Don't penalize if truck is OFFLINE OR engine is OFF (sentido común)
    # Engine OFF detection: rpm is None or rpm == 0
    engine_off = rpm is None or rpm == 0
    if not has_fuel_sensor and truck_status != TruckStatus.OFFLINE and not engine_off:
        health -= 25
        sensor_disconnected = True
        issues.append("No fuel sensor data")

    # 2. Check data freshness (20 points)
    if data_age_min is not None:
        if data_age_min > 240:  # > 4 hours
            health -= 20
            old_data = True
            issues.append(f"Stale data ({data_age_min:.0f} min old)")
        elif data_age_min > 120:  # > 2 hours
            health -= 10
            old_data = True
            issues.append(f"Old data ({data_age_min:.0f} min)")

    # 3. Check drift (30 points) - IMPROVED with more granular categories
    if drift_pct is not None:
        abs_drift = abs(drift_pct)
        if abs_drift > 20:
            health -= 30
            high_drift = True
            issues.append(f"CRITICAL drift ({drift_pct:+.1f}%) - possible theft/leak")
        elif abs_drift > 15:
            health -= 25
            high_drift = True
            issues.append(f"Severe drift ({drift_pct:+.1f}%) - investigate immediately")
        elif abs_drift > 10:
            health -= 20
            high_drift = True
            issues.append(f"High drift ({drift_pct:+.1f}%) - needs attention")
        elif abs_drift > 7:
            health -= 15
            issues.append(f"Elevated drift ({drift_pct:+.1f}%) - monitor closely")
        elif abs_drift > 5:
            health -= 10
            issues.append(f"Moderate drift ({drift_pct:+.1f}%)")
        elif abs_drift > 3:
            health -= 5
            issues.append(f"Minor drift ({drift_pct:+.1f}%)")
        # else: drift <= 3% is normal, no penalty

    # 4. Check sensor behavior (15 points)
    if len(sensor_readings) >= 10:
        # Check for frozen sensor (same value for extended period)
        unique_values = len(set(sensor_readings[-10:]))
        if unique_values <= 2 and is_moving:
            health -= 15
            sensor_frozen = True
            issues.append("Sensor frozen (no variation)")

        # Check for noisy sensor (high variance)
        if len(sensor_readings) >= 20:
            variance = np.var(sensor_readings[-20:])
            if variance > 100:  # > 10% std deviation
                health -= 10
                sensor_noisy = True
                issues.append("Sensor very noisy")

    # 5. Check GPS quality (10 points)
    if hdop is not None and hdop > 2.0:
        health -= 10
        gps_poor = True
        issues.append(f"Poor GPS (HDOP={hdop:.1f})")

    # Clamp to 0-100
    health = max(0, min(100, health))

    # Determine status
    if health >= 90:
        status = "EXCELLENT"
    elif health >= 75:
        status = "GOOD"
    elif health >= 50:
        status = "WARNING"
    else:
        status = "CRITICAL"

    # Calculate diagnostic stats
    drift_current = drift_pct
    sensor_variance = (
        np.var(sensor_readings[-20:]) if len(sensor_readings) >= 20 else None
    )
    last_change = (
        abs(sensor_readings[-1] - sensor_readings[-2])
        if len(sensor_readings) >= 2
        else None
    )

    return TruckHealthScore(
        truck_id=truck_id,
        health_score=health,
        status=status,
        issues=issues if issues else ["All systems normal"],
        sensor_frozen=sensor_frozen,
        sensor_noisy=sensor_noisy,
        sensor_disconnected=sensor_disconnected,
        high_drift=high_drift,
        old_data=old_data,
        gps_poor=gps_poor,
        drift_current=drift_current,
        data_age_minutes=data_age_min,
        sensor_variance_24h=(
            float(sensor_variance) if sensor_variance is not None else None
        ),
        last_sensor_change=last_change,
    )


# ============================================================================
# MYSQL WRITER (NEW - Parallel to CSV)
# ============================================================================
# ============================================================================
# FUEL ESTIMATOR (Reconstructed)
# ============================================================================
class FuelEstimator:
    """
    Kalman Filter for Fuel Level Estimation and Drift Detection
    """

    def __init__(
        self,
        truck_id: str,
        capacity_liters: float,
        config: Dict,
        tanks_config: Optional[TanksConfig] = None,
    ):
        self.truck_id = truck_id
        self.capacity_liters = capacity_liters
        self.config = config

        # State
        self.initialized = False
        self.level_liters = 0.0
        self.level_pct = 0.0
        self.consumption_lph = 0.0
        self.last_update_time = None
        self.last_fuel_lvl_pct = None

        # Refuel tracking
        self.recent_refuel = False
        self.refuel_volume_factor = 1.0
        if tanks_config:
            self.refuel_volume_factor = tanks_config.get_refuel_factor(
                truck_id, config.get("refuel_volume_factor", 1.0)
            )

        # Kalman parameters - OPTIMIZED for filtering sensor noise
        self.Q_r = config.get(
            "Q_r", 0.1
        )  # Process noise (low = trust consumption model)
        self.Q_L_moving = config.get(
            "Q_L_moving", 4.0
        )  # High when moving (slosh/accel)
        self.Q_L_static = config.get("Q_L_static", 1.0)  # Lower when stopped
        self.Q_L = self.Q_L_moving  # Default to moving (conservative)
        self.P = 1.0  # Error covariance
        self.is_moving = True  # Track movement state

        # 🆕 History for adaptive noise calculation
        self.speed_history = []
        self.altitude_history = []
        self.last_speed = None
        self.last_altitude = None
        self.last_noise_timestamp = None

        # 🆕 ECU FUEL COUNTER TRACKING (Total Fuel Used)
        # This allows EXACT consumption calculation instead of estimates
        self.last_total_fuel_used = None  # ECU cumulative counter (gallons)
        self.ecu_consumption_available = False  # True if we can use ECU data
        self.ecu_failure_count = 0  # Consecutive failures
        self.ecu_last_success_time = None  # Last successful ECU reading
        self.ecu_degraded = False  # True if ECU is unreliable

        # Drift tracking
        self.drift_pct = 0.0
        self.drift_warning = False

        # Initialize L (internal state for Kalman)
        self.L = None
        self.P_L = 20.0  # Initial uncertainty

    def initialize(self, sensor_pct: float):
        """Initialize the filter with a sensor reading"""
        self.level_pct = sensor_pct
        self.level_liters = (sensor_pct / 100.0) * self.capacity_liters
        self.L = self.level_liters
        self.initialized = True
        self.last_fuel_lvl_pct = sensor_pct
        self.P = 1.0

    def check_emergency_reset(
        self, sensor_pct: float, time_gap_hours: float, truck_status: str = "UNKNOWN"
    ) -> bool:
        """
        🆕 v3.0.9-CRITICAL: Emergency reset for high drift after long offline gaps

        Reset Kalman filter when BOTH conditions are met:
        1. Time gap > 2 hours (truck was offline for a long time)
        2. Drift > 30% (estimate very far from sensor)

        This prevents accumulated drift of 30-54% after long offline periods.
        """
        if sensor_pct is None or not self.initialized or self.L is None:
            return False

        # Calculate current drift
        estimated_pct = (self.L / self.capacity_liters) * 100
        drift_pct = abs(estimated_pct - sensor_pct)

        # 🔴 CRITERIA FOR EMERGENCY RESET:
        EMERGENCY_GAP_THRESHOLD = 2.0  # hours
        EMERGENCY_DRIFT_THRESHOLD = 30.0  # percent

        if (
            time_gap_hours > EMERGENCY_GAP_THRESHOLD
            and drift_pct > EMERGENCY_DRIFT_THRESHOLD
        ):
            logger.warning(
                f"[{self.truck_id}] 🔴 EMERGENCY RESET TRIGGERED:\n"
                f"   Status: {truck_status}\n"
                f"   Time gap: {time_gap_hours:.1f} hours (>{EMERGENCY_GAP_THRESHOLD}h threshold)\n"
                f"   Drift: {drift_pct:.1f}% (>{EMERGENCY_DRIFT_THRESHOLD}% threshold)\n"
                f"   Estimated: {estimated_pct:.1f}%\n"
                f"   Sensor: {sensor_pct:.1f}%\n"
                f"   → Resetting Kalman to sensor value"
            )

            # Reset to sensor value
            self.initialize(sensor_pct)

            # Moderate uncertainty after reset
            self.P_L = 20.0

            logger.info(
                f"[{self.truck_id}] ✅ Emergency reset complete: "
                f"L={self.L:.1f}L ({sensor_pct:.1f}%), P_L={self.P_L:.1f}"
            )

            return True

        return False

    def auto_resync(self, sensor_pct: float):
        """
        Auto-resync if drift is EXTREMELY high (>15%)

        🆕 IMPORTANT: Normal drift (1-10%) is EXPECTED and HEALTHY!
        It means the Kalman filter is doing its job filtering sensor noise.

        Only resync when:
        1. Drift > 15% normally (something is very wrong)
        2. Drift > 30% after refuel (give slosh time to settle)
        """
        if not self.initialized or sensor_pct is None or self.L is None:
            return

        estimated_pct = (self.L / self.capacity_liters) * 100
        drift_pct = abs(estimated_pct - sensor_pct)

        # 🆕 RAISED THRESHOLD from 10% to 15% to preserve Kalman filtering
        # Normal sensor noise can cause 3-8% "drift" which is actually the filter working!
        RESYNC_THRESHOLD_NORMAL = 15.0  # Was 10.0
        RESYNC_THRESHOLD_REFUEL = 30.0  # After refuel, allow more drift

        if drift_pct > RESYNC_THRESHOLD_NORMAL and (
            not self.recent_refuel or drift_pct > RESYNC_THRESHOLD_REFUEL
        ):
            logger.warning(
                f"[{self.truck_id}] ⚠️ EXTREME DRIFT ({drift_pct:.1f}% > {RESYNC_THRESHOLD_NORMAL}%) - Auto-resyncing to sensor"
            )
            self.initialize(sensor_pct)

    def predict(self, dt_hours: float, consumption_lph: float):
        """Predict next state based on consumption"""
        if not self.initialized:
            return

        # x_pred = x - u * dt
        self.level_liters -= consumption_lph * dt_hours
        self.level_pct = (self.level_liters / self.capacity_liters) * 100.0
        self.consumption_lph = consumption_lph

        # Update internal L state
        if self.L is not None:
            self.L -= consumption_lph * dt_hours

        # P_pred = P + Q
        self.P += self.Q_r * dt_hours

    def calculate_ecu_consumption(
        self,
        total_fuel_used: Optional[float],
        dt_hours: float,
        fuel_rate_lph: Optional[float] = None,  # For cross-validation
    ) -> Optional[float]:
        """
        🆕 ECU-BASED EXACT CONSUMPTION CALCULATION (ROBUST VERSION)

        Uses the ECU's "Total Fuel Used" cumulative counter to calculate
        EXACT fuel consumption instead of estimating from speed/load.

        The ECU counter is the most accurate source because:
        1. It's measured by the engine computer directly (J1939 SPN 250)
        2. Accounts for ACTUAL injector fuel delivery
        3. No estimation errors from MPG assumptions
        4. Works regardless of driving conditions

        VALIDATION LAYERS:
        1. Reset detection (new < old)
        2. Time delta minimum (10 seconds)
        3. Physical range check (0.1 - 50 GPH for Class 8)
        4. Cross-check with fuel_rate sensor (warn if >5 GPH discrepancy)
        5. Failure counting for intelligent fallback

        Args:
            total_fuel_used: ECU cumulative fuel counter (gallons)
            dt_hours: Time delta in hours
            fuel_rate_lph: Optional fuel rate sensor for cross-validation

        Returns:
            Consumption rate in liters/hour, or None if ECU data unavailable/invalid
        """
        # Physical limits for Class 8 trucks
        MAX_CONSUMPTION_GPH = 50.0  # Max realistic (heavy load, uphill)
        MIN_TIME_DELTA_HOURS = 10 / 3600  # 10 seconds minimum

        # Check if ECU is degraded (too many failures)
        if self.ecu_degraded:
            # Check if we should try to recover (every 10 minutes)
            if self.ecu_last_success_time:
                time_since = (
                    datetime.now(timezone.utc) - self.ecu_last_success_time
                ).total_seconds()
                if time_since > 600:  # Try recovery after 10 min
                    self.ecu_degraded = False
                    self.ecu_failure_count = 0
                    logger.info(
                        f"[{self.truck_id}] 🔄 ECU recovery attempt after {time_since/60:.1f} min"
                    )
                else:
                    return None
            else:
                return None

        # Validation 1: Data availability
        if total_fuel_used is None:
            self._record_ecu_failure("no_data")
            return None

        # Validation 2: Time delta minimum
        if dt_hours < MIN_TIME_DELTA_HOURS:
            # Don't count as failure - just skip this reading
            return None

        # First reading - initialize counter
        if self.last_total_fuel_used is None:
            self.last_total_fuel_used = total_fuel_used
            self.ecu_consumption_available = False
            return None

        # Calculate delta (gallons consumed since last reading)
        fuel_delta_gal = total_fuel_used - self.last_total_fuel_used

        # Validation 3: Reset detection
        if fuel_delta_gal < 0:
            logger.warning(
                f"[{self.truck_id}] ⚠️ ECU counter reset detected "
                f"({self.last_total_fuel_used:.2f} → {total_fuel_used:.2f}). Reinitializing."
            )
            self.last_total_fuel_used = total_fuel_used
            self._record_ecu_failure("reset")
            return None

        # Calculate consumption rate in GPH
        consumption_gph = fuel_delta_gal / dt_hours if dt_hours > 0 else 0

        # Validation 4: Physical range check
        if consumption_gph > MAX_CONSUMPTION_GPH:
            logger.warning(
                f"[{self.truck_id}] ⚠️ ECU consumption unrealistic: {consumption_gph:.1f} GPH > {MAX_CONSUMPTION_GPH} max"
            )
            self.last_total_fuel_used = total_fuel_used
            self._record_ecu_failure("high_consumption")
            return None

        # Note: Allow 0 consumption (engine off or idle with very low rate)
        # but warn if it's been 0 for too long

        # Validation 5: Cross-check with fuel_rate sensor (if available)
        if fuel_rate_lph is not None and fuel_rate_lph > 0:
            fuel_rate_gph = fuel_rate_lph / 3.78541
            discrepancy_gph = abs(consumption_gph - fuel_rate_gph)

            if discrepancy_gph > 5.0:  # >5 GPH difference is suspicious
                logger.warning(
                    f"[{self.truck_id}] ⚠️ ECU vs FuelRate discrepancy: "
                    f"ECU={consumption_gph:.1f} GPH, Sensor={fuel_rate_gph:.1f} GPH, Δ={discrepancy_gph:.1f}"
                )
                # Don't fail - just warn. ECU is usually more accurate.

        # Update counter
        self.last_total_fuel_used = total_fuel_used

        # Convert to liters per hour
        consumption_lph = consumption_gph * 3.78541

        # Record success
        self._record_ecu_success()

        # Log periodically for monitoring
        if not hasattr(self, "_ecu_log_counter"):
            self._ecu_log_counter = 0
        self._ecu_log_counter += 1

        if self._ecu_log_counter % 20 == 0:  # Log every ~5 minutes
            status = "✅" if not self.ecu_degraded else "⚠️"
            logger.info(
                f"⛽ [{self.truck_id}] {status} ECU: {fuel_delta_gal:.3f} gal in {dt_hours*60:.1f}min "
                f"= {consumption_gph:.2f} GPH ({consumption_lph:.1f} L/h)"
            )

        return consumption_lph

    def _record_ecu_failure(self, reason: str):
        """Track ECU failures for intelligent fallback"""
        self.ecu_failure_count += 1
        self.ecu_consumption_available = False

        if self.ecu_failure_count >= 5:
            if not self.ecu_degraded:
                logger.warning(
                    f"[{self.truck_id}] 🔴 ECU DEGRADED after {self.ecu_failure_count} failures "
                    f"(last: {reason}). Falling back to fuel_rate/idle."
                )
            self.ecu_degraded = True

    def _record_ecu_success(self):
        """Track ECU success to reset failure counter"""
        self.ecu_failure_count = 0
        self.ecu_consumption_available = True
        self.ecu_last_success_time = datetime.now(timezone.utc)

        if self.ecu_degraded:
            logger.info(f"[{self.truck_id}] ✅ ECU recovered - back to primary source")
            self.ecu_degraded = False

    def calculate_adaptive_noise(
        self,
        speed: Optional[float],
        altitude: Optional[float],
        timestamp: datetime,
        engine_load: Optional[float] = None,  # 🆕 Engine load % from ECU
    ) -> float:
        """
        🆕 INTELLIGENT ADAPTIVE NOISE - Detects real physical conditions:

        1. PENDIENTE (Grade/Incline):
           - Calculated from altitude delta / distance traveled
           - Fuel sloshes forward going uphill, backward going downhill
           - >3% grade = significant effect on sensor

        2. ACELERACIÓN (Acceleration):
           - Calculated from speed delta / time delta
           - Rapid accel/decel causes fuel to slosh fore/aft
           - >2 mph/s = significant effect

        3. SLOSH (Fuel Sloshing):
           - Inferred from speed variance over last readings
           - Stop-and-go traffic = high slosh
           - Steady cruise = low slosh

        4. ENGINE LOAD (🆕):
           - Direct from ECU - indicates actual engine effort
           - High load = climbing, accelerating, heavy cargo
           - More accurate than inferring from altitude

        Returns Q_L (measurement noise) - higher = trust sensor less
        """
        # Base noise levels
        Q_L_BASE = 1.0  # Baseline (static, level road)
        Q_L_MOVING = 2.0  # Moving on flat road
        Q_L_GRADE = 3.0  # On incline/decline
        Q_L_ACCEL = 4.0  # Accelerating/braking
        Q_L_SLOSH = 5.0  # High slosh (stop-and-go)
        Q_L_MAX = 6.0  # Maximum noise

        noise_factors = []

        # --- Factor 1: Basic Movement ---
        if speed is None or speed < 1.0:
            # Static - most reliable readings
            self.is_moving = False
            return Q_L_BASE

        self.is_moving = True
        noise_factors.append(("moving", Q_L_MOVING))

        # --- Factor 2: GRADE/INCLINE Detection ---
        if altitude is not None and self.last_altitude is not None and speed > 5:
            # Calculate grade from altitude change
            # Need distance traveled to calculate grade %
            time_delta_h = 15 / 3600  # Assume 15s interval
            distance_mi = speed * time_delta_h  # Speed in mph
            distance_ft = distance_mi * 5280

            if distance_ft > 10:  # Minimum distance for meaningful calculation
                altitude_delta = altitude - self.last_altitude  # In feet
                grade_pct = (altitude_delta / distance_ft) * 100

                # Grade effects on fuel sensor:
                # >3% grade = fuel sloshes noticeably
                # >6% grade = significant slosh
                # >10% grade = very unreliable
                if abs(grade_pct) > 10:
                    noise_factors.append(("steep_grade", Q_L_MAX))
                elif abs(grade_pct) > 6:
                    noise_factors.append(("medium_grade", Q_L_GRADE + 1.5))
                elif abs(grade_pct) > 3:
                    noise_factors.append(("mild_grade", Q_L_GRADE))

        # --- Factor 3: ACCELERATION Detection ---
        if speed is not None and self.last_speed is not None:
            time_delta_s = 15  # Assume 15s interval
            accel = abs(speed - self.last_speed) / time_delta_s  # mph/s

            # Acceleration effects on fuel sensor:
            # >1 mph/s = mild slosh
            # >2 mph/s = moderate slosh
            # >3 mph/s = severe slosh (hard braking/accel)
            if accel > 3:
                noise_factors.append(("hard_accel", Q_L_SLOSH + 1.0))
            elif accel > 2:
                noise_factors.append(("moderate_accel", Q_L_ACCEL))
            elif accel > 1:
                noise_factors.append(("mild_accel", Q_L_ACCEL - 1.0))

        # --- Factor 4: SPEED VARIANCE (Slosh from stop-and-go) ---
        self.speed_history.append(speed)
        if len(self.speed_history) > 10:
            self.speed_history.pop(0)

        if len(self.speed_history) >= 5:
            import numpy as np

            speed_std = np.std(self.speed_history)
            speed_mean = np.mean(self.speed_history)

            # High variance relative to mean = stop-and-go traffic
            if speed_mean > 5:
                cv = speed_std / speed_mean  # Coefficient of variation
                if cv > 0.5:
                    noise_factors.append(("stop_and_go", Q_L_SLOSH))
                elif cv > 0.3:
                    noise_factors.append(("variable_speed", Q_L_GRADE))

        # --- Factor 5: HIGH SPEED (more wind/vibration effects) ---
        if speed > 70:
            noise_factors.append(("high_speed", Q_L_MOVING + 0.5))

        # --- Factor 6: ENGINE LOAD (🆕 direct from ECU) ---
        # High engine load = climbing, heavy acceleration, heavy cargo
        # This is MORE ACCURATE than inferring from altitude
        if engine_load is not None:
            if engine_load > 80:
                noise_factors.append(("high_engine_load", Q_L_SLOSH))
            elif engine_load > 60:
                noise_factors.append(("medium_engine_load", Q_L_ACCEL))
            elif engine_load > 40:
                noise_factors.append(("mild_engine_load", Q_L_GRADE))

        # Update history for next iteration
        self.last_speed = speed
        self.last_altitude = altitude
        self.last_timestamp = timestamp

        # Calculate final Q_L as max of all factors (worst case)
        if noise_factors:
            final_Q_L = max(f[1] for f in noise_factors)
            # Log significant noise factors (when above basic moving threshold)
            if final_Q_L > Q_L_MOVING:
                factors_str = ", ".join(
                    f"{f[0]}:{f[1]:.1f}" for f in noise_factors if f[1] > Q_L_MOVING
                )
                if factors_str:
                    logger.info(
                        f"🔊 [{self.truck_id}] Adaptive Q_L={final_Q_L:.1f} ({factors_str})"
                    )
            return min(final_Q_L, Q_L_MAX)

        return Q_L_MOVING

    def set_movement_state(self, is_moving: bool):
        """
        🆕 Adaptive Kalman: Adjust measurement noise based on movement state
        - Moving: High noise (slosh, acceleration, incline) → trust sensor less
        - Static: Low noise (sensor more stable) → trust sensor more

        NOTE: Prefer using calculate_adaptive_noise() for intelligent adjustment
        """
        self.is_moving = is_moving
        if is_moving:
            self.Q_L = self.Q_L_moving
        else:
            self.Q_L = self.Q_L_static

    def update(self, measured_pct: float):
        """Update state with measurement using adaptive Kalman gain"""
        measured_liters = (measured_pct / 100.0) * self.capacity_liters

        # Update timestamp
        self.last_update_time = datetime.now(timezone.utc)

        if not self.initialized:
            self.initialize(measured_pct)
            return

        # Kalman Gain with ADAPTIVE measurement noise
        # K = P / (P + R) where R varies based on movement
        R = self.Q_L  # Adaptive: high when moving, low when static
        K = self.P / (self.P + R)

        # Clamp K to prevent over-correction (max 30% adjustment per reading)
        K = min(K, 0.30)

        # Update state
        # x = x_pred + K * (z - x_pred)
        innovation = measured_liters - self.level_liters
        self.level_liters += K * innovation
        self.level_pct = (self.level_liters / self.capacity_liters) * 100.0

        # Update internal L state
        if self.L is not None:
            self.L = self.level_liters

        # Update covariance
        # P = (1 - K) * P
        self.P = (1 - K) * self.P

        # Calculate drift (for monitoring, not for reset)
        self.drift_pct = self.level_pct - measured_pct
        self.drift_warning = abs(self.drift_pct) > self.config.get("max_drift_pct", 5.0)

        self.last_fuel_lvl_pct = measured_pct

        # 🆕 Only auto-resync on EXTREME drift (>15%) to preserve filtering
        # Normal drift is expected and healthy - it means we're filtering noise
        self.auto_resync(measured_pct)

    def get_estimate(self) -> Dict:
        return {
            "level_liters": self.level_liters,
            "level_pct": self.level_pct,
            "consumption_lph": self.consumption_lph,
            "drift_pct": self.drift_pct,
            "drift_warning": self.drift_warning,
            "kalman_gain": self.P / (self.P + self.Q_L),  # 🆕 Expose K for debugging
            "is_moving": self.is_moving,
            "ecu_consumption_available": self.ecu_consumption_available,  # 🆕 ECU data status
        }

    def apply_refuel_reset(
        self, new_fuel_pct: float, timestamp: datetime, gallons_added: float
    ):
        """
        🆕 v3.11.2: Reset estimator state after refuel detection.

        Called when a gap-based or sensor-based refuel is detected.
        Resets the Kalman filter to trust the new sensor reading.

        Args:
            new_fuel_pct: Current fuel level % from sensor (after refuel)
            timestamp: Timestamp of the refuel detection
            gallons_added: Estimated gallons added during refuel
        """
        # Convert to liters for internal state
        gallons_to_liters = 3.78541
        liters_added = gallons_added * gallons_to_liters

        # Reset to sensor reading (trust the new level)
        self.level_pct = new_fuel_pct
        self.level_liters = (new_fuel_pct / 100.0) * self.capacity_liters
        self.L = self.level_liters
        self.last_fuel_lvl_pct = new_fuel_pct

        # Mark as recently refueled (affects drift thresholds)
        self.recent_refuel = True
        self.last_update_time = timestamp

        # Reset drift tracking (clean slate after refuel)
        self.drift_pct = 0.0
        self.drift_warning = False

        # Reset Kalman covariance to moderate value (not too high, not too low)
        # This allows filter to adapt quickly to post-refuel readings
        self.P = 2.0

        # Reset ECU tracking for clean consumption calculation
        self.last_total_fuel_used = None

        logger.info(
            f"⛽ [{self.truck_id}] Refuel reset applied: "
            f"+{gallons_added:.1f} gal → {new_fuel_pct:.1f}% "
            f"({self.level_liters:.0f}L)"
        )


def get_latest_reading(
    engine, unit_id: int, max_fuel_lvl_age_min: int = 240
) -> Optional[pd.DataFrame]:
    """
    Get latest reading from Wialon DB (Placeholder for parallel processor compatibility)
    """
    return None


def normalize_units(
    df: pd.DataFrame, config: Dict, last_fuel_pct: float, normalizer
) -> Dict:
    """
    Normalize sensor data (Placeholder for parallel processor compatibility)
    """
    return {}


# ============================================================================
# MAIN EXECUTION LOOP
# ============================================================================
# NOTE: TRUCK_UNIT_MAPPING imported from wialon_reader.py (single source of truth)

# Import parallel processor for 4-8x speedup


def process_single_truck(
    truck_data,
    estimator,
    reporter,
    mpg_state,
    anchor_detector,
    tanks_config,
    last_processed_epoch: int,
    last_refuel_time: Optional[datetime] = None,  # 🆕 v3.11.1: For deduplication
    refuel_cooldown_minutes: int = 30,  # 🆕 v3.11.1: Cooldown period
) -> dict:
    """
    Process a single truck's data - extracted for parallel processing.

    Returns dict with:
        - success: bool
        - last_epoch: int (for tracking)
        - refuel_time: datetime (if refuel detected, for deduplication)
        - error: str (if failed)
    """
    truck_id = truck_data.truck_id

    try:
        # 🆕 CHECK FOR DUPLICATE/STALE DATA
        if truck_data.epoch_time <= last_processed_epoch:
            return {
                "success": True,
                "last_epoch": last_processed_epoch,
                "skipped": True,
            }

        # Calculate data age
        data_age_min = (
            datetime.now(timezone.utc) - truck_data.timestamp
        ).total_seconds() / 60.0

        # Extract sensor data
        sensors = {
            "fuel_lvl": truck_data.fuel_lvl,
            "fuel_rate": truck_data.fuel_rate,
            "obd_speed": truck_data.speed,
            "rpm": truck_data.rpm,
            "hdop": truck_data.hdop,
            "altitude": truck_data.altitude,
            "cool_temp": truck_data.coolant_temp,
            "odom": truck_data.odometer,
        }

        # Determine status
        # 🔧 FIX: Lowered threshold from 5 to 2 mph to match Beyond
        is_moving = (truck_data.speed or 0) > 2
        rpm = truck_data.rpm or 0
        pwr_ext = truck_data.pwr_ext or 0

        # 🆕 Enhanced Status Logic
        # 🔧 FIX v3.9.7: Reduced OFFLINE threshold from 30 to 15 min to match Beyond
        if data_age_min > 15:
            truck_status = TruckStatus.OFFLINE
        elif is_moving:
            truck_status = TruckStatus.MOVING
        elif rpm > 0:
            truck_status = TruckStatus.STOPPED
        elif (truck_data.fuel_rate or 0) > 0.3:
            truck_status = TruckStatus.STOPPED
        elif pwr_ext > 13.2:
            truck_status = TruckStatus.PARKED
        else:
            truck_status = TruckStatus.OFFLINE

        # Calculate Idle
        idle_gph, idle_method = calculate_idle_consumption(
            truck_status.value,
            rpm,
            truck_data.fuel_rate,
            estimator.level_liters,
            None,
            POLL_INTERVAL / 3600.0,
            IdleConfig(),
            truck_id,
        )

        idle_mode_enum = detect_idle_mode(idle_gph)
        idle_mode = idle_mode_enum.value

        # Emergency reset check
        if estimator.last_update_time:
            time_gap = (
                datetime.now(timezone.utc) - estimator.last_update_time
            ).total_seconds() / 3600.0

            if estimator.check_emergency_reset(
                sensor_pct=truck_data.fuel_lvl,
                time_gap_hours=time_gap,
                truck_status=truck_status.value,
            ):
                logger.info(f"[{truck_id}] 🔄 Emergency reset applied")

        # CONSUMPTION CALCULATION (ECU > fuel_rate > idle)
        speed_mph = truck_data.speed or 0

        # 🔧 FIX v3.10.3: Dynamic minimum fuel_rate based on speed
        # At highway speeds, fuel_rate < 3 GPH (11.4 L/h) is physically impossible for Class 8
        # This catches defective sensors reporting unrealistically low values
        if speed_mph >= 50:
            min_lph = 11.4  # ~3 GPH minimum at highway (impossible to be lower)
        elif speed_mph >= 30:
            min_lph = 7.6  # ~2 GPH minimum at moderate speeds
        else:
            min_lph = 3.8  # ~1 GPH minimum at low speeds/idle

        consumption_lph = 0.0
        fuel_rate_lph = truck_data.fuel_rate if truck_data.fuel_rate else None

        total_fuel_used = getattr(truck_data, "total_fuel_used", None)
        ecu_consumption = estimator.calculate_ecu_consumption(
            total_fuel_used=total_fuel_used,
            dt_hours=POLL_INTERVAL / 3600.0,
            fuel_rate_lph=fuel_rate_lph,
        )

        if ecu_consumption is not None and 0 <= ecu_consumption < 200:
            consumption_lph = ecu_consumption
        elif fuel_rate_lph and min_lph <= fuel_rate_lph <= 40.0:
            consumption_lph = fuel_rate_lph
        elif is_moving and speed_mph > 0:
            # 🔧 FIX v3.9.7: Estimate consumption when MOVING without sensor data
            # Physics-based estimation using speed as proxy for engine load
            # Class 8 trucks: ~4-5 GPH (15-19 L/h) at highway, ~3 GPH (11 L/h) at lower speeds
            estimated_lph = 11.0 + (speed_mph / 10.0)  # 11-17 L/h range (3-4.5 GPH)
            consumption_lph = min(estimated_lph, 25.0)  # Cap at 25 L/h (~6.6 GPH)
            logger.debug(
                f"[{truck_id}] 📊 Using physics-based consumption estimate: "
                f"{consumption_lph:.1f} L/h ({consumption_lph/3.78541:.2f} GPH) at {speed_mph:.0f} mph"
            )
        else:
            consumption_lph = idle_gph * 3.78541

        # Adaptive Kalman noise
        estimator.Q_L = estimator.calculate_adaptive_noise(
            speed=truck_data.speed,
            altitude=truck_data.altitude,
            timestamp=truck_data.timestamp,
            engine_load=getattr(truck_data, "engine_load", None),
        )

        estimator.predict(POLL_INTERVAL / 3600.0, consumption_lph)

        # 🆕 v3.11.2: GAP-AWARE REFUEL DETECTION
        # INDUSTRY STANDARD: Trucks turn off engine during refueling for safety
        # This causes a data gap (no transmission while engine off)
        # Pattern: truck at 25% → gap (5-20 min) → truck at 75% = REFUEL
        #
        # Detection strategy:
        # 1. Detect data gaps (time since last reading)
        # 2. Compare current fuel level with LAST KNOWN level before gap
        # 3. If significant increase after gap → refuel detected
        refuel_detected = False
        refuel_gallons = 0.0
        refuel_threshold_pct = COMMON_CONFIG.get("refuel_jump_threshold_pct", 10.0)
        refuel_volume_factor = COMMON_CONFIG.get("refuel_volume_factor", 0.90)
        tank_capacity_liters = tanks_config.get_capacity(truck_id)

        # 🆕 v3.11.2: Minimum gap to consider as "engine was off for refueling"
        MIN_REFUEL_GAP_MINUTES = 5  # Typical refueling takes 5-15 minutes
        MAX_REFUEL_GAP_MINUTES = 120  # Don't consider gaps > 2 hours as refuel

        if truck_data.fuel_lvl is not None:
            # Calculate time since last update from multiple sources
            time_since_last = 0
            reference_fuel_pct = None
            reference_source = "none"
            reference_timestamp = None

            # 🆕 v3.11.2: PRIORITY 1 - Check MySQL for last known level (most reliable after gaps)
            last_db_record = get_last_fuel_level_cached(truck_id)
            if last_db_record and last_db_record.get("sensor_pct"):
                db_sensor_pct = last_db_record["sensor_pct"]
                db_timestamp = last_db_record.get("timestamp_utc")

                if db_timestamp:
                    if isinstance(db_timestamp, datetime):
                        if db_timestamp.tzinfo is None:
                            db_timestamp = db_timestamp.replace(tzinfo=timezone.utc)
                        time_since_db = (
                            datetime.now(timezone.utc) - db_timestamp
                        ).total_seconds() / 60  # minutes

                        # 🆕 v3.11.2: CRITICAL - Use DB record if there's a gap
                        # A gap of 5+ minutes while truck is now moving suggests refueling occurred
                        if time_since_db >= MIN_REFUEL_GAP_MINUTES:
                            reference_fuel_pct = db_sensor_pct
                            reference_timestamp = db_timestamp
                            reference_source = f"pre_gap_db({time_since_db:.0f}min)"
                            time_since_last = time_since_db
                            logger.info(
                                f"[{truck_id}] 🔍 Gap detected: {time_since_db:.0f}min since last data. "
                                f"Last known level: {db_sensor_pct:.1f}%, Current: {truck_data.fuel_lvl:.1f}%"
                            )

            # PRIORITY 2 - Use estimator if recent (no gap)
            if reference_fuel_pct is None:
                if estimator.last_update_time:
                    time_since_last = (
                        datetime.now(timezone.utc) - estimator.last_update_time
                    ).total_seconds() / 60

                if (
                    estimator.level_pct is not None
                    and time_since_last < MIN_REFUEL_GAP_MINUTES
                ):
                    reference_fuel_pct = estimator.level_pct
                    reference_source = "estimator"

            # PRIORITY 3 - Fallback to estimator even if stale
            if reference_fuel_pct is None and estimator.level_pct is not None:
                reference_fuel_pct = estimator.level_pct
                reference_source = "estimator_fallback"
                if estimator.last_update_time:
                    time_since_last = (
                        datetime.now(timezone.utc) - estimator.last_update_time
                    ).total_seconds() / 60

            # Now calculate fuel jump against reference
            if reference_fuel_pct is not None:
                fuel_jump_pct = truck_data.fuel_lvl - reference_fuel_pct

                # 🆕 v3.11.2: GAP-BASED REFUEL DETECTION
                # If there's a gap (engine was off) AND fuel increased → REFUEL
                is_gap_refuel = (
                    time_since_last >= MIN_REFUEL_GAP_MINUTES
                    and time_since_last <= MAX_REFUEL_GAP_MINUTES
                    and fuel_jump_pct > refuel_threshold_pct
                )

                # Legacy conditions (kept for non-gap scenarios)
                was_stopped = (truck_data.speed or 0) < 5
                large_jump = fuel_jump_pct > 30.0
                after_gap = time_since_last > 10
                previous_valid = (
                    reference_fuel_pct > 1.0
                )  # Not recovering from frozen sensor

                # 🔧 v3.11.2: Unified detection - gap OR traditional conditions
                can_detect_refuel = (
                    is_gap_refuel  # 🆕 New: gap-based detection
                    or was_stopped
                    or large_jump
                    or after_gap
                    or time_since_last > 5
                )

                if (
                    fuel_jump_pct > refuel_threshold_pct
                    and fuel_jump_pct < 95.0
                    and previous_valid
                    and can_detect_refuel
                ):
                    # 🆕 v3.11.1: CHECK COOLDOWN - prevent duplicate refuel detection
                    cooldown_ok = True
                    if last_refuel_time is not None:
                        time_since_refuel = (
                            datetime.now(timezone.utc) - last_refuel_time
                        ).total_seconds() / 60  # minutes
                        if time_since_refuel < refuel_cooldown_minutes:
                            cooldown_ok = False
                            logger.debug(
                                f"[{truck_id}] ⏳ Refuel skipped (cooldown: {time_since_refuel:.0f}/{refuel_cooldown_minutes}min)"
                            )

                    if cooldown_ok:
                        # 🆕 v3.11.6: ANTI-NOISE FILTER
                        # Check if reference fuel level is valid (not a sensor glitch)
                        # This prevents false positives like NQ6975: 45%→2.8%→45% detected as refuel
                        ref_valid, ref_reason = is_reference_valid(
                            truck_id, reference_fuel_pct
                        )

                        if not ref_valid:
                            logger.warning(
                                f"[{truck_id}] 🚫 Refuel REJECTED ({ref_reason}): "
                                f"{reference_fuel_pct:.1f}% → {truck_data.fuel_lvl:.1f}% looks like sensor noise"
                            )
                            refuel_detected = False
                        else:
                            # 🆕 v3.11.2: Use actual tank capacity for calculation
                            # For trucks with dual tanks, get the real capacity
                            actual_tank_gallons = (
                                tanks_config.get_capacity(truck_id) * 0.264172
                            )

                            # Calculate gallons added based on percentage jump
                            gallons_raw = (fuel_jump_pct / 100.0) * actual_tank_gallons
                            refuel_gallons = gallons_raw * refuel_volume_factor
                            refuel_detected = True

                            # Determine detection reason
                            if is_gap_refuel:
                                reason = f"gap_refuel({time_since_last:.0f}min)"
                            elif was_stopped:
                                reason = "stopped"
                            elif large_jump:
                                reason = "large_jump"
                            elif reference_source.startswith("mysql"):
                                reason = f"after_gap({reference_source})"
                            else:
                                reason = "after_gap"

                            logger.info(
                                f"[{truck_id}] ⛽ REFUEL DETECTED ({reason}): {reference_fuel_pct:.1f}% → {truck_data.fuel_lvl:.1f}% "
                                f"(+{fuel_jump_pct:.1f}% = {refuel_gallons:.1f} gal, gap={time_since_last:.0f}min)"
                            )

                            # 🆕 v3.9.7: Log to dedicated refuel audit file
                            refuel_logger.info(
                                f"{truck_id}|{reason}|{reference_fuel_pct:.1f}|{truck_data.fuel_lvl:.1f}|"
                                f"{fuel_jump_pct:.1f}|{refuel_gallons:.1f}|{time_since_last:.0f}"
                            )

                            # 🆕 v3.11.5: Add to pending refuels for consecutive detection
                            # This allows multi-jump refuels (like RR3094: 171.6 gal) to be
                            # summed as a single event instead of only detecting first jump
                            finalized = add_pending_refuel(
                                truck_id=truck_id,
                                gallons=refuel_gallons,
                                before_pct=reference_fuel_pct,
                                after_pct=truck_data.fuel_lvl,
                                timestamp=truck_data.timestamp,
                                tanks_config=tanks_config,
                            )
                            # If a previous refuel was finalized, it's already saved to DB

                            # Apply refuel reset to estimator
                            estimator.apply_refuel_reset(
                                new_fuel_pct=truck_data.fuel_lvl,
                                timestamp=truck_data.timestamp,
                                gallons_added=refuel_gallons,
                            )

                            # 🆕 v3.9.7: Update Prometheus metrics for refuel
                            try:
                                metrics = get_metrics()
                                metrics.inc("refuels_detected_total")
                                metrics.set("refuels_last_gallons", refuel_gallons)
                            except Exception:
                                pass  # Metrics are optional

                            # 🆕 v3.8.0: Send SMS/Email notification for refuel
                            try:
                                alert_manager = get_alert_manager()
                                alert_manager.alert_refuel(
                                    truck_id=truck_id,
                                    gallons_added=refuel_gallons,
                                    new_level_pct=truck_data.fuel_lvl,
                                    send_sms=True,  # Send both SMS and Email
                                )
                                logger.info(
                                    f"[{truck_id}] 📱 Refuel alert sent (SMS + Email)"
                                )
                            except Exception as alert_err:
                                logger.warning(
                                    f"[{truck_id}] ⚠️ Failed to send refuel alert: {alert_err}"
                                )

                # 🆕 v3.10.7: FUEL THEFT DETECTION
                # Detect sudden fuel drops that are NOT normal consumption
                elif fuel_jump_pct < -10.0 and previous_valid:
                    # Calculate gallons lost
                    fuel_drop_pct = abs(fuel_jump_pct)
                    gallons_lost = (
                        (fuel_drop_pct / 100.0) * tank_capacity_liters * 0.264172
                    )

                    # Determine if this is suspicious (theft) vs normal consumption
                    # Normal consumption: ~0.5-2% per 15 min at highway speeds
                    # Suspicious: >10% drop in short time while stopped
                    is_suspicious = False
                    theft_reason = ""

                    if not is_moving and fuel_drop_pct > 15.0:
                        # Truck stopped with large drop = very suspicious
                        is_suspicious = True
                        theft_reason = "large_drop_while_stopped"
                    elif fuel_drop_pct > 20.0 and time_since_last < 30:
                        # Huge drop in short time = suspicious regardless
                        is_suspicious = True
                        theft_reason = "rapid_large_drop"
                    elif (
                        not is_moving and fuel_drop_pct > 10.0 and time_since_last < 15
                    ):
                        # Moderate drop while stopped in short time
                        is_suspicious = True
                        theft_reason = "moderate_drop_stopped"

                    if is_suspicious:
                        logger.warning(
                            f"[{truck_id}] 🚨 POSSIBLE FUEL THEFT ({theft_reason}): "
                            f"{reference_fuel_pct:.1f}% → {truck_data.fuel_lvl:.1f}% "
                            f"(-{fuel_drop_pct:.1f}% = -{gallons_lost:.1f} gal in {time_since_last:.0f}min)"
                        )

                        # Log to dedicated refuel audit file (also tracks theft)
                        refuel_logger.warning(
                            f"{truck_id}|THEFT|{theft_reason}|{reference_fuel_pct:.1f}|{truck_data.fuel_lvl:.1f}|"
                            f"-{fuel_drop_pct:.1f}|{gallons_lost:.1f}|{time_since_last:.0f}"
                        )

                        # Update Prometheus metrics for theft
                        try:
                            metrics = get_metrics()
                            metrics.inc("fuel_theft_detected_total")
                            metrics.set("fuel_theft_last_gallons", gallons_lost)
                        except Exception:
                            pass

                        # Send alert for potential theft
                        try:
                            alert_manager = get_alert_manager()
                            # Use drift alert as theft alert (or add alert_theft method)
                            if hasattr(alert_manager, "alert_theft"):
                                alert_manager.alert_theft(
                                    truck_id=truck_id,
                                    gallons_lost=gallons_lost,
                                    drop_pct=fuel_drop_pct,
                                    reason=theft_reason,
                                )
                            else:
                                # Fallback to drift alert
                                alert_manager.alert_drift(
                                    truck_id=truck_id,
                                    drift_pct=fuel_drop_pct,
                                    details=f"POSSIBLE THEFT: -{gallons_lost:.1f} gal ({theft_reason})",
                                )
                            logger.info(f"[{truck_id}] 📱 Theft alert sent")
                        except Exception as alert_err:
                            logger.warning(
                                f"[{truck_id}] ⚠️ Failed to send theft alert: {alert_err}"
                            )

        # 🔧 FIX v3.9.7: Handle missing fuel sensor gracefully
        # If fuel_lvl is None but estimator is initialized, continue with prediction only
        if truck_data.fuel_lvl is not None and not refuel_detected:
            estimator.update(truck_data.fuel_lvl)
            # 🆕 v3.11.6: Update fuel history for anti-noise filter
            update_fuel_history(truck_id, truck_data.fuel_lvl)
        elif truck_data.fuel_lvl is None and estimator.initialized:
            # Sensor unavailable - estimator continues with prediction only (no update)
            # This allows estimated_pct to show a value based on consumption
            logger.debug(f"[{truck_id}] Fuel sensor unavailable, using prediction only")

        estimate = estimator.get_estimate()

        # 🔧 FIX v3.9.2: Calculate odom_delta_mi from previous reading
        odom_delta_mi = 0.0
        if truck_data.odometer is not None and mpg_state.last_odometer_mi is not None:
            raw_delta = truck_data.odometer - mpg_state.last_odometer_mi
            # Validate: should be positive and reasonable (< 50 miles per cycle)
            if 0.0 < raw_delta < 50.0:
                odom_delta_mi = raw_delta
            elif raw_delta < 0:
                # Odometer rollback or reset - ignore
                logger.debug(
                    f"[{truck_id}] Ignoring negative odom delta: {raw_delta:.2f}"
                )

        # Update last odometer for next cycle
        if truck_data.odometer is not None:
            mpg_state.last_odometer_mi = truck_data.odometer

        # 🔧 FIX v3.9.6: Update MPG state (was missing!)
        # Only update when moving and have valid odom_delta
        if is_moving and odom_delta_mi > 0:
            # 🔧 FIX v3.10.7: Use ACTUAL timestamp delta instead of POLL_INTERVAL
            # Wialon data arrives every ~120s, not 15s, so using POLL_INTERVAL
            # underestimates fuel consumption by ~8x, causing inflated MPG values
            delta_hours = POLL_INTERVAL / 3600.0  # Default fallback

            if mpg_state.last_timestamp is not None:
                actual_delta_sec = truck_data.epoch_time - mpg_state.last_timestamp
                # Validate: between 10 seconds and 10 minutes
                if 10 < actual_delta_sec < 600:
                    delta_hours = actual_delta_sec / 3600.0
                    logger.debug(
                        f"[{truck_id}] Using actual delta: {actual_delta_sec:.0f}s "
                        f"({delta_hours*3600:.0f}s vs POLL_INTERVAL={POLL_INTERVAL}s)"
                    )

            # Try to get fuel consumption from various sources
            delta_fuel_gal = 0.0

            if consumption_lph > 0:
                # 1. Best: Use ECU/fuel_rate consumption if available
                delta_fuel_gal = (consumption_lph * delta_hours) / 3.78541
            elif (
                truck_data.fuel_lvl is not None
                and mpg_state.last_fuel_lvl_pct is not None
            ):
                # 2. Fallback: Calculate from fuel level drop
                fuel_drop_pct = mpg_state.last_fuel_lvl_pct - truck_data.fuel_lvl
                if 0 < fuel_drop_pct < 5.0:  # Reasonable drop (0-5% per cycle)
                    tank_liters = tanks_config.get_capacity(truck_id)
                    delta_fuel_liters = (fuel_drop_pct / 100.0) * tank_liters
                    delta_fuel_gal = delta_fuel_liters / 3.78541
                    mpg_state.fuel_source_stats["sensor"] = (
                        mpg_state.fuel_source_stats.get("sensor", 0) + 1
                    )

            # Only update MPG if we have valid fuel consumption
            if delta_fuel_gal > 0:
                update_mpg_state(
                    mpg_state,
                    odom_delta_mi,
                    delta_fuel_gal,
                    MPGConfig(),
                    truck_id,
                )

        # 🔧 FIX v3.10.7: ALWAYS update last_timestamp for delta calculation
        mpg_state.last_timestamp = truck_data.epoch_time

        # 🔧 FIX v3.9.6: ALWAYS update last_fuel_lvl_pct for next cycle
        if truck_data.fuel_lvl is not None:
            mpg_state.last_fuel_lvl_pct = truck_data.fuel_lvl

        # Anchor detection
        anchor_detected = False
        anchor_type = AnchorType.NONE
        static_anchors_count = 0
        micro_anchors_count = 0
        refuel_events_count = 1 if refuel_detected else 0

        if truck_data.fuel_lvl is not None:
            static_anchor = anchor_detector.check_static_anchor(
                timestamp=truck_data.timestamp,
                speed=truck_data.speed,
                rpm=truck_data.rpm,
                fuel_pct=truck_data.fuel_lvl,
                hdop=getattr(truck_data, "hdop", None),
                drift_pct=estimate.get("drift_pct", 0.0),
            )
            if static_anchor:
                anchor_detected = True
                anchor_type = AnchorType.STATIC
                static_anchors_count = 1

            # 🔧 FIX v3.9.4: Also check for micro anchors (stable cruise)
            if not anchor_detected:
                micro_anchor = anchor_detector.check_micro_anchor(
                    timestamp=truck_data.timestamp,
                    speed=truck_data.speed,
                    fuel_pct=truck_data.fuel_lvl,
                    hdop=getattr(truck_data, "hdop", None),
                    altitude_ft=getattr(truck_data, "altitude", None),
                    drift_pct=estimate.get("drift_pct", 0.0),
                )
                if micro_anchor:
                    anchor_detected = True
                    anchor_type = AnchorType.MICRO
                    micro_anchors_count = 1

            # Mark refuel as anchor type if detected
            if refuel_detected:
                anchor_detected = True
                anchor_type = AnchorType.REFUEL

        # Write to CSV/MySQL
        reporter.write_row(
            truck_data.timestamp,
            data_age_min,
            truck_status,
            estimate,
            sensors,
            odom_delta_mi,  # 🔧 FIX v3.9.2: Pass calculated odom delta
            estimate["drift_pct"],
            estimate["drift_warning"],
            anchor_detected,
            anchor_type,
            {
                "static_anchors": static_anchors_count,
                "micro_anchors": micro_anchors_count,
                "refuel_events": refuel_events_count,
            },
            {},
            None,
            tanks_config,
            truck_id,
            mpg_state.mpg_current,
            refuel_gallons,  # 🆕 Pass refuel gallons to reporter
            idle_method.value,
            idle_mode,
            truck_data.epoch_time,
        )

        return {
            "success": True,
            "last_epoch": truck_data.epoch_time,
            "truck_id": truck_id,
            "refuel_time": (
                datetime.now(timezone.utc) if refuel_detected else None
            ),  # 🆕 v3.11.1
        }

    except Exception as e:
        logger.error(f"[{truck_id}] ❌ Processing error: {e}")
        return {
            "success": False,
            "last_epoch": last_processed_epoch,
            "error": str(e),
            "truck_id": truck_id,
            "refuel_time": None,  # 🆕 v3.11.1
        }


def main():
    logger.info(
        "🚀 Starting Fuel Copilot v3.11.6 (Anti-Noise Filter + Consecutive Refuel)..."
    )

    # 🆕 v3.6.0: Initialize Observability
    metrics = get_metrics()
    health = get_health_checker()

    # Register health checks
    health.register(
        "self",
        lambda: HealthCheckResult(
            name="self",
            status=HealthStatus.HEALTHY,
            message="Fuel Copilot is running",
        ),
    )

    # Initialize Wialon Reader
    wialon_config = WialonConfig()
    reader = WialonReader(wialon_config, TRUCK_UNIT_MAPPING)

    if not reader.connect():
        logger.error("❌ Failed to connect to Wialon DB. Exiting.")
        return

    # Register database health check
    health.register(
        "database",
        lambda: HealthCheckResult(
            name="database",
            status=(
                HealthStatus.HEALTHY
                if reader.connection is not None
                else HealthStatus.UNHEALTHY
            ),
            message=(
                "Wialon DB connected"
                if reader.connection is not None
                else "Wialon DB disconnected"
            ),
        ),
    )

    # 🆕 v3.9.7: Register MySQL health check
    def check_mysql_health():
        try:
            from bulk_mysql_handler import get_local_session
            from sqlalchemy import text

            session = get_local_session()
            session.execute(text("SELECT 1"))
            session.close()
            return HealthCheckResult(
                name="mysql",
                status=HealthStatus.HEALTHY,
                message="Local MySQL connected",
            )
        except Exception as e:
            return HealthCheckResult(
                name="mysql",
                status=HealthStatus.UNHEALTHY,
                message=f"Local MySQL error: {str(e)[:50]}",
            )

    health.register("mysql", check_mysql_health)

    # Start observability server (port 9090)
    obs_server = ObservabilityServer(metrics, health, port=9090)
    obs_server.start()
    logger.info("📊 Metrics available at http://localhost:9090/metrics")

    # 🆕 v3.11.0: Cleanup stale estimator states on startup
    # This prevents the bug where trucks show OFFLINE in dashboard
    # when they're actually MOVING in Wialon (due to stale state files)
    logger.info("🧹 Checking for stale estimator states...")
    cleanup_stale_estimator_states(max_age_hours=2.0)

    # Initialize state for each truck
    estimators = {}
    reporters = {}
    mpg_states = {}
    anchor_detectors = {}  # 🆕 Anchor detectors for Kalman calibration
    last_processed_epochs = {}  # 🆕 Track last processed data to avoid duplicates
    last_refuel_times = (
        {}
    )  # 🆕 v3.11.1: Track last refuel time per truck for deduplication
    tanks_config = TanksConfig("tanks.yaml")

    # 🆕 Load persisted MPG states
    saved_mpg_states = load_mpg_states()

    # Initialize estimators (using TRUCK_CONFIG from tanks.yaml)
    restored_count = 0
    fresh_count = 0

    for truck_id in TRUCK_CONFIG:
        capacity = tanks_config.get_capacity(truck_id)
        estimators[truck_id] = FuelEstimator(
            truck_id, capacity, COMMON_CONFIG, tanks_config
        )
        reporters[truck_id] = CSVReporter(truck_id)
        anchor_detectors[truck_id] = AnchorDetector(COMMON_CONFIG)  # 🆕

        # Restore MPG state if available
        if truck_id in saved_mpg_states:
            mpg_states[truck_id] = saved_mpg_states[truck_id]
        else:
            mpg_states[truck_id] = MPGState()

        # 🆕 v3.11.0: Try to restore FRESH estimator state
        saved_state = load_estimator_state(truck_id)
        if saved_state:
            if restore_estimator_from_state(estimators[truck_id], saved_state):
                restored_count += 1
            else:
                fresh_count += 1
        else:
            fresh_count += 1

        last_processed_epochs[truck_id] = 0  # Initialize epoch tracking
        last_refuel_times[truck_id] = None  # 🆕 v3.11.1: No refuels detected yet

    # 🆕 v3.11.1: REFUEL DEDUPLICATION COOLDOWN (30 minutes)
    REFUEL_COOLDOWN_MINUTES = 30

    # 🔧 FIX v3.9.4: Save MPG states every 5 minutes instead of every cycle
    last_mpg_save_time = time.time()
    last_state_save_time = time.time()  # 🆕 v3.11.0
    MPG_SAVE_INTERVAL = 300  # 5 minutes
    STATE_SAVE_INTERVAL = 60  # 🆕 v3.11.0: Save estimator states every 60 seconds

    logger.info(
        f"✅ Initialized {len(estimators)} truck estimators "
        f"({restored_count} restored, {fresh_count} fresh)"
    )

    try:
        while True:
            start_time = time.time()
            logger.info("🔄 Starting poll cycle...")

            try:
                # Get data for all trucks
                trucks_data = reader.get_all_trucks_data()
                trucks_data_by_id = {td.truck_id: td for td in trucks_data}

                # 🆕 PARALLEL PROCESSING (5x speedup)
                from concurrent.futures import ThreadPoolExecutor, as_completed

                processed_count = 0
                error_count = 0

                with ThreadPoolExecutor(
                    max_workers=8, thread_name_prefix="TruckWorker"
                ) as executor:
                    futures = {}

                    for truck_id in estimators.keys():
                        if truck_id not in trucks_data_by_id:
                            continue

                        truck_data = trucks_data_by_id[truck_id]

                        # Skip duplicates
                        if truck_data.epoch_time <= last_processed_epochs.get(
                            truck_id, 0
                        ):
                            continue

                        future = executor.submit(
                            process_single_truck,
                            truck_data,
                            estimators[truck_id],
                            reporters[truck_id],
                            mpg_states[truck_id],
                            anchor_detectors[truck_id],
                            tanks_config,
                            last_processed_epochs.get(truck_id, 0),
                            last_refuel_times.get(
                                truck_id
                            ),  # 🆕 v3.11.1: Pass last refuel time
                            REFUEL_COOLDOWN_MINUTES,  # 🆕 v3.11.1: Pass cooldown setting
                        )
                        futures[future] = truck_id

                    for future in as_completed(futures):
                        truck_id = futures[future]
                        try:
                            result = future.result()
                            if result.get("success"):
                                processed_count += 1
                                last_processed_epochs[truck_id] = result.get(
                                    "last_epoch", 0
                                )
                                # 🆕 v3.11.1: Update last refuel time if refuel detected
                                if result.get("refuel_time"):
                                    last_refuel_times[truck_id] = result["refuel_time"]
                            else:
                                error_count += 1
                        except Exception as e:
                            logger.error(f"[{truck_id}] Thread error: {e}")
                            error_count += 1

                elapsed_inner = time.time() - start_time
                logger.info(
                    f"✅ Processed {processed_count} trucks in {elapsed_inner:.1f}s "
                    f"({processed_count/max(elapsed_inner, 0.1):.1f} trucks/sec) [PARALLEL]"
                )

                # 🆕 v3.6.0: Update Prometheus metrics
                metrics.inc("trucks_processed_total", processed_count)
                metrics.inc("errors_total", error_count)
                metrics.set("active_trucks", len(trucks_data))
                metrics.set("cycle_duration_seconds", elapsed_inner)
                metrics.observe(
                    "truck_processing_seconds", elapsed_inner / max(processed_count, 1)
                )
            except Exception as e:
                logger.error(f"❌ Cycle error: {e}")
                import traceback

                traceback.print_exc()

            # Sleep
            elapsed = time.time() - start_time
            sleep_time = max(0, POLL_INTERVAL - elapsed)

            # 🔧 FIX v3.9.4: Save MPG states every 5 minutes (was every cycle)
            if time.time() - last_mpg_save_time >= MPG_SAVE_INTERVAL:
                save_mpg_states(mpg_states)
                last_mpg_save_time = time.time()

            # 🆕 v3.11.0: Save estimator states every 60 seconds
            # This ensures we can recover from crashes without losing much state
            if time.time() - last_state_save_time >= STATE_SAVE_INTERVAL:
                for truck_id in estimators:
                    save_estimator_state(
                        truck_id, estimators[truck_id], mpg_states.get(truck_id)
                    )
                last_state_save_time = time.time()
                logger.debug(f"💾 Saved estimator states for {len(estimators)} trucks")

                # 🆕 v3.11.5: Flush stale pending refuels (>15 min old)
                # This ensures multi-jump refuels are finalized and saved to DB
                flush_stale_pending_refuels(tanks_config, max_age_minutes=15)

            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("🛑 Stopping Fuel Copilot...")

        # 🆕 v3.11.5: Finalize any pending refuels before shutdown
        logger.info("💾 Finalizing pending refuels...")
        flush_stale_pending_refuels(tanks_config, max_age_minutes=0)  # Force flush all

        # 🆕 v3.11.0: Save all states before shutdown
        logger.info("💾 Saving states before shutdown...")
        save_mpg_states(mpg_states)
        for truck_id in estimators:
            save_estimator_state(
                truck_id, estimators[truck_id], mpg_states.get(truck_id)
            )
        logger.info(f"✅ Saved states for {len(estimators)} trucks")

        obs_server.stop()  # 🆕 v3.6.0: Clean shutdown
        reader.disconnect()
        for reporter in reporters.values():
            reporter.close()
    except Exception as e:
        logger.critical(f"🔥 FATAL CRASH: {e}", exc_info=True)
        try:
            # 🆕 v3.11.0: Try to save states even on crash
            save_mpg_states(mpg_states)
            for truck_id in estimators:
                save_estimator_state(
                    truck_id, estimators[truck_id], mpg_states.get(truck_id)
                )
            logger.info("💾 Saved states before crash exit")
        except Exception as save_err:
            logger.error(f"Could not save states: {save_err}")
        try:
            obs_server.stop()  # 🆕 v3.6.0: Clean shutdown
            reader.disconnect()
            for reporter in reporters.values():
                reporter.close()
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
