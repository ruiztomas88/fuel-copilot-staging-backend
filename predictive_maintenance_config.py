"""
Predictive Maintenance Configuration for Critical Components
Defines component-specific parameters for Weibull+ARIMA ensemble predictions

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

from typing import Any, Dict

# Component definitions with Weibull parameters and monitoring sensors
CRITICAL_COMPONENTS = {
    "turbocharger": {
        "description": "Turbocharger assembly",
        "weibull_params": {
            "shape": 2.8,  # β (shape) - Higher = wear-out failures
            "scale": 8000,  # η (scale) - Expected life in engine hours
        },
        "arima_order": (1, 1, 1),  # ARIMA(p,d,q) for sensor trend analysis
        "ensemble_weight_weibull": 0.65,  # Higher weight = trust age-based model more
        "ensemble_weight_arima": 0.35,
        "sensors": {
            "primary": "intake_press",  # Intake manifold pressure (kPa)
            "secondary": ["boost_press", "intake_air_temp", "intercooler_temp"],
        },
        "thresholds": {
            "warning_ttf_hours": 500,  # Warn when TTF < 500 hours
            "critical_ttf_hours": 200,  # Critical when TTF < 200 hours
            "sensor_min": 80,  # Min intake pressure (kPa) - too low = turbo issue
            "sensor_max": 280,  # Max intake pressure (kPa) - too high = overboost
        },
        "maintenance_interval_hours": 10000,  # Recommended inspection interval
    },
    "oil_pump": {
        "description": "Engine oil pump",
        "weibull_params": {
            "shape": 1.5,  # β - Moderate wear-out
            "scale": 15000,  # η - Expected life in engine hours
        },
        "arima_order": (2, 1, 1),  # More AR terms for pressure trend
        "ensemble_weight_weibull": 0.50,  # Equal weight (pressure more important)
        "ensemble_weight_arima": 0.50,
        "sensors": {
            "primary": "oil_press",  # Oil pressure (psi)
            "secondary": ["oil_temp", "engine_load", "rpm"],
        },
        "thresholds": {
            "warning_ttf_hours": 1000,
            "critical_ttf_hours": 300,
            "sensor_min": 35,  # Min oil pressure (psi) at operating temp
            "sensor_max": 85,  # Max oil pressure (psi)
        },
        "maintenance_interval_hours": 15000,
    },
    "coolant_pump": {
        "description": "Water pump / coolant circulation",
        "weibull_params": {
            "shape": 2.2,  # β - Wear-out pattern
            "scale": 12000,  # η - Expected life in engine hours
        },
        "arima_order": (1, 1, 1),
        "ensemble_weight_weibull": 0.55,
        "ensemble_weight_arima": 0.45,
        "sensors": {
            "primary": "coolant_temp",  # Coolant temperature (°F)
            "secondary": ["ambient_temp", "engine_load", "speed"],
        },
        "thresholds": {
            "warning_ttf_hours": 800,
            "critical_ttf_hours": 250,
            "sensor_min": 160,  # Min operating temp (°F) - too low = thermostat stuck
            "sensor_max": 230,  # Max operating temp (°F) - overheating
        },
        "maintenance_interval_hours": 12000,
    },
    "fuel_pump": {
        "description": "Fuel transfer pump",
        "weibull_params": {
            "shape": 1.8,
            "scale": 10000,
        },
        "arima_order": (1, 1, 1),
        "ensemble_weight_weibull": 0.60,
        "ensemble_weight_arima": 0.40,
        "sensors": {
            "primary": "fuel_press",  # Fuel pressure (psi) - if available
            "secondary": ["fuel_temp", "fuel_rate", "engine_load"],
        },
        "thresholds": {
            "warning_ttf_hours": 700,
            "critical_ttf_hours": 200,
            "sensor_min": 45,  # Min fuel pressure (psi)
            "sensor_max": 95,  # Max fuel pressure (psi)
        },
        "maintenance_interval_hours": 10000,
    },
    "def_pump": {
        "description": "DEF (Diesel Exhaust Fluid) dosing pump",
        "weibull_params": {
            "shape": 2.5,  # Higher shape = crystallization wear
            "scale": 6000,  # Shorter life due to DEF corrosion
        },
        "arima_order": (1, 1, 1),
        "ensemble_weight_weibull": 0.70,  # Trust age more (known failure mode)
        "ensemble_weight_arima": 0.30,
        "sensors": {
            "primary": "def_level",  # DEF tank level (%)
            "secondary": ["def_temp", "exhaust_temp"],
        },
        "thresholds": {
            "warning_ttf_hours": 400,
            "critical_ttf_hours": 150,
            "sensor_min": 10,  # Min DEF level (%) - low level warning
            "sensor_max": 100,
        },
        "maintenance_interval_hours": 6000,
    },
}


def get_component_config(component_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific component.

    Args:
        component_name: One of the keys in CRITICAL_COMPONENTS

    Returns:
        Configuration dictionary for the component

    Raises:
        ValueError: If component_name is not recognized
    """
    if component_name not in CRITICAL_COMPONENTS:
        raise ValueError(
            f"Unknown component: {component_name}. "
            f"Available: {list(CRITICAL_COMPONENTS.keys())}"
        )
    return CRITICAL_COMPONENTS[component_name]


def get_all_component_names() -> list[str]:
    """Get list of all configured component names."""
    return list(CRITICAL_COMPONENTS.keys())


def get_sensor_for_component(component_name: str) -> str:
    """Get primary sensor name for a component."""
    config = get_component_config(component_name)
    return config["sensors"]["primary"]


def should_alert(component_name: str, ttf_hours: float) -> tuple[bool, str]:
    """
    Check if an alert should be triggered based on TTF.

    Args:
        component_name: Component to check
        ttf_hours: Predicted time-to-failure in hours

    Returns:
        Tuple of (should_alert, severity_level)
        severity_level is one of: "OK", "WARNING", "CRITICAL"
    """
    config = get_component_config(component_name)

    if ttf_hours < config["thresholds"]["critical_ttf_hours"]:
        return True, "CRITICAL"
    elif ttf_hours < config["thresholds"]["warning_ttf_hours"]:
        return True, "WARNING"
    else:
        return False, "OK"
