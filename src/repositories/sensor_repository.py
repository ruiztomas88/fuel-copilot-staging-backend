"""
Sensor Repository - Database access for sensor operations

⚠️ ADAPTED for fuel_copilot_local schema (fuel_metrics)
Sensors are stored as columns in fuel_metrics table.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging
import pymysql
from pymysql import cursors

logger = logging.getLogger(__name__)


class SensorRepository:
    """Repository for sensor data access operations."""

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        logger.info(f"SensorRepository initialized for DB: {db_config.get('database')}")

    def _get_connection(self):
        """Get database connection."""
        return pymysql.connect(**self.db_config, cursorclass=cursors.DictCursor)

    def get_truck_sensors(self, truck_id: str) -> Dict[str, Any]:
        """Get latest sensor readings for a truck from fuel_metrics."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        truck_id,
                        timestamp_utc,
                        coolant_temp_f,
                        oil_pressure_psi,
                        oil_temp_f,
                        battery_voltage,
                        engine_load_pct,
                        def_level_pct,
                        ambient_temp_f,
                        intake_air_temp_f,
                        trans_temp_f,
                        fuel_temp_f,
                        intercooler_temp_f,
                        intake_press_kpa
                    FROM fuel_metrics
                    WHERE truck_id = %s
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                """, (truck_id,))
                sensors = cursor.fetchone()
                logger.debug(f"Fetched sensors for truck {truck_id}")
                return sensors if sensors else {}
        finally:
            conn.close()

    def get_sensor_history(self, truck_id: str, sensor_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get sensor history for specified hours."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                
                # Map sensor names to column names
                sensor_column_map = {
                    'coolant': 'coolant_temp_f',
                    'oil_pressure': 'oil_pressure_psi',
                    'oil_temp': 'oil_temp_f',
                    'battery': 'battery_voltage',
                    'engine_load': 'engine_load_pct',
                    'def': 'def_level_pct',
                    'ambient_temp': 'ambient_temp_f',
                    'intake_temp': 'intake_air_temp_f',
                    'trans_temp': 'trans_temp_f',
                    'fuel_temp': 'fuel_temp_f'
                }
                
                column = sensor_column_map.get(sensor_name, sensor_name)
                
                cursor.execute(f"""
                    SELECT 
                        timestamp_utc,
                        {column} as value
                    FROM fuel_metrics
                    WHERE truck_id = %s
                      AND timestamp_utc >= %s
                    ORDER BY timestamp_utc ASC
                """, (truck_id, cutoff))
                
                history = cursor.fetchall()
                logger.debug(f"Fetched {len(history)} readings for {sensor_name} on {truck_id}")
                return history
        finally:
            conn.close()

    def get_all_sensors_for_fleet(self) -> List[Dict[str, Any]]:
        """Get latest sensor readings for all trucks."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        fm1.truck_id,
                        fm1.timestamp_utc,
                        fm1.coolant_temp_f,
                        fm1.oil_pressure_psi,
                        fm1.oil_temp_f,
                        fm1.battery_voltage,
                        fm1.engine_load_pct,
                        fm1.def_level_pct
                    FROM fuel_metrics fm1
                    WHERE timestamp_utc = (
                        SELECT MAX(timestamp_utc)
                        FROM fuel_metrics fm2
                        WHERE fm2.truck_id = fm1.truck_id
                    )
                    ORDER BY fm1.truck_id
                """)
                sensors = cursor.fetchall()
                logger.debug(f"Fetched sensors for {len(sensors)} trucks")
                return sensors
        finally:
            conn.close()

    def get_sensor_alerts(self, truck_id: str) -> List[Dict[str, Any]]:
        """Get current sensor-based alerts for a truck."""
        sensors = self.get_truck_sensors(truck_id)
        if not sensors:
            return []
        
        alerts = []
        
        # Check critical sensor thresholds
        if sensors.get('coolant_temp_f') and sensors['coolant_temp_f'] > 230:
            alerts.append({
                'type': 'COOLANT_HIGH',
                'severity': 'CRITICAL',
                'sensor': 'coolant_temp_f',
                'value': sensors['coolant_temp_f'],
                'threshold': 230,
                'message': f"Coolant temperature critically high: {sensors['coolant_temp_f']}°F"
            })
        
        if sensors.get('oil_pressure_psi') and sensors['oil_pressure_psi'] < 15:
            alerts.append({
                'type': 'OIL_PRESSURE_LOW',
                'severity': 'CRITICAL',
                'sensor': 'oil_pressure_psi',
                'value': sensors['oil_pressure_psi'],
                'threshold': 15,
                'message': f"Oil pressure critically low: {sensors['oil_pressure_psi']} PSI"
            })
        
        if sensors.get('battery_voltage') and sensors['battery_voltage'] < 11.5:
            alerts.append({
                'type': 'BATTERY_LOW',
                'severity': 'WARNING',
                'sensor': 'battery_voltage',
                'value': sensors['battery_voltage'],
                'threshold': 11.5,
                'message': f"Battery voltage low: {sensors['battery_voltage']}V"
            })
        
        if sensors.get('def_level_pct') and sensors['def_level_pct'] < 10:
            alerts.append({
                'type': 'DEF_LOW',
                'severity': 'WARNING',
                'sensor': 'def_level_pct',
                'value': sensors['def_level_pct'],
                'threshold': 10,
                'message': f"DEF level low: {sensors['def_level_pct']}%"
            })
        
        return alerts
