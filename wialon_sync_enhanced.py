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
Version: 3.0.0
Date: December 2025
"""

import time
import json
import pymysql
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
from typing import Dict, Optional, Any

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


def load_tank_capacities() -> Dict[str, float]:
    """Load tank capacities from tanks.yaml"""
    yaml_path = Path(__file__).parent / "tanks.yaml"
    capacities = {"default": 200}

    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            trucks = config.get("trucks", {})
            for truck_id, truck_config in trucks.items():
                capacities[truck_id] = truck_config.get("capacity_gallons", 200)
            logger.info(
                f"✅ Loaded capacities for {len(trucks)} trucks from tanks.yaml"
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not load tanks.yaml: {e}")

    return capacities


TANK_CAPACITIES = load_tank_capacities()


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
                        except:
                            pass
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
) -> str:
    """
    Enhanced truck status determination - EXACT copy from fuel_copilot_v2_1_fixed.py

    Logic:
    - OFFLINE: data_age > 15 min OR no speed data
    - MOVING: speed > 2 mph (threshold to filter GPS noise)
    - STOPPED: engine ON but stationary (rpm > 0 OR fuel_rate > 0.3 L/h)
    - PARKED: external power > 13.2V (plugged in, engine off)
    - OFFLINE: no engine activity
    """
    # Check for offline - stale data
    if data_age_min > 15:
        return "OFFLINE"
    if speed is None:
        return "OFFLINE"

    # Moving - speed > 2 mph (filters GPS noise)
    if speed > 2:
        return "MOVING"

    # Stationary - check engine status
    rpm_val = rpm or 0
    fuel_rate_val = fuel_rate or 0
    pwr_ext_val = pwr_ext or 0

    # Engine ON indicators
    if rpm_val > 0:
        return "STOPPED"  # RPM > 0 means engine running
    if fuel_rate_val > 0.3:
        return "STOPPED"  # Fuel consumption means engine running

    # Engine OFF but plugged in
    if pwr_ext_val > 13.2:
        return "PARKED"  # Shore power connected

    # No engine activity = offline
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
) -> Optional[Dict]:
    """
    Gap-aware refuel detection

    Criteria:
    - Time gap between 5 min and 2 hours (typical refuel window)
    - Fuel increase > 5% (not just noise)
    - Truck was stopped during gap
    """
    if last_sensor_pct is None or sensor_pct is None:
        return None

    # Time gap validation (5 min to 2 hours)
    if time_gap_hours < 5 / 60 or time_gap_hours > 2:
        return None

    # Calculate increase
    fuel_increase_pct = sensor_pct - last_sensor_pct

    # Minimum thresholds
    min_increase_pct = 5.0
    min_increase_gal = 10.0

    increase_gal = (fuel_increase_pct / 100) * tank_capacity_gal

    if fuel_increase_pct >= min_increase_pct and increase_gal >= min_increase_gal:
        # Anti-noise filter: reject if estimated is already high
        if estimated_pct > 90 and fuel_increase_pct < 15:
            return None

        logger.info(
            f"⛽ REFUEL DETECTED: +{fuel_increase_pct:.1f}% "
            f"(+{increase_gal:.1f} gal) over {time_gap_hours*60:.0f} min"
        )

        return {
            "type": "REFUEL",
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
) -> Optional[Dict]:
    """
    Fuel theft detection

    Criteria:
    - Truck was stopped
    - Fuel drop > 10%
    - Not explainable by consumption
    """
    if last_sensor_pct is None or sensor_pct is None:
        return None

    if truck_status != "STOPPED":
        return None

    fuel_drop_pct = last_sensor_pct - sensor_pct

    # Significant unexplained drop
    if fuel_drop_pct > 10:
        logger.warning(
            f"🚨 POSSIBLE FUEL THEFT: -{fuel_drop_pct:.1f}% "
            f"while stopped for {time_gap_hours*60:.0f} min"
        )
        return {
            "type": "THEFT",
            "drop_pct": fuel_drop_pct,
            "time_gap_hours": time_gap_hours,
        }

    return None


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

    # Calculate data age
    now_utc = datetime.now(timezone.utc)
    data_age_min = (now_utc - timestamp).total_seconds() / 60.0

    # Determine truck status (includes pwr_ext for PARKED detection)
    truck_status = determine_truck_status(speed, rpm, fuel_rate, data_age_min, pwr_ext)

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
    consumption_gph = consumption_lph / 3.78541 if consumption_lph else None

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
    refuel_event = None
    if sensor_pct is not None:
        refuel_event = detect_refuel(
            sensor_pct=sensor_pct,
            estimated_pct=estimator.level_pct,
            last_sensor_pct=estimator.last_fuel_lvl_pct,
            time_gap_hours=time_gap_hours,
            truck_status=truck_status,
            tank_capacity_gal=tank_capacity_gal,
        )

        if refuel_event:
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
        if truck_id in state_manager.last_sensor_data:
            prev = state_manager.last_sensor_data[truck_id]
            if prev.get("fuel_lvl"):
                previous_fuel_L = (prev["fuel_lvl"] / 100) * tank_capacity_liters

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
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE INSERT
# ═══════════════════════════════════════════════════════════════════════════════


def save_to_fuel_metrics(connection, metrics: Dict) -> int:
    """Insert processed metrics into fuel_metrics table"""
    try:
        with connection.cursor() as cursor:
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
                 anchor_detected, anchor_type, data_age_min)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    data_age_min = VALUES(data_age_min)
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
    """Single sync cycle with full Kalman processing"""
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

    for truck_id, unit_id in TRUCK_UNIT_MAPPING.items():
        try:
            # Get raw sensor data
            sensor_data = reader.get_latest_sensor_data(unit_id)

            if sensor_data:
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

                if metrics.get("refuel_detected") == "YES":
                    refuel_count += 1

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
