"""
Driver Behavior Scoring Engine v1.0.0
═══════════════════════════════════════════════════════════════════════════════

Calculates driver safety scores based on REAL data from Wialon DB:
- OverSpeed events (event_id 54) - 15 point deduction per event
- Long Idle events (event_id 20) - 5 point deduction per hour
- DTC events (event_id 24) - 2 point deduction per new code
- Speedings table data (km/h over limit)

IMPORTANT: Based on VERIFIED data in Wialon DB (wialon_collect).
- We DO NOT have Harsh Accel/Brake/Corner events (112/113/114) yet
- We DO NOT have Fuel Theft/Refuel events (512/513) yet
- Scoring will expand when more event types become available

Score Range: 0-100
- 90-100: Excellent Driver ⭐
- 75-89: Good Driver 👍
- 60-74: Average Driver ⚠️
- Below 60: Needs Improvement 🔴

Pacific Track Device Configuration (from screenshots):
- Harsh Accel Threshold: 280 mg
- Harsh Brake Threshold: 320 mg
- Harsh Corner Threshold: 280 mg
- OverSpeed Threshold: 105 km/h

Author: Fuel Analytics Team
Version: 1.0.0
Created: December 2025
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging

# Import Pacific Track events for scoring
try:
    from pacific_track_events import (
        calculate_driver_score_impact,
        get_event_description,
        SCORING_EVENTS,
    )

    PACIFIC_TRACK_AVAILABLE = True
except ImportError:
    PACIFIC_TRACK_AVAILABLE = False

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING CONFIGURATION - Based on verified Wialon data
# ═══════════════════════════════════════════════════════════════════════════════


class EventType(Enum):
    """Event types available in Wialon DB"""

    OVER_SPEED = 54  # ✅ Available - 15 pts deduction
    LONG_IDLE = 20  # ✅ Available - 5 pts/hour deduction
    DTC_CHANGE = 24  # ✅ Available - 2 pts deduction
    TOWING_ALARM = 56  # ✅ Available - 25 pts deduction
    TOWING_START = 58  # ✅ Available - info only
    # Future events when detected by devices:
    # HARSH_ACCEL = 112   # ⏳ Not yet - 10 pts
    # HARSH_BRAKE = 113   # ⏳ Not yet - 10 pts
    # HARSH_CORNER = 114  # ⏳ Not yet - 10 pts


# Scoring deductions per event
SCORING_RULES = {
    # Currently available events
    EventType.OVER_SPEED: -15,  # Speeding is dangerous
    EventType.LONG_IDLE: -5,  # Per hour of idle
    EventType.DTC_CHANGE: -2,  # Driver may have caused issue
    EventType.TOWING_ALARM: -25,  # Potential theft/unauthorized movement
    # Future events (will be enabled when data available):
    # EventType.HARSH_ACCEL: -10,
    # EventType.HARSH_BRAKE: -10,
    # EventType.HARSH_CORNER: -10,
}

# Speeding severity multipliers (based on km/h over limit)
SPEEDING_SEVERITY = {
    "minor": {"threshold": 10, "multiplier": 1.0},  # 1-10 km/h over
    "moderate": {"threshold": 20, "multiplier": 1.5},  # 11-20 km/h over
    "severe": {"threshold": 30, "multiplier": 2.0},  # 21-30 km/h over
    "extreme": {"threshold": 999, "multiplier": 3.0},  # 31+ km/h over
}


@dataclass
class DriverEvent:
    """A single driving event that affects score"""

    truck_id: str
    event_type: EventType
    timestamp: datetime
    score_impact: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "event_type": self.event_type.name,
            "event_id": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "score_impact": self.score_impact,
            "details": self.details,
        }


@dataclass
class SpeedingEvent:
    """A speeding event from the speedings table"""

    truck_id: str
    timestamp: datetime
    max_speed_kmh: float
    speed_limit_kmh: float
    duration_seconds: int
    distance_meters: float
    score_impact: int

    @property
    def over_limit_kmh(self) -> float:
        return self.max_speed_kmh - self.speed_limit_kmh


@dataclass
class DriverScore:
    """Complete driver score with breakdown"""

    truck_id: str
    score: int  # 0-100
    grade: str  # Letter grade
    period_start: datetime
    period_end: datetime
    events: List[DriverEvent]
    speeding_events: List[SpeedingEvent]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "score": self.score,
            "grade": self.grade,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "events_count": len(self.events),
            "speeding_events_count": len(self.speeding_events),
            "summary": self.summary,
            "events": [e.to_dict() for e in self.events],
            "speeding_events": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "max_speed_kmh": s.max_speed_kmh,
                    "speed_limit_kmh": s.speed_limit_kmh,
                    "over_limit_kmh": s.over_limit_kmh,
                    "duration_seconds": s.duration_seconds,
                    "score_impact": s.score_impact,
                }
                for s in self.speeding_events
            ],
        }


class DriverScoringEngine:
    """
    Calculates driver safety scores from Wialon event data.

    Usage:
        engine = DriverScoringEngine()

        # Process events from Wialon sensors table
        engine.process_event(truck_id, event_id=54, timestamp, details)

        # Calculate score for a period
        score = engine.calculate_score(truck_id, period_days=30)

        # Get fleet ranking
        rankings = engine.get_fleet_rankings()
    """

    def __init__(self, base_score: int = 100):
        self.base_score = base_score
        self._events: Dict[str, List[DriverEvent]] = {}  # truck_id -> events
        self._speeding_events: Dict[str, List[SpeedingEvent]] = (
            {}
        )  # truck_id -> speeding
        self._idle_hours: Dict[str, float] = {}  # truck_id -> total idle hours

    def process_event(
        self,
        truck_id: str,
        event_id: int,
        timestamp: datetime,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[DriverEvent]:
        """
        Process a single event from Wialon.

        Args:
            truck_id: Vehicle identifier
            event_id: Pacific Track event ID (54, 20, 24, etc.)
            timestamp: When event occurred
            details: Additional event data

        Returns:
            DriverEvent if event affects score, None otherwise
        """
        # Map event_id to EventType
        try:
            event_type = EventType(event_id)
        except ValueError:
            # Event not tracked for scoring
            return None

        # Calculate score impact
        if PACIFIC_TRACK_AVAILABLE:
            score_impact = calculate_driver_score_impact(event_id)
        else:
            score_impact = SCORING_RULES.get(event_type, 0)

        if score_impact == 0:
            return None

        event = DriverEvent(
            truck_id=truck_id,
            event_type=event_type,
            timestamp=timestamp,
            score_impact=score_impact,
            details=details or {},
        )

        # Store event
        if truck_id not in self._events:
            self._events[truck_id] = []
        self._events[truck_id].append(event)

        logger.debug(f"[{truck_id}] Event {event_type.name}: {score_impact} pts")

        return event

    def process_speeding(
        self,
        truck_id: str,
        timestamp: datetime,
        max_speed_kmh: float,
        speed_limit_kmh: float,
        duration_seconds: int,
        distance_meters: float = 0,
    ) -> SpeedingEvent:
        """
        Process a speeding event from the speedings table.

        Args:
            truck_id: Vehicle identifier
            timestamp: When speeding started
            max_speed_kmh: Maximum recorded speed
            speed_limit_kmh: Road speed limit
            duration_seconds: How long speeding lasted
            distance_meters: Distance traveled while speeding

        Returns:
            SpeedingEvent with calculated score impact
        """
        over_limit = max_speed_kmh - speed_limit_kmh

        # Determine severity and calculate impact
        base_impact = -15  # Base deduction for speeding
        multiplier = 1.0

        for severity, config in SPEEDING_SEVERITY.items():
            if over_limit <= config["threshold"]:
                multiplier = config["multiplier"]
                break

        score_impact = int(base_impact * multiplier)

        event = SpeedingEvent(
            truck_id=truck_id,
            timestamp=timestamp,
            max_speed_kmh=max_speed_kmh,
            speed_limit_kmh=speed_limit_kmh,
            duration_seconds=duration_seconds,
            distance_meters=distance_meters,
            score_impact=score_impact,
        )

        if truck_id not in self._speeding_events:
            self._speeding_events[truck_id] = []
        self._speeding_events[truck_id].append(event)

        return event

    def add_idle_hours(self, truck_id: str, hours: float):
        """Add idle hours for a truck (affects score)"""
        current = self._idle_hours.get(truck_id, 0)
        self._idle_hours[truck_id] = current + hours

    def calculate_score(
        self,
        truck_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        period_days: int = 30,
    ) -> DriverScore:
        """
        Calculate driver score for a truck over a period.

        Args:
            truck_id: Vehicle identifier
            period_start: Start of scoring period (default: period_days ago)
            period_end: End of scoring period (default: now)
            period_days: Number of days to look back (default: 30)

        Returns:
            DriverScore with complete breakdown
        """
        now = datetime.now(timezone.utc)

        if period_end is None:
            period_end = now
        if period_start is None:
            period_start = period_end - timedelta(days=period_days)

        # Filter events in period
        events_in_period = []
        for event in self._events.get(truck_id, []):
            if period_start <= event.timestamp <= period_end:
                events_in_period.append(event)

        speeding_in_period = []
        for speeding in self._speeding_events.get(truck_id, []):
            if period_start <= speeding.timestamp <= period_end:
                speeding_in_period.append(speeding)

        # Calculate total deductions
        event_deductions = sum(e.score_impact for e in events_in_period)
        speeding_deductions = sum(s.score_impact for s in speeding_in_period)

        # Idle deductions (5 points per hour)
        idle_hours = self._idle_hours.get(truck_id, 0)
        idle_deductions = int(idle_hours * -5)

        total_deductions = event_deductions + speeding_deductions + idle_deductions

        # Calculate final score (minimum 0)
        score = max(0, self.base_score + total_deductions)

        # Determine grade
        grade = self._get_grade(score)

        # Build summary
        summary = {
            "base_score": self.base_score,
            "total_deductions": total_deductions,
            "breakdown": {
                "events": event_deductions,
                "speeding": speeding_deductions,
                "idle": idle_deductions,
            },
            "event_counts": {
                "total_events": len(events_in_period),
                "speeding_events": len(speeding_in_period),
                "by_type": self._count_by_type(events_in_period),
            },
            "idle_hours": idle_hours,
            "grade_info": self._get_grade_info(grade),
        }

        return DriverScore(
            truck_id=truck_id,
            score=score,
            grade=grade,
            period_start=period_start,
            period_end=period_end,
            events=events_in_period,
            speeding_events=speeding_in_period,
            summary=summary,
        )

    def _get_grade(self, score: int) -> str:
        """Get letter grade for score"""
        if score >= 90:
            return "A"  # Excellent ⭐
        elif score >= 80:
            return "B"  # Good 👍
        elif score >= 70:
            return "C"  # Average ⚠️
        elif score >= 60:
            return "D"  # Below Average
        else:
            return "F"  # Needs Improvement 🔴

    def _get_grade_info(self, grade: str) -> Dict[str, str]:
        """Get grade information"""
        grades = {
            "A": {
                "label": "Excelente",
                "emoji": "⭐",
                "description": "Conductor ejemplar",
            },
            "B": {"label": "Bueno", "emoji": "👍", "description": "Conducción segura"},
            "C": {"label": "Promedio", "emoji": "⚠️", "description": "Área de mejora"},
            "D": {"label": "Bajo", "emoji": "📉", "description": "Requiere atención"},
            "F": {
                "label": "Crítico",
                "emoji": "🔴",
                "description": "Necesita capacitación",
            },
        }
        return grades.get(grade, grades["C"])

    def _count_by_type(self, events: List[DriverEvent]) -> Dict[str, int]:
        """Count events by type"""
        counts = {}
        for event in events:
            type_name = event.event_type.name
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def get_fleet_rankings(
        self, period_days: int = 30, min_events: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get ranked list of all trucks by driver score.

        Args:
            period_days: Period to calculate scores for
            min_events: Minimum events to include in ranking

        Returns:
            List of trucks sorted by score (highest first)
        """
        all_truck_ids = set(self._events.keys()) | set(self._speeding_events.keys())

        rankings = []
        for truck_id in all_truck_ids:
            score = self.calculate_score(truck_id, period_days=period_days)

            # Only include if has minimum activity
            total_events = len(score.events) + len(score.speeding_events)
            if total_events >= min_events:
                rankings.append(
                    {
                        "truck_id": truck_id,
                        "score": score.score,
                        "grade": score.grade,
                        "total_events": total_events,
                        "deductions": score.summary["total_deductions"],
                    }
                )

        # Sort by score descending
        rankings.sort(key=lambda x: x["score"], reverse=True)

        # Add rank
        for i, r in enumerate(rankings, 1):
            r["rank"] = i

        return rankings

    def get_improvement_tips(self, truck_id: str) -> List[Dict[str, str]]:
        """
        Get personalized improvement tips based on driver's event history.

        Returns:
            List of tips with priority and description
        """
        score = self.calculate_score(truck_id)
        tips = []

        # Analyze event types
        by_type = score.summary["event_counts"]["by_type"]

        if by_type.get("OVER_SPEED", 0) > 0:
            tips.append(
                {
                    "priority": "high",
                    "category": "speeding",
                    "tip": "Respetar límites de velocidad. Cada exceso deduce 15-45 puntos.",
                    "icon": "🚦",
                }
            )

        if score.summary["idle_hours"] > 2:
            tips.append(
                {
                    "priority": "medium",
                    "category": "idle",
                    "tip": f"Reducir tiempo de ralentí ({score.summary['idle_hours']:.1f}h). Apagar motor en paradas largas.",
                    "icon": "⏱️",
                }
            )

        if by_type.get("DTC_CHANGE", 0) > 0:
            tips.append(
                {
                    "priority": "medium",
                    "category": "maintenance",
                    "tip": "Reportar códigos de falla inmediatamente. Verificar procedimientos pre-viaje.",
                    "icon": "🔧",
                }
            )

        if len(score.speeding_events) > 0:
            # Find worst speeding
            worst = max(score.speeding_events, key=lambda s: s.over_limit_kmh)
            tips.append(
                {
                    "priority": "high",
                    "category": "speeding",
                    "tip": f"Exceso máximo: {worst.over_limit_kmh:.0f} km/h sobre límite. Ajustar velocidad.",
                    "icon": "⚠️",
                }
            )

        if score.score >= 90:
            tips.append(
                {
                    "priority": "low",
                    "category": "recognition",
                    "tip": "¡Excelente conducción! Mantener el buen trabajo.",
                    "icon": "⭐",
                }
            )

        return tips


# ═══════════════════════════════════════════════════════════════════════════════
# WIALON DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════════


def load_events_from_wialon(
    engine: DriverScoringEngine, wialon_connection, period_days: int = 30
) -> int:
    """
    Load driving events from Wialon database into scoring engine.

    Args:
        engine: DriverScoringEngine instance
        wialon_connection: MySQL connection to Wialon DB
        period_days: How many days of data to load

    Returns:
        Number of events loaded
    """
    cursor = wialon_connection.cursor(dictionary=True)
    events_loaded = 0

    # Load Over Speed events (event_id = 54)
    cursor.execute(
        """
        SELECT 
            u.unit_name as truck_id,
            s.event_time as timestamp,
            s.event_id,
            s.event_value
        FROM sensors s
        JOIN units u ON s.unit_id = u.unit_id
        WHERE s.event_id = 54
          AND s.event_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY s.event_time
    """,
        (period_days,),
    )

    for row in cursor.fetchall():
        engine.process_event(
            truck_id=row["truck_id"],
            event_id=54,
            timestamp=row["timestamp"],
            details={"value": row.get("event_value")},
        )
        events_loaded += 1

    # Load Long Idle events (event_id = 20)
    cursor.execute(
        """
        SELECT 
            u.unit_name as truck_id,
            s.event_time as timestamp,
            s.event_id,
            s.event_value
        FROM sensors s
        JOIN units u ON s.unit_id = u.unit_id
        WHERE s.event_id = 20
          AND s.event_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY s.event_time
    """,
        (period_days,),
    )

    for row in cursor.fetchall():
        engine.process_event(
            truck_id=row["truck_id"],
            event_id=20,
            timestamp=row["timestamp"],
            details={"value": row.get("event_value")},
        )
        events_loaded += 1

    # Load speedings from speedings table
    cursor.execute(
        """
        SELECT 
            u.unit_name as truck_id,
            sp.start_time as timestamp,
            sp.max_speed as max_speed_kmh,
            sp.speed_limit as speed_limit_kmh,
            sp.duration_seconds,
            sp.distance as distance_meters
        FROM speedings sp
        JOIN units u ON sp.unit_id = u.unit_id
        WHERE sp.start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY sp.start_time
    """,
        (period_days,),
    )

    for row in cursor.fetchall():
        engine.process_speeding(
            truck_id=row["truck_id"],
            timestamp=row["timestamp"],
            max_speed_kmh=row["max_speed_kmh"],
            speed_limit_kmh=row["speed_limit_kmh"],
            duration_seconds=row["duration_seconds"],
            distance_meters=row.get("distance_meters", 0),
        )
        events_loaded += 1

    cursor.close()
    logger.info(f"Loaded {events_loaded} driver events from Wialon")

    return events_loaded


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_scoring_engine: Optional[DriverScoringEngine] = None


def get_scoring_engine() -> DriverScoringEngine:
    """Get or create global scoring engine instance"""
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = DriverScoringEngine()
    return _scoring_engine


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("\n" + "=" * 60)
    print("DRIVER SCORING ENGINE TEST")
    print("=" * 60)

    engine = DriverScoringEngine()

    # Simulate events
    now = datetime.now(timezone.utc)

    # Good driver - few events
    engine.process_event("CO0681", 54, now - timedelta(days=5))  # 1 overspeed
    score1 = engine.calculate_score("CO0681")
    print(f"\n[CO0681] Score: {score1.score} ({score1.grade})")
    print(f"  Deductions: {score1.summary['total_deductions']}")

    # Bad driver - many events
    for i in range(5):
        engine.process_event("PC1280", 54, now - timedelta(days=i))  # 5 overspeeds
    engine.process_speeding("PC1280", now, 140, 105, 120, 5000)  # 35 km/h over!
    engine.add_idle_hours("PC1280", 4.5)  # 4.5 hours idle

    score2 = engine.calculate_score("PC1280")
    print(f"\n[PC1280] Score: {score2.score} ({score2.grade})")
    print(f"  Deductions: {score2.summary['total_deductions']}")
    print(f"  Breakdown: {score2.summary['breakdown']}")

    # Get tips
    print(f"\n  Tips for improvement:")
    for tip in engine.get_improvement_tips("PC1280"):
        print(f"    {tip['icon']} [{tip['priority']}] {tip['tip']}")

    # Fleet rankings
    print("\n" + "-" * 40)
    print("FLEET RANKINGS:")
    for r in engine.get_fleet_rankings():
        print(f"  #{r['rank']} {r['truck_id']}: {r['score']} ({r['grade']})")

    print("\n" + "=" * 60)
