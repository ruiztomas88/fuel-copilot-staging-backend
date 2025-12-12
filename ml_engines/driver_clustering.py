"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    DRIVER CLUSTERING ENGINE                                    ║
║                 K-Means for Driver Behavior Analysis                           ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Groups drivers into behavioral clusters automatically.                        ║
║  No manual categorization needed - ML finds natural groupings.                 ║
║                                                                                ║
║  Features:                                                                     ║
║  - MPG performance                                                             ║
║  - Idle behavior                                                               ║
║  - Driving patterns (speed, consistency)                                       ║
║  - Fuel efficiency                                                             ║
║                                                                                ║
║  Output clusters:                                                              ║
║  - "Efficient Pros" - Top performers                                           ║
║  - "Solid Performers" - Consistent, good habits                               ║
║  - "Needs Coaching" - Improvement opportunities                                ║
║  - "At Risk" - Requires immediate attention                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Fuel Copilot ML Team
Version: 1.0.0
Date: December 2025
"""

import logging
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Optional, Any, Tuple
import warnings
import threading
from functools import lru_cache

logger = logging.getLogger(__name__)

# 🆕 v5.5.5: Cache for clustering results (avoid re-training on every request)
_clustering_cache: Dict[str, Dict[str, Any]] = {}
_clustering_cache_lock = threading.Lock()
_CLUSTERING_CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_cached_analysis(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached clustering analysis if still valid."""
    with _clustering_cache_lock:
        if cache_key in _clustering_cache:
            cached = _clustering_cache[cache_key]
            if (
                datetime.now(timezone.utc).timestamp() - cached["timestamp"]
                < _CLUSTERING_CACHE_TTL_SECONDS
            ):
                logger.info(
                    f"🎯 Using cached clustering analysis (key: {cache_key[:20]}...)"
                )
                return cached["data"]
            else:
                # Expired - remove
                del _clustering_cache[cache_key]
    return None


def _set_cached_analysis(cache_key: str, data: Dict[str, Any]):
    """Cache clustering analysis result."""
    with _clustering_cache_lock:
        _clustering_cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }
        # Cleanup old entries (keep max 10)
        if len(_clustering_cache) > 10:
            oldest_key = min(
                _clustering_cache.keys(),
                key=lambda k: _clustering_cache[k]["timestamp"],
            )
            del _clustering_cache[oldest_key]


# Cluster labels based on characteristics
CLUSTER_PROFILES = {
    "efficient_pro": {
        "name": "Efficient Pro",
        "emoji": "🏆",
        "color": "#10B981",  # Green
        "description": "Top performers with excellent fuel efficiency and minimal idle time",
        "coaching": "Keep up the great work! Consider mentoring other drivers.",
    },
    "solid_performer": {
        "name": "Solid Performer",
        "emoji": "✅",
        "color": "#3B82F6",  # Blue
        "description": "Consistent performance with good habits",
        "coaching": "Small improvements in idle management could push you to the top tier.",
    },
    "needs_coaching": {
        "name": "Needs Coaching",
        "emoji": "📈",
        "color": "#F59E0B",  # Amber
        "description": "Room for improvement in fuel efficiency or idle habits",
        "coaching": "Focus on reducing idle time and maintaining steady speeds.",
    },
    "at_risk": {
        "name": "At Risk",
        "emoji": "⚠️",
        "color": "#EF4444",  # Red
        "description": "Significant improvement needed in multiple areas",
        "coaching": "Schedule a coaching session to review driving habits.",
    },
}


class DriverClusteringEngine:
    """
    K-Means clustering for driver behavior segmentation.

    How it works:
    1. Extracts driver metrics (MPG, idle %, speed patterns, etc.)
    2. Normalizes features to same scale
    3. K-Means finds natural groupings
    4. Labels clusters based on centroid characteristics

    Benefits over manual grading:
    - Adapts to YOUR fleet's distribution
    - Finds natural break points
    - Identifies outliers automatically
    """

    def __init__(self, n_clusters: int = 4):
        """
        Initialize clustering engine.

        Args:
            n_clusters: Number of clusters (default 4 for our categories)
        """
        self.n_clusters = n_clusters
        self.model = KMeans(
            n_clusters=n_clusters, random_state=42, n_init=10, max_iter=300
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.cluster_labels = {}  # Maps cluster ID to profile key
        self.feature_names = [
            "avg_mpg",
            "idle_pct",
            "avg_speed",
            "speed_consistency",
            "fuel_efficiency_score",
            "high_rpm_pct",
            "harsh_events_per_hour",
        ]
        self.driver_features = {}  # Cache of features per driver
        self.cluster_centroids = None

    def extract_driver_features(self, driver_data: pd.DataFrame) -> pd.Series:
        """
        Extract behavioral features from driver's trip data.

        Args:
            driver_data: DataFrame with columns:
                speed_mph, rpm, consumption_gph, engine_hours,
                idle_hours, truck_status, odometer_miles

        Returns:
            Series with extracted features
        """
        if driver_data.empty or len(driver_data) < 10:
            return pd.Series()

        features = {}

        # Feature 1: Average MPG
        # Calculate from consumption and distance
        total_fuel = driver_data["consumption_gph"].sum()

        if "odometer_miles" in driver_data.columns:
            distance = (
                driver_data["odometer_miles"].max()
                - driver_data["odometer_miles"].min()
            )
        else:
            # Estimate from speed and time
            hours = len(driver_data) / 60  # Assuming 1 row per minute
            avg_speed = driver_data["speed_mph"].mean()
            distance = avg_speed * hours

        if total_fuel > 0 and distance > 0:
            features["avg_mpg"] = distance / total_fuel
        else:
            features["avg_mpg"] = 6.0  # Default for trucks

        # Feature 2: Idle percentage
        engine_hours = (
            driver_data["engine_hours"].max() - driver_data["engine_hours"].min()
        )
        idle_hours = driver_data["idle_hours"].max() - driver_data["idle_hours"].min()

        if engine_hours > 0:
            features["idle_pct"] = (idle_hours / engine_hours) * 100
        else:
            # Fallback: calculate from status
            idle_rows = len(driver_data[driver_data["truck_status"] == "idle"])
            features["idle_pct"] = (idle_rows / len(driver_data)) * 100

        features["idle_pct"] = min(features["idle_pct"], 50)  # Cap at 50%

        # Feature 3: Average speed (when moving)
        moving_data = driver_data[driver_data["speed_mph"] > 5]
        features["avg_speed"] = (
            moving_data["speed_mph"].mean() if len(moving_data) > 0 else 0
        )

        # Feature 4: Speed consistency (lower std = more consistent)
        if len(moving_data) > 5:
            features["speed_consistency"] = 100 - min(
                moving_data["speed_mph"].std() * 2, 50
            )
        else:
            features["speed_consistency"] = 50

        # Feature 5: Fuel efficiency score (MPG normalized + idle penalty)
        mpg_score = min(features["avg_mpg"] / 8.0, 1.0) * 50  # Max 50 pts for MPG
        idle_score = max(0, 50 - features["idle_pct"] * 2)  # Max 50 pts for low idle
        features["fuel_efficiency_score"] = mpg_score + idle_score

        # Feature 6: High RPM percentage (rpm > 1800)
        high_rpm = len(driver_data[driver_data["rpm"] > 1800])
        features["high_rpm_pct"] = (high_rpm / len(driver_data)) * 100

        # Feature 7: Harsh events per hour (estimated from speed changes)
        if "speed_mph" in driver_data.columns and len(driver_data) > 5:
            speed_changes = driver_data["speed_mph"].diff().abs()
            harsh_count = len(speed_changes[speed_changes > 10])
            hours = len(driver_data) / 60
            features["harsh_events_per_hour"] = harsh_count / max(hours, 1)
        else:
            features["harsh_events_per_hour"] = 0

        return pd.Series(features)

    def fit(self, drivers_data: Dict[str, pd.DataFrame]) -> bool:
        """
        Train the clustering model on all drivers' data.

        Args:
            drivers_data: Dict mapping truck_id -> DataFrame of trip data

        Returns:
            True if training successful
        """
        if len(drivers_data) < self.n_clusters:
            logger.warning(
                f"Not enough drivers ({len(drivers_data)}) for {self.n_clusters} clusters"
            )
            return False

        # Extract features for all drivers
        features_list = []
        truck_ids = []

        for truck_id, data in drivers_data.items():
            features = self.extract_driver_features(data)
            if not features.empty:
                features_list.append(features)
                truck_ids.append(truck_id)
                self.driver_features[truck_id] = features

        if len(features_list) < self.n_clusters:
            logger.warning(f"Not enough valid drivers ({len(features_list)})")
            return False

        # Create feature matrix
        X = pd.DataFrame(features_list)
        X = X.fillna(X.median())

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Fit K-Means
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model.fit(X_scaled)

        self.cluster_centroids = self.model.cluster_centers_
        self.is_trained = True

        # Label clusters based on centroid characteristics
        self._label_clusters()

        logger.info(f"✅ Driver clustering trained on {len(features_list)} drivers")
        return True

    def _label_clusters(self):
        """
        Assign meaningful labels to clusters based on their centroids.
        Uses efficiency score and idle percentage to rank.
        """
        if self.cluster_centroids is None:
            return

        # Get indices for key features
        feature_idx = {name: i for i, name in enumerate(self.feature_names)}

        # Score each cluster: higher efficiency, lower idle = better
        cluster_scores = []
        for i, centroid in enumerate(self.cluster_centroids):
            eff_score = centroid[feature_idx["fuel_efficiency_score"]]
            idle_penalty = centroid[feature_idx["idle_pct"]]
            score = eff_score - idle_penalty * 0.5
            cluster_scores.append((i, score))

        # Sort by score (best first)
        cluster_scores.sort(key=lambda x: x[1], reverse=True)

        # Assign labels
        profile_keys = ["efficient_pro", "solid_performer", "needs_coaching", "at_risk"]
        for rank, (cluster_id, _) in enumerate(cluster_scores):
            if rank < len(profile_keys):
                self.cluster_labels[cluster_id] = profile_keys[rank]
            else:
                self.cluster_labels[cluster_id] = "needs_coaching"

    def predict_cluster(self, driver_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Predict which cluster a driver belongs to.

        Args:
            driver_data: Driver's trip data

        Returns:
            Cluster assignment with profile info
        """
        if not self.is_trained:
            return {"error": "Model not trained"}

        features = self.extract_driver_features(driver_data)
        if features.empty:
            return {"error": "Could not extract features"}

        # Scale
        X = pd.DataFrame([features])
        X = X.fillna(0)
        X_scaled = self.scaler.transform(X)

        # Predict
        cluster_id = self.model.predict(X_scaled)[0]
        profile_key = self.cluster_labels.get(cluster_id, "needs_coaching")
        profile = CLUSTER_PROFILES[profile_key]

        return {
            "cluster_id": int(cluster_id),
            "cluster_name": profile["name"],
            "cluster_emoji": profile["emoji"],
            "cluster_color": profile["color"],
            "description": profile["description"],
            "coaching_tip": profile["coaching"],
            "metrics": {
                "avg_mpg": round(features.get("avg_mpg", 0), 1),
                "idle_pct": round(features.get("idle_pct", 0), 1),
                "avg_speed": round(features.get("avg_speed", 0), 1),
                "fuel_efficiency_score": round(
                    features.get("fuel_efficiency_score", 0), 1
                ),
            },
        }

    def get_all_clusters(self) -> List[Dict[str, Any]]:
        """
        Get cluster assignments for all trained drivers.

        Returns:
            List of driver cluster info
        """
        if not self.is_trained:
            return []

        results = []
        for truck_id, features in self.driver_features.items():
            X = pd.DataFrame([features]).fillna(0)
            X_scaled = self.scaler.transform(X)
            cluster_id = self.model.predict(X_scaled)[0]
            profile_key = self.cluster_labels.get(cluster_id, "needs_coaching")
            profile = CLUSTER_PROFILES[profile_key]

            results.append(
                {
                    "truck_id": truck_id,
                    "cluster_id": int(cluster_id),
                    "cluster_name": profile["name"],
                    "cluster_emoji": profile["emoji"],
                    "cluster_color": profile["color"],
                    "description": profile["description"],
                    "coaching_tip": profile["coaching"],
                    "metrics": {
                        "avg_mpg": round(features.get("avg_mpg", 0), 1),
                        "idle_pct": round(features.get("idle_pct", 0), 1),
                        "avg_speed": round(features.get("avg_speed", 0), 1),
                        "fuel_efficiency_score": round(
                            features.get("fuel_efficiency_score", 0), 1
                        ),
                    },
                }
            )

        return results

    def get_cluster_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for each cluster.

        Returns:
            Dict with cluster distributions and metrics
        """
        if not self.is_trained:
            return {"error": "Model not trained"}

        all_drivers = self.get_all_clusters()

        # Group by cluster
        clusters = {}
        for driver in all_drivers:
            key = self.cluster_labels.get(driver["cluster_id"], "needs_coaching")
            if key not in clusters:
                profile = CLUSTER_PROFILES[key]
                clusters[key] = {
                    "name": profile["name"],
                    "emoji": profile["emoji"],
                    "color": profile["color"],
                    "count": 0,
                    "drivers": [],
                    "avg_metrics": {
                        "avg_mpg": [],
                        "idle_pct": [],
                        "avg_speed": [],
                        "fuel_efficiency_score": [],
                    },
                    "description": profile["description"],
                }

            clusters[key]["count"] += 1
            clusters[key]["drivers"].append(driver["truck_id"])
            for metric in clusters[key]["avg_metrics"]:
                clusters[key]["avg_metrics"][metric].append(
                    driver["metrics"].get(metric, 0)
                )

        # Calculate averages
        for key in clusters:
            for metric in clusters[key]["avg_metrics"]:
                values = clusters[key]["avg_metrics"][metric]
                clusters[key]["avg_metrics"][metric] = round(
                    np.mean(values) if values else 0, 1
                )

        # Calculate clustering quality (silhouette score)
        if len(self.driver_features) >= self.n_clusters + 1:
            try:
                X = pd.DataFrame(list(self.driver_features.values())).fillna(0)
                X_scaled = self.scaler.transform(X)
                labels = self.model.predict(X_scaled)
                quality = silhouette_score(X_scaled, labels)
            except:
                quality = 0.5
        else:
            quality = 0.5

        return {
            "clusters": clusters,
            "total_drivers": len(all_drivers),
            "clustering_quality": round(quality, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_driver_data(truck_id: str, days: int = 30) -> pd.DataFrame:
    """
    Fetch driver/truck data from database.
    """
    from database_pool import get_engine
    from sqlalchemy import text

    query = """
        SELECT 
            timestamp_utc,
            truck_id,
            speed_mph,
            rpm,
            consumption_gph,
            engine_hours,
            idle_hours,
            truck_status,
            odometer_miles
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
        return df
    except Exception as e:
        logger.error(f"Error fetching driver data for {truck_id}: {e}")
        return pd.DataFrame()


def get_all_drivers_data(days: int = 30) -> Dict[str, pd.DataFrame]:
    """
    Fetch data for all drivers in the fleet.
    """
    from config import get_allowed_trucks

    drivers_data = {}
    trucks = get_allowed_trucks()

    # 🔧 v5.5.2: Added detailed logging for debugging
    logger.info(f"ML Clustering: Fetching data for {len(trucks)} trucks")

    for truck_id in trucks:
        data = get_driver_data(truck_id, days)
        if len(data) >= 10:
            drivers_data[truck_id] = data
            logger.debug(f"ML: {truck_id} has {len(data)} records - included")
        else:
            logger.debug(f"ML: {truck_id} has {len(data)} records - skipped (min 10)")

    logger.info(
        f"ML Clustering: {len(drivers_data)}/{len(trucks)} drivers with sufficient data"
    )
    return drivers_data


def analyze_driver_clusters(days: int = 30) -> Dict[str, Any]:
    """
    Main entry point: Analyze and cluster all drivers.

    🆕 v5.5.5: Results are cached for 1 hour to avoid re-training on every request.

    Args:
        days: Days of history to analyze

    Returns:
        Complete clustering analysis with:
        - Cluster summary
        - Individual driver assignments
        - Recommendations
    """
    # 🆕 v5.5.5: Check cache first
    cache_key = f"clustering_{date.today().isoformat()}_{days}"
    cached = _get_cached_analysis(cache_key)
    if cached:
        return cached

    logger.info(f"Starting driver clustering analysis ({days} days of data)")

    # Fetch data
    drivers_data = get_all_drivers_data(days)

    if len(drivers_data) < 4:
        return {
            "error": f"Insufficient data: only {len(drivers_data)} drivers with data",
            "minimum_required": 4,
        }

    # Determine optimal cluster count (min of 4 or driver count)
    n_clusters = min(4, len(drivers_data))

    # Create and fit model
    engine = DriverClusteringEngine(n_clusters=n_clusters)
    success = engine.fit(drivers_data)

    if not success:
        return {
            "error": "Clustering failed - could not train model",
            "drivers_found": len(drivers_data),
        }

    # Get results
    summary = engine.get_cluster_summary()
    all_drivers = engine.get_all_clusters()

    # Generate fleet-wide insights
    insights = _generate_fleet_insights(summary, all_drivers)

    result = {
        "summary": summary,
        "drivers": all_drivers,
        "insights": insights,
        "analysis_period_days": days,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 🆕 v5.5.5: Cache the result
    _set_cached_analysis(cache_key, result)

    return result


def _generate_fleet_insights(summary: Dict, drivers: List[Dict]) -> List[Dict]:
    """Generate actionable insights from clustering results."""
    insights = []

    clusters = summary.get("clusters", {})
    total = summary.get("total_drivers", 1)

    # Insight 1: Top performer percentage
    efficient = clusters.get("efficient_pro", {})
    if efficient.get("count", 0) > 0:
        pct = round(efficient["count"] / total * 100)
        insights.append(
            {
                "type": "positive",
                "icon": "🌟",
                "title": "Strong Core",
                "message": f"{pct}% of drivers are top performers. Consider a recognition program.",
            }
        )

    # Insight 2: At-risk drivers
    at_risk = clusters.get("at_risk", {})
    if at_risk.get("count", 0) > 0:
        insights.append(
            {
                "type": "warning",
                "icon": "⚠️",
                "title": "Coaching Needed",
                "message": f"{at_risk['count']} drivers need immediate coaching attention: {', '.join(at_risk.get('drivers', [])[:3])}",
            }
        )

    # Insight 3: Idle comparison
    if "at_risk" in clusters and "efficient_pro" in clusters:
        at_risk_idle = clusters["at_risk"].get("avg_metrics", {}).get("idle_pct", 0)
        efficient_idle = (
            clusters["efficient_pro"].get("avg_metrics", {}).get("idle_pct", 0)
        )
        idle_diff = at_risk_idle - efficient_idle
        if idle_diff > 5:
            savings_estimate = round(
                idle_diff * at_risk.get("count", 0) * 50
            )  # $50 per % idle
            insights.append(
                {
                    "type": "opportunity",
                    "icon": "💰",
                    "title": "Idle Savings Opportunity",
                    "message": f"At-risk drivers idle {round(idle_diff)}% more. Reducing could save ~${savings_estimate}/month.",
                }
            )

    # Insight 4: MPG spread
    all_mpg = [d["metrics"]["avg_mpg"] for d in drivers]
    if all_mpg:
        mpg_spread = max(all_mpg) - min(all_mpg)
        if mpg_spread > 1.5:
            insights.append(
                {
                    "type": "opportunity",
                    "icon": "📊",
                    "title": "MPG Variance",
                    "message": f"MPG varies by {round(mpg_spread, 1)} across fleet. Training could normalize performance.",
                }
            )

    # Insight 5: Best performer recognition
    if drivers:
        best = max(drivers, key=lambda d: d["metrics"]["fuel_efficiency_score"])
        insights.append(
            {
                "type": "recognition",
                "icon": "🏆",
                "title": "Top Performer",
                "message": f"{best['truck_id']} leads with {best['metrics']['avg_mpg']} MPG and {best['metrics']['idle_pct']}% idle.",
            }
        )

    return insights


def get_driver_cluster(truck_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get cluster info for a single driver.

    Args:
        truck_id: Driver/truck identifier
        days: Days of history

    Returns:
        Driver's cluster assignment and comparison to peers
    """
    # Need to run full clustering to place driver in context
    result = analyze_driver_clusters(days)

    if "error" in result:
        return result

    # Find the driver
    for driver in result["drivers"]:
        if driver["truck_id"] == truck_id:
            # Add comparison to cluster average
            cluster_key = None
            for key, cluster in result["summary"]["clusters"].items():
                if truck_id in cluster.get("drivers", []):
                    cluster_key = key
                    break

            if cluster_key:
                cluster_avg = result["summary"]["clusters"][cluster_key]["avg_metrics"]
                driver["vs_cluster"] = {
                    "mpg_diff": round(
                        driver["metrics"]["avg_mpg"] - cluster_avg["avg_mpg"], 1
                    ),
                    "idle_diff": round(
                        driver["metrics"]["idle_pct"] - cluster_avg["idle_pct"], 1
                    ),
                }

            return driver

    return {"error": f"Driver {truck_id} not found in analysis"}
