"""
🛡️ ADVANCED FUEL THEFT DETECTION ENGINE v4.1.0
═══════════════════════════════════════════════════════════════════════════════

Sophisticated multi-signal theft detection system that combines:
1. Fuel level analysis (drops, recovery patterns)
2. Trip/movement correlation (was truck moving during drop?)
3. GPS location analysis (where was the truck?)
4. Time pattern analysis (night, weekends, holidays)
5. Sensor health scoring (is sensor reliable?)
6. Machine learning-style confidence scoring

KEY INSIGHT from analysis:
- Most "theft" alerts are actually NORMAL CONSUMPTION during trips
- Real theft happens when truck is PARKED (0 miles, 0 speed)
- Sensor issues show RECOVERY within minutes

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────┐
│                    THEFT DETECTION PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│  [Fuel Drop Detected] → [Movement Check] → [Location Check]     │
│          ↓                    ↓                   ↓              │
│  [Sensor Health]    → [Time Analysis]   → [Confidence Score]    │
│          ↓                    ↓                   ↓              │
│  [Classification: THEFT | CONSUMPTION | SENSOR_ISSUE]           │
└─────────────────────────────────────────────────────────────────┘

Author: Fuel Copilot Team
Created: December 2025
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pymysql
import yaml
from sqlalchemy import text

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


class EventClassification(Enum):
    """Classification of fuel drop events"""

    THEFT_CONFIRMED = "ROBO CONFIRMADO"
    THEFT_SUSPECTED = "ROBO SOSPECHOSO"
    CONSUMPTION_NORMAL = "CONSUMO NORMAL"
    CONSUMPTION_IDLE = "CONSUMO EN RALENTÍ"
    SENSOR_ISSUE = "PROBLEMA DE SENSOR"
    SENSOR_DISCONNECT = "SENSOR DESCONECTADO"
    DATA_GAP = "BRECHA DE DATOS"
    REFUEL_NEGATIVE = "AJUSTE POST-RECARGA"


class RiskLevel(Enum):
    """Risk severity levels"""

    CRITICAL = "CRÍTICO"
    HIGH = "ALTO"
    MEDIUM = "MEDIO"
    LOW = "BAJO"
    NONE = "NINGUNO"


@dataclass
class FuelDrop:
    """Represents a detected fuel drop event"""

    truck_id: str
    timestamp: datetime
    fuel_before_pct: float
    fuel_after_pct: float
    fuel_before_gal: float
    fuel_after_gal: float
    drop_pct: float
    drop_gal: float
    time_gap_minutes: float
    odometer_before: float
    odometer_after: float
    miles_driven: float
    prev_status: Optional[str] = None
    curr_status: Optional[str] = None


@dataclass
class TripContext:
    """Trip/movement context during a fuel drop"""

    was_moving: bool
    distance_miles: float
    avg_speed_mph: float
    max_speed_mph: float
    trip_start: Optional[datetime] = None
    trip_end: Optional[datetime] = None
    is_parked: bool = False


@dataclass
class LocationContext:
    """GPS location context"""

    latitude: float
    longitude: float
    location_type: str = "UNKNOWN"  # e.g., "YARD", "GAS_STATION", "HIGHWAY", "UNKNOWN"
    is_known_safe_zone: bool = False


@dataclass
class SensorHealth:
    """Sensor reliability metrics"""

    is_connected: bool
    readings_last_hour: int
    variance_last_hour: float
    has_recovery_pattern: bool
    recovery_time_minutes: Optional[float] = None
    recovery_to_pct: Optional[float] = None
    volatility_score: float = 0.0  # 0-100, higher = more volatile/unreliable


@dataclass
class TimeContext:
    """Time-based context"""

    hour: int
    is_night: bool  # 10pm - 6am
    is_weekend: bool
    is_business_hours: bool  # 6am - 8pm weekdays
    day_of_week: str


@dataclass
class ConfidenceFactors:
    """Breakdown of confidence scoring factors"""

    movement_factor: float = 0.0  # -50 to +30 (negative if moving)
    time_factor: float = 0.0  # 0 to +15 (night/weekend bonus)
    sensor_factor: float = 0.0  # -40 to 0 (penalty for bad sensor)
    drop_size_factor: float = 0.0  # 0 to +25 (larger drop = more suspicious)
    location_factor: float = 0.0  # -20 to +10 (known safe zones vs unknown)
    pattern_factor: float = 0.0  # 0 to +20 (matches known theft patterns)
    recovery_factor: float = 0.0  # -50 to 0 (penalty if recovered)

    @property
    def total(self) -> float:
        """Calculate total confidence score (0-100)"""
        base = 50  # Start at 50%
        total = (
            base
            + self.movement_factor
            + self.time_factor
            + self.sensor_factor
            + self.drop_size_factor
            + self.location_factor
            + self.pattern_factor
            + self.recovery_factor
        )
        return max(0, min(100, total))


@dataclass
class TheftAnalysisResult:
    """Complete result of theft analysis for a single event"""

    fuel_drop: FuelDrop
    trip_context: TripContext
    sensor_health: SensorHealth
    time_context: TimeContext
    confidence: ConfidenceFactors
    classification: EventClassification
    risk_level: RiskLevel
    explanation: str
    recommended_action: str
    estimated_loss_gal: float = 0.0
    estimated_loss_usd: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v4.2.0: THEFT PATTERN ANALYZER - Historical pattern detection
# ═══════════════════════════════════════════════════════════════════════════════


class TheftPatternAnalyzer:
    """
    🆕 v4.2.0: Analyzes theft patterns based on historical data.

    Tracks confirmed/suspected theft events per truck and calculates
    pattern_factor based on:
    - Repeated theft events on same truck
    - Same day of week patterns
    - Same time of day patterns
    - Recency of previous events
    """

    def __init__(self, history_days: int = 90):
        self._theft_history: Dict[str, List[Dict]] = {}
        self.history_days = history_days

    def add_confirmed_theft(
        self,
        truck_id: str,
        timestamp: datetime,
        drop_gal: float,
        confidence: float,
    ):
        """Record a confirmed or suspected theft event for pattern analysis."""
        if truck_id not in self._theft_history:
            self._theft_history[truck_id] = []

        self._theft_history[truck_id].append(
            {
                "timestamp": timestamp,
                "drop_gal": drop_gal,
                "confidence": confidence,
                "day_of_week": timestamp.weekday(),
                "hour": timestamp.hour,
            }
        )

        # Prune old events beyond history_days
        cutoff = datetime.now() - timedelta(days=self.history_days)
        self._theft_history[truck_id] = [
            e for e in self._theft_history[truck_id] if e["timestamp"] > cutoff
        ]

    def calculate_pattern_factor(
        self,
        truck_id: str,
        current_timestamp: datetime,
    ) -> Tuple[float, str]:
        """
        Calculate pattern_factor (0 to +20) based on historical patterns.

        Returns:
            Tuple of (factor, reason_description)
        """
        history = self._theft_history.get(truck_id, [])

        if not history:
            return 0.0, ""

        factor = 0.0
        reasons = []

        # Factor 1: Truck has previous theft events (+10 for 1, +15 for 2+)
        if len(history) >= 2:
            factor += 15
            reasons.append(f"{len(history)} robos previos")
        elif len(history) == 1:
            factor += 10
            reasons.append("1 robo previo")

        # Factor 2: Same day of week pattern (+5)
        current_dow = current_timestamp.weekday()
        dow_matches = sum(1 for h in history if h["day_of_week"] == current_dow)
        if dow_matches >= 2:
            factor += 5
            day_name = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][current_dow]
            reasons.append(f"patrón {day_name}")

        # Factor 3: Same time window pattern (±2 hours) (+5)
        current_hour = current_timestamp.hour
        hour_matches = sum(
            1
            for h in history
            if abs(h["hour"] - current_hour) <= 2 or abs(h["hour"] - current_hour) >= 22
        )
        if hour_matches >= 2:
            factor += 5
            reasons.append(f"patrón ~{current_hour}:00h")

        # Factor 4: Recent event (within 7 days) makes current more suspicious (+5)
        recent_cutoff = current_timestamp - timedelta(days=7)
        recent_events = [h for h in history if h["timestamp"] > recent_cutoff]
        if recent_events:
            factor += 5
            reasons.append("evento reciente")

        # Cap at 20
        factor = min(factor, 20.0)

        reason_str = ", ".join(reasons) if reasons else ""
        return factor, reason_str

    def get_truck_risk_profile(self, truck_id: str) -> Dict:
        """Get risk profile summary for a truck."""
        history = self._theft_history.get(truck_id, [])

        if not history:
            return {
                "truck_id": truck_id,
                "theft_count": 0,
                "risk_level": "LOW",
                "total_loss_gal": 0,
            }

        total_loss = sum(h["drop_gal"] for h in history)
        avg_confidence = sum(h["confidence"] for h in history) / len(history)

        if len(history) >= 3 or total_loss > 100:
            risk = "HIGH"
        elif len(history) >= 2 or total_loss > 50:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        return {
            "truck_id": truck_id,
            "theft_count": len(history),
            "risk_level": risk,
            "total_loss_gal": round(total_loss, 1),
            "avg_confidence": round(avg_confidence, 1),
            "last_event": history[-1]["timestamp"].isoformat() if history else None,
        }


# Global pattern analyzer instance
PATTERN_ANALYZER = TheftPatternAnalyzer()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TheftDetectionConfig:
    """Configuration for theft detection thresholds"""

    # Minimum thresholds to consider as potential theft
    min_drop_pct: float = 10.0  # At least 10% drop
    min_drop_gallons: float = 15.0  # At least 15 gallons
    max_time_window_hours: float = 6.0  # Drop must happen within 6 hours

    # Movement thresholds
    parked_max_miles: float = 0.5  # Less than 0.5 mi = considered parked
    parked_max_speed: float = 2.0  # Less than 2 mph = considered parked

    # Sensor health thresholds
    recovery_window_minutes: float = 30.0  # Check for recovery within 30 min
    recovery_tolerance_pct: float = 15.0  # Recovery must be within 15% of original
    sensor_volatility_threshold: float = 8.0  # StdDev threshold for "noisy"

    # Time patterns (higher risk)
    night_start_hour: int = 22  # 10 PM
    night_end_hour: int = 6  # 6 AM

    # Confidence thresholds
    theft_confirmed_threshold: float = 85.0
    theft_suspected_threshold: float = 60.0
    sensor_issue_threshold: float = 30.0

    # Fuel price for loss calculations
    fuel_price_per_gallon: float = 3.50


# Global config instance
CONFIG = TheftDetectionConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_wialon_connection():
    """Get connection to Wialon remote database (read-only sensor data)"""
    _password = os.getenv("WIALON_DB_PASS") or os.getenv("DB_PASS")
    if not _password:
        raise ValueError("WIALON_DB_PASS or DB_PASS environment variable required")

    return pymysql.connect(
        host=os.getenv("WIALON_DB_HOST", os.getenv("DB_HOST", "20.127.200.135")),
        port=int(os.getenv("WIALON_DB_PORT", os.getenv("DB_PORT", "3306"))),
        user=os.getenv("WIALON_DB_USER", os.getenv("DB_USER", "tomas")),
        password=_password,
        database=os.getenv("WIALON_DB_NAME", os.getenv("DB_NAME", "wialon_collect")),
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_local_engine():
    """Get SQLAlchemy engine for local fuel_copilot database"""
    try:
        from database_mysql import get_sqlalchemy_engine

        return get_sqlalchemy_engine()
    except ImportError:
        logger.warning("Could not import database_mysql, using direct connection")
        return None


def load_unit_mapping() -> Dict[str, int]:
    """Load truck_id → wialon unit_id mapping from tanks.yaml"""
    try:
        tanks_path = os.path.join(os.path.dirname(__file__), "tanks.yaml")
        with open(tanks_path, "r") as f:
            tanks = yaml.safe_load(f)

        mapping = {}
        for truck_id, config in tanks.get("trucks", {}).items():
            if "unit_id" in config:
                mapping[truck_id] = config["unit_id"]
        return mapping
    except Exception as e:
        logger.error(f"Error loading tanks.yaml: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH DATA LOADING (OPTIMIZED)
# ═══════════════════════════════════════════════════════════════════════════════


def load_all_trips(
    wialon_conn, unit_ids: List[int], days_back: int
) -> Dict[int, List[Dict]]:
    """
    Load ALL trips for all units in ONE query - much faster than per-drop queries.
    Returns dict: unit_id -> list of trips (sorted by from_datetime)
    """
    if not unit_ids:
        return {}

    trips_by_unit: Dict[int, List[Dict]] = {uid: [] for uid in unit_ids}

    try:
        with wialon_conn.cursor() as cursor:
            # Single query for all trips
            placeholders = ",".join(["%s"] * len(unit_ids))
            cursor.execute(
                f"""
                SELECT DISTINCT
                    unit,
                    from_datetime, 
                    to_datetime, 
                    distance_miles,
                    avg_speed,
                    max_speed
                FROM trips 
                WHERE unit IN ({placeholders})
                AND from_datetime > NOW() - INTERVAL %s DAY
                ORDER BY unit, from_datetime
            """,
                (*unit_ids, days_back),
            )

            for row in cursor.fetchall():
                unit_id = int(row["unit"])
                if unit_id in trips_by_unit:
                    trips_by_unit[unit_id].append(
                        {
                            "from_datetime": row["from_datetime"],
                            "to_datetime": row["to_datetime"],
                            "distance_miles": float(row["distance_miles"] or 0),
                            "avg_speed": float(row["avg_speed"] or 0),
                            "max_speed": float(row["max_speed"] or 0),
                        }
                    )

        logger.info(f"📦 Loaded trips for {len(unit_ids)} units")
    except Exception as e:
        logger.error(f"Error loading trips: {e}")

    return trips_by_unit


def get_trip_context_from_cache(trips: List[Dict], event_time: datetime) -> TripContext:
    """
    Find trip context from pre-loaded trips data (fast, in-memory).
    """
    # Find active trip (trip that covers the event time)
    for trip in trips:
        if trip["from_datetime"] <= event_time <= trip["to_datetime"]:
            return TripContext(
                was_moving=True,
                distance_miles=trip["distance_miles"],
                avg_speed_mph=trip["avg_speed"],
                max_speed_mph=trip["max_speed"],
                trip_start=trip["from_datetime"],
                trip_end=trip["to_datetime"],
                is_parked=False,
            )

    # No active trip - find last trip before event
    last_trip = None
    for trip in trips:
        if trip["to_datetime"] < event_time:
            last_trip = trip
        else:
            break  # Trips are sorted by from_datetime

    if last_trip:
        time_parked = event_time - last_trip["to_datetime"]
        hours_parked = time_parked.total_seconds() / 3600
        return TripContext(
            was_moving=False,
            distance_miles=0,
            avg_speed_mph=0,
            max_speed_mph=0,
            trip_end=last_trip["to_datetime"],
            is_parked=hours_parked > 0.5,
        )

    # No trip data - assume parked
    return TripContext(
        was_moving=False,
        distance_miles=0,
        avg_speed_mph=0,
        max_speed_mph=0,
        is_parked=True,
    )


def get_sensor_health_fast(
    fuel_before_pct: float,
    fuel_after_pct: float,
    drop_pct: float = None,
    time_gap_minutes: float = None,
) -> SensorHealth:
    """
    🆕 v4.2.0: Enhanced fast sensor health check with heuristic volatility.

    Estimates sensor reliability without DB query using:
    - Drop to near-zero = disconnect
    - Very large sudden drop = likely sensor spike
    - Drop size vs time gap ratio = volatility indicator
    """
    # Calculate drop if not provided
    if drop_pct is None:
        drop_pct = fuel_before_pct - fuel_after_pct

    # Check for sensor disconnect (drop to near-zero)
    if fuel_after_pct <= 5 and fuel_before_pct > 20:
        return SensorHealth(
            is_connected=False,
            readings_last_hour=0,
            variance_last_hour=0,
            has_recovery_pattern=False,
            volatility_score=100.0,
        )

    # 🆕 v4.2.0: Estimate volatility based on drop characteristics
    volatility_score = 5.0  # Default: assume reliable

    # Heuristic 1: Very sudden large drops suggest sensor spike
    if time_gap_minutes and time_gap_minutes < 5 and drop_pct > 20:
        # >20% drop in <5 min is physically unlikely = sensor issue
        volatility_score = 60.0
    elif time_gap_minutes and time_gap_minutes < 15 and drop_pct > 40:
        # >40% drop in <15 min is also suspicious
        volatility_score = 45.0

    # Heuristic 2: Check for implausible consumption rate
    # Max realistic consumption: ~50 GPH = ~190 LPH
    # For a 200 gal tank, that's ~25% per hour max
    if time_gap_minutes and time_gap_minutes > 0:
        hours = time_gap_minutes / 60
        max_reasonable_drop_pct = 25 * hours  # 25% per hour max
        if drop_pct > max_reasonable_drop_pct * 2:
            # Drop is 2x faster than physically possible = sensor noise
            volatility_score = max(volatility_score, 35.0)

    # Heuristic 3: Drop exactly to round numbers often indicates sensor reset
    if fuel_after_pct in [0, 10, 20, 25, 50, 75, 100]:
        volatility_score = max(volatility_score, 20.0)

    return SensorHealth(
        is_connected=True,
        readings_last_hour=10,  # Assume OK (no DB access)
        variance_last_hour=2.0,
        has_recovery_pattern=False,
        volatility_score=volatility_score,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ORIGINAL FUNCTIONS (kept for reference but not used in optimized path)
# ═══════════════════════════════════════════════════════════════════════════════


def get_trip_context(
    wialon_conn, unit_id: int, event_time: datetime, window_minutes: int = 60
) -> TripContext:
    """
    Query Wialon trips table to determine if truck was moving during fuel drop.

    This is THE KEY to eliminating false positives:
    - If truck was in motion → fuel drop is CONSUMPTION, not theft
    - If truck was parked → fuel drop is SUSPICIOUS

    Args:
        wialon_conn: PyMySQL connection to Wialon database
        unit_id: Wialon unit ID for the truck
        event_time: Timestamp of the fuel drop event
        window_minutes: Time window to check for trips (before and after)

    Returns:
        TripContext with movement information
    """
    window_start = event_time - timedelta(minutes=window_minutes)
    window_end = event_time + timedelta(minutes=window_minutes)

    with wialon_conn.cursor() as cursor:
        # Find trips that overlap with the event time
        cursor.execute(
            """
            SELECT 
                from_datetime, 
                to_datetime, 
                distance_miles,
                avg_speed,
                max_speed
            FROM trips 
            WHERE unit = %s
            AND from_datetime <= %s
            AND to_datetime >= %s
            ORDER BY from_datetime
            LIMIT 1
        """,
            (unit_id, event_time, event_time),
        )

        active_trip = cursor.fetchone()

        if active_trip:
            # Truck was on an active trip during the fuel drop
            return TripContext(
                was_moving=True,
                distance_miles=float(active_trip["distance_miles"] or 0),
                avg_speed_mph=float(active_trip["avg_speed"] or 0),
                max_speed_mph=float(active_trip["max_speed"] or 0),
                trip_start=active_trip["from_datetime"],
                trip_end=active_trip["to_datetime"],
                is_parked=False,
            )

        # No active trip - check when the last trip ended
        cursor.execute(
            """
            SELECT 
                to_datetime,
                distance_miles
            FROM trips 
            WHERE unit = %s
            AND to_datetime < %s
            ORDER BY to_datetime DESC
            LIMIT 1
        """,
            (unit_id, event_time),
        )

        last_trip = cursor.fetchone()

        if last_trip:
            # Calculate how long truck has been parked
            time_parked = event_time - last_trip["to_datetime"]
            hours_parked = time_parked.total_seconds() / 3600

            return TripContext(
                was_moving=False,
                distance_miles=0,
                avg_speed_mph=0,
                max_speed_mph=0,
                trip_start=None,
                trip_end=last_trip["to_datetime"],
                is_parked=hours_parked > 0.5,  # Parked for more than 30 min
            )

        # No trip data available
        return TripContext(
            was_moving=False,
            distance_miles=0,
            avg_speed_mph=0,
            max_speed_mph=0,
            is_parked=True,  # Assume parked if no trip data
        )


def get_sensor_health(
    wialon_conn,
    unit_id: int,
    event_time: datetime,
    fuel_before_pct: float,
    fuel_after_pct: float,
) -> SensorHealth:
    """
    Analyze sensor reliability and check for recovery patterns.

    Sensor issues show distinct patterns:
    - Sudden drop followed by quick recovery (within 30 min)
    - High variance in readings (noisy sensor)
    - Drop to exactly 0% (sensor disconnect)

    Args:
        wialon_conn: PyMySQL connection to Wialon database
        unit_id: Wialon unit ID
        event_time: Timestamp of the fuel drop
        fuel_before_pct: Fuel level before drop
        fuel_after_pct: Fuel level after drop

    Returns:
        SensorHealth with reliability metrics
    """
    # Check for sensor disconnect (drop to near-zero)
    if fuel_after_pct <= 5 and fuel_before_pct > 20:
        return SensorHealth(
            is_connected=False,
            readings_last_hour=0,
            variance_last_hour=0,
            has_recovery_pattern=False,
            volatility_score=100.0,  # Maximum unreliability
        )

    with wialon_conn.cursor() as cursor:
        # Get readings in the hour after the drop to check for recovery
        cursor.execute(
            """
            SELECT measure_datetime, value
            FROM sensors
            WHERE unit = %s
            AND n = 'Fuel Level'
            AND measure_datetime BETWEEN %s AND %s
            ORDER BY measure_datetime
        """,
            (
                unit_id,
                event_time,
                event_time + timedelta(minutes=CONFIG.recovery_window_minutes),
            ),
        )

        recovery_readings = cursor.fetchall()

        # Check for recovery pattern
        has_recovery = False
        recovery_time = None
        recovery_to = None

        if recovery_readings:
            for reading in recovery_readings:
                if reading["value"] is not None:
                    recovery_gap = abs(fuel_before_pct - float(reading["value"]))
                    if recovery_gap <= CONFIG.recovery_tolerance_pct:
                        has_recovery = True
                        recovery_time = (
                            reading["measure_datetime"] - event_time
                        ).total_seconds() / 60
                        recovery_to = float(reading["value"])
                        break

        # Get readings in the hour before for variance calculation
        cursor.execute(
            """
            SELECT value
            FROM sensors
            WHERE unit = %s
            AND n = 'Fuel Level'
            AND measure_datetime BETWEEN %s AND %s
            AND value IS NOT NULL
        """,
            (unit_id, event_time - timedelta(hours=1), event_time),
        )

        hour_readings = cursor.fetchall()
        readings_count = len(hour_readings)

        # Calculate variance
        variance = 0.0
        if readings_count >= 2:
            values = [float(r["value"]) for r in hour_readings if r["value"]]
            if values:
                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values)

        # Calculate volatility score (0-100)
        volatility = min(100, variance * 5)  # Scale variance to 0-100

        return SensorHealth(
            is_connected=True,
            readings_last_hour=readings_count,
            variance_last_hour=variance,
            has_recovery_pattern=has_recovery,
            recovery_time_minutes=recovery_time,
            recovery_to_pct=recovery_to,
            volatility_score=volatility,
        )


def get_time_context(event_time: datetime) -> TimeContext:
    """
    Analyze time-based factors for the event.

    Theft is more likely during:
    - Night hours (10 PM - 6 AM)
    - Weekends
    - Non-business hours

    Args:
        event_time: Timestamp of the event

    Returns:
        TimeContext with time analysis
    """
    hour = event_time.hour
    day_of_week = event_time.strftime("%A")
    is_weekend = event_time.weekday() >= 5  # Saturday=5, Sunday=6

    is_night = hour >= CONFIG.night_start_hour or hour < CONFIG.night_end_hour
    is_business = not is_weekend and 6 <= hour <= 20

    return TimeContext(
        hour=hour,
        is_night=is_night,
        is_weekend=is_weekend,
        is_business_hours=is_business,
        day_of_week=day_of_week,
    )


def calculate_confidence(
    fuel_drop: FuelDrop,
    trip_context: TripContext,
    sensor_health: SensorHealth,
    time_context: TimeContext,
) -> ConfidenceFactors:
    """
    Calculate confidence score using multi-factor analysis.

    This is the core of the algorithm - combining multiple signals
    into a single confidence score that represents how likely
    this event is actual theft vs. normal consumption or sensor issue.

    Scoring breakdown:
    - Movement (-50 to +30): Most important - moving = consumption
    - Time (0 to +15): Night/weekend bonus
    - Sensor (-40 to 0): Penalty for unreliable sensor
    - Drop size (0 to +25): Larger drop = more suspicious
    - Recovery (-50 to 0): Heavy penalty if fuel recovered
    """
    factors = ConfidenceFactors()

    # ═══════════════════════════════════════════════════════════════════════════
    # MOVEMENT FACTOR (-50 to +30) - THE MOST IMPORTANT FACTOR
    # ═══════════════════════════════════════════════════════════════════════════
    if trip_context.was_moving:
        # Truck was in motion - this is almost certainly consumption
        if trip_context.distance_miles > 10:
            factors.movement_factor = -50  # Strong negative - definitely consumption
        elif trip_context.distance_miles > 5:
            factors.movement_factor = -40
        elif trip_context.distance_miles > 1:
            factors.movement_factor = -30
        else:
            factors.movement_factor = -15  # Small movement but still suspicious
    else:
        # Truck was parked - more suspicious
        if trip_context.is_parked:
            factors.movement_factor = +30  # Maximum suspicion for parked truck
        else:
            factors.movement_factor = +10  # Unknown status

    # ═══════════════════════════════════════════════════════════════════════════
    # TIME FACTOR (0 to +15)
    # ═══════════════════════════════════════════════════════════════════════════
    if time_context.is_night:
        factors.time_factor += 10  # Night time bonus
    if time_context.is_weekend:
        factors.time_factor += 5  # Weekend bonus
    if not time_context.is_business_hours:
        factors.time_factor += 3  # Non-business hours

    # Cap at 15
    factors.time_factor = min(15, factors.time_factor)

    # ═══════════════════════════════════════════════════════════════════════════
    # SENSOR FACTOR (-40 to 0)
    # ═══════════════════════════════════════════════════════════════════════════
    if not sensor_health.is_connected:
        factors.sensor_factor = -40  # Sensor disconnect - ignore completely
    elif sensor_health.volatility_score > 50:
        factors.sensor_factor = -30  # Very noisy sensor
    elif sensor_health.volatility_score > 30:
        factors.sensor_factor = -20  # Somewhat noisy
    elif sensor_health.volatility_score > 15:
        factors.sensor_factor = -10  # Slight noise
    else:
        factors.sensor_factor = 0  # Sensor seems reliable

    # ═══════════════════════════════════════════════════════════════════════════
    # DROP SIZE FACTOR (0 to +25)
    # ═══════════════════════════════════════════════════════════════════════════
    if fuel_drop.drop_gal >= 50:
        factors.drop_size_factor = 25  # Very large drop
    elif fuel_drop.drop_gal >= 30:
        factors.drop_size_factor = 20
    elif fuel_drop.drop_gal >= 20:
        factors.drop_size_factor = 15
    elif fuel_drop.drop_gal >= 15:
        factors.drop_size_factor = 10
    else:
        factors.drop_size_factor = 5

    # Percentage-based bonus
    if fuel_drop.drop_pct >= 30:
        factors.drop_size_factor += 5

    # Cap at 25
    factors.drop_size_factor = min(25, factors.drop_size_factor)

    # ═══════════════════════════════════════════════════════════════════════════
    # RECOVERY FACTOR (-50 to 0)
    # ═══════════════════════════════════════════════════════════════════════════
    if sensor_health.has_recovery_pattern:
        # Fuel recovered - almost certainly a sensor issue
        if (
            sensor_health.recovery_time_minutes
            and sensor_health.recovery_time_minutes < 10
        ):
            factors.recovery_factor = -50  # Very quick recovery = sensor glitch
        elif (
            sensor_health.recovery_time_minutes
            and sensor_health.recovery_time_minutes < 20
        ):
            factors.recovery_factor = -40
        else:
            factors.recovery_factor = (
                -30
            )  # Slower recovery but still suspicious of sensor

    # ═══════════════════════════════════════════════════════════════════════════
    # PATTERN FACTOR (0 to +20) - 🆕 v4.2.0: Uses TheftPatternAnalyzer
    # ═══════════════════════════════════════════════════════════════════════════
    # Historical pattern analysis from PATTERN_ANALYZER
    pattern_factor, pattern_reason = PATTERN_ANALYZER.calculate_pattern_factor(
        fuel_drop.truck_id,
        fuel_drop.timestamp,
    )
    factors.pattern_factor = pattern_factor

    # Additional heuristic: Classic theft pattern (long idle + big drop)
    if (
        fuel_drop.time_gap_minutes > 60
        and fuel_drop.miles_driven < 1
        and fuel_drop.drop_gal > 20
        and factors.pattern_factor < 15  # Don't double-count
    ):
        factors.pattern_factor = max(factors.pattern_factor, 15)

    return factors


def classify_event(
    confidence: ConfidenceFactors,
    fuel_drop: FuelDrop,
    trip_context: TripContext,
    sensor_health: SensorHealth,
) -> Tuple[EventClassification, RiskLevel, str, str]:
    """
    Classify the event based on confidence score and context.

    Returns:
        Tuple of (classification, risk_level, explanation, recommended_action)
    """
    score = confidence.total

    # ═══════════════════════════════════════════════════════════════════════════
    # SENSOR ISSUES - Check first (overrides other classifications)
    # ═══════════════════════════════════════════════════════════════════════════
    if not sensor_health.is_connected:
        return (
            EventClassification.SENSOR_DISCONNECT,
            RiskLevel.NONE,
            f"Sensor desconectado - el nivel cayó de {fuel_drop.fuel_before_pct:.0f}% a {fuel_drop.fuel_after_pct:.0f}% (típico de desconexión)",
            "Verificar conexión del sensor de combustible",
        )

    if sensor_health.has_recovery_pattern:
        recovery_info = ""
        if sensor_health.recovery_time_minutes:
            recovery_info = f" en {sensor_health.recovery_time_minutes:.0f} minutos"
        return (
            EventClassification.SENSOR_ISSUE,
            RiskLevel.LOW,
            f"Problema de sensor - el nivel se recuperó a {sensor_health.recovery_to_pct:.0f}%{recovery_info}",
            "Monitorear sensor, considerar recalibración si persiste",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # CONSUMPTION - Truck was moving
    # ═══════════════════════════════════════════════════════════════════════════
    if trip_context.was_moving and trip_context.distance_miles > 1:
        mpg = (
            trip_context.distance_miles / fuel_drop.drop_gal
            if fuel_drop.drop_gal > 0
            else 0
        )
        return (
            EventClassification.CONSUMPTION_NORMAL,
            RiskLevel.NONE,
            f"Consumo normal en ruta - {trip_context.distance_miles:.1f} millas recorridas ({mpg:.1f} MPG)",
            "No requiere acción - consumo esperado",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # THEFT CLASSIFICATION - Based on confidence score
    # ═══════════════════════════════════════════════════════════════════════════

    # Build context-aware explanation
    # Consider "moving" only if there was actual distance traveled
    actually_moved = trip_context.was_moving and trip_context.distance_miles > 0.5

    if actually_moved:
        movement_status = "en ruta"
        movement_detail = f" ({trip_context.distance_miles:.1f} mi)"
    elif trip_context.was_moving and trip_context.distance_miles <= 0.5:
        movement_status = "con motor encendido"  # Engine on but minimal movement
        movement_detail = " (sin desplazamiento)"
    else:
        movement_status = "parqueado"
        movement_detail = ""

    if score >= CONFIG.theft_confirmed_threshold:
        return (
            EventClassification.THEFT_CONFIRMED,
            RiskLevel.CRITICAL,
            f"🚨 Alta probabilidad de robo - camión {movement_status}{movement_detail}, {fuel_drop.drop_gal:.0f} gal perdidos, confianza {score:.0f}%",
            "INVESTIGAR INMEDIATAMENTE - Revisar cámaras, verificar nivel físico del tanque",
        )

    if score >= CONFIG.theft_suspected_threshold:
        return (
            EventClassification.THEFT_SUSPECTED,
            RiskLevel.HIGH,
            f"⚠️ Posible robo - camión {movement_status}{movement_detail}, {fuel_drop.drop_gal:.0f} gal perdidos, confianza {score:.0f}%",
            "Verificar nivel de combustible y revisar ubicación del camión",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # BORDERLINE CASES
    # ═══════════════════════════════════════════════════════════════════════════
    if score >= 40:
        return (
            EventClassification.THEFT_SUSPECTED,
            RiskLevel.MEDIUM,
            f"Pérdida sospechosa - {fuel_drop.drop_gal:.0f} galones, confianza {score:.0f}%",
            "Monitorear y verificar en próxima inspección",
        )

    # Default - likely consumption or data issue
    return (
        EventClassification.CONSUMPTION_IDLE,
        RiskLevel.LOW,
        f"Probable consumo en ralentí o brecha de datos - {fuel_drop.drop_gal:.0f} galones en {fuel_drop.time_gap_minutes:.0f} minutos",
        "No requiere acción inmediata",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR DATA EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════


def _get_drops_from_wialon(
    days_back: int, unit_mapping: Dict[str, int], reverse_mapping: Dict[int, str]
) -> List[FuelDrop]:
    """
    Extract fuel drops directly from Wialon sensors table.
    Used as fallback when local DB has no data.
    """
    drops = []

    try:
        conn = get_wialon_connection()
        with conn.cursor() as cursor:
            # Get all fuel level readings with LAG
            cursor.execute(
                """
                SELECT 
                    unit,
                    measure_datetime,
                    value,
                    LAG(value) OVER (PARTITION BY unit ORDER BY measure_datetime) as prev_value,
                    LAG(measure_datetime) OVER (PARTITION BY unit ORDER BY measure_datetime) as prev_ts
                FROM sensors
                WHERE n = 'Fuel Level'
                AND measure_datetime > NOW() - INTERVAL %s DAY
                AND value IS NOT NULL
                ORDER BY unit, measure_datetime
            """,
                (days_back,),
            )

            for row in cursor.fetchall():
                if row["prev_value"] is None or row["prev_ts"] is None:
                    continue

                unit_id = row["unit"]
                truck_id = reverse_mapping.get(int(unit_id))
                if not truck_id:
                    continue

                prev_pct = float(row["prev_value"])
                curr_pct = float(row["value"])
                drop_pct = prev_pct - curr_pct

                # Only significant drops
                if drop_pct < CONFIG.min_drop_pct:
                    continue

                # Get truck capacity to calculate gallons
                # Default to 200 gal if not known
                capacity_gal = 200.0
                drop_gal = (drop_pct / 100.0) * capacity_gal

                if drop_gal < CONFIG.min_drop_gallons:
                    continue

                # Calculate time gap
                timestamp = row["measure_datetime"]
                prev_ts = row["prev_ts"]
                time_gap_min = (timestamp - prev_ts).total_seconds() / 60
                time_gap_hours = time_gap_min / 60

                if time_gap_hours > CONFIG.max_time_window_hours:
                    continue

                drops.append(
                    FuelDrop(
                        truck_id=truck_id,
                        timestamp=timestamp,
                        fuel_before_pct=prev_pct,
                        fuel_after_pct=curr_pct,
                        fuel_before_gal=(prev_pct / 100.0) * capacity_gal,
                        fuel_after_gal=(curr_pct / 100.0) * capacity_gal,
                        drop_pct=drop_pct,
                        drop_gal=drop_gal,
                        time_gap_minutes=time_gap_min,
                        odometer_before=0,  # Not available in sensors
                        odometer_after=0,
                        miles_driven=0,  # Will be determined from trips
                    )
                )

        conn.close()
    except Exception as e:
        logger.error(f"Error querying Wialon for drops: {e}")

    return drops


def _process_local_results(results, unit_mapping: Dict[str, int]) -> List[FuelDrop]:
    """Process results from local fuel_copilot database into FuelDrop objects."""
    drops = []

    for row in results:
        truck_id = row[0]
        timestamp = row[1]
        est_pct = float(row[2] or 0)
        est_gal = float(row[3] or 0)
        prev_pct = float(row[8] or 0) if row[8] else None
        prev_gal = float(row[9] or 0) if row[9] else None
        prev_ts = row[10]
        prev_odo = float(row[11] or 0) if row[11] else 0
        odometer = float(row[7] or 0) if row[7] else 0
        prev_status = row[12]
        curr_status = row[6]

        if prev_pct is None or prev_gal is None or prev_ts is None:
            continue

        drop_pct = prev_pct - est_pct
        drop_gal = prev_gal - est_gal

        if drop_gal < CONFIG.min_drop_gallons or drop_pct < CONFIG.min_drop_pct:
            continue

        time_gap_min = (timestamp - prev_ts).total_seconds() / 60
        time_gap_hours = time_gap_min / 60

        if time_gap_hours > CONFIG.max_time_window_hours:
            continue

        miles_driven = max(0, odometer - prev_odo) if prev_odo > 0 else 0

        drops.append(
            FuelDrop(
                truck_id=truck_id,
                timestamp=timestamp,
                fuel_before_pct=prev_pct,
                fuel_after_pct=est_pct,
                fuel_before_gal=prev_gal,
                fuel_after_gal=est_gal,
                drop_pct=drop_pct,
                drop_gal=drop_gal,
                time_gap_minutes=time_gap_min,
                odometer_before=prev_odo,
                odometer_after=odometer,
                miles_driven=miles_driven,
                prev_status=prev_status,
                curr_status=curr_status,
            )
        )

    return drops


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_fuel_drops_advanced(days_back: int = 7) -> Dict[str, Any]:
    """
    🛡️ ADVANCED FUEL THEFT ANALYSIS

    This is the main entry point for the sophisticated theft detection system.
    It queries fuel metrics, cross-references with Wialon trip data, and
    applies multi-factor analysis to classify each fuel drop event.

    Data Sources:
    1. Primary: Local fuel_copilot DB (processed metrics)
    2. Fallback: Direct Wialon sensors table (if local is empty)

    Args:
        days_back: Number of days to analyze (default 7)

    Returns:
        Dict with analysis results including:
        - summary: Overall statistics
        - events: List of analyzed events
        - trucks_at_risk: Trucks with potential theft events
        - insights: Key findings and recommendations
    """
    logger.info(f"🔍 Starting advanced theft analysis for last {days_back} days...")

    # Load unit mapping
    unit_mapping = load_unit_mapping()
    reverse_mapping = {v: k for k, v in unit_mapping.items()}

    # Initialize results
    all_results: List[TheftAnalysisResult] = []
    trucks_summary: Dict[str, Dict] = {}

    # Try to get fuel drops - first from local DB, then from Wialon
    fuel_drops: List[FuelDrop] = []
    data_source = "local"

    # Try local database first
    engine = get_local_engine()
    if engine:
        try:
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
                    odometer_mi,
                    LAG(estimated_pct) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_pct,
                    LAG(estimated_gallons) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_gal,
                    LAG(timestamp_utc) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_ts,
                    LAG(odometer_mi) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_odo,
                    LAG(truck_status) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_status
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL :days_back DAY
                  AND estimated_gallons IS NOT NULL
                  AND estimated_pct IS NOT NULL
                ORDER BY truck_id, timestamp_utc
            """
            )

            with engine.connect() as conn:
                local_results = conn.execute(query, {"days_back": days_back}).fetchall()

            if local_results:
                fuel_drops = _process_local_results(local_results, unit_mapping)
                logger.info(
                    f"📊 Found {len(fuel_drops)} significant drops from local DB"
                )
        except Exception as e:
            logger.warning(f"Could not query local DB: {e}")

    # Fallback to Wialon if no local data
    if not fuel_drops:
        logger.info("📡 Local DB empty, querying Wialon directly...")
        data_source = "wialon"
        fuel_drops = _get_drops_from_wialon(days_back, unit_mapping, reverse_mapping)
        logger.info(f"📊 Found {len(fuel_drops)} significant drops from Wialon")

    if not fuel_drops:
        return _empty_analysis_result(days_back)

    # ═══════════════════════════════════════════════════════════════════════════
    # BATCH LOAD TRIP DATA (OPTIMIZED - one query instead of 91+)
    # ═══════════════════════════════════════════════════════════════════════════
    wialon_conn = None
    try:
        wialon_conn = get_wialon_connection()

        # Get all unique unit_ids we need
        truck_ids = list(set(drop.truck_id for drop in fuel_drops))
        unit_ids = [unit_mapping.get(tid) for tid in truck_ids if unit_mapping.get(tid)]
        unit_ids = list(set(filter(None, unit_ids)))

        logger.info(f"📦 Loading trips for {len(unit_ids)} units...")
        all_trips = load_all_trips(wialon_conn, unit_ids, days_back + 1)

        # Process each drop using cached data (fast!)
        logger.info(f"🔄 Analyzing {len(fuel_drops)} drops...")
        for i, drop in enumerate(fuel_drops):
            if (i + 1) % 20 == 0:
                logger.info(f"  Processed {i + 1}/{len(fuel_drops)} drops...")

            # Get unit_id for this truck
            unit_id = unit_mapping.get(drop.truck_id)
            if not unit_id:
                continue

            # Get trip context from cache (fast, in-memory)
            trips_for_unit = all_trips.get(unit_id, [])
            trip_context = get_trip_context_from_cache(trips_for_unit, drop.timestamp)

            # Get sensor health (fast version - no DB query)
            # 🆕 v4.2.0: Pass additional context for better volatility estimation
            sensor_health = get_sensor_health_fast(
                drop.fuel_before_pct,
                drop.fuel_after_pct,
                drop_pct=drop.drop_pct,
                time_gap_minutes=drop.time_gap_minutes,
            )

            # Get time context
            time_context = get_time_context(drop.timestamp)

            # Calculate confidence
            confidence = calculate_confidence(
                drop, trip_context, sensor_health, time_context
            )

            # Classify event
            classification, risk_level, explanation, action = classify_event(
                confidence, drop, trip_context, sensor_health
            )

            # Calculate loss (only for theft events)
            loss_gal = 0.0
            loss_usd = 0.0
            if classification in [
                EventClassification.THEFT_CONFIRMED,
                EventClassification.THEFT_SUSPECTED,
            ]:
                loss_gal = drop.drop_gal
                loss_usd = loss_gal * CONFIG.fuel_price_per_gallon

            # Create result
            result = TheftAnalysisResult(
                fuel_drop=drop,
                trip_context=trip_context,
                sensor_health=sensor_health,
                time_context=time_context,
                confidence=confidence,
                classification=classification,
                risk_level=risk_level,
                explanation=explanation,
                recommended_action=action,
                estimated_loss_gal=loss_gal,
                estimated_loss_usd=loss_usd,
            )

            all_results.append(result)

            # Update truck summary
            if drop.truck_id not in trucks_summary:
                trucks_summary[drop.truck_id] = {
                    "theft_events": 0,
                    "sensor_events": 0,
                    "consumption_events": 0,
                    "total_loss_gal": 0,
                    "highest_confidence": 0,
                    "highest_risk": RiskLevel.NONE,
                }

            if classification in [
                EventClassification.THEFT_CONFIRMED,
                EventClassification.THEFT_SUSPECTED,
            ]:
                trucks_summary[drop.truck_id]["theft_events"] += 1
                trucks_summary[drop.truck_id]["total_loss_gal"] += loss_gal
                trucks_summary[drop.truck_id]["highest_confidence"] = max(
                    trucks_summary[drop.truck_id]["highest_confidence"],
                    confidence.total,
                )
                if (
                    risk_level.value
                    > trucks_summary[drop.truck_id]["highest_risk"].value
                ):
                    trucks_summary[drop.truck_id]["highest_risk"] = risk_level

                # 🆕 v4.2.0: Register in pattern analyzer for future pattern detection
                PATTERN_ANALYZER.add_confirmed_theft(
                    truck_id=drop.truck_id,
                    timestamp=drop.timestamp,
                    drop_gal=drop.drop_gal,
                    confidence=confidence.total,
                )
            elif classification in [
                EventClassification.SENSOR_ISSUE,
                EventClassification.SENSOR_DISCONNECT,
            ]:
                trucks_summary[drop.truck_id]["sensor_events"] += 1
            else:
                trucks_summary[drop.truck_id]["consumption_events"] += 1

    except Exception as e:
        logger.error(f"Error analyzing drops: {e}", exc_info=True)
    finally:
        if wialon_conn:
            wialon_conn.close()

    # Build response
    return _build_analysis_response(all_results, trucks_summary, days_back)


def _build_analysis_response(
    results: List[TheftAnalysisResult],
    trucks_summary: Dict[str, Dict],
    days_back: int,
) -> Dict[str, Any]:
    """Build the final response dictionary"""

    # Count by classification
    theft_confirmed = [
        r for r in results if r.classification == EventClassification.THEFT_CONFIRMED
    ]
    theft_suspected = [
        r for r in results if r.classification == EventClassification.THEFT_SUSPECTED
    ]
    sensor_issues = [
        r
        for r in results
        if r.classification
        in [EventClassification.SENSOR_ISSUE, EventClassification.SENSOR_DISCONNECT]
    ]
    consumption = [
        r
        for r in results
        if r.classification
        in [
            EventClassification.CONSUMPTION_NORMAL,
            EventClassification.CONSUMPTION_IDLE,
        ]
    ]

    # Calculate totals
    total_loss_gal = sum(r.estimated_loss_gal for r in results)
    total_loss_usd = sum(r.estimated_loss_usd for r in results)

    # Build trucks at risk list
    trucks_at_risk = []
    for truck_id, data in trucks_summary.items():
        if data["theft_events"] > 0:
            trucks_at_risk.append(
                {
                    "truck_id": truck_id,
                    "theft_events": data["theft_events"],
                    "sensor_events": data["sensor_events"],
                    "consumption_events": data["consumption_events"],
                    "total_loss_gallons": round(data["total_loss_gal"], 1),
                    "total_loss_usd": round(
                        data["total_loss_gal"] * CONFIG.fuel_price_per_gallon, 2
                    ),
                    "highest_confidence": round(data["highest_confidence"], 1),
                    "risk_level": data["highest_risk"].value,
                }
            )

    # Sort by risk
    trucks_at_risk.sort(
        key=lambda x: (x["highest_confidence"], x["total_loss_gallons"]), reverse=True
    )

    # Build events list
    events = []
    for r in results:
        events.append(
            {
                "truck_id": r.fuel_drop.truck_id,
                "timestamp": r.fuel_drop.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "date": r.fuel_drop.timestamp.strftime("%Y-%m-%d"),
                "time": r.fuel_drop.timestamp.strftime("%H:%M"),
                "classification": r.classification.value,
                "risk_level": r.risk_level.value,
                "confidence_pct": round(r.confidence.total, 1),
                "fuel_drop_gallons": round(r.fuel_drop.drop_gal, 1),
                "fuel_drop_pct": round(r.fuel_drop.drop_pct, 1),
                "fuel_before_pct": round(r.fuel_drop.fuel_before_pct, 1),
                "fuel_after_pct": round(r.fuel_drop.fuel_after_pct, 1),
                "time_gap_minutes": round(r.fuel_drop.time_gap_minutes, 0),
                "miles_driven": round(r.fuel_drop.miles_driven, 1),
                "was_moving": r.trip_context.was_moving,
                "trip_distance": round(r.trip_context.distance_miles, 1),
                "sensor_recovered": r.sensor_health.has_recovery_pattern,
                "is_night": r.time_context.is_night,
                "explanation": r.explanation,
                "recommended_action": r.recommended_action,
                "confidence_breakdown": {
                    "movement": round(r.confidence.movement_factor, 1),
                    "time": round(r.confidence.time_factor, 1),
                    "sensor": round(r.confidence.sensor_factor, 1),
                    "drop_size": round(r.confidence.drop_size_factor, 1),
                    "recovery": round(r.confidence.recovery_factor, 1),
                },
                "estimated_loss_gal": round(r.estimated_loss_gal, 1),
                "estimated_loss_usd": round(r.estimated_loss_usd, 2),
            }
        )

    # Sort events by confidence
    events.sort(key=lambda x: x["confidence_pct"], reverse=True)

    # Generate insights
    insights = []

    if len(theft_confirmed) > 0:
        insights.append(
            {
                "priority": "CRÍTICA",
                "type": "ROBO CONFIRMADO",
                "finding": f"{len(theft_confirmed)} evento(s) de robo confirmado detectados",
                "recommendation": "🚨 INVESTIGAR INMEDIATAMENTE",
            }
        )

    if len(theft_suspected) > 0:
        insights.append(
            {
                "priority": "ALTA",
                "type": "ROBO SOSPECHOSO",
                "finding": f"{len(theft_suspected)} evento(s) sospechosos requieren verificación",
                "recommendation": "Verificar nivel físico de tanques afectados",
            }
        )

    if len(sensor_issues) > 5:
        insights.append(
            {
                "priority": "MEDIA",
                "type": "SENSORES INESTABLES",
                "finding": f"{len(sensor_issues)} problemas de sensor detectados",
                "recommendation": "Considerar recalibración de sensores afectados",
            }
        )

    if len(consumption) > len(theft_confirmed) + len(theft_suspected) + len(
        sensor_issues
    ):
        insights.append(
            {
                "priority": "INFO",
                "type": "CONSUMO NORMAL",
                "finding": f"{len(consumption)} caídas fueron consumo normal en ruta",
                "recommendation": "Sistema funcionando correctamente - filtrando falsos positivos",
            }
        )

    if not insights:
        insights.append(
            {
                "priority": "INFO",
                "type": "SIN ALERTAS",
                "finding": "No se detectaron eventos de robo en este período",
                "recommendation": "Continuar monitoreo normal",
            }
        )

    return {
        "period_days": days_back,
        "fuel_price_per_gal": CONFIG.fuel_price_per_gallon,
        "algorithm_version": "4.1.0-advanced",
        "summary": {
            "total_events_analyzed": len(results),
            "theft_confirmed": len(theft_confirmed),
            "theft_suspected": len(theft_suspected),
            "sensor_issues": len(sensor_issues),
            "normal_consumption": len(consumption),
            "total_suspected_loss_gallons": round(total_loss_gal, 1),
            "total_suspected_loss_usd": round(total_loss_usd, 2),
            "trucks_affected": len(trucks_at_risk),
        },
        "trucks_at_risk": trucks_at_risk[:20],
        "events": events[:50],  # Top 50 events
        "insights": insights,
        "detection_config": {
            "min_drop_gallons": CONFIG.min_drop_gallons,
            "min_drop_pct": CONFIG.min_drop_pct,
            "recovery_window_minutes": CONFIG.recovery_window_minutes,
            "theft_confirmed_threshold": CONFIG.theft_confirmed_threshold,
            "theft_suspected_threshold": CONFIG.theft_suspected_threshold,
        },
    }


def _empty_analysis_result(days_back: int) -> Dict[str, Any]:
    """Return empty analysis result"""
    return {
        "period_days": days_back,
        "fuel_price_per_gal": CONFIG.fuel_price_per_gallon,
        "algorithm_version": "4.1.0-advanced",
        "summary": {
            "total_events_analyzed": 0,
            "theft_confirmed": 0,
            "theft_suspected": 0,
            "sensor_issues": 0,
            "normal_consumption": 0,
            "total_suspected_loss_gallons": 0,
            "total_suspected_loss_usd": 0,
            "trucks_affected": 0,
        },
        "trucks_at_risk": [],
        "events": [],
        "insights": [
            {
                "priority": "INFO",
                "type": "SIN DATOS",
                "finding": "No hay datos disponibles para el período seleccionado",
                "recommendation": "Verificar conexión a base de datos",
            }
        ],
        "detection_config": {
            "min_drop_gallons": CONFIG.min_drop_gallons,
            "min_drop_pct": CONFIG.min_drop_pct,
            "recovery_window_minutes": CONFIG.recovery_window_minutes,
            "theft_confirmed_threshold": CONFIG.theft_confirmed_threshold,
            "theft_suspected_threshold": CONFIG.theft_suspected_threshold,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE FOR TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(f"\n🛡️ Advanced Theft Detection Analysis - Last {days} days\n")

    result = analyze_fuel_drops_advanced(days)

    # Print summary
    print("=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    summary = result["summary"]
    print(f"  Eventos analizados: {summary['total_events_analyzed']}")
    print(f"  🚨 Robos confirmados: {summary['theft_confirmed']}")
    print(f"  ⚠️ Robos sospechosos: {summary['theft_suspected']}")
    print(f"  🔧 Problemas de sensor: {summary['sensor_issues']}")
    print(f"  ✅ Consumo normal: {summary['normal_consumption']}")
    print(
        f"  💰 Pérdida estimada: {summary['total_suspected_loss_gallons']:.1f} gal (${summary['total_suspected_loss_usd']:.2f})"
    )

    # Print trucks at risk
    if result["trucks_at_risk"]:
        print("\n" + "=" * 80)
        print("🚛 CAMIONES EN RIESGO")
        print("=" * 80)
        for truck in result["trucks_at_risk"][:10]:
            print(
                f"  {truck['truck_id']}: {truck['theft_events']} eventos, "
                f"{truck['total_loss_gallons']:.1f} gal, "
                f"confianza {truck['highest_confidence']:.0f}%, "
                f"riesgo {truck['risk_level']}"
            )

    # Print top events
    print("\n" + "=" * 80)
    print("📋 EVENTOS PRINCIPALES")
    print("=" * 80)
    for event in result["events"][:10]:
        print(
            f"  [{event['classification']}] {event['truck_id']} @ {event['timestamp']}"
        )
        print(
            f"    Caída: {event['fuel_drop_pct']:.0f}% ({event['fuel_drop_gallons']:.0f} gal)"
        )
        # Better movement status description
        dist = event.get("distance_miles", 0)
        if event["was_moving"] and dist > 0.5:
            movement_str = f"En ruta ({dist:.1f} mi)"
        elif event["was_moving"]:
            movement_str = "Motor encendido (sin desplazamiento)"
        else:
            movement_str = "Parqueado"
        print(f"    Confianza: {event['confidence_pct']:.0f}% | {movement_str}")
        print(f"    → {event['explanation']}")
        print()

    # Print insights
    print("=" * 80)
    print("💡 INSIGHTS")
    print("=" * 80)
    for insight in result["insights"]:
        print(f"  [{insight['priority']}] {insight['type']}")
        print(f"    {insight['finding']}")
        print(f"    → {insight['recommendation']}")
        print()
