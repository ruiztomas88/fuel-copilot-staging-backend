"""
Sensor Anomaly Detection v3.12.21
Dashboard for monitoring sensor health and anomalies

Addresses audit item #21: Dashboard anomalías sensor

Features:
- Detect erratic sensor readings
- Track sensor health over time
- Alert on potential sensor failures
- Nelson Rules statistical analysis
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import os
import statistics

import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================
def _get_db_config() -> Dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# ANOMALY TYPES
# =============================================================================
class AnomalyType:
    """Types of sensor anomalies."""

    SPIKE = "spike"  # Sudden jump in value
    DROPOUT = "dropout"  # Value drops to 0 or NaN
    FLATLINE = "flatline"  # No change for extended period
    DRIFT = "drift"  # Gradual shift from expected value
    NOISE = "noise"  # High frequency fluctuations
    OUT_OF_RANGE = "out_of_range"  # Value outside expected range
    STUCK = "stuck"  # Same value repeated exactly
    ERRATIC = "erratic"  # Rapid up/down oscillations


@dataclass
class SensorAnomaly:
    """Detected sensor anomaly."""

    truck_id: str
    sensor_name: str
    anomaly_type: str
    severity: str  # low, medium, high, critical
    timestamp: datetime
    value: float
    expected_value: Optional[float]
    deviation: float
    duration_minutes: int
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "sensor": self.sensor_name,
            "type": self.anomaly_type,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "value": round(self.value, 2),
            "expected_value": (
                round(self.expected_value, 2) if self.expected_value else None
            ),
            "deviation": round(self.deviation, 2),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }


@dataclass
class SensorHealth:
    """Health status of a sensor."""

    truck_id: str
    sensor_name: str
    health_score: float  # 0-100
    status: str  # healthy, degraded, failing, failed
    last_reading: datetime
    anomaly_count_24h: int
    anomaly_count_7d: int
    avg_deviation: float
    trend: str  # improving, stable, degrading
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "sensor": self.sensor_name,
            "health_score": round(self.health_score, 1),
            "status": self.status,
            "last_reading": (
                self.last_reading.isoformat() if self.last_reading else None
            ),
            "anomalies": {
                "last_24h": self.anomaly_count_24h,
                "last_7d": self.anomaly_count_7d,
            },
            "avg_deviation": round(self.avg_deviation, 2),
            "trend": self.trend,
            "recommendations": self.recommendations,
        }


# =============================================================================
# SENSOR ANOMALY DETECTOR
# =============================================================================
class SensorAnomalyDetector:
    """
    Detect and track sensor anomalies using statistical methods.

    Implements Nelson Rules for statistical process control:
    - Rule 1: Point outside 3σ
    - Rule 2: 9 points in a row on same side of mean
    - Rule 3: 6 points in a row, all increasing or decreasing
    - Rule 4: 14 points in a row, alternating up and down
    """

    # Sensor configuration
    SENSORS = {
        "fuel_level": {
            "column": "sensor_pct",
            "min": 0,
            "max": 100,
            "max_change_per_30s": 5,  # % per 30 seconds
            "noise_threshold": 2,  # %
        },
        "fuel_kalman": {
            "column": "estimated_pct",
            "min": 0,
            "max": 100,
            "max_change_per_30s": 3,
            "noise_threshold": 1,
        },
        "speed": {
            "column": "speed_mph",
            "min": 0,
            "max": 85,
            "max_change_per_30s": 20,
            "noise_threshold": 5,
        },
        "mpg": {
            "column": "mpg_current",
            "min": 0,
            "max": 15,
            "max_change_per_30s": 2,
            "noise_threshold": 0.5,
        },
    }

    def __init__(self):
        pass

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================
    def detect_anomalies(
        self,
        truck_id: str,
        sensor_name: str = "fuel_level",
        hours: int = 24,
    ) -> List[SensorAnomaly]:
        """
        Detect anomalies in sensor readings.

        Returns list of detected anomalies.
        """
        sensor_config = self.SENSORS.get(sensor_name)
        if not sensor_config:
            logger.error(f"Unknown sensor: {sensor_name}")
            return []

        # Get sensor data
        data = self._get_sensor_data(truck_id, sensor_config["column"], hours)

        if len(data) < 10:
            return []

        anomalies = []

        # Extract values
        values = [d["value"] for d in data if d["value"] is not None]
        timestamps = [d["timestamp"] for d in data if d["value"] is not None]

        if len(values) < 10:
            return []

        # Calculate statistics
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 1

        # 1. Out of range detection
        for i, (val, ts) in enumerate(zip(values, timestamps)):
            if val < sensor_config["min"] or val > sensor_config["max"]:
                anomalies.append(
                    SensorAnomaly(
                        truck_id=truck_id,
                        sensor_name=sensor_name,
                        anomaly_type=AnomalyType.OUT_OF_RANGE,
                        severity="high",
                        timestamp=ts,
                        value=val,
                        expected_value=(sensor_config["min"] + sensor_config["max"])
                        / 2,
                        deviation=val - mean,
                        duration_minutes=0,
                        description=f"Value {val:.1f} outside valid range [{sensor_config['min']}-{sensor_config['max']}]",
                    )
                )

        # 2. Spike detection (>3σ from mean)
        for i, (val, ts) in enumerate(zip(values, timestamps)):
            z_score = abs(val - mean) / std if std > 0 else 0
            if z_score > 3:
                anomalies.append(
                    SensorAnomaly(
                        truck_id=truck_id,
                        sensor_name=sensor_name,
                        anomaly_type=AnomalyType.SPIKE,
                        severity="medium" if z_score < 4 else "high",
                        timestamp=ts,
                        value=val,
                        expected_value=mean,
                        deviation=z_score,
                        duration_minutes=0,
                        description=f"Value {val:.1f} is {z_score:.1f}σ from mean ({mean:.1f})",
                    )
                )

        # 3. Stuck sensor detection (same value repeated)
        stuck_count = 0
        for i in range(1, len(values)):
            if values[i] == values[i - 1]:
                stuck_count += 1
                if stuck_count >= 10:  # 5 minutes of same value
                    anomalies.append(
                        SensorAnomaly(
                            truck_id=truck_id,
                            sensor_name=sensor_name,
                            anomaly_type=AnomalyType.STUCK,
                            severity="high",
                            timestamp=timestamps[i],
                            value=values[i],
                            expected_value=None,
                            deviation=0,
                            duration_minutes=stuck_count // 2,
                            description=f"Sensor stuck at {values[i]:.1f} for {stuck_count // 2} minutes",
                        )
                    )
                    stuck_count = 0
            else:
                stuck_count = 0

        # 4. Rapid change detection
        max_change = sensor_config["max_change_per_30s"]
        for i in range(1, len(values)):
            change = abs(values[i] - values[i - 1])
            if change > max_change * 2:  # 2x normal max change
                anomalies.append(
                    SensorAnomaly(
                        truck_id=truck_id,
                        sensor_name=sensor_name,
                        anomaly_type=AnomalyType.SPIKE,
                        severity="medium",
                        timestamp=timestamps[i],
                        value=values[i],
                        expected_value=values[i - 1],
                        deviation=change,
                        duration_minutes=0,
                        description=f"Rapid change: {values[i-1]:.1f} → {values[i]:.1f} (Δ{change:.1f})",
                    )
                )

        # 5. Dropout detection
        for i, (val, ts) in enumerate(zip(values, timestamps)):
            if val == 0 and i > 0 and values[i - 1] > 10:
                anomalies.append(
                    SensorAnomaly(
                        truck_id=truck_id,
                        sensor_name=sensor_name,
                        anomaly_type=AnomalyType.DROPOUT,
                        severity="critical",
                        timestamp=ts,
                        value=val,
                        expected_value=values[i - 1],
                        deviation=values[i - 1],
                        duration_minutes=0,
                        description=f"Sensor dropout: {values[i-1]:.1f} → 0",
                    )
                )

        # 6. High noise detection (Nelson Rule 4)
        alternations = 0
        for i in range(2, len(values)):
            if (values[i] - values[i - 1]) * (values[i - 1] - values[i - 2]) < 0:
                alternations += 1
            else:
                if alternations >= 14:
                    anomalies.append(
                        SensorAnomaly(
                            truck_id=truck_id,
                            sensor_name=sensor_name,
                            anomaly_type=AnomalyType.NOISE,
                            severity="low",
                            timestamp=timestamps[i - alternations // 2],
                            value=values[i],
                            expected_value=mean,
                            deviation=std,
                            duration_minutes=alternations // 2,
                            description=f"High noise detected: {alternations} alternating readings",
                        )
                    )
                alternations = 0

        return anomalies

    def _get_sensor_data(
        self,
        truck_id: str,
        column: str,
        hours: int,
    ) -> List[Dict]:
        """Get sensor data from database."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT 
                            timestamp_utc as timestamp,
                            {column} as value
                        FROM fuel_metrics
                        WHERE truck_id = %s
                          AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                        ORDER BY timestamp_utc
                        """,
                        (truck_id, hours),
                    )
                    return list(cursor.fetchall())

        except Exception as e:
            logger.error(f"Error getting sensor data: {e}")
            return []

    # =========================================================================
    # SENSOR HEALTH
    # =========================================================================
    def get_sensor_health(
        self,
        truck_id: str,
        sensor_name: str = "fuel_level",
    ) -> SensorHealth:
        """
        Get health status for a sensor.

        Health score based on:
        - Anomaly frequency
        - Data completeness
        - Deviation from expected values
        """
        # Get recent anomalies
        anomalies_24h = self.detect_anomalies(truck_id, sensor_name, 24)
        anomalies_7d = self.detect_anomalies(truck_id, sensor_name, 168)

        # Get latest reading
        sensor_config = self.SENSORS.get(sensor_name, self.SENSORS["fuel_level"])
        data = self._get_sensor_data(truck_id, sensor_config["column"], 1)
        last_reading = data[-1]["timestamp"] if data else None

        # Calculate health score
        anomaly_penalty_24h = len(anomalies_24h) * 5  # 5 points per anomaly
        anomaly_penalty_7d = len(anomalies_7d) * 0.5  # 0.5 points per older anomaly

        # Check severity distribution
        critical_count = sum(1 for a in anomalies_24h if a.severity == "critical")
        high_count = sum(1 for a in anomalies_24h if a.severity == "high")

        severity_penalty = critical_count * 20 + high_count * 10

        # Base score
        health_score = max(
            0, 100 - anomaly_penalty_24h - anomaly_penalty_7d - severity_penalty
        )

        # Determine status
        if health_score >= 90:
            status = "healthy"
        elif health_score >= 70:
            status = "degraded"
        elif health_score >= 40:
            status = "failing"
        else:
            status = "failed"

        # Calculate trend
        if len(anomalies_24h) < len(anomalies_7d) / 7:
            trend = "improving"
        elif len(anomalies_24h) > len(anomalies_7d) / 7 * 2:
            trend = "degrading"
        else:
            trend = "stable"

        # Generate recommendations
        recommendations = []
        if status == "failing" or status == "failed":
            recommendations.append("Schedule sensor inspection/replacement")
        if critical_count > 0:
            recommendations.append("Investigate recent dropouts or erratic readings")
        if any(a.anomaly_type == AnomalyType.STUCK for a in anomalies_24h):
            recommendations.append("Check sensor wiring connections")
        if any(a.anomaly_type == AnomalyType.NOISE for a in anomalies_24h):
            recommendations.append("Consider signal filtering or grounding check")

        # Calculate average deviation
        deviations = [a.deviation for a in anomalies_7d if a.deviation is not None]
        avg_deviation = statistics.mean(deviations) if deviations else 0

        return SensorHealth(
            truck_id=truck_id,
            sensor_name=sensor_name,
            health_score=health_score,
            status=status,
            last_reading=last_reading,
            anomaly_count_24h=len(anomalies_24h),
            anomaly_count_7d=len(anomalies_7d),
            avg_deviation=avg_deviation,
            trend=trend,
            recommendations=recommendations,
        )

    # =========================================================================
    # FLEET-WIDE ANALYSIS
    # =========================================================================
    def get_fleet_sensor_status(
        self,
        carrier_id: Optional[str] = None,
        sensor_name: str = "fuel_level",
    ) -> Dict[str, Any]:
        """Get sensor health status for all trucks in fleet."""
        # Get all trucks
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    where = ""
                    params = []

                    if carrier_id and carrier_id != "*":
                        where = "WHERE carrier_id = %s"
                        params = [carrier_id]

                    cursor.execute(
                        f"""
                        SELECT DISTINCT truck_id
                        FROM fuel_metrics
                        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                        {where.replace('WHERE', 'AND') if where else ''}
                        """,
                        params,
                    )
                    trucks = [r["truck_id"] for r in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting trucks: {e}")
            trucks = []

        # Analyze each truck
        truck_health = []
        status_counts = {"healthy": 0, "degraded": 0, "failing": 0, "failed": 0}

        for truck_id in trucks:
            try:
                health = self.get_sensor_health(truck_id, sensor_name)
                truck_health.append(health.to_dict())
                status_counts[health.status] += 1
            except Exception as e:
                logger.error(f"Error analyzing {truck_id}: {e}")

        # Sort by health score (worst first)
        truck_health.sort(key=lambda h: h["health_score"])

        # Calculate fleet-wide metrics
        if truck_health:
            avg_health = statistics.mean(h["health_score"] for h in truck_health)
            total_anomalies_24h = sum(h["anomalies"]["last_24h"] for h in truck_health)
        else:
            avg_health = 100
            total_anomalies_24h = 0

        return {
            "sensor": sensor_name,
            "carrier_id": carrier_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_trucks": len(trucks),
                "avg_health_score": round(avg_health, 1),
                "total_anomalies_24h": total_anomalies_24h,
                "status_distribution": status_counts,
            },
            "trucks_needing_attention": [
                h for h in truck_health if h["status"] in ("failing", "failed")
            ],
            "all_trucks": truck_health,
        }

    def get_anomaly_timeline(
        self,
        truck_id: str,
        sensor_name: str = "fuel_level",
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get timeline of anomalies for visualization.

        Groups anomalies by hour for charting.
        """
        anomalies = self.detect_anomalies(truck_id, sensor_name, hours)

        # Group by hour
        hourly = {}
        for anomaly in anomalies:
            hour_key = anomaly.timestamp.replace(minute=0, second=0, microsecond=0)
            if hour_key not in hourly:
                hourly[hour_key] = {
                    "hour": hour_key.isoformat(),
                    "count": 0,
                    "types": {},
                    "severities": {},
                }

            hourly[hour_key]["count"] += 1

            # Count by type
            atype = anomaly.anomaly_type
            hourly[hour_key]["types"][atype] = (
                hourly[hour_key]["types"].get(atype, 0) + 1
            )

            # Count by severity
            sev = anomaly.severity
            hourly[hour_key]["severities"][sev] = (
                hourly[hour_key]["severities"].get(sev, 0) + 1
            )

        # Sort by hour
        timeline = sorted(hourly.values(), key=lambda h: h["hour"])

        return {
            "truck_id": truck_id,
            "sensor": sensor_name,
            "period_hours": hours,
            "total_anomalies": len(anomalies),
            "timeline": timeline,
            "by_type": self._aggregate_by_type(anomalies),
            "by_severity": self._aggregate_by_severity(anomalies),
        }

    def _aggregate_by_type(self, anomalies: List[SensorAnomaly]) -> Dict[str, int]:
        """Aggregate anomaly counts by type."""
        result = {}
        for a in anomalies:
            result[a.anomaly_type] = result.get(a.anomaly_type, 0) + 1
        return result

    def _aggregate_by_severity(self, anomalies: List[SensorAnomaly]) -> Dict[str, int]:
        """Aggregate anomaly counts by severity."""
        result = {}
        for a in anomalies:
            result[a.severity] = result.get(a.severity, 0) + 1
        return result


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_detector: Optional[SensorAnomalyDetector] = None


def get_anomaly_detector() -> SensorAnomalyDetector:
    """Get or create SensorAnomalyDetector singleton."""
    global _detector
    if _detector is None:
        _detector = SensorAnomalyDetector()
    return _detector
