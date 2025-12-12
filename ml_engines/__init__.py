"""
ML Engines for Fuel Copilot
- Anomaly Detection (Isolation Forest)
- Driver Clustering (K-Means)

🆕 v5.5.0: ML Intelligence module
"""

from .anomaly_detector import EngineAnomalyDetector, analyze_truck_anomaly, analyze_fleet_anomalies, get_fleet_anomaly_summary
from .driver_clustering import DriverClusteringEngine, analyze_driver_clusters, get_driver_cluster

__all__ = [
    'EngineAnomalyDetector',
    'analyze_truck_anomaly', 
    'analyze_fleet_anomalies',
    'get_fleet_anomaly_summary',
    'DriverClusteringEngine',
    'analyze_driver_clusters',
    'get_driver_cluster',
]
