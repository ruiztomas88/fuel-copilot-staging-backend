"""
Anomaly Detection Engine using Isolation Forest
Detects fuel theft, sensor malfunctions, and unusual consumption patterns
Part of ML/AI Roadmap - Feature #3
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pymysql
from pymysql.cursors import DictCursor
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AnomalyDetection:
    """Represents a detected anomaly"""

    truck_id: str
    timestamp: datetime
    anomaly_type: str  # 'fuel_theft', 'sensor_malfunction', 'unusual_consumption'
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    anomaly_score: float  # -1 to 1, lower is more anomalous
    features: Dict[str, float]  # Feature values that triggered detection
    description: str

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "truck_id": self.truck_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "anomaly_score": round(self.anomaly_score, 3),
            "features": {k: round(v, 2) for k, v in self.features.items()},
            "description": self.description,
        }


class AnomalyDetector:
    """
    Detects anomalies in fuel consumption using Isolation Forest.

    Anomaly Types:
    - Fuel Theft: Large drop in fuel level while parked
    - Sensor Malfunction: Erratic readings, impossible values
    - Unusual Consumption: MPG far outside normal range for conditions
    """

    def __init__(self, db_connection=None):
        """
        Initialize anomaly detector

        Args:
            db_connection: Optional database connection. If None, creates new connection.
        """
        if db_connection:
            self.db = db_connection
        else:
            self.db = pymysql.connect(
                host=os.getenv("MYSQL_HOST", "localhost"),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "fuel_copilot_local"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                charset="utf8mb4",
                autocommit=True,
                cursorclass=DictCursor,
            )

        # Isolation Forest parameters
        self.contamination = 0.05  # Expected proportion of anomalies (5%)
        self.n_estimators = 100
        self.random_state = 42

        # Models (trained on-demand)
        self.models: Dict[str, IsolationForest] = {}
        self.scalers: Dict[str, StandardScaler] = {}

    def extract_features(
        self, truck_id: str, period_days: int = 7, min_samples: int = 50
    ) -> Optional[np.ndarray]:
        """
        Extract features for anomaly detection

        Features:
        - mpg_current
        - fuel_level_pct
        - idle_hours_pct
        - speed_avg
        - fuel_flow_rate (gallons/hour)
        - fuel_level_change_rate (% per hour)

        Args:
            truck_id: Truck identifier
            period_days: Days of historical data to extract
            min_samples: Minimum samples required

        Returns:
            NumPy array of features (n_samples, n_features) or None
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    mpg_current,
                    estimated_pct as fuel_level_pct,
                    idle_hours_ecu / NULLIF(engine_hours, 0) * 100 as idle_pct,
                    speed_mph as speed_avg,
                    estimated_gallons / NULLIF(TIMESTAMPDIFF(HOUR, LAG(timestamp_utc) OVER (ORDER BY timestamp_utc), timestamp_utc), 0) as fuel_flow_rate,
                    (estimated_pct - LAG(estimated_pct) OVER (ORDER BY timestamp_utc)) / 
                        NULLIF(TIMESTAMPDIFF(HOUR, LAG(timestamp_utc) OVER (ORDER BY timestamp_utc), timestamp_utc), 0) as fuel_change_rate
                FROM fuel_metrics
                WHERE truck_id = %s
                  AND timestamp_utc >= %s
                  AND timestamp_utc <= %s
                  AND mpg_current IS NOT NULL
                  AND mpg_current > 0
                  AND estimated_pct IS NOT NULL
                ORDER BY timestamp_utc
            """,
                (truck_id, start_date, end_date),
            )

            rows = cursor.fetchall()

        if len(rows) < min_samples:
            logger.info(
                f"Insufficient samples for {truck_id}: {len(rows)} < {min_samples}"
            )
            return None

        # Extract features
        features = []
        for row in rows:
            if row["mpg_current"] is None:
                continue

            feature_vector = [
                float(row["mpg_current"] or 0),
                float(row["fuel_level_pct"] or 0),
                float(row["idle_pct"] or 0),
                float(row["speed_avg"] or 0),
                float(row["fuel_flow_rate"] or 0),
                float(row["fuel_change_rate"] or 0),
            ]

            # Skip if any feature is NaN or inf
            if any(np.isnan(feature_vector)) or any(np.isinf(feature_vector)):
                continue

            features.append(feature_vector)

        if len(features) < min_samples:
            return None

        return np.array(features)

    def train_model(self, truck_id: str, period_days: int = 30) -> bool:
        """
        Train Isolation Forest model for a truck

        Args:
            truck_id: Truck identifier
            period_days: Days of training data

        Returns:
            True if training successful, False otherwise
        """
        features = self.extract_features(
            truck_id, period_days=period_days, min_samples=100
        )

        if features is None:
            logger.warning(f"Cannot train model for {truck_id}: insufficient data")
            return False

        # Scale features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        # Train Isolation Forest
        model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        model.fit(features_scaled)

        # Store model and scaler
        self.models[truck_id] = model
        self.scalers[truck_id] = scaler

        logger.info(
            f"Trained anomaly model for {truck_id} with {len(features)} samples"
        )
        return True

    def detect_anomalies(
        self, truck_id: str, check_period_days: int = 1, retrain: bool = False
    ) -> List[AnomalyDetection]:
        """
        Detect anomalies for a truck

        Args:
            truck_id: Truck identifier
            check_period_days: Days to check for anomalies
            retrain: Force model retraining

        Returns:
            List of detected anomalies
        """
        # Train model if not exists or retrain requested
        if truck_id not in self.models or retrain:
            success = self.train_model(truck_id)
            if not success:
                return []

        # Get recent data
        features = self.extract_features(
            truck_id, period_days=check_period_days, min_samples=1
        )

        if features is None:
            return []

        # Scale features
        scaler = self.scalers[truck_id]
        features_scaled = scaler.transform(features)

        # Predict anomalies
        predictions = self.models[truck_id].predict(features_scaled)
        scores = self.models[truck_id].decision_function(features_scaled)

        # Get timestamps
        end_date = datetime.now()
        start_date = end_date - timedelta(days=check_period_days)

        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT timestamp_utc
                FROM fuel_metrics
                WHERE truck_id = %s
                  AND timestamp_utc >= %s
                  AND timestamp_utc <= %s
                  AND mpg_current IS NOT NULL
                ORDER BY timestamp_utc
            """,
                (truck_id, start_date, end_date),
            )

            timestamps = [row["timestamp_utc"] for row in cursor.fetchall()]

        # Build anomaly list
        anomalies = []
        feature_names = [
            "mpg",
            "fuel_level_pct",
            "idle_pct",
            "speed_avg",
            "fuel_flow_rate",
            "fuel_change_rate",
        ]

        for i, (prediction, score) in enumerate(zip(predictions, scores)):
            if prediction == -1:  # Anomaly detected
                if i >= len(timestamps):
                    continue

                # Classify anomaly type
                feature_dict = {
                    name: features[i][j] for j, name in enumerate(feature_names)
                }
                anomaly_type, description = self._classify_anomaly(feature_dict)

                # Determine severity based on score
                severity = self._determine_severity(score)

                anomaly = AnomalyDetection(
                    truck_id=truck_id,
                    timestamp=timestamps[i],
                    anomaly_type=anomaly_type,
                    severity=severity,
                    anomaly_score=float(score),
                    features=feature_dict,
                    description=description,
                )
                anomalies.append(anomaly)

        return anomalies

    def _classify_anomaly(self, features: Dict[str, float]) -> Tuple[str, str]:
        """
        Classify anomaly type based on feature values

        Args:
            features: Feature dictionary

        Returns:
            Tuple of (anomaly_type, description)
        """
        mpg = features["mpg"]
        fuel_change_rate = features["fuel_change_rate"]
        idle_pct = features["idle_pct"]
        speed = features["speed_avg"]

        # Fuel theft: Large negative fuel change while parked
        if fuel_change_rate < -10 and speed < 5:
            return (
                "fuel_theft",
                f"Large fuel drop ({fuel_change_rate:.1f}%/hr) while parked",
            )

        # Sensor malfunction: Impossible values
        if mpg > 15 or mpg < 1:
            return "sensor_malfunction", f"Impossible MPG value: {mpg:.2f}"

        if features["fuel_level_pct"] > 100 or features["fuel_level_pct"] < 0:
            return (
                "sensor_malfunction",
                f'Invalid fuel level: {features["fuel_level_pct"]:.1f}%',
            )

        # Unusual consumption: Very low MPG
        if mpg < 3 and idle_pct < 30:
            return (
                "unusual_consumption",
                f"Unusually low MPG: {mpg:.2f} (not idle-related)",
            )

        # Very high idle
        if idle_pct > 80:
            return "unusual_consumption", f"Excessive idle time: {idle_pct:.1f}%"

        # Default
        return "unusual_consumption", "Anomalous fuel consumption pattern detected"

    def _determine_severity(self, score: float) -> str:
        """
        Determine severity based on anomaly score

        Args:
            score: Anomaly score from Isolation Forest (-1 to 1)

        Returns:
            Severity level: CRITICAL, HIGH, MEDIUM, LOW
        """
        # Lower score = more anomalous
        if score < -0.3:
            return "CRITICAL"
        elif score < -0.2:
            return "HIGH"
        elif score < -0.1:
            return "MEDIUM"
        else:
            return "LOW"

    def get_fleet_anomalies(
        self, check_period_days: int = 1, min_severity: str = "LOW"
    ) -> Dict[str, List[AnomalyDetection]]:
        """
        Get anomalies for entire fleet

        Args:
            check_period_days: Days to check
            min_severity: Minimum severity to report

        Returns:
            Dictionary mapping truck_id to list of anomalies
        """
        # Get all trucks
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT truck_id
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
                ORDER BY truck_id
            """,
                (check_period_days,),
            )

            truck_ids = [row["truck_id"] for row in cursor.fetchall()]

        severity_levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        min_severity_level = severity_levels.get(min_severity, 0)

        fleet_anomalies = {}
        for truck_id in truck_ids:
            anomalies = self.detect_anomalies(
                truck_id, check_period_days=check_period_days
            )

            # Filter by severity
            filtered_anomalies = [
                a
                for a in anomalies
                if severity_levels.get(a.severity, 0) >= min_severity_level
            ]

            if filtered_anomalies:
                fleet_anomalies[truck_id] = filtered_anomalies

        return fleet_anomalies

    def store_anomaly(self, anomaly: AnomalyDetection) -> bool:
        """
        Store anomaly in database

        Args:
            anomaly: AnomalyDetection object

        Returns:
            True if stored successfully
        """
        try:
            # Create table if not exists
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS anomaly_detections (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        truck_id VARCHAR(50) NOT NULL,
                        timestamp_utc DATETIME NOT NULL,
                        anomaly_type VARCHAR(50) NOT NULL,
                        severity VARCHAR(20) NOT NULL,
                        anomaly_score FLOAT NOT NULL,
                        features JSON,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_truck_timestamp (truck_id, timestamp_utc),
                        INDEX idx_severity (severity),
                        INDEX idx_type (anomaly_type),
                        INDEX idx_created (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
                )

            # Insert anomaly
            import json

            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO anomaly_detections 
                    (truck_id, timestamp_utc, anomaly_type, severity, anomaly_score, features, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        anomaly.truck_id,
                        anomaly.timestamp,
                        anomaly.anomaly_type,
                        anomaly.severity,
                        anomaly.anomaly_score,
                        json.dumps(anomaly.features),
                        anomaly.description,
                    ),
                )

            return True

        except Exception as e:
            logger.error(f"Error storing anomaly: {e}")
            return False


# Singleton instance
_anomaly_detector_instance = None


def get_anomaly_detector(db_connection=None) -> AnomalyDetector:
    """Get singleton instance of AnomalyDetector"""
    global _anomaly_detector_instance
    if _anomaly_detector_instance is None:
        _anomaly_detector_instance = AnomalyDetector(db_connection=db_connection)
    return _anomaly_detector_instance
