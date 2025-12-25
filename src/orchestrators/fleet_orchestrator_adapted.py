"""
Fleet Orchestrator - ADAPTED for our fuel_copilot_local database

Combines repositories and services to provide high-level fleet operations.
This is a simplified version that reuses our existing database_mysql functions.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
import logging
import json

from src.repositories.truck_repository import TruckRepository
from src.repositories.sensor_repository import SensorRepository
from src.repositories.def_repository import DEFRepository
from src.repositories.dtc_repository import DTCRepository
from src.services.analytics_service_adapted import AnalyticsService
from src.services.priority_engine import PriorityEngine

logger = logging.getLogger(__name__)


def convert_to_json_serializable(obj):
    """Convert Decimal and datetime objects to JSON serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    return obj


class FleetOrchestrator:
    """
    High-level fleet operations orchestrator.
    
    Coordinates between repositories and services to provide
    complete fleet management functionality.
    """

    def __init__(
        self,
        truck_repo: TruckRepository,
        sensor_repo: SensorRepository,
        def_repo: DEFRepository,
        dtc_repo: DTCRepository
    ):
        """Initialize orchestrator with repositories."""
        self.truck_repo = truck_repo
        self.sensor_repo = sensor_repo
        self.def_repo = def_repo
        self.dtc_repo = dtc_repo
        
        # Initialize services
        self.analytics = AnalyticsService()
        self.priority_engine = PriorityEngine()
        
        logger.info("FleetOrchestrator initialized")

    def get_command_center_data(self) -> Dict[str, Any]:
        """
        Get comprehensive fleet data for command center dashboard.
        
        Returns:
            Dictionary with fleet summary, truck details, alerts, etc.
        """
        try:
            # Get fleet summary
            fleet_summary = self.analytics.get_fleet_summary()
            
            # Get all trucks with their latest data
            trucks = self.truck_repo.get_all_trucks()
            
            # Get active alerts
            sensor_alerts = []
            for truck in trucks[:5]:  # Limit for performance
                alerts = self.sensor_repo.get_sensor_alerts(truck['truck_id'])
                sensor_alerts.extend(alerts)
            
            # Get trucks with low DEF
            low_def_trucks = self.def_repo.get_low_def_trucks(threshold=15)
            
            # Get active DTCs
            fleet_dtcs = self.dtc_repo.get_fleet_dtcs()
            
            # Combine into response and convert all Decimals/datetimes
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'fleet_summary': fleet_summary,
                'total_trucks': len(trucks),
                'trucks': [
                    {
                        'truck_id': t['truck_id'],
                        'status': t.get('status'),
                        'fuel_level': float(t['fuel_level']) if t.get('fuel_level') else None,
                        'speed': float(t['speed']) if t.get('speed') else None,
                        'mpg': float(t['mpg']) if t.get('mpg') else None,
                        'last_update': t.get('last_update').isoformat() if t.get('last_update') else None
                    }
                    for t in trucks[:20]  # Limit for response size
                ],
                'alerts': {
                    'sensor_alerts': sensor_alerts[:10],
                    'low_def': len(low_def_trucks),
                    'active_dtcs': len(fleet_dtcs)
                },
                'metrics': {
                    'active_trucks': fleet_summary.get('active_trucks', 0),
                    'offline_trucks': fleet_summary.get('offline_trucks', 0),
                    'moving_trucks': fleet_summary.get('moving_trucks', 0),
                    'idling_trucks': fleet_summary.get('idling_trucks', 0)
                }
            }
            
            # Convert any remaining Decimals/datetimes
            return convert_to_json_serializable(data)
            
        except Exception as e:
            logger.error(f"Error getting command center data: {e}", exc_info=True)
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def get_truck_detail(self, truck_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific truck."""
        try:
            truck = self.truck_repo.get_truck_by_id(truck_id)
            if not truck:
                return {'error': f'Truck {truck_id} not found'}
            
            sensors = self.sensor_repo.get_truck_sensors(truck_id)
            sensor_alerts = self.sensor_repo.get_sensor_alerts(truck_id)
            def_level = self.def_repo.get_def_level(truck_id)
            dtcs = self.dtc_repo.get_active_dtcs(truck_id)
            
            data = {
                'truck_id': truck_id,
                'basic_info': truck,
                'sensors': sensors,
                'alerts': sensor_alerts,
                'def_level': float(def_level) if def_level else None,
                'dtcs': dtcs
            }
            
            return convert_to_json_serializable(data)
            
        except Exception as e:
            logger.error(f"Error getting truck detail for {truck_id}: {e}")
            return {'error': str(e)}

    def get_fleet_health_overview(self) -> Dict[str, Any]:
        """Get fleet-wide health overview."""
        try:
            all_sensors = self.sensor_repo.get_all_sensors_for_fleet()
            low_def = self.def_repo.get_low_def_trucks(threshold=20)
            dtc_counts = self.dtc_repo.get_dtc_count_by_truck(days=7)
            
            # Calculate health scores
            trucks_with_issues = len([s for s in all_sensors if s.get('coolant_temp_f') and s['coolant_temp_f'] > 220])
            trucks_with_low_def = len(low_def)
            trucks_with_dtcs = len(dtc_counts)
            
            return {
                'total_trucks': len(all_sensors),
                'trucks_with_issues': trucks_with_issues,
                'trucks_with_low_def': trucks_with_low_def,
                'trucks_with_dtcs': trucks_with_dtcs,
                'health_score': max(0, 100 - (trucks_with_issues * 5) - (trucks_with_low_def * 2) - (trucks_with_dtcs * 3))
            }
            
        except Exception as e:
            logger.error(f"Error getting fleet health: {e}")
            return {'error': str(e)}
