"""
Wialon to MySQL Sync - Enhanced Real-time Data Bridge v3.0
🚀 FULL KALMAN FILTER INTEGRATION

This enhanced sync script properly integrates:
- FuelEstimator (Kalman Filter) from estimator.py
- MPG tracking from mpg_engine.py
- Idle consumption calculation from idle_engine.py
- State persistence for continuity across restarts

FIXES ALL DASHBOARD ISSUES:
✅ Kalman vs Sensor values (not just N/A)
✅ Proper drift calculation (estimated - sensor)
✅ Real MPG tracking with EMA smoothing
✅ Idle consumption with temperature adjustment
✅ Refuel detection
✅ Emergency reset for extreme drift

Author: Fuel Copilot Team
Version: 3.12.21
Date: December 2025
"""

import os
import time
import json
import pymysql
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the existing sophisticated modules
from estimator import FuelEstimator, AnchorDetector, AnchorType
from mpg_engine import MPGState, MPGConfig, update_mpg_state, reset_mpg_state
from idle_engine import (
    calculate_idle_consumption,
    detect_idle_mode,
    IdleMethod,
    IdleConfig,
)
from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING

# 🆕 v3.12.27: Import fuel event classifier for theft/sensor differentiation
from alert_service import (
    get_fuel_classifier,
    get_alert_manager,
    send_theft_confirmed_alert,
    send_sensor_issue_alert,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

LOCAL_DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "fuel_admin",
    "password": "FuelCopilot2025!",
    "database": "fuel_copilot",
    "autocommit": True,
}

# State persistence paths
DATA_DIR = Path(__file__).parent / "data"
ESTIMATOR_STATES_DIR = DATA_DIR / "estimator_states"
MPG_STATES_FILE = DATA_DIR / "mpg_states.json"

# Kalman configuration
KALMAN_CONFIG = {
    "Q_r": 0.1,  # Process noise
    "Q_L_moving": 4.0,  # Measurement noise when moving
    "Q_L_static": 1.0,  # Measurement noise when static
    "max_drift_pct": 7.5,  # Drift warning threshold
    "emergency_drift_threshold": 30.0,  # Emergency reset threshold
    "emergency_gap_hours": 2.0,  # Time gap for emergency reset
    "refuel_volume_factor": 1.0,
}

# ═══════════════════════════════════════════════════════════════════════════════
# TANK CAPACITIES
# ═══════════════════════════════════════════════════════════════════════════════


def load_tank_config() -> tuple[Dict[str, float], Dict[str, float]]:
    """Load tank capacities and refuel factors from tanks.yaml"""
    yaml_path = Path(__file__).parent / "tanks.yaml"
    capacities: Dict[str, float] = {"default": 200.0}
    refuel_factors: Dict[str, float] = {"default": 1.0}  # Default: no adjustment

    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            trucks = config.get("trucks", {})
            for truck_id, truck_config in trucks.items():
                capacities[truck_id] = float(truck_config.get("capacity_gallons", 200))
                # Load refuel_factor if specified (for sensor calibration)
                if "refuel_factor" in truck_config:
                    refuel_factors[truck_id] = float(truck_config["refuel_factor"])
            logger.info(
                f"✅ Loaded capacities for {len(trucks)} trucks from tanks.yaml"
            )
            factors_count = len([k for k in refuel_factors if k != "default"])
            if factors_count > 0:
                logger.info(f"✅ Loaded refuel_factors for {factors_count} trucks")
        except Exception as e:
            logger.warning(f"⚠️ Could not load tanks.yaml: {e}")

    return capacities, refuel_factors


TANK_CAPACITIES, REFUEL_FACTORS = load_tank_config()


def get_refuel_factor(truck_id: str) -> float:
    """Get refuel factor for a truck (sensor calibration adjustment)"""
    return REFUEL_FACTORS.get(truck_id, REFUEL_FACTORS["default"])


def get_tank_capacity_liters(truck_id: str) -> float:
    """Get tank capacity in liters for a truck"""
    gallons = TANK_CAPACITIES.get(truck_id, TANK_CAPACITIES["default"])
    return gallons * 3.78541


# ═══════════════════════════════════════════════════════════════════════════════
# STATE PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════


class StateManager:
    """Manages persistence of estimator and MPG states"""

    def __init__(self):
        ESTIMATOR_STATES_DIR.mkdir(parents=True, exist_ok=True)
        self.estimators: Dict[str, FuelEstimator] = {}
        self.mpg_states: Dict[str, MPGState] = {}
        self.anchor_detectors: Dict[str, AnchorDetector] = {}
        self.last_sensor_data: Dict[str, Dict] = {}
        self._load_states()

    def _load_states(self):
        """Load persisted states on startup"""
        # Load MPG states
        if MPG_STATES_FILE.exists():
            try:
                with open(MPG_STATES_FILE, "r") as f:
                    data = json.load(f)
                for truck_id, state_data in data.items():
                    mpg_state = MPGState(
                        distance_accum=state_data.get("distance_accum", 0.0),
                        fuel_accum_gal=state_data.get("fuel_accum_gal", 0.0),
                        mpg_current=state_data.get("mpg_current"),
                        window_count=state_data.get("window_count", 0),
                        last_fuel_lvl_pct=state_data.get("last_fuel_lvl_pct"),
                        last_odometer_mi=state_data.get("last_odometer_mi"),
                        last_timestamp=state_data.get("last_timestamp"),
                    )
                    self.mpg_states[truck_id] = mpg_state
                logger.info(f"✅ Loaded MPG states for {len(self.mpg_states)} trucks")
            except Exception as e:
                logger.warning(f"⚠️ Could not load MPG states: {e}")

        # Load estimator states
        for state_file in ESTIMATOR_STATES_DIR.glob("*_state.json"):
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                truck_id = data.get("truck_id")
                if truck_id:
                    capacity_liters = get_tank_capacity_liters(truck_id)
                    estimator = FuelEstimator(
                        truck_id=truck_id,
                        capacity_liters=capacity_liters,
                        config=KALMAN_CONFIG,
                    )
                    # Restore state
                    estimator.initialized = data.get("initialized", False)
                    estimator.level_liters = data.get("level_liters", 0.0)
                    estimator.level_pct = data.get("level_pct", 0.0)
                    estimator.L = data.get("L", 0.0)
                    estimator.P = data.get("P", 1.0)
                    estimator.P_L = data.get("P_L", 20.0)
                    estimator.drift_pct = data.get("drift_pct", 0.0)
                    estimator.last_fuel_lvl_pct = data.get("last_fuel_lvl_pct")
                    if data.get("last_timestamp"):
                        try:
                            estimator.last_update_time = datetime.fromisoformat(
                                data["last_timestamp"]
                            )
                        except (ValueError, TypeError) as e:
                            logger.debug(
                                f"Invalid timestamp format for {truck_id}: {e}"
                            )
                    self.estimators[truck_id] = estimator
            except Exception as e:
                logger.warning(f"⚠️ Could not load state from {state_file}: {e}")

        logger.info(f"✅ Loaded estimator states for {len(self.estimators)} trucks")

    def get_estimator(self, truck_id: str) -> FuelEstimator:
        """Get or create estimator for a truck"""
        if truck_id not in self.estimators:
            capacity_liters = get_tank_capacity_liters(truck_id)
            self.estimators[truck_id] = FuelEstimator(
                truck_id=truck_id,
                capacity_liters=capacity_liters,
                config=KALMAN_CONFIG,
            )
        return self.estimators[truck_id]

    def get_mpg_state(self, truck_id: str) -> MPGState:
        """Get or create MPG state for a truck"""
        if truck_id not in self.mpg_states:
            self.mpg_states[truck_id] = MPGState()
        return self.mpg_states[truck_id]

    def get_anchor_detector(self, truck_id: str) -> AnchorDetector:
        """Get or create anchor detector for a truck"""
        if truck_id not in self.anchor_detectors:
            self.anchor_detectors[truck_id] = AnchorDetector(KALMAN_CONFIG)
        return self.anchor_detectors[truck_id]

    def save_states(self):
        """Persist all states to disk"""
        # Save MPG states
        try:
            mpg_data = {}
            for truck_id, state in self.mpg_states.items():
                mpg_data[truck_id] = {
                    "distance_accum": state.distance_accum,
                    "fuel_accum_gal": state.fuel_accum_gal,
                    "mpg_current": state.mpg_current,
                    "window_count": state.window_count,
                    "last_fuel_lvl_pct": state.last_fuel_lvl_pct,
                    "last_odometer_mi": state.last_odometer_mi,
                    "last_timestamp": state.last_timestamp,
                    "fuel_source_stats": state.fuel_source_stats,
                }
            with open(MPG_STATES_FILE, "w") as f:
                json.dump(mpg_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save MPG states: {e}")

        # Save estimator states
        for truck_id, estimator in self.estimators.items():
            try:
                state_file = ESTIMATOR_STATES_DIR / f"{truck_id}_state.json"
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
                    "last_timestamp": (
                        estimator.last_update_time.isoformat()
                        if estimator.last_update_time
                        else None
                    ),
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "mpg_current": (
                        self.mpg_states[truck_id].mpg_current
                        if truck_id in self.mpg_states
                        else None
                    ),
                }
                with open(state_file, "w") as f:
                    json.dump(state_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save estimator state for {truck_id}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# TRUCK PROCESSING LOGIC (FROM ORIGINAL fuel_copilot_v2_1_fixed.py)
# ═══════════════════════════════════════════════════════════════════════════════


def determine_truck_status(
    speed: Optional[float],
    rpm: Optional[float],
    fuel_rate: Optional[float],
    data_age_min: float,
    pwr_ext: Optional[float] = None,
    engine_load: Optional[float] = None,
    coolant_temp: Optional[float] = None,
) -> str:
    """
    Enhanced truck status determination v3 - Fixed STOPPED detection

    🔧 FIX v3.12.1: Check engine indicators BEFORE speed check
    Previously, speed=None would return OFFLINE even if RPM > 0 (engine running)

    Status Hierarchy:
    1. OFFLINE: Data too old (>15 min)
    2. STOPPED: Engine ON but stationary (RPM > 0, speed = 0 or None) - IDLING
    3. MOVING: Vehicle in motion (speed > 2 mph)
    4. PARKED: Engine OFF, vehicle connected (shore power or recent data)
    5. OFFLINE: No activity detected

    Engine ON Indicators (any one = engine running):
    - RPM > 0
    - Fuel rate > 0.3 L/h
    - Engine load > 0%
    - Coolant temp > 120°F (engine at operating temp)
    """
    # Check for offline - stale data (no communication in 15+ minutes)
    if data_age_min > 15:
        return "OFFLINE"

    # 🔧 FIX v3.12.1: Check engine indicators FIRST (before speed check)
    # This ensures trucks with RPM > 0 but speed=None are marked STOPPED, not OFFLINE
    rpm_val = rpm or 0
    fuel_rate_val = fuel_rate or 0
    engine_load_val = engine_load or 0
    coolant_temp_val = coolant_temp or 0  # °F
    pwr_ext_val = pwr_ext or 0
    speed_val = speed or 0

    # Engine ON indicators (any one = engine running)
    engine_running = (
        rpm_val > 0
        or fuel_rate_val > 0.3
        or engine_load_val > 0
        or coolant_temp_val > 120  # Engine at operating temperature
    )

    # If engine is running and speed is low/none = STOPPED (idling)
    if engine_running and speed_val < 2:
        return "STOPPED"

    # Moving - speed > 2 mph (filters GPS noise/drift)
    if speed_val > 2:
        return "MOVING"

    # No GPS data and no engine indicators = truly offline
    if speed is None and not engine_running:
        return "OFFLINE"

    # Engine OFF checks
    # Shore power connected (13.2V+ indicates external power)
    if pwr_ext_val > 13.2:
        return "PARKED"  # Plugged in, engine off

    # Battery voltage in normal range (12-13.2V) = recently used, parked
    if pwr_ext_val > 11.5:
        return "PARKED"  # Battery shows truck is connected and alive

    # Coolant temp between ambient and running = recently stopped
    if coolant_temp_val > 60 and coolant_temp_val <= 120:
        return "PARKED"  # Engine cooling down = recently parked

    # Data is fresh (<15 min) but no engine activity = parked
    if data_age_min < 5:
        return "PARKED"  # Very recent data, just no activity

    # Fallback - older data with no activity
    return "OFFLINE"


def calculate_consumption(
    speed: Optional[float],
    rpm: Optional[float],
    fuel_rate: Optional[float],
    total_fuel_used: Optional[float],
    estimator: FuelEstimator,
    dt_hours: float,
    truck_status: str,
) -> float:
    """
    Multi-source consumption calculation with intelligent fallback

    Priority:
    1. ECU cumulative counter (most accurate)
    2. fuel_rate sensor (if valid for current speed)
    3. Physics-based estimate
    """
    # Try ECU consumption first
    ecu_consumption = estimator.calculate_ecu_consumption(
        total_fuel_used, dt_hours, fuel_rate
    )
    if ecu_consumption is not None:
        return ecu_consumption

    # Validate fuel_rate sensor
    if fuel_rate is not None and fuel_rate > 0:
        # Determine minimum valid fuel_rate based on speed
        if speed is not None and speed > 40:
            min_lph = 8.0  # Highway minimum
        elif speed is not None and speed > 20:
            min_lph = 5.0  # City minimum
        elif speed is not None and speed > 5:
            min_lph = 3.0  # Low speed minimum
        else:
            min_lph = 1.5  # Idle minimum

        if fuel_rate >= min_lph:
            return fuel_rate

    # Physics-based fallback
    if truck_status == "MOVING" and speed is not None and speed > 5:
        # Approximate: base + speed factor
        # ~15 L/100km at highway speeds
        return 15.0 + (speed * 0.15)
    elif truck_status == "STOPPED":
        return 2.5  # Idle consumption
    else:
        return 0.0


def detect_refuel(
    sensor_pct: float,
    estimated_pct: float,
    last_sensor_pct: Optional[float],
    time_gap_hours: float,
    truck_status: str,
    tank_capacity_gal: float,
    truck_id: str = "",
) -> Optional[Dict]:
    """
    Gap-aware refuel detection using Kalman estimate as baseline.

    🔧 v3.12.29: Use Kalman estimate (estimated_pct) as "before" reference
    - The Kalman filter tracks expected fuel level based on consumption model
    - When sensor shows higher than Kalman after a gap → refuel detected
    - This is more accurate than comparing two noisy sensor readings

    Criteria:
    - Time gap between 5 min and 24 hours (extended for overnight refuels)
    - Sensor > Kalman by > 15% (fuel was added)
    - Minimum 10 gallons added

    🔧 v3.15.4: Extended max gap from 2h to 24h to catch overnight refuels
    Many trucks refuel when offline (nights/weekends) and the 2h limit
    was causing missed detections (e.g., FF7702).

    The Kalman represents "what we expected" after consumption
    The Sensor represents "what's actually in the tank now"
    Difference = fuel added during the gap
    """
    if sensor_pct is None or estimated_pct is None:
        return None

    # Time gap validation (5 min to 24 hours)
    # 🔧 v3.15.4: Extended from 2h to 24h for overnight refuels
    if time_gap_hours < 5 / 60 or time_gap_hours > 24:
        return None

    # 🔧 v3.12.29: Calculate increase using Kalman as baseline
    # fuel_increase = current_sensor - kalman_estimate (what we expected)
    fuel_increase_pct = sensor_pct - estimated_pct

    # Minimum thresholds
    # 🔧 v3.12.16: 15% threshold reduces false positives from sensor noise
    min_increase_pct = 15.0
    min_increase_gal = 10.0

    # 🔧 v3.12.28: Apply refuel_factor for sensor calibration
    refuel_factor = get_refuel_factor(truck_id)
    increase_gal_raw = (fuel_increase_pct / 100) * tank_capacity_gal
    increase_gal = increase_gal_raw * refuel_factor

    if fuel_increase_pct >= min_increase_pct and increase_gal >= min_increase_gal:
        # Extra safety: reject small jumps when tank is already nearly full
        # (likely sensor noise, not actual refuel)
        # 🔧 v3.15.3: Allow refuels >25 gal even near full tank (FF7702 case)
        # A jump from 80%→99% is valid (~38 gal) even though <20% increase
        if sensor_pct > 95 and fuel_increase_pct < 20 and increase_gal < 25:
            logger.debug(
                f"⏭️ Skipping small near-full jump: {truck_id} +{fuel_increase_pct:.1f}% +{increase_gal:.1f}gal"
            )
            return None

        factor_note = f" (factor={refuel_factor})" if refuel_factor != 1.0 else ""
        logger.info(
            f"⛽ REFUEL DETECTED: Kalman={estimated_pct:.1f}% → Sensor={sensor_pct:.1f}% "
            f"(+{fuel_increase_pct:.1f}%, +{increase_gal:.1f} gal{factor_note}) over {time_gap_hours*60:.0f} min"
        )

        return {
            "type": "REFUEL",
            "prev_pct": estimated_pct,  # 🔧 Now using Kalman estimate as "before"
            "new_pct": sensor_pct,
            "increase_pct": fuel_increase_pct,
            "increase_gal": increase_gal,
            "time_gap_hours": time_gap_hours,
        }

    return None


def detect_fuel_theft(
    sensor_pct: float,
    estimated_pct: float,
    last_sensor_pct: Optional[float],
    truck_status: str,
    time_gap_hours: float,
    tank_capacity_gal: float = 200.0,
) -> Optional[Dict]:
    """
    🆕 v3.12.21: Enhanced Fuel theft detection with multiple heuristics.

    Detection criteria (ANY match triggers alert):
    1. STOPPED theft: Large drop (>10%) while truck was stopped
    2. RAPID theft: Very large drop (>20%) in short time (<1 hour)
    3. PATTERN theft: Multiple moderate drops (>5%) when consumption doesn't explain it

    Args:
        sensor_pct: Current sensor reading (%)
        estimated_pct: Expected level based on consumption model
        last_sensor_pct: Previous sensor reading (%)
        truck_status: MOVING, STOPPED, or IDLE
        time_gap_hours: Time since last reading
        tank_capacity_gal: Tank capacity for gallon calculations

    Returns:
        Dict with theft details or None if no theft detected
    """
    if last_sensor_pct is None or sensor_pct is None:
        return None

    fuel_drop_pct = last_sensor_pct - sensor_pct
    fuel_drop_gal = fuel_drop_pct * tank_capacity_gal / 100

    # No significant drop
    if fuel_drop_pct <= 3:
        return None

    theft_confidence = 0.0
    theft_type = None
    reasons = []

    # 1. STOPPED theft: Drop while truck was stationary
    if truck_status == "STOPPED":
        if fuel_drop_pct > 10:
            theft_confidence = 0.9
            theft_type = "STOPPED_THEFT"
            reasons.append(f"Large drop ({fuel_drop_pct:.1f}%) while stopped")
        elif fuel_drop_pct > 5:
            theft_confidence = 0.6
            theft_type = "STOPPED_SUSPICIOUS"
            reasons.append(f"Moderate drop ({fuel_drop_pct:.1f}%) while stopped")

    # 2. RAPID theft: Very large drop in short time
    if fuel_drop_pct > 20 and time_gap_hours < 1.0:
        # This is suspicious regardless of status
        if theft_confidence < 0.85:
            theft_confidence = 0.85
            theft_type = "RAPID_LOSS"
            reasons.append(
                f"Rapid loss ({fuel_drop_pct:.1f}%) in {time_gap_hours*60:.0f} min"
            )

    # 3. UNEXPLAINED: Drop much larger than expected consumption
    if estimated_pct is not None:
        expected_drop = last_sensor_pct - estimated_pct
        unexplained_drop = (
            fuel_drop_pct - expected_drop if expected_drop > 0 else fuel_drop_pct
        )

        if unexplained_drop > 8:  # >8% more than expected
            if theft_confidence < 0.7:
                theft_confidence = 0.7
                theft_type = "UNEXPLAINED_LOSS"
            reasons.append(f"Unexplained loss of {unexplained_drop:.1f}%")

    # 4. IDLE theft: Drop while engine running but not moving (siphoning)
    if truck_status == "IDLE" and fuel_drop_pct > 8:
        if theft_confidence < 0.65:
            theft_confidence = 0.65
            theft_type = "IDLE_LOSS"
            reasons.append(f"Significant drop ({fuel_drop_pct:.1f}%) while idling")

    # Only report if confidence is high enough
    if theft_confidence >= 0.6:
        logger.warning(
            f"🚨 POSSIBLE FUEL THEFT ({theft_type}): -{fuel_drop_pct:.1f}% "
            f"({fuel_drop_gal:.1f} gal) while {truck_status} for {time_gap_hours*60:.0f} min. "
            f"Confidence: {theft_confidence:.0%}"
        )
        return {
            "type": theft_type,
            "drop_pct": fuel_drop_pct,
            "drop_gal": fuel_drop_gal,
            "time_gap_hours": time_gap_hours,
            "confidence": theft_confidence,
            "reasons": reasons,
            "truck_status": truck_status,
        }

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# REFUEL PERSISTENCE & NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Cooldown tracker to avoid duplicate notifications
_refuel_notification_cooldown: Dict[str, datetime] = {}

# 🆕 v3.12.20: Pending refuels buffer for consecutive jump consolidation
# When refueling, sensor may report: 10% → 40% → 80% → 100% in quick succession
# This buffer accumulates all jumps and saves/notifies as ONE event
_pending_refuels: Dict[str, Dict] = {}
CONSECUTIVE_REFUEL_WINDOW_MINUTES = 10  # Jumps within 10 min = same refuel event


def add_pending_refuel(
    truck_id: str,
    gallons: float,
    before_pct: float,
    after_pct: float,
    timestamp: datetime,
) -> Optional[Dict]:
    """
    🆕 v3.12.20: Buffer consecutive refuel jumps into single event.

    When a truck refuels, the sensor may report multiple jumps:
    - Jump 1: 10% → 40% (+30%)
    - Jump 2: 40% → 80% (+40%)  ← within 10 min = same refuel event
    - Jump 3: 80% → 100% (+20%) ← within 10 min = same refuel event

    This accumulates all jumps. Returns finalized event when window expires.
    """
    global _pending_refuels

    now = datetime.now(timezone.utc)

    if truck_id in _pending_refuels:
        pending = _pending_refuels[truck_id]
        time_since_last = (now - pending["last_jump_time"]).total_seconds() / 60

        if time_since_last <= CONSECUTIVE_REFUEL_WINDOW_MINUTES:
            # Within window - accumulate
            pending["gallons"] += gallons
            pending["end_pct"] = after_pct
            pending["last_jump_time"] = now
            logger.info(
                f"[{truck_id}] 📊 Consecutive refuel jump: +{gallons:.1f} gal "
                f"(total: {pending['gallons']:.1f} gal, {pending['start_pct']:.1f}% → {after_pct:.1f}%)"
            )
            return None
        else:
            # Window expired - finalize previous, start new
            finalized = finalize_pending_refuel(truck_id)

            _pending_refuels[truck_id] = {
                "start_pct": before_pct,
                "end_pct": after_pct,
                "gallons": gallons,
                "start_time": timestamp,
                "last_jump_time": now,
            }
            return finalized
    else:
        # Start new pending refuel
        _pending_refuels[truck_id] = {
            "start_pct": before_pct,
            "end_pct": after_pct,
            "gallons": gallons,
            "start_time": timestamp,
            "last_jump_time": now,
        }
        return None


def finalize_pending_refuel(truck_id: str) -> Optional[Dict]:
    """
    🆕 v3.12.20: Finalize a pending refuel - returns data for DB save & notification.
    """
    global _pending_refuels

    if truck_id not in _pending_refuels:
        return None

    pending = _pending_refuels.pop(truck_id)

    return {
        "truck_id": truck_id,
        "gallons": pending["gallons"],
        "start_pct": pending["start_pct"],
        "end_pct": pending["end_pct"],
        "timestamp": pending["start_time"],
    }


def flush_stale_pending_refuels(max_age_minutes: int = 15) -> List[Dict]:
    """
    🆕 v3.12.20: Finalize any pending refuels older than max_age_minutes.
    Call periodically to ensure refuels don't stay buffered forever.
    """
    global _pending_refuels

    now = datetime.now(timezone.utc)
    stale_trucks = []
    finalized = []

    for truck_id, pending in _pending_refuels.items():
        age_minutes = (now - pending["last_jump_time"]).total_seconds() / 60
        if age_minutes > max_age_minutes:
            stale_trucks.append(truck_id)

    for truck_id in stale_trucks:
        result = finalize_pending_refuel(truck_id)
        if result:
            finalized.append(result)
            logger.info(
                f"[{truck_id}] ✅ Flushed pending refuel: +{result['gallons']:.1f} gal"
            )

    return finalized


def save_refuel_event(
    connection,
    truck_id: str,
    timestamp_utc: datetime,
    fuel_before: float,
    fuel_after: float,
    gallons_added: float,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    refuel_type: str = "NORMAL",
) -> bool:
    """
    Save refuel event to refuel_events table.

    🔧 v3.12.28: Added duplicate check to prevent double inserts.
    Checks for existing refuel within 5-minute window for same truck.

    Returns True if successfully inserted, False if duplicate or error.
    """
    try:
        with connection.cursor() as cursor:
            # 🔧 v3.12.30: Check for duplicate refuel using fuel_after percentage
            # Previous check used gallons_added ±5 gal, but Kalman drift can cause
            # different gallon calculations for same actual refuel.
            # fuel_after is more stable - same sensor reading = same after%.
            check_query = """
                SELECT id, gallons_added FROM refuel_events 
                WHERE truck_id = %s 
                  AND timestamp_utc BETWEEN %s - INTERVAL 5 MINUTE AND %s + INTERVAL 5 MINUTE
                  AND ABS(fuel_after - %s) < 2
                LIMIT 1
            """
            cursor.execute(
                check_query, (truck_id, timestamp_utc, timestamp_utc, fuel_after)
            )
            existing = cursor.fetchone()

            if existing:
                logger.info(
                    f"⏭️ Duplicate refuel skipped: {truck_id} +{gallons_added:.1f} gal "
                    f"(existing: +{existing['gallons_added']:.1f} gal at {fuel_after:.1f}%)"
                )
                return False

            # Insert new refuel event
            query = """
                INSERT INTO refuel_events 
                (timestamp_utc, truck_id, carrier_id, fuel_before, fuel_after, 
                 gallons_added, refuel_type, latitude, longitude, confidence, validated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(
                query,
                (
                    timestamp_utc,
                    truck_id,
                    "skylord",
                    fuel_before,
                    fuel_after,
                    gallons_added,
                    refuel_type,
                    latitude,
                    longitude,
                    0.9,  # High confidence for detected refuels
                    0,  # Not validated yet
                ),
            )
            connection.commit()
            logger.info(f"💾 Refuel saved to DB: {truck_id} +{gallons_added:.1f} gal")
            return True
    except Exception as e:
        logger.error(f"❌ Failed to save refuel to DB for {truck_id}: {e}")
        return False


def send_refuel_notification(
    truck_id: str,
    gallons_added: float,
    fuel_before: float,
    fuel_after: float,
    timestamp_utc: datetime,
) -> bool:
    """
    Send SMS and Email notification for refuel event.

    Uses environment variables for configuration:
    - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBERS
    - SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO/ALERT_EMAIL_TO

    Enforces 30 minute cooldown per truck to avoid spam.
    """
    global _refuel_notification_cooldown

    # Check cooldown (30 minutes)
    now = datetime.now(timezone.utc)
    last_notification = _refuel_notification_cooldown.get(truck_id)
    if last_notification:
        minutes_since = (now - last_notification).total_seconds() / 60
        if minutes_since < 30:
            logger.info(
                f"⏳ Notification cooldown active for {truck_id} ({minutes_since:.1f} min ago)"
            )
            return False

    message = (
        f"⛽ REFUEL DETECTED\n"
        f"Truck: {truck_id}\n"
        f"Added: +{gallons_added:.1f} gal\n"
        f"Before: {fuel_before:.1f}% → After: {fuel_after:.1f}%\n"
        f"Time: {timestamp_utc.strftime('%Y-%m-%d %H:%M UTC')}"
    )

    success = False

    # Try SMS via Twilio
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER")
        to_numbers = os.getenv("TWILIO_TO_NUMBERS", "")

        if account_sid and auth_token and from_number and to_numbers:
            from twilio.rest import Client

            client = Client(account_sid, auth_token)

            for to_number in to_numbers.split(","):
                to_number = to_number.strip()
                if to_number:
                    try:
                        client.messages.create(
                            body=message, from_=from_number, to=to_number
                        )
                        logger.info(f"📱 SMS sent to {to_number} for {truck_id} refuel")
                        success = True
                    except Exception as sms_err:
                        logger.error(f"❌ SMS failed to {to_number}: {sms_err}")
        else:
            logger.debug("📱 SMS not configured (missing Twilio env vars)")
    except ImportError:
        logger.warning("📱 Twilio library not installed - SMS disabled")
    except Exception as e:
        logger.error(f"❌ SMS notification error: {e}")

    # Try Email via SMTP
    try:
        import smtplib
        from email.message import EmailMessage

        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        # Support both variable names
        alert_to = os.getenv("ALERT_TO") or os.getenv("ALERT_EMAIL_TO")

        if smtp_user and smtp_pass and alert_to:
            msg = EmailMessage()
            msg["From"] = smtp_user
            msg["To"] = alert_to
            msg["Subject"] = f"⛽ Refuel Detected: {truck_id} +{gallons_added:.1f} gal"
            msg.set_content(message)

            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info(f"📧 Email sent to {alert_to} for {truck_id} refuel")
            success = True
        else:
            logger.debug("📧 Email not configured (missing SMTP env vars)")
    except Exception as e:
        logger.error(f"❌ Email notification error: {e}")

    # Update cooldown if any notification succeeded
    if success:
        _refuel_notification_cooldown[truck_id] = now

    return success


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSING FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def process_truck(
    truck_id: str,
    sensor_data: Dict,
    state_manager: StateManager,
    mpg_config: MPGConfig,
    idle_config: IdleConfig,
) -> Dict:
    """
    Full processing pipeline for a single truck

    Steps:
    1. Extract sensor values
    2. Determine truck status
    3. Calculate time delta
    4. Check emergency reset
    5. Calculate consumption
    6. Run Kalman predict/update
    7. Check for refuels
    8. Update MPG tracking
    9. Calculate idle consumption
    10. Return complete metrics
    """
    # Get estimator and states
    estimator = state_manager.get_estimator(truck_id)
    mpg_state = state_manager.get_mpg_state(truck_id)
    anchor_detector = state_manager.get_anchor_detector(truck_id)

    # Tank capacity
    tank_capacity_gal = TANK_CAPACITIES.get(truck_id, TANK_CAPACITIES["default"])
    tank_capacity_liters = tank_capacity_gal * 3.78541

    # Extract sensor values
    timestamp = sensor_data.get("timestamp", datetime.now(timezone.utc))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    speed = sensor_data.get("speed")  # mph
    rpm = sensor_data.get("rpm")
    fuel_lvl = sensor_data.get("fuel_lvl")  # Percentage
    fuel_rate = sensor_data.get("fuel_rate")  # L/h
    odometer = sensor_data.get("odometer")  # miles
    altitude = sensor_data.get("altitude")  # feet
    latitude = sensor_data.get("latitude")
    longitude = sensor_data.get("longitude")
    engine_hours = sensor_data.get("engine_hours")
    hdop = sensor_data.get("hdop")
    coolant_temp = sensor_data.get("coolant_temp")
    total_fuel_used = sensor_data.get("total_fuel_used")  # Gallons (ECU counter)
    pwr_ext = sensor_data.get("pwr_ext")  # Battery voltage (V)
    engine_load = sensor_data.get("engine_load")  # Engine load %
    # 🆕 v3.12.26: Engine Health sensors
    oil_press = sensor_data.get("oil_press")  # Oil Pressure (psi)
    oil_temp = sensor_data.get("oil_temp")  # Oil Temperature (°F)
    def_level = sensor_data.get("def_level")  # DEF Level (%)
    intake_air_temp = sensor_data.get("intake_air_temp")  # Intake Air Temp (°F)
    # 🆕 v5.3.3: Ambient temperature for weather-adjusted alerts
    ambient_temp = sensor_data.get("ambient_temp")  # Outside Air Temp (°F)
    # 🆕 v5.3.3: ECU idle fuel counter (most accurate idle measurement)
    total_idle_fuel = sensor_data.get("total_idle_fuel")  # Gallons (ECU idle counter)

    # Calculate data age
    now_utc = datetime.now(timezone.utc)
    data_age_min = (now_utc - timestamp).total_seconds() / 60.0

    # Determine truck status (enhanced with multiple sensors)
    truck_status = determine_truck_status(
        speed, rpm, fuel_rate, data_age_min, pwr_ext, engine_load, coolant_temp
    )

    # Calculate time delta from last update
    dt_hours = 0.0
    time_gap_hours = 0.0
    if estimator.last_update_time:
        time_gap_hours = (timestamp - estimator.last_update_time).total_seconds() / 3600
        dt_hours = min(time_gap_hours, 1.0)  # Cap at 1 hour for predictions

    # Sensor percentage
    sensor_pct = fuel_lvl

    # Initialize estimator if needed
    if not estimator.initialized and sensor_pct is not None:
        estimator.initialize(sensor_pct=sensor_pct)

    # Check emergency reset (high drift after long offline)
    if sensor_pct is not None and time_gap_hours > 2:
        estimator.check_emergency_reset(sensor_pct, time_gap_hours, truck_status)

    # Calculate consumption
    consumption_lph = calculate_consumption(
        speed, rpm, fuel_rate, total_fuel_used, estimator, dt_hours, truck_status
    )
    # 🔧 FIX v3.12.1: Use 'is not None' instead of truthy check
    # 0.0 is a valid consumption value, shouldn't become None
    consumption_gph = consumption_lph / 3.78541 if consumption_lph is not None else None

    # Kalman predict phase (only if reasonable time delta)
    if dt_hours > 0 and dt_hours < 1.0:
        # Calculate adaptive noise based on conditions
        Q_L = estimator.calculate_adaptive_noise(speed, altitude, timestamp)

        # Predict
        estimator.predict(
            dt_hours=dt_hours,
            consumption_lph=consumption_lph,
            speed_mph=speed,
        )

    # Check for refuel before update
    # 🔧 v3.12.19: Use last_sensor_data instead of estimator.last_fuel_lvl_pct
    # This correctly compares consecutive sensor readings, not Kalman state
    refuel_event = None
    last_sensor_pct_for_refuel = None
    if truck_id in state_manager.last_sensor_data:
        prev_data = state_manager.last_sensor_data[truck_id]
        last_sensor_pct_for_refuel = prev_data.get("fuel_lvl")

    if sensor_pct is not None:
        # 🔍 Debug: Log refuel check parameters (now using Kalman as baseline)
        kalman_pct = estimator.level_pct
        fuel_vs_kalman = sensor_pct - kalman_pct
        if fuel_vs_kalman > 10:  # Log significant jumps vs Kalman
            logger.info(
                f"[REFUEL-CHECK] {truck_id}: kalman={kalman_pct:.1f}%, sensor={sensor_pct:.1f}%, "
                f"diff={fuel_vs_kalman:.1f}%, gap={time_gap_hours*60:.1f}min"
            )

        refuel_event = detect_refuel(
            sensor_pct=sensor_pct,
            estimated_pct=kalman_pct,
            last_sensor_pct=last_sensor_pct_for_refuel,
            time_gap_hours=time_gap_hours,
            truck_status=truck_status,
            tank_capacity_gal=tank_capacity_gal,
            truck_id=truck_id,
        )

        if refuel_event:
            logger.info(
                f"🚰 [REFUEL-DETECTED] {truck_id}: {refuel_event['prev_pct']:.1f}% → {refuel_event['new_pct']:.1f}% "
                f"(+{refuel_event['increase_pct']:.1f}%, +{refuel_event.get('increase_gal', 0):.1f} gal)"
            )
            # Hard reset after refuel
            estimator.apply_refuel_reset(
                new_fuel_pct=sensor_pct,
                timestamp=timestamp,
                gallons_added=refuel_event.get("increase_gal", 0),
            )
            reset_mpg_state(mpg_state, "REFUEL", truck_id)

    # Kalman update phase
    if sensor_pct is not None and not refuel_event:
        estimator.update(sensor_pct)

    # Check for theft
    theft_event = detect_fuel_theft(
        sensor_pct=sensor_pct,
        estimated_pct=estimator.level_pct,
        last_sensor_pct=estimator.last_fuel_lvl_pct,
        truck_status=truck_status,
        time_gap_hours=time_gap_hours,
        tank_capacity_gal=tank_capacity_gal,
    )

    # Update estimator timestamp
    estimator.last_update_time = timestamp

    # Calculate estimated values
    estimated_pct = estimator.level_pct
    estimated_liters = estimator.level_liters
    estimated_gallons = estimated_liters / 3.78541

    # Sensor values (raw)
    sensor_liters = (sensor_pct / 100) * tank_capacity_liters if sensor_pct else None
    sensor_gallons = (sensor_pct / 100) * tank_capacity_gal if sensor_pct else None

    # Calculate drift
    drift_pct = 0.0
    if sensor_pct is not None and estimated_pct is not None:
        drift_pct = estimated_pct - sensor_pct
    drift_warning = "YES" if abs(drift_pct) > 7.5 else "NO"

    # MPG tracking (only for MOVING trucks)
    mpg_current = mpg_state.mpg_current
    if truck_status == "MOVING" and speed and speed > 5:
        # Calculate deltas
        delta_miles = 0.0
        delta_gallons = 0.0

        if mpg_state.last_odometer_mi is not None and odometer:
            delta_miles = odometer - mpg_state.last_odometer_mi
            if delta_miles < 0:
                delta_miles = 0.0  # Odometer reset

        if mpg_state.last_fuel_lvl_pct is not None and sensor_pct:
            fuel_drop_pct = mpg_state.last_fuel_lvl_pct - sensor_pct
            if fuel_drop_pct > 0:
                delta_gallons = (fuel_drop_pct / 100) * tank_capacity_gal
                mpg_state.fuel_source_stats["sensor"] += 1
            elif consumption_gph and dt_hours > 0:
                # Use consumption rate as fallback
                delta_gallons = consumption_gph * dt_hours
                mpg_state.fuel_source_stats["fallback"] += 1

        # Update MPG state
        if delta_miles > 0 or delta_gallons > 0:
            mpg_state = update_mpg_state(
                mpg_state, delta_miles, delta_gallons, mpg_config, truck_id
            )
            mpg_current = mpg_state.mpg_current

        # Update tracking values
        mpg_state.last_odometer_mi = odometer
        mpg_state.last_fuel_lvl_pct = sensor_pct
        mpg_state.last_timestamp = timestamp.timestamp()

    # Idle consumption calculation
    idle_gph = 0.0
    idle_method = "NOT_IDLE"
    idle_mode = None

    if truck_status == "STOPPED":
        previous_fuel_L = None
        previous_idle_fuel = None  # 🆕 v5.3.3: Track previous ECU idle counter
        previous_idle_gph = None  # 🆕 v5.4.3: For EMA smoothing

        if truck_id in state_manager.last_sensor_data:
            prev = state_manager.last_sensor_data[truck_id]
            if prev.get("fuel_lvl"):
                previous_fuel_L = (prev["fuel_lvl"] / 100) * tank_capacity_liters
            # 🆕 v5.3.3: Get previous ECU idle fuel counter
            previous_idle_fuel = prev.get("total_idle_fuel")
            # 🆕 v5.4.3: Get previous idle GPH for EMA smoothing
            previous_idle_gph = prev.get("idle_gph")

        idle_gph, method_enum = calculate_idle_consumption(
            truck_status=truck_status,
            rpm=rpm,
            fuel_rate=fuel_rate,
            current_fuel_L=estimated_liters,
            previous_fuel_L=previous_fuel_L,
            time_delta_hours=dt_hours,
            config=idle_config,
            truck_id=truck_id,
            temperature_f=coolant_temp,
            # 🆕 v5.3.3: Pass ECU idle fuel counter for highest accuracy (±0.1%)
            total_idle_fuel=total_idle_fuel,
            previous_total_idle_fuel=previous_idle_fuel,
            # 🆕 v5.4.3: Pass previous idle GPH for EMA smoothing
            previous_idle_gph=previous_idle_gph,
        )
        idle_method = method_enum.value
        idle_mode_enum = detect_idle_mode(idle_gph, idle_config)
        idle_mode = idle_mode_enum.value

    # Anchor detection
    anchor_detected = "NO"
    anchor_type = "NONE"

    if truck_status == "STOPPED":
        anchor = anchor_detector.check_static_anchor(
            timestamp=timestamp,
            speed=speed,
            rpm=rpm,
            fuel_pct=sensor_pct,
            hdop=hdop,
            drift_pct=drift_pct,
        )
        if anchor:
            anchor_detected = "YES"
            anchor_type = "STATIC"
    elif truck_status == "MOVING" and speed and speed > 30:
        anchor = anchor_detector.check_micro_anchor(
            timestamp=timestamp,
            speed=speed,
            fuel_pct=sensor_pct,
            hdop=hdop,
            altitude_ft=altitude,
            drift_pct=drift_pct,
        )
        if anchor:
            anchor_detected = "YES"
            anchor_type = "MICRO"

    # Store last sensor data for next cycle
    # 🆕 v5.4.3: Include idle_gph for EMA smoothing
    sensor_data["idle_gph"] = idle_gph
    state_manager.last_sensor_data[truck_id] = sensor_data

    # Return complete metrics
    return {
        "timestamp_utc": timestamp,
        "truck_id": truck_id,
        "carrier_id": "skylord",
        "truck_status": truck_status,
        "latitude": latitude,
        "longitude": longitude,
        "speed_mph": speed,
        "estimated_liters": round(estimated_liters, 2) if estimated_liters else None,
        "estimated_gallons": round(estimated_gallons, 2) if estimated_gallons else None,
        "estimated_pct": round(estimated_pct, 2) if estimated_pct else None,
        "sensor_pct": sensor_pct,
        "sensor_liters": round(sensor_liters, 2) if sensor_liters else None,
        "sensor_gallons": round(sensor_gallons, 2) if sensor_gallons else None,
        "consumption_lph": round(consumption_lph, 2) if consumption_lph else None,
        "consumption_gph": round(consumption_gph, 3) if consumption_gph else None,
        "mpg_current": round(mpg_current, 2) if mpg_current else None,
        "rpm": int(rpm) if rpm else None,
        "engine_hours": engine_hours,
        "odometer_mi": odometer,
        "altitude_ft": altitude,
        "hdop": hdop,
        "coolant_temp_f": coolant_temp,
        "idle_gph": round(idle_gph, 3) if idle_gph else None,
        "idle_method": idle_method,
        "idle_mode": idle_mode,
        "drift_pct": round(drift_pct, 2),
        "drift_warning": drift_warning,
        "anchor_detected": anchor_detected,
        "anchor_type": anchor_type,
        "data_age_min": round(data_age_min, 2),
        "refuel_detected": "YES" if refuel_event else "NO",
        "theft_detected": "YES" if theft_event else "NO",
        # Refuel event details for persistence and notifications
        "refuel_event": refuel_event,
        "fuel_before_pct": estimator.last_fuel_lvl_pct if refuel_event else None,
        # 🆕 v3.12.26: Engine Health sensors
        "oil_pressure_psi": oil_press,
        "oil_temp_f": oil_temp,
        "battery_voltage": pwr_ext,
        "engine_load_pct": engine_load,
        "def_level_pct": def_level,
        "intake_air_temp_f": intake_air_temp,
        # 🆕 v5.3.3: Ambient temperature for weather-adjusted alerts
        "ambient_temp_f": ambient_temp,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE INSERT
# ═══════════════════════════════════════════════════════════════════════════════


def save_to_fuel_metrics(connection, metrics: Dict) -> int:
    """Insert processed metrics into fuel_metrics table"""
    # Convert PARKED to OFFLINE for database compatibility
    # The DB schema only supports MOVING/STOPPED/OFFLINE
    db_status = metrics.get("truck_status", "OFFLINE")
    if db_status == "PARKED":
        db_status = "OFFLINE"
    metrics["truck_status"] = db_status

    try:
        with connection.cursor() as cursor:
            # 🆕 v5.3.3: Added ambient_temp_f and intake_air_temp_f columns
            query = """
                INSERT INTO fuel_metrics 
                (timestamp_utc, truck_id, carrier_id, truck_status,
                 latitude, longitude, speed_mph,
                 estimated_liters, estimated_gallons, estimated_pct,
                 sensor_pct, sensor_liters, sensor_gallons,
                 consumption_lph, consumption_gph, mpg_current,
                 rpm, engine_hours, odometer_mi,
                 altitude_ft, hdop, coolant_temp_f,
                 idle_method, idle_mode, drift_pct, drift_warning,
                 anchor_detected, anchor_type, data_age_min,
                 oil_pressure_psi, oil_temp_f, battery_voltage, 
                 engine_load_pct, def_level_pct,
                 ambient_temp_f, intake_air_temp_f)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    truck_status = VALUES(truck_status),
                    latitude = VALUES(latitude),
                    longitude = VALUES(longitude),
                    speed_mph = VALUES(speed_mph),
                    estimated_liters = VALUES(estimated_liters),
                    estimated_gallons = VALUES(estimated_gallons),
                    estimated_pct = VALUES(estimated_pct),
                    sensor_pct = VALUES(sensor_pct),
                    sensor_liters = VALUES(sensor_liters),
                    sensor_gallons = VALUES(sensor_gallons),
                    consumption_lph = VALUES(consumption_lph),
                    consumption_gph = VALUES(consumption_gph),
                    mpg_current = VALUES(mpg_current),
                    rpm = VALUES(rpm),
                    engine_hours = VALUES(engine_hours),
                    odometer_mi = VALUES(odometer_mi),
                    altitude_ft = VALUES(altitude_ft),
                    hdop = VALUES(hdop),
                    coolant_temp_f = VALUES(coolant_temp_f),
                    idle_method = VALUES(idle_method),
                    idle_mode = VALUES(idle_mode),
                    drift_pct = VALUES(drift_pct),
                    drift_warning = VALUES(drift_warning),
                    data_age_min = VALUES(data_age_min),
                    oil_pressure_psi = VALUES(oil_pressure_psi),
                    oil_temp_f = VALUES(oil_temp_f),
                    battery_voltage = VALUES(battery_voltage),
                    engine_load_pct = VALUES(engine_load_pct),
                    def_level_pct = VALUES(def_level_pct),
                    ambient_temp_f = VALUES(ambient_temp_f),
                    intake_air_temp_f = VALUES(intake_air_temp_f)
            """

            values = (
                metrics["timestamp_utc"],
                metrics["truck_id"],
                metrics["carrier_id"],
                metrics["truck_status"],
                metrics["latitude"],
                metrics["longitude"],
                metrics["speed_mph"],
                metrics["estimated_liters"],
                metrics["estimated_gallons"],
                metrics["estimated_pct"],
                metrics["sensor_pct"],
                metrics["sensor_liters"],
                metrics["sensor_gallons"],
                metrics["consumption_lph"],
                metrics["consumption_gph"],
                metrics["mpg_current"],
                metrics["rpm"],
                metrics["engine_hours"],
                metrics["odometer_mi"],
                metrics["altitude_ft"],
                metrics["hdop"],
                metrics["coolant_temp_f"],
                metrics["idle_method"],
                metrics["idle_mode"],
                metrics["drift_pct"],
                metrics["drift_warning"],
                metrics["anchor_detected"],
                metrics["anchor_type"],
                metrics["data_age_min"],
                # 🆕 v3.12.26: Engine Health sensors
                metrics.get("oil_pressure_psi"),
                metrics.get("oil_temp_f"),
                metrics.get("battery_voltage"),
                metrics.get("engine_load_pct"),
                metrics.get("def_level_pct"),
                # 🆕 v5.3.3: Temperature sensors for weather-adjusted alerts
                metrics.get("ambient_temp_f"),
                metrics.get("intake_air_temp_f"),
            )

            cursor.execute(query, values)
            return cursor.rowcount

    except Exception as e:
        logger.error(f"Error saving metrics for {metrics.get('truck_id')}: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SYNC LOOP
# ═══════════════════════════════════════════════════════════════════════════════


def get_local_connection():
    return pymysql.connect(**LOCAL_DB_CONFIG)


def sync_cycle(
    reader: WialonReader,
    local_conn,
    state_manager: StateManager,
    mpg_config: MPGConfig,
    idle_config: IdleConfig,
):
    """Single sync cycle with full Kalman processing - OPTIMIZED BATCH VERSION"""
    cycle_start = time.time()

    logger.info("═" * 70)
    logger.info(
        f"🔄 ENHANCED SYNC CYCLE - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    logger.info("═" * 70)

    total_inserted = 0
    trucks_processed = 0
    status_counts = {
        "MOVING": 0,
        "STOPPED": 0,
        "PARKED": 0,
        "OFFLINE": 0,
        "NO_DATA": 0,
    }
    refuel_count = 0

    # 🚀 OPTIMIZED: Get ALL truck data in ONE batch query
    logger.info("📊 Fetching data for all trucks in batch...")
    all_truck_data = reader.get_all_trucks_data()

    if not all_truck_data:
        logger.warning("⚠️ No truck data retrieved from Wialon")
        return

    logger.info(f"✅ Retrieved data for {len(all_truck_data)} trucks")

    # Process each truck's data
    for truck_data in all_truck_data:
        truck_id = truck_data.truck_id
        try:
            # Convert TruckSensorData to dict format expected by process_truck
            sensor_data = {
                "timestamp": truck_data.timestamp,
                "latitude": getattr(truck_data, "latitude", None),
                "longitude": getattr(truck_data, "longitude", None),
                "speed": truck_data.speed,
                "rpm": truck_data.rpm,
                "fuel_lvl": truck_data.fuel_lvl,
                "fuel_rate": truck_data.fuel_rate,
                "odometer": truck_data.odometer,
                "altitude": truck_data.altitude,
                "engine_hours": truck_data.engine_hours,
                "hdop": truck_data.hdop,
                "coolant_temp": truck_data.coolant_temp,
                "total_fuel_used": truck_data.total_fuel_used,
                "pwr_ext": truck_data.pwr_ext,
                "engine_load": truck_data.engine_load,
                "oil_press": truck_data.oil_press,
                "oil_temp": truck_data.oil_temp,
                "def_level": truck_data.def_level,
                "intake_air_temp": truck_data.intake_air_temp,
            }

            # Full processing with Kalman
            metrics = process_truck(
                truck_id=truck_id,
                sensor_data=sensor_data,
                state_manager=state_manager,
                mpg_config=mpg_config,
                idle_config=idle_config,
            )

            # Save to database
            inserted = save_to_fuel_metrics(local_conn, metrics)
            total_inserted += inserted
            trucks_processed += 1

            # Track status
            status = metrics["truck_status"]
            status_counts[status] = status_counts.get(status, 0) + 1

            # Handle refuel detection - buffer consecutive jumps
            # 🆕 v3.12.20: Use pending buffer to consolidate multi-jump refuels
            if metrics.get("refuel_detected") == "YES" and metrics.get("refuel_event"):
                refuel_count += 1
                refuel_evt = metrics["refuel_event"]

                # Calculate fuel percentages
                fuel_before = metrics.get("fuel_before_pct") or 0
                fuel_after = metrics.get("sensor_pct") or 0
                gallons_added = refuel_evt.get("increase_gal", 0)

                # Add to pending buffer instead of saving immediately
                finalized = add_pending_refuel(
                    truck_id=truck_id,
                    gallons=gallons_added,
                    before_pct=fuel_before,
                    after_pct=fuel_after,
                    timestamp=metrics["timestamp_utc"],
                )

                # If a previous refuel was finalized, save and notify
                if finalized:
                    # 🔧 v3.12.28: Only notify if save was successful (not duplicate)
                    was_saved = save_refuel_event(
                        connection=local_conn,
                        truck_id=finalized["truck_id"],
                        timestamp_utc=finalized["timestamp"],
                        fuel_before=finalized["start_pct"],
                        fuel_after=finalized["end_pct"],
                        gallons_added=finalized["gallons"],
                        latitude=metrics.get("latitude"),
                        longitude=metrics.get("longitude"),
                        refuel_type="GAP_DETECTED",
                    )
                    if was_saved:
                        send_refuel_notification(
                            truck_id=finalized["truck_id"],
                            gallons_added=finalized["gallons"],
                            fuel_before=finalized["start_pct"],
                            fuel_after=finalized["end_pct"],
                            timestamp_utc=finalized["timestamp"],
                        )

                # 🆕 v3.12.27: Process fuel events with intelligent classification
                # This differentiates THEFT from SENSOR_ISSUE by monitoring recovery
                try:
                    fuel_classifier = get_fuel_classifier()
                    last_sensor = metrics.get("fuel_before_pct") or 0
                    current_sensor = metrics.get("sensor_pct") or 0

                    if last_sensor > 0 and current_sensor > 0:
                        location = None
                        if metrics.get("latitude") and metrics.get("longitude"):
                            location = f"({metrics['latitude']:.4f}, {metrics['longitude']:.4f})"

                        # Get tank capacity for this truck
                        tank_cap = TANK_CAPACITIES.get(
                            truck_id, TANK_CAPACITIES.get("default", 200.0)
                        )

                        fuel_event = fuel_classifier.process_fuel_reading(
                            truck_id=truck_id,
                            last_fuel_pct=last_sensor,
                            current_fuel_pct=current_sensor,
                            tank_capacity_gal=tank_cap,
                            location=location,
                            truck_status=metrics.get("truck_status", "UNKNOWN"),
                        )

                        if fuel_event:
                            classification = fuel_event.get("classification")

                            if classification == "THEFT_CONFIRMED":
                                # Fuel stayed low - confirmed theft
                                logger.warning(
                                    f"🚨 {truck_id}: THEFT CONFIRMED - sending alert"
                                )
                                send_theft_confirmed_alert(
                                    truck_id=truck_id,
                                    fuel_drop_gallons=fuel_event.get("drop_gal", 0),
                                    fuel_drop_pct=fuel_event.get("drop_pct", 0),
                                    time_waited_minutes=fuel_event.get(
                                        "time_waited_minutes", 0
                                    ),
                                    location=location,
                                )

                            elif classification == "SENSOR_ISSUE":
                                # Fuel recovered - sensor problem
                                logger.info(
                                    f"🔧 {truck_id}: SENSOR ISSUE detected - sending maintenance alert"
                                )
                                recovery_info = (
                                    f"Dropped from {fuel_event.get('original_fuel_pct', 0):.1f}% "
                                    f"to {fuel_event.get('drop_fuel_pct', 0):.1f}%, "
                                    f"recovered to {fuel_event.get('current_fuel_pct', 0):.1f}%"
                                )
                                send_sensor_issue_alert(
                                    truck_id=truck_id,
                                    drop_pct=fuel_event.get("drop_pct", 0),
                                    drop_gal=fuel_event.get("drop_gal", 0),
                                    recovery_info=recovery_info,
                                    volatility=fuel_classifier.get_sensor_volatility(
                                        truck_id
                                    ),
                                )

                            elif classification == "THEFT_SUSPECTED":
                                # Extreme drop while stopped - immediate alert
                                logger.warning(
                                    f"🚨 {truck_id}: THEFT SUSPECTED (extreme drop)"
                                )
                                # This is handled by the old system already

                            elif classification == "PENDING_VERIFICATION":
                                # Drop detected, waiting for recovery check
                                logger.info(f"⏳ {truck_id}: Drop pending verification")

                            # Log all classified events
                            logger.debug(
                                f"📊 {truck_id}: Fuel event classified as {classification}"
                            )

                except Exception as e:
                    logger.error(f"Error in fuel classifier for {truck_id}: {e}")

                # Log with details
                status_emoji = {
                    "MOVING": "🚛",
                    "STOPPED": "⏸️",
                    "PARKED": "🅿️",
                    "OFFLINE": "📴",
                }.get(status, "❓")

                speed_str = (
                    f"{metrics['speed_mph']:.1f}" if metrics["speed_mph"] else "N/A"
                )
                sensor_str = (
                    f"{metrics['sensor_pct']:.1f}" if metrics["sensor_pct"] else "N/A"
                )
                kalman_str = (
                    f"{metrics['estimated_pct']:.1f}"
                    if metrics["estimated_pct"]
                    else "N/A"
                )
                drift_str = (
                    f"{metrics['drift_pct']:+.1f}" if metrics["drift_pct"] else "0.0"
                )
                mpg_str = (
                    f"{metrics['mpg_current']:.1f}" if metrics["mpg_current"] else "N/A"
                )

                logger.info(
                    f"{status_emoji} {truck_id}: {status} | "
                    f"Speed: {speed_str} | "
                    f"Sensor: {sensor_str}% | "
                    f"Kalman: {kalman_str}% | "
                    f"Drift: {drift_str}% | "
                    f"MPG: {mpg_str}"
                )
            else:
                status_counts["NO_DATA"] += 1
                logger.warning(f"⚠️ {truck_id}: No data from Wialon")

        except Exception as e:
            logger.error(f"Error processing {truck_id}: {e}")
            import traceback

            traceback.print_exc()

    # 🆕 v3.12.20: Flush any stale pending refuels (older than 15 min)
    # 🔧 v3.12.28: Only notify if save was successful (not duplicate)
    stale_refuels = flush_stale_pending_refuels(max_age_minutes=15)
    for finalized in stale_refuels:
        try:
            was_saved = save_refuel_event(
                connection=local_conn,
                truck_id=finalized["truck_id"],
                timestamp_utc=finalized["timestamp"],
                fuel_before=finalized["start_pct"],
                fuel_after=finalized["end_pct"],
                gallons_added=finalized["gallons"],
                refuel_type="GAP_DETECTED",
            )
            if was_saved:
                send_refuel_notification(
                    truck_id=finalized["truck_id"],
                    gallons_added=finalized["gallons"],
                    fuel_before=finalized["start_pct"],
                    fuel_after=finalized["end_pct"],
                    timestamp_utc=finalized["timestamp"],
                )
        except Exception as e:
            logger.error(f"Error saving stale refuel for {finalized['truck_id']}: {e}")

    # Save states periodically
    state_manager.save_states()

    cycle_duration = time.time() - cycle_start

    # Summary
    logger.info("─" * 70)
    logger.info("📊 STATUS SUMMARY:")
    logger.info(
        f"   🚛 MOVING: {status_counts['MOVING']} | "
        f"⏸️ STOPPED: {status_counts['STOPPED']} | "
        f"🅿️ PARKED: {status_counts['PARKED']} | "
        f"📴 OFFLINE: {status_counts['OFFLINE']} | "
        f"❓ NO_DATA: {status_counts['NO_DATA']}"
    )
    if refuel_count > 0:
        logger.info(f"   ⛽ REFUELS DETECTED: {refuel_count}")
    logger.info(
        f"⏱️ Cycle completed in {cycle_duration:.2f}s. "
        f"Trucks: {trucks_processed}, Records: {total_inserted}"
    )
    logger.info("")


def main():
    logger.info("🚀 ENHANCED WIALON TO MYSQL SYNC v3.0 STARTING")
    logger.info(
        "   Features: Kalman Filter, MPG Tracking, Idle Analysis, Refuel Detection"
    )

    # Initialize state manager
    state_manager = StateManager()

    # Configuration
    mpg_config = MPGConfig()
    idle_config = IdleConfig()

    # Initialize Wialon Reader
    wialon_config = WialonConfig()
    reader = WialonReader(wialon_config, TRUCK_UNIT_MAPPING)

    if not reader.connect():
        logger.error("❌ Failed to connect to Remote Wialon DB")
        return

    # Connect to Local DB
    try:
        local_conn = get_local_connection()
        logger.info("✅ Connected to Local MySQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Local MySQL: {e}")
        return

    try:
        while True:
            sync_cycle(reader, local_conn, state_manager, mpg_config, idle_config)
            time.sleep(15)  # 15 second intervals

            # Keep connection alive
            local_conn.ping(reconnect=True)

    except KeyboardInterrupt:
        logger.info("Stopping...")
        state_manager.save_states()
    finally:
        reader.disconnect()
        local_conn.close()


if __name__ == "__main__":
    main()
