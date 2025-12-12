"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              PREDICTIVE MAINTENANCE V3 - CLEAN IMPLEMENTATION                  ║
║                         December 2025 - From Scratch                           ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  DESIGN PRINCIPLES:                                                            ║
║  1. ZERO dependencies on other health engines (they crash)                     ║
║  2. Direct SQL queries - no complex ORM                                        ║
║  3. Always returns data (demo fallback if DB fails)                           ║
║  4. Simple threshold + trend analysis only                                     ║
║  5. Impossible to crash the backend                                            ║
║                                                                                ║
║  NEW IN V3:                                                                    ║
║  - Operational Context Engine (smart threshold adjustment)                     ║
║  - Nelson Rules for statistical anomaly detection                              ║
║  - Kalman Confidence Indicator                                                 ║
║  - Adaptive Q_r based on truck status                                          ║
║  - Maintenance Schedule Engine                                                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import os
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TANKS.YAML FILTER - Only analyze trucks in our fleet
# ═══════════════════════════════════════════════════════════════════════════════

# 🆕 v5.4.2: Use centralized get_allowed_trucks() from config.py
try:
    from config import get_allowed_trucks

    logger.info("[V3] Using centralized get_allowed_trucks from config.py")
except ImportError:
    logger.warning("[V3] Could not import from config, using local fallback")

    def get_allowed_trucks() -> Set[str]:
        """
        Fallback: Load allowed truck IDs from tanks.yaml.
        Prefer using config.get_allowed_trucks() instead.
        """
        try:
            tanks_path = Path(__file__).parent / "tanks.yaml"
            if tanks_path.exists():
                with open(tanks_path, "r", encoding="utf-8") as f:
                    tanks_config = yaml.safe_load(f)
                    if tanks_config and "trucks" in tanks_config:
                        allowed = set(tanks_config["trucks"].keys())
                        logger.info(
                            f"[V3] Loaded {len(allowed)} trucks from tanks.yaml"
                        )
                        return allowed
        except Exception as e:
            logger.warning(f"[V3] Could not load tanks.yaml: {e}")

        # Fallback: hardcoded list
        return {
            "VD3579",
            "JC1282",
            "JC9352",
            "NQ6975",
            "GP9677",
            "JB8004",
            "FM2416",
            "FM3679",
            "FM9838",
            "JB6858",
            "JP3281",
            "JR7099",
            "RA9250",
            "RH1522",
            "RR1272",
            "BV6395",
            "CO0681",
            "CS8087",
            "DR6664",
            "DO9356",
            "DO9693",
            "FS7166",
            "MA8159",
            "MO0195",
            "PC1280",
            "RD5229",
            "RR3094",
            "RT9127",
            "SG5760",
            "YM6023",
            "MJ9547",
            "FM3363",
            "GC9751",
            "LV1422",
            "LC6799",
            "RC6625",
            "FF7702",
            "OG2033",
            "OS3717",
            "EM8514",
            "MR7679",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONAL CONTEXT ENGINE - THE COMPETITIVE ADVANTAGE
# ═══════════════════════════════════════════════════════════════════════════════
# Geotab/Samsara: "Coolant 210°F = ALERT" (always)
# YOUR SYSTEM: "Coolant 210°F + climbing grade + load 85% = NORMAL"
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class OperationalContext:
    """Context that affects what's 'normal' for sensor readings"""

    mode: str  # "normal", "grade_climbing", "heavy_haul", "idle", "cold_start"
    speed: float = 0.0
    rpm: float = 0.0
    engine_load: float = 0.0
    altitude_delta: float = 0.0  # positive = climbing
    ambient_temp: float = 70.0

    # Threshold adjustments based on context
    coolant_temp_adjustment: float = 0.0  # Add to normal threshold
    oil_temp_adjustment: float = 0.0
    oil_press_adjustment: float = 0.0

    explanation: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def detect_operational_context(
    sensors: Dict[str, float], prev_altitude: Optional[float] = None
) -> OperationalContext:
    """
    Analyze current sensor readings to determine operational context.
    This is what makes your system smarter than Geotab/Samsara.
    """
    speed = sensors.get("speed", 0) or 0
    rpm = sensors.get("rpm", 0) or 0
    engine_load = sensors.get("engine_load", 0) or 0
    altitude = sensors.get("altitude", 0) or 0
    air_temp = sensors.get("air_temp", sensors.get("intake_air_temp", 70)) or 70

    # Calculate altitude delta if we have previous reading
    altitude_delta = 0.0
    if prev_altitude is not None and altitude:
        altitude_delta = altitude - prev_altitude

    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT DETECTION LOGIC
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. GRADE CLIMBING: High load + low speed + moderate RPM + altitude increasing
    if engine_load > 65 and speed < 50 and 1200 < rpm < 1900 and altitude_delta > 0:
        return OperationalContext(
            mode="grade_climbing",
            speed=speed,
            rpm=rpm,
            engine_load=engine_load,
            altitude_delta=altitude_delta,
            ambient_temp=air_temp,
            coolant_temp_adjustment=15.0,  # Allow 15°F higher coolant temp
            oil_temp_adjustment=10.0,  # Allow 10°F higher oil temp
            oil_press_adjustment=-5.0,  # Oil pressure can be 5 PSI lower under load
            explanation="Climbing grade with load - elevated temps are expected",
        )

    # 2. HEAVY HAUL: Very high load + moderate speed (flat ground hauling)
    if engine_load > 75 and speed > 30:
        return OperationalContext(
            mode="heavy_haul",
            speed=speed,
            rpm=rpm,
            engine_load=engine_load,
            altitude_delta=altitude_delta,
            ambient_temp=air_temp,
            coolant_temp_adjustment=10.0,
            oil_temp_adjustment=8.0,
            oil_press_adjustment=-3.0,
            explanation="Heavy load conditions - slightly elevated temps are normal",
        )

    # 3. IDLE: Very low speed + low RPM
    if speed < 3 and 0 < rpm < 900:
        return OperationalContext(
            mode="idle",
            speed=speed,
            rpm=rpm,
            engine_load=engine_load,
            altitude_delta=altitude_delta,
            ambient_temp=air_temp,
            coolant_temp_adjustment=-5.0,  # STRICTER threshold at idle
            oil_temp_adjustment=0.0,
            oil_press_adjustment=0.0,  # Oil pressure should be normal at idle
            explanation="Idling - cooling system should maintain normal temps",
        )

    # 4. COLD START: Low coolant temp + low oil temp (engine warming up)
    coolant = sensors.get("cool_temp", 180) or 180
    oil_temp = sensors.get("oil_temp", 180) or 180
    if coolant < 160 or oil_temp < 150:
        return OperationalContext(
            mode="cold_start",
            speed=speed,
            rpm=rpm,
            engine_load=engine_load,
            altitude_delta=altitude_delta,
            ambient_temp=air_temp,
            coolant_temp_adjustment=0.0,
            oil_temp_adjustment=0.0,
            oil_press_adjustment=10.0,  # Oil pressure can be higher when cold (thicker oil)
            explanation="Engine warming up - readings may be outside normal range temporarily",
        )

    # 5. HOT AMBIENT: Adjust for hot weather
    if air_temp > 95:
        return OperationalContext(
            mode="hot_ambient",
            speed=speed,
            rpm=rpm,
            engine_load=engine_load,
            altitude_delta=altitude_delta,
            ambient_temp=air_temp,
            coolant_temp_adjustment=8.0,  # Allow slightly higher temps in hot weather
            oil_temp_adjustment=5.0,
            oil_press_adjustment=0.0,
            explanation=f"Hot ambient temperature ({air_temp}°F) - slightly elevated engine temps expected",
        )

    # 6. NORMAL OPERATION
    return OperationalContext(
        mode="normal",
        speed=speed,
        rpm=rpm,
        engine_load=engine_load,
        altitude_delta=altitude_delta,
        ambient_temp=air_temp,
        coolant_temp_adjustment=0.0,
        oil_temp_adjustment=0.0,
        oil_press_adjustment=0.0,
        explanation="Normal operating conditions",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NELSON RULES - STATISTICAL ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
# Detects patterns BEFORE they cross thresholds
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class NelsonViolation:
    rule: int
    rule_name: str
    description: str
    severity: str
    sensor: str
    values: List[float]


def check_nelson_rules(values: List[float], sensor_name: str) -> List[NelsonViolation]:
    """
    Check Nelson Rules for statistical process control.
    These detect anomalies BEFORE they cross thresholds.

    Rules implemented:
    - Rule 1: One point > 3σ from mean (extreme outlier)
    - Rule 2: Nine points in a row on same side of mean (shift)
    - Rule 3: Six points in a row monotonically increasing/decreasing (trend)
    """
    if len(values) < 10:
        return []

    violations = []

    try:
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)

        if stdev == 0:  # All values identical
            return []

        # ═══════════════════════════════════════════════════════════════════════
        # RULE 1: One point more than 3σ from mean
        # ═══════════════════════════════════════════════════════════════════════
        latest = values[-1]
        z_score = abs(latest - mean) / stdev
        if z_score > 3:
            violations.append(
                NelsonViolation(
                    rule=1,
                    rule_name="Extreme Outlier",
                    description=f"Current value ({latest:.1f}) is {z_score:.1f}σ from mean ({mean:.1f})",
                    severity="high",
                    sensor=sensor_name,
                    values=[latest],
                )
            )

        # ═══════════════════════════════════════════════════════════════════════
        # RULE 2: Nine points in a row on same side of mean
        # ═══════════════════════════════════════════════════════════════════════
        if len(values) >= 9:
            last_9 = values[-9:]
            above_mean = sum(1 for v in last_9 if v > mean)
            below_mean = sum(1 for v in last_9 if v < mean)

            if above_mean == 9:
                violations.append(
                    NelsonViolation(
                        rule=2,
                        rule_name="Mean Shift (High)",
                        description=f"9 consecutive readings above average - possible sensor drift or system change",
                        severity="medium",
                        sensor=sensor_name,
                        values=last_9,
                    )
                )
            elif below_mean == 9:
                violations.append(
                    NelsonViolation(
                        rule=2,
                        rule_name="Mean Shift (Low)",
                        description=f"9 consecutive readings below average - possible sensor drift or degradation",
                        severity="medium",
                        sensor=sensor_name,
                        values=last_9,
                    )
                )

        # ═══════════════════════════════════════════════════════════════════════
        # RULE 3: Six points monotonically increasing or decreasing
        # ═══════════════════════════════════════════════════════════════════════
        if len(values) >= 6:
            last_6 = values[-6:]

            # Check if strictly increasing
            is_increasing = all(last_6[i] < last_6[i + 1] for i in range(5))
            # Check if strictly decreasing
            is_decreasing = all(last_6[i] > last_6[i + 1] for i in range(5))

            if is_increasing:
                violations.append(
                    NelsonViolation(
                        rule=3,
                        rule_name="Upward Trend",
                        description=f"6 consecutive increases detected - monitor for continued rise",
                        severity="medium",
                        sensor=sensor_name,
                        values=last_6,
                    )
                )
            elif is_decreasing:
                violations.append(
                    NelsonViolation(
                        rule=3,
                        rule_name="Downward Trend",
                        description=f"6 consecutive decreases detected - monitor for continued decline",
                        severity="medium",
                        sensor=sensor_name,
                        values=last_6,
                    )
                )

    except Exception as e:
        logger.warning(f"Nelson rules check failed for {sensor_name}: {e}")

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
# KALMAN CONFIDENCE INDICATOR
# ═══════════════════════════════════════════════════════════════════════════════


def get_kalman_confidence(P: float) -> Dict[str, Any]:
    """
    Convert Kalman filter covariance (P) to confidence level.
    Lower P = higher confidence in the estimate.
    """
    if P < 0.5:
        return {
            "level": "HIGH",
            "score": 95,
            "color": "green",
            "description": "Highly confident estimate based on consistent sensor data",
        }
    elif P < 2.0:
        return {
            "level": "MEDIUM",
            "score": 75,
            "color": "yellow",
            "description": "Moderate confidence - some sensor variability detected",
        }
    elif P < 5.0:
        return {
            "level": "LOW",
            "score": 50,
            "color": "orange",
            "description": "Low confidence - high sensor variability or limited data",
        }
    else:
        return {
            "level": "VERY_LOW",
            "score": 25,
            "color": "red",
            "description": "Very low confidence - sensor data unreliable or insufficient",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE Q_r (Process Noise) - KALMAN FILTER IMPROVEMENT
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_adaptive_Q_r(truck_status: str, consumption_lph: float = 0.0) -> float:
    """
    Calculate adaptive process noise based on truck operational state.

    - PARKED: Very low process noise (fuel shouldn't change)
    - STOPPED/IDLE: Low process noise (only idle consumption)
    - MOVING: Higher process noise (active consumption)

    This improves Kalman filter accuracy by adjusting expectations
    based on what the truck is actually doing.
    """
    if truck_status == "PARKED":
        return 0.01  # Almost no expected change
    elif truck_status == "STOPPED":
        return 0.05  # Small idle consumption
    elif truck_status == "IDLE":
        return 0.05 + (consumption_lph / 100) * 0.02
    else:  # MOVING
        # Base + proportional to consumption rate
        return 0.1 + (consumption_lph / 50) * 0.1


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE SCHEDULE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MaintenanceItem:
    type: str  # "oil_change", "service", "def_fill", etc.
    title: str
    due_in_miles: Optional[int]
    due_in_hours: Optional[int]
    urgency: str  # "overdue", "due_soon", "upcoming", "ok"
    message: str

    def to_dict(self) -> Dict:
        return asdict(self)


# Maintenance intervals for Class 8 trucks (Freightliner/Kenworth standards)
MAINTENANCE_INTERVALS = {
    "oil_change": {
        "miles": 25000,
        "hours": 500,
        "title": "Oil Change",
        "description": "Engine oil and filter change",
    },
    "fuel_filter": {
        "miles": 30000,
        "hours": 600,
        "title": "Fuel Filter",
        "description": "Fuel filter replacement",
    },
    "air_filter": {
        "miles": 50000,
        "hours": 1000,
        "title": "Air Filter",
        "description": "Air filter inspection/replacement",
    },
    "transmission_service": {
        "miles": 100000,
        "hours": 2000,
        "title": "Transmission Service",
        "description": "Transmission fluid and filter",
    },
    "coolant_flush": {
        "miles": 150000,
        "hours": 3000,
        "title": "Coolant Flush",
        "description": "Cooling system flush and refill",
    },
}


def calculate_maintenance_schedule(
    current_odometer: float,
    current_engine_hours: float,
    last_service_odometer: Optional[float] = None,
    last_service_hours: Optional[float] = None,
) -> List[MaintenanceItem]:
    """
    Calculate upcoming maintenance items based on odometer and engine hours.
    """
    items = []

    # Default: assume last service was at reasonable intervals if not provided
    if last_service_odometer is None:
        # Estimate based on typical service interval
        last_service_odometer = max(0, current_odometer - 20000)
    if last_service_hours is None:
        last_service_hours = max(0, current_engine_hours - 400)

    for maint_type, config in MAINTENANCE_INTERVALS.items():
        miles_since = current_odometer - last_service_odometer
        hours_since = current_engine_hours - last_service_hours

        miles_remaining = config["miles"] - miles_since
        hours_remaining = config["hours"] - hours_since

        # Use whichever comes first
        if miles_remaining <= 0 or hours_remaining <= 0:
            urgency = "overdue"
            message = f"OVERDUE by {abs(min(miles_remaining, 0)):,.0f} miles or {abs(min(hours_remaining, 0)):,.0f} hours"
        elif (
            miles_remaining < config["miles"] * 0.1
            or hours_remaining < config["hours"] * 0.1
        ):
            urgency = "due_soon"
            message = (
                f"Due in {miles_remaining:,.0f} miles or {hours_remaining:,.0f} hours"
            )
        elif (
            miles_remaining < config["miles"] * 0.25
            or hours_remaining < config["hours"] * 0.25
        ):
            urgency = "upcoming"
            message = f"Upcoming in {miles_remaining:,.0f} miles or {hours_remaining:,.0f} hours"
        else:
            urgency = "ok"
            message = f"Next service in {miles_remaining:,.0f} miles or {hours_remaining:,.0f} hours"

        items.append(
            MaintenanceItem(
                type=maint_type,
                title=config["title"],
                due_in_miles=int(miles_remaining) if miles_remaining > 0 else 0,
                due_in_hours=int(hours_remaining) if hours_remaining > 0 else 0,
                urgency=urgency,
                message=message,
            )
        )

    # Sort by urgency
    urgency_order = {"overdue": 0, "due_soon": 1, "upcoming": 2, "ok": 3}
    items.sort(key=lambda x: urgency_order.get(x.urgency, 4))

    return items


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR THRESHOLDS - Based on J1939 standards for Class 8 trucks
# ═══════════════════════════════════════════════════════════════════════════════

SENSOR_THRESHOLDS = {
    "oil_press": {
        "unit": "psi",
        "critical_low": 15,
        "warning_low": 25,
        "normal_min": 30,
        "normal_max": 70,
        "description": "Engine Oil Pressure",
        "critical_action": "STOP ENGINE - Check oil level and pump immediately",
        "warning_action": "Schedule oil system inspection within 24 hours",
        "failure_cost": 40000,  # Engine replacement
        "prevention_cost": 2500,  # Oil pump service
    },
    "cool_temp": {
        "unit": "°F",
        "warning_high": 220,
        "critical_high": 230,
        "normal_min": 180,
        "normal_max": 210,
        "cold_warning": 140,
        "description": "Coolant Temperature",
        "critical_action": "PULL OVER - Risk of engine damage from overheating",
        "warning_action": "Check coolant level, thermostat, and radiator",
        "failure_cost": 25000,  # Head gasket + engine damage
        "prevention_cost": 1500,  # Cooling system service
    },
    "oil_temp": {
        "unit": "°F",
        "warning_high": 250,
        "critical_high": 260,
        "normal_min": 180,
        "normal_max": 240,
        "description": "Engine Oil Temperature",
        "critical_action": "Reduce load - Oil viscosity compromised",
        "warning_action": "Check oil cooler and cooling system",
        "failure_cost": 15000,
        "prevention_cost": 800,
    },
    "pwr_ext": {
        "unit": "V",
        "critical_low": 11.5,
        "warning_low": 12.4,
        "normal_min": 13.2,
        "normal_max": 14.8,
        "warning_high": 15.2,
        "critical_high": 16.0,
        "description": "Battery/Charging System",
        "critical_action": "Check alternator - Battery not charging",
        "warning_action": "Schedule electrical system inspection",
        "failure_cost": 3000,  # Roadside + tow + alternator
        "prevention_cost": 400,  # Battery + alternator check
    },
    "def_level": {
        "unit": "%",
        "critical_low": 5,
        "warning_low": 15,
        "normal_min": 20,
        "description": "DEF Level",
        "critical_action": "REFILL DEF NOW - Engine derate imminent",
        "warning_action": "Plan DEF refill within 24 hours",
        "failure_cost": 2000,  # Derate + lost time
        "prevention_cost": 100,  # DEF refill
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Alert:
    truck_id: str
    sensor: str
    severity: str
    title: str
    message: str
    current_value: float
    threshold: float
    action: str
    potential_cost: int = 0
    prevention_cost: int = 0
    trend_info: Optional[str] = None
    context_suppressed: bool = False  # True if alert would have fired without context

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TruckHealth:
    truck_id: str
    health_score: int
    status: str
    sensors: Dict[str, float]
    alerts: List[Dict]
    last_updated: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FleetHealthReport:
    total_trucks: int
    healthy_count: int
    warning_count: int
    critical_count: int
    average_score: float
    total_potential_savings: int
    trucks: List[Dict]
    all_alerts: List[Dict]
    all_anomalies: List[Dict]  # Nelson rule violations
    suppressed_alerts_count: int  # Alerts prevented by operational context
    generated_at: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE HELPERS - USE EXISTING CONNECTION POOL
# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL FIX v5.3.2: Don't create individual connections!
# Use the existing database_pool.py to prevent connection exhaustion.
# ═══════════════════════════════════════════════════════════════════════════════


def execute_wialon_query(query: str, params: Optional[dict] = None) -> list:
    """
    Execute query on Wialon database using connection pool.
    Returns list of dict rows or empty list on error.

    🔒 v5.3.3: Now uses dict params for named parameter binding (SQLAlchemy)
    """
    try:
        from database_pool import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))
            # Convert to list of dicts
            rows = [dict(row._mapping) for row in result.fetchall()]
            return rows
    except Exception as e:
        logger.warning(f"[V3] Wialon query error: {e}")
        return []


def execute_fuel_query(query: str, params: tuple = None) -> list:
    """
    Execute query on fuel_copilot database using connection pool.
    Returns list of dict rows or empty list on error.

    NOTE: Uses centralized connection pool from database_pool.py
    to prevent connection exhaustion (BUG #2 FIX from audit v5.4)
    """
    try:
        from database_pool import execute_local_query

        return execute_local_query(query, params)
    except Exception as e:
        logger.warning(f"[V3] Fuel DB query error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR DATA FETCHING - USING CONNECTION POOL
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_current_sensors_from_wialon() -> Dict[str, Dict[str, float]]:
    """
    Fetch latest sensor readings from Wialon using connection pool.
    Returns dict: {truck_id: {sensor_name: value}}
    """
    query = """
        SELECT 
            s.n as truck_name,
            s.p as param,
            s.value,
            s.m as epoch
        FROM sensors s
        INNER JOIN (
            SELECT unit, p, MAX(m) as max_epoch
            FROM sensors
            WHERE m >= UNIX_TIMESTAMP() - 7200
            AND p IN ('oil_press', 'cool_temp', 'oil_temp', 'pwr_ext', 
                      'def_level', 'rpm', 'engine_load', 'fuel_rate', 'speed',
                      'altitude', 'air_temp', 'intake_air_temp', 'odom', 'engine_hours')
            GROUP BY unit, p
        ) latest ON s.unit = latest.unit AND s.p = latest.p AND s.m = latest.max_epoch
        WHERE s.m >= UNIX_TIMESTAMP() - 7200
    """

    rows = execute_wialon_query(query)
    if not rows:
        logger.warning("[V3] No sensor data from Wialon, using demo data")
        return {}

    trucks: Dict[str, Dict[str, float]] = {}
    for row in rows:
        truck_id = row.get("truck_name")
        if not truck_id:
            continue

        if truck_id not in trucks:
            trucks[truck_id] = {}

        param = row.get("param")
        value = row.get("value")

        if value is not None and param:
            trucks[truck_id][param] = float(value)

    logger.info(f"[V3] Fetched sensors for {len(trucks)} trucks from Wialon")
    return trucks


def fetch_current_sensors_from_fuel_db() -> Dict[str, Dict[str, float]]:
    """
    Fallback: fetch sensor data from fuel_metrics table.
    🔧 v5.3.6: Enhanced to include all available sensors, not just fuel_level/speed
    """
    query = """
        SELECT 
            t1.truck_id,
            t1.sensor_pct as fuel_level,
            t1.speed_mph as speed,
            t1.rpm,
            t1.coolant_temp_f as cool_temp,
            t1.consumption_gph as fuel_rate,
            t1.altitude_ft as altitude,
            t1.oil_pressure_psi as oil_press,
            t1.battery_voltage as pwr_ext,
            t1.def_level_pct as def_level,
            t1.engine_load_pct as engine_load,
            t1.oil_temp_f as oil_temp,
            t1.intake_air_temp_f as intake_air_temp,
            t1.ambient_temp_f as air_temp,
            t1.truck_status,
            t1.timestamp_utc
        FROM fuel_metrics t1
        INNER JOIN (
            SELECT truck_id, MAX(id) as max_id
            FROM fuel_metrics
            WHERE timestamp_utc >= NOW() - INTERVAL 2 HOUR
            GROUP BY truck_id
        ) t2 ON t1.truck_id = t2.truck_id AND t1.id = t2.max_id
    """

    rows = execute_fuel_query(query)
    if not rows:
        return {}

    trucks: Dict[str, Dict[str, float]] = {}
    for row in rows:
        truck_id = row.get("truck_id")
        if truck_id:
            # Include all non-null sensor values
            sensors = {}
            sensor_mappings = [
                ("fuel_level", "fuel_level"),
                ("speed", "speed"),
                ("rpm", "rpm"),
                ("cool_temp", "cool_temp"),
                ("fuel_rate", "fuel_rate"),
                ("altitude", "altitude"),
                ("oil_press", "oil_press"),
                ("pwr_ext", "pwr_ext"),
                ("def_level", "def_level"),
                ("engine_load", "engine_load"),
                ("oil_temp", "oil_temp"),
                ("intake_air_temp", "intake_air_temp"),
                ("air_temp", "air_temp"),
            ]
            for db_key, sensor_key in sensor_mappings:
                val = row.get(db_key)
                if val is not None:
                    sensors[sensor_key] = float(val)

            trucks[truck_id] = sensors

    logger.info(f"[V3] Fetched sensors for {len(trucks)} trucks from fuel_metrics")
    return trucks


def fetch_historical_sensors(
    truck_id: str, days: int = 7
) -> Dict[str, List[Tuple[datetime, float]]]:
    """
    Fetch historical sensor data for trend analysis.
    Returns: {sensor_name: [(timestamp, value), ...]}

    🔒 v5.3.3: Fixed SQL injection - now uses parameterized query
    """
    # Use parameterized query to prevent SQL injection
    seconds_back = days * 86400
    query = """
        SELECT p as param, value, m as epoch
        FROM sensors
        WHERE n = :truck_id
        AND m >= UNIX_TIMESTAMP() - :seconds_back
        AND p IN ('oil_press', 'cool_temp', 'oil_temp', 'pwr_ext')
        ORDER BY m ASC
    """

    rows = execute_wialon_query(
        query, {"truck_id": truck_id, "seconds_back": seconds_back}
    )
    if not rows:
        return {}

    history: Dict[str, List[Tuple[datetime, float]]] = {}
    for row in rows:
        param = row.get("param")
        if not param:
            continue

        if param not in history:
            history[param] = []

        epoch = row.get("epoch")
        value = row.get("value")
        if epoch and value is not None:
            ts = datetime.fromtimestamp(epoch, tz=timezone.utc)
            history[param].append((ts, float(value)))

    return history


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_sensor_thresholds(
    truck_id: str,
    sensors: Dict[str, float],
    context: Optional[OperationalContext] = None,
) -> Tuple[List[Alert], int]:
    """
    Check current sensor values against thresholds.
    NOW WITH OPERATIONAL CONTEXT - adjusts thresholds based on conditions.

    This is what makes your system SMARTER than Geotab/Samsara.

    Returns: (alerts, suppressed_count)
    """
    alerts = []
    suppressed_count = 0

    # Get operational context if not provided
    if context is None:
        context = detect_operational_context(sensors)

    for sensor_name, config in SENSOR_THRESHOLDS.items():
        value = sensors.get(sensor_name)
        if value is None:
            continue

        # ═══════════════════════════════════════════════════════════════════════
        # APPLY CONTEXT ADJUSTMENTS - THE KEY DIFFERENTIATOR
        # ═══════════════════════════════════════════════════════════════════════
        adjusted_warning_high = config.get("warning_high", 999)
        adjusted_critical_high = config.get("critical_high", 999)
        adjusted_warning_low = config.get("warning_low", -999)
        adjusted_critical_low = config.get("critical_low", -999)

        # Apply context-based adjustments
        if sensor_name == "cool_temp":
            adjusted_warning_high += context.coolant_temp_adjustment
            adjusted_critical_high += context.coolant_temp_adjustment
        elif sensor_name == "oil_temp":
            adjusted_warning_high += context.oil_temp_adjustment
            adjusted_critical_high += context.oil_temp_adjustment
        elif sensor_name == "oil_press":
            adjusted_warning_low += context.oil_press_adjustment
            adjusted_critical_low += context.oil_press_adjustment

        # Track if alert was suppressed by context
        suppressed_by_context = False
        original_would_alert = False

        # ═══════════════════════════════════════════════════════════════════════
        # CHECK THRESHOLDS (with adjusted values)
        # ═══════════════════════════════════════════════════════════════════════

        # Check critical low
        if "critical_low" in config:
            original_would_alert = value < config["critical_low"]
            if value < adjusted_critical_low:
                alerts.append(
                    Alert(
                        truck_id=truck_id,
                        sensor=sensor_name,
                        severity=Severity.CRITICAL.value,
                        title=f"Critical Low {config['description']}",
                        message=f"{config['description']} at {value:.1f} {config['unit']} - below critical threshold of {adjusted_critical_low:.0f}",
                        current_value=value,
                        threshold=adjusted_critical_low,
                        action=config["critical_action"],
                        potential_cost=config.get("failure_cost", 0),
                        prevention_cost=config.get("prevention_cost", 0),
                    )
                )
            elif original_would_alert and value >= adjusted_critical_low:
                suppressed_by_context = True

        # Check warning low
        if "warning_low" in config and not any(a.sensor == sensor_name for a in alerts):
            original_would_alert = value < config["warning_low"]
            if value < adjusted_warning_low:
                alerts.append(
                    Alert(
                        truck_id=truck_id,
                        sensor=sensor_name,
                        severity=Severity.HIGH.value,
                        title=f"Low {config['description']}",
                        message=f"{config['description']} at {value:.1f} {config['unit']} - below warning threshold of {adjusted_warning_low:.0f}",
                        current_value=value,
                        threshold=adjusted_warning_low,
                        action=config["warning_action"],
                        potential_cost=config.get("failure_cost", 0),
                        prevention_cost=config.get("prevention_cost", 0),
                    )
                )
            elif original_would_alert and value >= adjusted_warning_low:
                suppressed_by_context = True

        # Check critical high
        if "critical_high" in config:
            original_would_alert = value > config["critical_high"]
            if value > adjusted_critical_high:
                alerts.append(
                    Alert(
                        truck_id=truck_id,
                        sensor=sensor_name,
                        severity=Severity.CRITICAL.value,
                        title=f"Critical High {config['description']}",
                        message=f"{config['description']} at {value:.1f} {config['unit']} - above critical threshold of {adjusted_critical_high:.0f}",
                        current_value=value,
                        threshold=adjusted_critical_high,
                        action=config["critical_action"],
                        potential_cost=config.get("failure_cost", 0),
                        prevention_cost=config.get("prevention_cost", 0),
                    )
                )
            elif original_would_alert and value <= adjusted_critical_high:
                suppressed_by_context = True

        # Check warning high
        if "warning_high" in config and not any(
            a.sensor == sensor_name for a in alerts
        ):
            original_would_alert = value > config["warning_high"]
            if value > adjusted_warning_high:
                alerts.append(
                    Alert(
                        truck_id=truck_id,
                        sensor=sensor_name,
                        severity=Severity.HIGH.value,
                        title=f"High {config['description']}",
                        message=f"{config['description']} at {value:.1f} {config['unit']} - above warning threshold of {adjusted_warning_high:.0f}",
                        current_value=value,
                        threshold=adjusted_warning_high,
                        action=config["warning_action"],
                        potential_cost=config.get("failure_cost", 0),
                        prevention_cost=config.get("prevention_cost", 0),
                    )
                )
            elif original_would_alert and value <= adjusted_warning_high:
                suppressed_by_context = True

        # ═══════════════════════════════════════════════════════════════════════
        # LOG SUPPRESSED ALERTS (for debugging/analytics)
        # ═══════════════════════════════════════════════════════════════════════
        if suppressed_by_context:
            suppressed_count += 1
            logger.info(
                f"[CONTEXT] Alert suppressed for {truck_id}/{sensor_name}: "
                f"value={value:.1f}, mode={context.mode}, reason={context.explanation}"
            )

    return alerts, suppressed_count


def analyze_trends(
    truck_id: str, history: Dict[str, List[Tuple[datetime, float]]]
) -> List[Alert]:
    """
    Analyze 7-day trends to predict future issues.
    Uses simple linear regression.
    """
    alerts = []

    for sensor_name, readings in history.items():
        if len(readings) < 20:  # Need enough data points
            continue

        config = SENSOR_THRESHOLDS.get(sensor_name)
        if not config:
            continue

        # Calculate trend (simple linear regression)
        try:
            # Convert to days from first reading
            first_time = readings[0][0]
            x = [(r[0] - first_time).total_seconds() / 86400 for r in readings]
            y = [r[1] for r in readings]

            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(xi**2 for xi in x)

            # Slope calculation
            denominator = n * sum_x2 - sum_x**2
            if denominator == 0:
                continue

            slope = (n * sum_xy - sum_x * sum_y) / denominator
            current_value = y[-1]

            # For sensors where LOW is bad (oil_press, pwr_ext)
            if sensor_name in ["oil_press", "pwr_ext", "def_level"]:
                if slope < -0.5:  # Declining trend
                    warning_threshold = config.get("warning_low", 0)
                    if warning_threshold and current_value > warning_threshold:
                        days_to_warning = (current_value - warning_threshold) / abs(
                            slope
                        )
                        if 0 < days_to_warning < 14:
                            alerts.append(
                                Alert(
                                    truck_id=truck_id,
                                    sensor=sensor_name,
                                    severity=Severity.MEDIUM.value,
                                    title=f"{config['description']} Declining",
                                    message=f"{config['description']} trending down {abs(slope):.2f} {config['unit']}/day. May reach warning level in {int(days_to_warning)} days.",
                                    current_value=current_value,
                                    threshold=warning_threshold,
                                    action=f"Monitor closely. {config['warning_action']}",
                                    potential_cost=config.get("failure_cost", 0),
                                    prevention_cost=config.get("prevention_cost", 0),
                                    trend_info=f"Declining {abs(slope):.2f}/day",
                                )
                            )

            # For sensors where HIGH is bad (cool_temp, oil_temp)
            elif sensor_name in ["cool_temp", "oil_temp"]:
                if slope > 0.5:  # Rising trend
                    warning_threshold = config.get("warning_high", 999)
                    if current_value < warning_threshold:
                        days_to_warning = (warning_threshold - current_value) / slope
                        if 0 < days_to_warning < 14:
                            alerts.append(
                                Alert(
                                    truck_id=truck_id,
                                    sensor=sensor_name,
                                    severity=Severity.MEDIUM.value,
                                    title=f"{config['description']} Rising",
                                    message=f"{config['description']} trending up {slope:.2f} {config['unit']}/day. May reach warning level in {int(days_to_warning)} days.",
                                    current_value=current_value,
                                    threshold=warning_threshold,
                                    action=f"Monitor closely. {config['warning_action']}",
                                    potential_cost=config.get("failure_cost", 0),
                                    prevention_cost=config.get("prevention_cost", 0),
                                    trend_info=f"Rising {slope:.2f}/day",
                                )
                            )

        except Exception as e:
            logger.warning(f"Trend analysis failed for {truck_id}/{sensor_name}: {e}")
            continue

    return alerts


def calculate_health_score(
    sensors: Dict[str, float], alerts: List[Alert]
) -> Tuple[int, str]:
    """
    Calculate overall health score (0-100) with explanation.
    🔧 v5.3.6: Returns (score, explanation) for UI display

    Scoring breakdown:
    - Base: 100 points
    - Critical alert: -30 each
    - High alert: -15 each
    - Medium alert: -5 each
    - Low alert: -2 each
    - Missing critical sensors: -3 each (reduced from -5)
    """
    score = 100
    deductions = []

    # Deduct for alerts
    for alert in alerts:
        if alert.severity == Severity.CRITICAL.value:
            score -= 30
            deductions.append(f"Critical: {alert.message[:50]}")
        elif alert.severity == Severity.HIGH.value:
            score -= 15
            deductions.append(f"High: {alert.message[:50]}")
        elif alert.severity == Severity.MEDIUM.value:
            score -= 5
            deductions.append(f"Medium: {alert.message[:50]}")
        elif alert.severity == Severity.LOW.value:
            score -= 2

    # Check for important sensors (reduced penalty)
    important_sensors = ["oil_press", "cool_temp", "pwr_ext"]
    missing_sensors = []
    for s in important_sensors:
        if s not in sensors or sensors[s] is None:
            missing_sensors.append(s)
            score -= 3  # Reduced from -5

    if missing_sensors:
        sensor_names = {
            "oil_press": "Oil Pressure",
            "cool_temp": "Coolant Temp",
            "pwr_ext": "Battery",
        }
        missing_names = [sensor_names.get(s, s) for s in missing_sensors]
        deductions.append(f"Missing sensors: {', '.join(missing_names)}")

    final_score = max(0, min(100, score))

    # Build explanation
    if not deductions:
        explanation = "All systems operating normally"
    else:
        explanation = "; ".join(deductions[:3])  # Top 3 issues
        if len(deductions) > 3:
            explanation += f" (+{len(deductions)-3} more)"

    return final_score, explanation


def get_status_from_score(score: int) -> str:
    if score >= 80:
        return HealthStatus.HEALTHY.value
    elif score >= 50:
        return HealthStatus.WARNING.value
    else:
        return HealthStatus.CRITICAL.value


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_fleet_health(
    include_trends: bool = True, include_maintenance: bool = True
) -> FleetHealthReport:
    """
    Main function to analyze entire fleet health.

    NOW INCLUDES:
    - Operational context (smart threshold adjustment)
    - Nelson Rules anomaly detection
    - Maintenance schedule
    - Trend analysis

    🆕 v5.3.5: Now filters by tanks.yaml to match Dashboard behavior

    Returns complete report with all trucks, alerts, and summary.
    """
    # 🆕 v5.3.5: Get allowed trucks from tanks.yaml
    allowed_trucks = get_allowed_trucks()

    # Try to get real data
    sensors_data = fetch_current_sensors_from_wialon()

    # If Wialon fails, try fuel_metrics
    if not sensors_data:
        logger.info("Wialon unavailable, trying fuel_metrics...")
        sensors_data = fetch_current_sensors_from_fuel_db()

    # If still no data, return demo data
    if not sensors_data:
        logger.info("No real data available, returning demo data")
        return generate_demo_report()

    # 🆕 v5.3.5: Filter to only allowed trucks
    filtered_sensors = {k: v for k, v in sensors_data.items() if k in allowed_trucks}
    logger.info(
        f"[V3] Filtered from {len(sensors_data)} to {len(filtered_sensors)} trucks (tanks.yaml)"
    )

    if not filtered_sensors:
        logger.warning("[V3] No trucks matched tanks.yaml filter, returning demo data")
        return generate_demo_report()

    trucks_health = []
    all_alerts = []
    all_nelson_violations = []
    total_potential_savings = 0
    total_suppressed = 0

    for truck_id, sensors in filtered_sensors.items():
        # ═══════════════════════════════════════════════════════════════════════
        # 1. DETECT OPERATIONAL CONTEXT
        # ═══════════════════════════════════════════════════════════════════════
        context = detect_operational_context(sensors)

        # ═══════════════════════════════════════════════════════════════════════
        # 2. ANALYZE THRESHOLDS (with context-aware adjustments)
        # ═══════════════════════════════════════════════════════════════════════
        threshold_alerts, suppressed_count = analyze_sensor_thresholds(
            truck_id, sensors, context
        )
        total_suppressed += suppressed_count

        # ═══════════════════════════════════════════════════════════════════════
        # 3. ANALYZE TRENDS (7-day regression)
        # ═══════════════════════════════════════════════════════════════════════
        trend_alerts = []
        nelson_violations = []
        if include_trends:
            history = fetch_historical_sensors(truck_id, days=7)
            if history:
                trend_alerts = analyze_trends(truck_id, history)

                # ═══════════════════════════════════════════════════════════════
                # 4. NELSON RULES ANOMALY DETECTION
                # ═══════════════════════════════════════════════════════════════
                for sensor_name, readings in history.items():
                    if len(readings) >= 10:
                        values = [r[1] for r in readings]
                        violations = check_nelson_rules(values, sensor_name)
                        for v in violations:
                            v_dict = {
                                "truck_id": truck_id,
                                "rule": v.rule,
                                "rule_name": v.rule_name,
                                "description": v.description,
                                "severity": v.severity,
                                "sensor": v.sensor,
                            }
                            nelson_violations.append(v_dict)
                            all_nelson_violations.append(v_dict)

        # ═══════════════════════════════════════════════════════════════════════
        # 5. MAINTENANCE SCHEDULE
        # ═══════════════════════════════════════════════════════════════════════
        maintenance_items = []
        if include_maintenance:
            odometer = sensors.get("odom", 0) or 0
            engine_hours = sensors.get("engine_hours", 0) or 0
            if odometer > 0 or engine_hours > 0:
                maintenance_items = calculate_maintenance_schedule(
                    odometer, engine_hours
                )

        # Combine alerts
        truck_alerts = threshold_alerts + trend_alerts

        # Calculate savings potential
        for alert in truck_alerts:
            savings = alert.potential_cost - alert.prevention_cost
            if savings > 0:
                total_potential_savings += savings

        # Calculate health score (returns tuple: score, explanation)
        health_score, health_explanation = calculate_health_score(sensors, truck_alerts)
        status = get_status_from_score(health_score)

        # Build truck health object
        truck_data = {
            "truck_id": truck_id,
            "health_score": health_score,
            "health_explanation": health_explanation,  # 🆕 v5.3.6: Why this score?
            "status": status,
            "sensors": sensors,
            "alerts": [a.to_dict() for a in truck_alerts],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            # NEW: Operational context
            "operational_context": context.to_dict(),
            # NEW: Nelson violations
            "anomalies": nelson_violations,
            # NEW: Maintenance schedule
            "maintenance": (
                [m.to_dict() for m in maintenance_items] if maintenance_items else []
            ),
        }

        trucks_health.append(truck_data)
        all_alerts.extend([a.to_dict() for a in truck_alerts])

    # Sort trucks by health score (worst first)
    trucks_health.sort(key=lambda x: x["health_score"])

    # Sort alerts by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))

    # Calculate summary stats
    healthy_count = sum(1 for t in trucks_health if t["status"] == "healthy")
    warning_count = sum(1 for t in trucks_health if t["status"] == "warning")
    critical_count = sum(1 for t in trucks_health if t["status"] == "critical")
    avg_score = (
        statistics.mean([t["health_score"] for t in trucks_health])
        if trucks_health
        else 0
    )

    logger.info(
        f"[V3] Fleet analysis complete: {len(trucks_health)} trucks, {len(all_alerts)} alerts, {total_suppressed} suppressed by context"
    )

    return FleetHealthReport(
        total_trucks=len(trucks_health),
        healthy_count=healthy_count,
        warning_count=warning_count,
        critical_count=critical_count,
        average_score=round(avg_score, 1),
        total_potential_savings=total_potential_savings,
        trucks=trucks_health,
        all_alerts=all_alerts,
        all_anomalies=all_nelson_violations,
        suppressed_alerts_count=total_suppressed,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO DATA - Fallback when no real data available
# ═══════════════════════════════════════════════════════════════════════════════


def generate_demo_report() -> FleetHealthReport:
    """
    Generate demo data when real data is unavailable.
    This ensures the dashboard never crashes.
    """
    demo_context = OperationalContext(
        mode="normal",
        speed=55.0,
        rpm=1400,
        engine_load=45.0,
        altitude_delta=0.0,
        ambient_temp=72.0,
        explanation="Demo data - normal operating conditions",
    )

    demo_trucks = [
        {
            "truck_id": "DEMO-001",
            "health_score": 95,
            "status": "healthy",
            "sensors": {
                "oil_press": 45.0,
                "cool_temp": 195.0,
                "pwr_ext": 14.1,
                "speed": 55.0,
                "rpm": 1400,
            },
            "alerts": [],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "operational_context": demo_context.to_dict(),
            "anomalies": [],
            "maintenance": [],
        },
        {
            "truck_id": "DEMO-002",
            "health_score": 72,
            "status": "warning",
            "sensors": {
                "oil_press": 28.0,
                "cool_temp": 215.0,
                "pwr_ext": 13.2,
                "speed": 45.0,
                "rpm": 1600,
            },
            "alerts": [
                {
                    "truck_id": "DEMO-002",
                    "sensor": "oil_press",
                    "severity": "high",
                    "title": "Low Oil Pressure",
                    "message": "Oil pressure at 28.0 psi - below warning threshold of 30",
                    "current_value": 28.0,
                    "threshold": 30,
                    "action": "Schedule oil system inspection within 24 hours",
                    "potential_cost": 40000,
                    "prevention_cost": 2500,
                    "trend_info": None,
                    "context_suppressed": False,
                }
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "operational_context": demo_context.to_dict(),
            "anomalies": [],
            "maintenance": [],
        },
        {
            "truck_id": "DEMO-003",
            "health_score": 45,
            "status": "critical",
            "sensors": {
                "oil_press": 18.0,
                "cool_temp": 225.0,
                "pwr_ext": 11.8,
                "speed": 0.0,
                "rpm": 800,
            },
            "alerts": [
                {
                    "truck_id": "DEMO-003",
                    "sensor": "oil_press",
                    "severity": "critical",
                    "title": "Critical Low Oil Pressure",
                    "message": "Oil pressure at 18.0 psi - CRITICAL",
                    "current_value": 18.0,
                    "threshold": 20,
                    "action": "STOP ENGINE - Check oil level immediately",
                    "potential_cost": 40000,
                    "prevention_cost": 2500,
                    "trend_info": None,
                    "context_suppressed": False,
                },
                {
                    "truck_id": "DEMO-003",
                    "sensor": "cool_temp",
                    "severity": "high",
                    "title": "High Coolant Temperature",
                    "message": "Coolant at 225°F - approaching overheat",
                    "current_value": 225.0,
                    "threshold": 220,
                    "action": "Check cooling system",
                    "potential_cost": 25000,
                    "prevention_cost": 1500,
                    "trend_info": None,
                    "context_suppressed": False,
                },
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "operational_context": OperationalContext(
                mode="idle", speed=0, rpm=800, explanation="Idling"
            ).to_dict(),
            "anomalies": [],
            "maintenance": [],
        },
    ]

    all_alerts = []
    for truck in demo_trucks:
        all_alerts.extend(truck["alerts"])

    return FleetHealthReport(
        total_trucks=3,
        healthy_count=1,
        warning_count=1,
        critical_count=1,
        average_score=70.7,
        total_potential_savings=62000,
        trucks=demo_trucks,
        all_alerts=all_alerts,
        all_anomalies=[],
        suppressed_alerts_count=0,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE TRUCK ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_single_truck(
    truck_id: str, include_trends: bool = True, include_maintenance: bool = True
) -> Optional[Dict]:
    """
    Analyze a single truck's health with full V3 features.
    """
    # Get sensors for this truck
    all_sensors = fetch_current_sensors_from_wialon()
    sensors = all_sensors.get(truck_id)

    if not sensors:
        # Try fuel_metrics
        all_sensors = fetch_current_sensors_from_fuel_db()
        sensors = all_sensors.get(truck_id)

    if not sensors:
        return None

    # Detect operational context
    context = detect_operational_context(sensors)

    # Analyze thresholds with context
    threshold_alerts, suppressed_count = analyze_sensor_thresholds(
        truck_id, sensors, context
    )

    # Trends and Nelson Rules
    trend_alerts = []
    nelson_violations = []
    if include_trends:
        history = fetch_historical_sensors(truck_id, days=7)
        if history:
            trend_alerts = analyze_trends(truck_id, history)

            for sensor_name, readings in history.items():
                if len(readings) >= 10:
                    values = [r[1] for r in readings]
                    violations = check_nelson_rules(values, sensor_name)
                    for v in violations:
                        nelson_violations.append(
                            {
                                "truck_id": truck_id,
                                "rule": v.rule,
                                "rule_name": v.rule_name,
                                "description": v.description,
                                "severity": v.severity,
                                "sensor": v.sensor,
                            }
                        )

    # Maintenance schedule
    maintenance_items = []
    if include_maintenance:
        odometer = sensors.get("odom", 0) or 0
        engine_hours = sensors.get("engine_hours", 0) or 0
        if odometer > 0 or engine_hours > 0:
            maintenance_items = calculate_maintenance_schedule(odometer, engine_hours)

    all_alerts = threshold_alerts + trend_alerts
    health_score, health_explanation = calculate_health_score(sensors, all_alerts)

    return {
        "truck_id": truck_id,
        "health_score": health_score,
        "health_explanation": health_explanation,
        "status": get_status_from_score(health_score),
        "sensors": sensors,
        "alerts": [a.to_dict() for a in all_alerts],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "operational_context": context.to_dict(),
        "anomalies": nelson_violations,
        "maintenance": (
            [m.to_dict() for m in maintenance_items] if maintenance_items else []
        ),
        "suppressed_alerts_count": suppressed_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# KALMAN FILTER INTEGRATION - Adaptive Q_r for estimator.py
# ═══════════════════════════════════════════════════════════════════════════════


def get_recommended_Q_r(truck_id: str) -> Dict[str, Any]:
    """
    Get recommended Q_r (process noise) for a truck based on its current state.
    This function is designed to be called from the main fuel processing loop.

    Returns dict with:
    - Q_r: Recommended process noise value
    - status: Truck status (PARKED, STOPPED, IDLE, MOVING)
    - reason: Explanation for the recommendation
    """
    all_sensors = fetch_current_sensors_from_wialon()
    sensors = all_sensors.get(truck_id, {})

    speed = sensors.get("speed", 0) or 0
    rpm = sensors.get("rpm", 0) or 0
    fuel_rate = sensors.get("fuel_rate", 0) or 0

    # Determine truck status
    if speed < 1 and rpm < 100:
        status = "PARKED"
        Q_r = 0.01
        reason = "Engine off - minimal fuel change expected"
    elif speed < 3 and rpm < 900:
        status = "IDLE"
        Q_r = calculate_adaptive_Q_r("IDLE", fuel_rate)
        reason = f"Idling at {rpm:.0f} RPM - low consumption expected"
    elif speed < 3:
        status = "STOPPED"
        Q_r = 0.05
        reason = "Stopped with engine running"
    else:
        status = "MOVING"
        Q_r = calculate_adaptive_Q_r("MOVING", fuel_rate)
        reason = f"Moving at {speed:.0f} mph - active consumption"

    return {
        "Q_r": Q_r,
        "status": status,
        "reason": reason,
        "speed": speed,
        "rpm": rpm,
        "fuel_rate": fuel_rate,
    }
