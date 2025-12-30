"""
Truck-related fixtures for testing
"""

from datetime import datetime, timedelta

import pytest


@pytest.fixture
def sample_truck_data():
    """Complete truck data for testing"""
    return {
        "truck_id": "RA1234",
        "unit_id": 1234,
        "truck_status": "MOVING",
        "speed_mph": 65.5,
        "fuel_pct": 75.3,
        "fuel_gallons": 150.6,
        "mpg_current": 6.2,
        "avg_mpg_24h": 5.8,
        "consumption_gph": 10.5,
        "consumption_lph": 39.7,
        "rpm": 1450,
        "coolant_temp_f": 195,
        "oil_pressure_psi": 45,
        "altitude_ft": 1200,
        "odometer_mi": 125000,
        "idle_mode": "AUTO",
        "def_level_pct": 65.0,
        "def_level_liters": 18.5,
        "last_updated": datetime.now().isoformat(),
        "data_age_min": 2,
    }


@pytest.fixture
def sample_fleet_trucks():
    """Sample fleet of trucks"""
    base_time = datetime.now()
    return [
        {
            "truck_id": "RA1234",
            "truck_status": "MOVING",
            "mpg_current": 6.2,
            "fuel_pct": 75.3,
            "last_updated": base_time.isoformat(),
        },
        {
            "truck_id": "FF7702",
            "truck_status": "STOPPED",
            "mpg_current": 0.0,
            "fuel_pct": 45.8,
            "last_updated": base_time.isoformat(),
        },
        {
            "truck_id": "JX9900",
            "truck_status": "OFFLINE",
            "mpg_current": None,
            "fuel_pct": 20.1,
            "last_updated": (base_time - timedelta(hours=2)).isoformat(),
        },
    ]


@pytest.fixture
def sample_refuel_event():
    """Sample refuel event"""
    return {
        "truck_id": "RA1234",
        "timestamp": datetime.now().isoformat(),
        "fuel_level_before": 25.5,
        "fuel_level_after": 95.3,
        "gallons_added": 139.6,
        "refuel_type": "AUTOMATIC",
        "confidence_score": 0.95,
    }


@pytest.fixture
def sample_dtcs():
    """Sample DTCs for a truck"""
    return [
        {
            "dtc_code": "P0128",
            "description": "Coolant Thermostat Temperature Below Regulating Temperature",
            "status": "active",
            "count": 5,
        },
        {
            "dtc_code": "P0456",
            "description": "Evaporative Emission System Small Leak Detected",
            "status": "active",
            "count": 2,
        },
    ]


@pytest.fixture
def sample_sensors():
    """Sample sensor data"""
    return {
        "oil_pressure_psi": 45.5,
        "coolant_temp_f": 195,
        "oil_temp_f": 210,
        "def_level_pct": 65.0,
        "engine_load_pct": 55,
        "boost_psi": 18.5,
        "rpm": 1450,
        "fuel_rate_gph": 10.5,
    }
