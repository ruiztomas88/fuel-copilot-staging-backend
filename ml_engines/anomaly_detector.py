"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    ENGINE ANOMALY DETECTOR                                     ║
║               Isolation Forest for Predictive Maintenance                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Uses machine learning to detect engine anomalies BEFORE failures occur.       ║
║  No labels required - learns "normal" patterns and flags deviations.           ║
║                                                                                ║
║  Features extracted from existing sensors:                                     ║
║  - oil_pressure_psi (normalized by RPM)                                        ║
║  - coolant_temp_f / oil_temp_f ratio                                          ║
║  - consumption patterns                                                        ║
║  - idle behavior                                                               ║
║  - pressure stability                                                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Fuel Copilot ML Team
Version: 1.0.0
Date: December 2025
"""

import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pickle
import hashlib
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory for cached models
MODEL_CACHE_DIR = Path("/tmp/fuel_copilot_models")
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class EngineAnomalyDetector:
    """
    Isolation Forest-based anomaly detector for engine health.

    How it works:
    1. Extracts features from sensor data (oil pressure, temps, consumption)
    2. Trains on "normal" historical data (no failures)
    3. Scores new data points: -1 = anomaly, 1 = normal
    4. Converts to 0-100 score (100 = most anomalous)

    Key insight: Isolation Forest doesn't need labeled failure data.
    It learns what "normal" looks like and flags anything different.
    """

    def __init__(self, contamination: float = 0.05):
        """
        Initialize detector.

        Args:
            contamination: Expected proportion of anomalies (0.01-0.1)
                          Lower = more strict, fewer anomalies flagged
                          0.05 = expect ~5% of data to be anomalous
        """
        self.contamination = contamination
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,  # Use all CPU cores
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            "oil_press_normalized",
            "coolant_oil_ratio",
            "temp_delta",
            "consumption_rate",
            "idle_ratio",
            "pressure_stability",
            "rpm_efficiency",
            "temp_rise_rate",
        ]
        self.feature_stats = {}  # For z-score calculation

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract ML features from raw sensor data.

        This is where domain knowledge meets ML:
        - Oil pressure should correlate with RPM
        - Temperature ratios matter more than absolutes
        - Patterns over time reveal issues

        Args:
            df: Raw sensor DataFrame with columns:
                oil_pressure_psi, coolant_temp_f, oil_temp_f,
                rpm, speed_mph, consumption_gph, engine_hours, idle_hours

        Returns:
            Feature DataFrame ready for ML
        """
        features = pd.DataFrame()

        # Basic validation
        if df.empty or len(df) < 5:
            return features

        # Feature 1: Oil pressure normalized by RPM
        # Low pressure at high RPM = bad
        rpm_factor = np.maximum(df["rpm"].fillna(1000) / 1000, 0.5)
        features["oil_press_normalized"] = (
            df["oil_pressure_psi"].fillna(35) / rpm_factor
        )

        # Feature 2: Coolant to Oil temp ratio
        # Should stay relatively constant
        oil_temp = df["oil_temp_f"].fillna(200).replace(0, 200)
        features["coolant_oil_ratio"] = df["coolant_temp_f"].fillna(180) / oil_temp

        # Feature 3: Temperature delta
        # Large delta between oil and coolant = potential issue
        features["temp_delta"] = df["oil_temp_f"].fillna(200) - df[
            "coolant_temp_f"
        ].fillna(180)

        # Feature 4: Consumption rate
        features["consumption_rate"] = df["consumption_gph"].fillna(3).clip(0, 20)

        # Feature 5: Idle ratio
        # High idle ratio combined with high consumption = inefficiency
        engine_hrs = df["engine_hours"].fillna(1).replace(0, 1)
        idle_hrs = df["idle_hours"].fillna(0)
        features["idle_ratio"] = (idle_hrs / engine_hrs).clip(0, 1)

        # Feature 6: Pressure stability (rolling std)
        if len(df) >= 5:
            features["pressure_stability"] = (
                df["oil_pressure_psi"]
                .fillna(35)
                .rolling(window=min(5, len(df)), min_periods=1)
                .std()
                .fillna(2)
            )
        else:
            features["pressure_stability"] = 2.0

        # Feature 7: RPM efficiency (speed per RPM)
        rpm_safe = df["rpm"].fillna(1500).replace(0, 1500)
        features["rpm_efficiency"] = df["speed_mph"].fillna(0) / (rpm_safe / 1000)

        # Feature 8: Temperature rise rate
        if len(df) >= 2:
            features["temp_rise_rate"] = (
                df["oil_temp_f"].fillna(200).diff().fillna(0).clip(-10, 10)
            )
        else:
            features["temp_rise_rate"] = 0.0

        # Handle infinities and NaN
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(features.median())

        # Final fallback for any remaining NaN
        features = features.fillna(0)

        return features

    def train(self, historical_data: pd.DataFrame, min_samples: int = 50) -> bool:
        """
        Train the model on historical data.

        Args:
            historical_data: Raw sensor data (should be "normal" operation)
            min_samples: Minimum data points required

        Returns:
            True if training successful
        """
        if len(historical_data) < min_samples:
            logger.warning(
                f"Insufficient data for training: {len(historical_data)} < {min_samples}"
            )
            return False

        # Extract features
        features = self.extract_features(historical_data)

        if features.empty or len(features) < min_samples:
            logger.warning("Feature extraction failed or insufficient features")
            return False

        # Store feature statistics for z-score calculation
        for col in features.columns:
            self.feature_stats[col] = {
                "mean": features[col].mean(),
                "std": features[col].std() or 1.0,
            }

        # Scale features
        scaled = self.scaler.fit_transform(features)

        # Train model
        self.model.fit(scaled)
        self.is_trained = True

        logger.info(f"✅ Anomaly detector trained on {len(features)} samples")
        return True

    def predict(self, current_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Predict anomaly score for current data.

        Args:
            current_data: Recent sensor readings

        Returns:
            Dict with:
                - anomaly_score: 0-100 (100 = most anomalous)
                - is_anomaly: Boolean
                - status: NORMAL/WATCH/WARNING/CRITICAL
                - anomalous_features: List of concerning features
                - explanation: Human-readable description
        """
        if not self.is_trained:
            return {
                "anomaly_score": 0,
                "is_anomaly": False,
                "status": "ERROR",
                "anomalous_features": [],
                "explanation": "Model not trained yet",
            }

        if len(current_data) < 5:
            return {
                "anomaly_score": 0,
                "is_anomaly": False,
                "status": "INSUFFICIENT_DATA",
                "anomalous_features": [],
                "explanation": f"Need at least 5 data points, got {len(current_data)}",
            }

        # Extract features
        features = self.extract_features(current_data)

        if features.empty:
            return {
                "anomaly_score": 0,
                "is_anomaly": False,
                "status": "ERROR",
                "anomalous_features": [],
                "explanation": "Could not extract features from data",
            }

        # Scale features
        scaled = self.scaler.transform(features)

        # Get predictions (-1 = anomaly, 1 = normal)
        predictions = self.model.predict(scaled)

        # Get anomaly scores (decision_function: lower = more anomalous)
        scores = self.model.decision_function(scaled)

        # Convert to 0-100 scale (higher = more anomalous)
        # decision_function returns negative for anomalies
        avg_score = np.mean(scores)

        # Map to 0-100 where:
        # scores > 0.1 → 0-30 (normal)
        # scores 0 to 0.1 → 30-50 (watch)
        # scores -0.1 to 0 → 50-70 (warning)
        # scores < -0.1 → 70-100 (critical)
        if avg_score > 0.1:
            anomaly_score = max(0, 30 - (avg_score - 0.1) * 100)
        elif avg_score > 0:
            anomaly_score = 30 + (0.1 - avg_score) * 200
        elif avg_score > -0.1:
            anomaly_score = 50 + (-avg_score) * 200
        else:
            anomaly_score = min(100, 70 + (-avg_score - 0.1) * 150)

        anomaly_score = round(max(0, min(100, anomaly_score)), 1)

        # Determine status
        status = self._get_status(anomaly_score)

        # Identify which features are anomalous
        anomalous_features = self._identify_anomalous_features(features)

        # Generate human-readable explanation
        explanation = self._generate_explanation(
            anomaly_score, anomalous_features, status
        )

        return {
            "anomaly_score": anomaly_score,
            "is_anomaly": anomaly_score >= 50,
            "status": status,
            "anomalous_features": anomalous_features,
            "explanation": explanation,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _identify_anomalous_features(self, features: pd.DataFrame) -> List[Dict]:
        """Identify which specific features are anomalous using z-scores."""
        anomalous = []

        # Get the latest values (mean of recent data)
        latest = features.iloc[-min(10, len(features)) :].mean()

        for col in features.columns:
            if col not in self.feature_stats:
                continue

            value = latest[col]
            mean = self.feature_stats[col]["mean"]
            std = self.feature_stats[col]["std"]

            if std == 0:
                continue

            z_score = abs((value - mean) / std)

            if z_score > 2:  # More than 2 standard deviations
                severity = (
                    "high" if z_score > 3 else "medium" if z_score > 2.5 else "low"
                )
                anomalous.append(
                    {
                        "feature": col,
                        "value": round(value, 2),
                        "expected_range": f"{round(mean - 2*std, 1)} - {round(mean + 2*std, 1)}",
                        "z_score": round(z_score, 2),
                        "severity": severity,
                    }
                )

        # Sort by z-score
        anomalous.sort(key=lambda x: x["z_score"], reverse=True)
        return anomalous[:5]  # Top 5 most anomalous

    def _get_status(self, score: float) -> str:
        """Convert anomaly score to status."""
        if score < 30:
            return "NORMAL"
        elif score < 50:
            return "WATCH"
        elif score < 70:
            return "WARNING"
        else:
            return "CRITICAL"

    def _generate_explanation(
        self, score: float, features: List[Dict], status: str
    ) -> str:
        """Generate human-readable explanation."""
        feature_names_readable = {
            "oil_press_normalized": "oil pressure (RPM-adjusted)",
            "coolant_oil_ratio": "coolant/oil temperature ratio",
            "temp_delta": "temperature differential",
            "consumption_rate": "fuel consumption",
            "idle_ratio": "idle time ratio",
            "pressure_stability": "pressure stability",
            "rpm_efficiency": "RPM efficiency",
            "temp_rise_rate": "temperature rise rate",
        }

        if status == "NORMAL":
            return f"✅ All parameters within normal range (score: {score})"

        if not features:
            return (
                f"⚠️ Elevated anomaly score ({score}) but no specific feature identified"
            )

        # Build explanation
        feature_list = ", ".join(
            [
                feature_names_readable.get(f["feature"], f["feature"])
                for f in features[:3]
            ]
        )

        if status == "WATCH":
            return f"👀 WATCH: Slight deviations in {feature_list}. Worth monitoring."
        elif status == "WARNING":
            return (
                f"⚠️ WARNING: Notable anomalies in {feature_list}. Consider inspection."
            )
        else:
            return f"🔴 CRITICAL: Significant anomalies in {feature_list}. Immediate attention recommended."

    def save_model(self, truck_id: str) -> str:
        """Save trained model to cache."""
        if not self.is_trained:
            return ""

        model_path = MODEL_CACHE_DIR / f"anomaly_{truck_id}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "scaler": self.scaler,
                    "feature_stats": self.feature_stats,
                },
                f,
            )
        return str(model_path)

    def load_model(self, truck_id: str) -> bool:
        """Load model from cache."""
        model_path = MODEL_CACHE_DIR / f"anomaly_{truck_id}.pkl"
        if not model_path.exists():
            return False

        try:
            with open(model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.scaler = data["scaler"]
                self.feature_stats = data["feature_stats"]
                self.is_trained = True
            return True
        except Exception as e:
            logger.warning(f"Could not load model for {truck_id}: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_truck_sensor_data(truck_id: str, days: int = 30) -> pd.DataFrame:
    """
    Fetch sensor data for a truck from the database.

    Args:
        truck_id: Truck identifier (e.g., 'VD3579')
        days: Number of days of history to fetch

    Returns:
        DataFrame with sensor readings
    """
    from database_pool import get_engine
    from sqlalchemy import text

    # 🔧 v5.5.2: Made query more flexible - don't require oil_pressure_psi to be NOT NULL
    # The extract_features function handles NULL values with defaults
    query = """
        SELECT 
            timestamp_utc,
            oil_pressure_psi,
            coolant_temp_f,
            oil_temp_f,
            rpm,
            speed_mph,
            consumption_gph,
            engine_hours,
            idle_hours,
            truck_status
        FROM fuel_metrics
        WHERE truck_id = :truck_id
        AND timestamp_utc >= NOW() - INTERVAL :days DAY
        ORDER BY timestamp_utc
    """

    try:
        engine = get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(
                text(query), conn, params={"truck_id": truck_id, "days": days}
            )
        logger.info(f"ML: Fetched {len(df)} rows for {truck_id} (last {days} days)")
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {truck_id}: {e}")
        return pd.DataFrame()


def analyze_truck_anomaly(truck_id: str) -> Dict[str, Any]:
    """
    Analyze a single truck for anomalies.
    Main entry point for single-truck analysis.

    Args:
        truck_id: Truck identifier

    Returns:
        Anomaly analysis result
    """
    # 🔧 v5.5.2: Reduced minimum samples from 50 to 20 for better data availability
    MIN_SAMPLES = 20

    detector = EngineAnomalyDetector(contamination=0.05)

    # Try to load cached model
    model_loaded = detector.load_model(truck_id)

    # Fetch data
    training_data = get_truck_sensor_data(truck_id, days=30)

    if len(training_data) < MIN_SAMPLES:
        return {
            "truck_id": truck_id,
            "anomaly_score": 0,
            "is_anomaly": False,
            "status": "INSUFFICIENT_DATA",
            "anomalous_features": [],
            "explanation": f"Need at least {MIN_SAMPLES} data points, got {len(training_data)}",
            "data_points_analyzed": len(training_data),
        }

    # Train if model not loaded or if we have significantly more data
    if not model_loaded:
        success = detector.train(training_data, min_samples=MIN_SAMPLES)
        if success:
            detector.save_model(truck_id)
        else:
            return {
                "truck_id": truck_id,
                "anomaly_score": 0,
                "is_anomaly": False,
                "status": "ERROR",
                "anomalous_features": [],
                "explanation": "Could not train model on historical data",
            }

    # Get recent data for prediction (last 2 hours)
    recent_data = get_truck_sensor_data(truck_id, days=1)
    if len(recent_data) < 5:
        # Use training data tail if recent is insufficient
        recent_data = training_data.tail(MIN_SAMPLES)

    # Predict
    result = detector.predict(recent_data)
    result["truck_id"] = truck_id
    result["data_points_analyzed"] = len(recent_data)
    result["model_trained_on"] = len(training_data)

    return result


def analyze_fleet_anomalies() -> List[Dict[str, Any]]:
    """
    Analyze entire fleet for anomalies.
    Returns results sorted by anomaly score (highest first).

    Returns:
        List of anomaly results for all trucks
    """
    from config import get_allowed_trucks

    results = []
    trucks = get_allowed_trucks()

    logger.info(f"Analyzing anomalies for {len(trucks)} trucks...")

    for truck_id in trucks:
        try:
            result = analyze_truck_anomaly(truck_id)
            results.append(result)
        except Exception as e:
            logger.error(f"Error analyzing {truck_id}: {e}")
            results.append(
                {
                    "truck_id": truck_id,
                    "anomaly_score": 0,
                    "is_anomaly": False,
                    "status": "ERROR",
                    "anomalous_features": [],
                    "explanation": f"Analysis error: {str(e)}",
                }
            )

    # Sort by anomaly score (highest first)
    results.sort(key=lambda x: x.get("anomaly_score", 0), reverse=True)

    logger.info(f"✅ Fleet anomaly analysis complete. {len(results)} trucks analyzed.")

    return results


def get_fleet_anomaly_summary() -> Dict[str, Any]:
    """
    Get high-level summary of fleet anomaly status.

    Returns:
        Summary with counts by status and top issues
    """
    results = analyze_fleet_anomalies()

    # Count by status
    status_counts = {"NORMAL": 0, "WATCH": 0, "WARNING": 0, "CRITICAL": 0, "OTHER": 0}

    for r in results:
        status = r.get("status", "OTHER")
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["OTHER"] += 1

    # Calculate fleet health score (inverse of average anomaly)
    scores = [
        r.get("anomaly_score", 0)
        for r in results
        if r.get("status") not in ["ERROR", "INSUFFICIENT_DATA"]
    ]
    if scores:
        avg_anomaly = np.mean(scores)
        fleet_health_score = round(100 - avg_anomaly, 1)
    else:
        fleet_health_score = 100.0

    # Top issues (trucks with highest anomaly scores)
    top_issues = [
        {
            "truck_id": r["truck_id"],
            "score": r.get("anomaly_score", 0),
            "status": r.get("status", "UNKNOWN"),
            "explanation": r.get("explanation", ""),
        }
        for r in results[:5]
        if r.get("anomaly_score", 0) > 30
    ]

    return {
        "fleet_health_score": fleet_health_score,
        "total_trucks": len(results),
        "status_breakdown": status_counts,
        "top_issues": top_issues,
        "timestamp": datetime.utcnow().isoformat(),
    }
