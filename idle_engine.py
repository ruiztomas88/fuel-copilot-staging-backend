"""
Idle Engine - Hybrid idle consumption calculation

Three-tier method for calculating idle fuel consumption:
1. SENSOR_FUEL_RATE: Direct from fuel_rate sensor (most reliable)
2. CALCULATED_DELTA: From Kalman filter fuel level delta
3. FALLBACK_CONSENSUS: Conservative estimate when sensors unreliable

🆕 v3.4.0: Added temperature factor for climate-adjusted idle estimates

Author: Fuel Copilot Team
Version: v3.4.0
Date: November 26, 2025
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IdleMethod(Enum):
    """Idle calculation method used"""

    NOT_IDLE = "NOT_IDLE"
    ECU_IDLE_COUNTER = "ECU_IDLE_COUNTER"  # 🆕 v5.3.3: Direct from ECU (most accurate)
    SENSOR_FUEL_RATE = "SENSOR_FUEL_RATE"
    CALCULATED_DELTA = "CALCULATED_DELTA"
    FALLBACK_CONSENSUS = "FALLBACK_CONSENSUS"
    ENGINE_OFF = "ENGINE_OFF"


class IdleMode(Enum):
    """Idle mode classification"""

    ENGINE_OFF = "ENGINE_OFF"
    NORMAL = "NORMAL"  # 0.5-1.2 gph
    REEFER = "REEFER"  # 1.2-2.5 gph
    HEAVY = "HEAVY"  # >2.5 gph


@dataclass
class IdleConfig:
    """Configuration for idle calculation"""

    # fuel_rate sensor validation
    # 🔧 v3.10.7: Increased min from 0.3 to 1.5 LPH to filter noise
    # Real idle consumption is 1.9-9.5 LPH (0.5-2.5 GPH)
    # 0.3 LPH = 0.08 GPH which is too low and likely sensor noise
    fuel_rate_min_lph: float = 1.5
    fuel_rate_max_lph: float = 12.0

    # Delta calculation validation
    delta_min_time_hours: float = 0.2  # 12 minutes minimum
    delta_min_lph: float = 0.5
    delta_max_lph: float = 10.0

    # Fallback defaults
    fallback_gph: float = 0.8  # Conservative estimate

    # Idle mode thresholds (GPH)
    normal_max_gph: float = 1.2
    reefer_max_gph: float = 2.5

    # 🆕 Temperature adjustment settings
    temp_comfort_low_f: float = 60.0  # Below this: heating needed
    temp_comfort_high_f: float = 75.0  # Above this: AC needed
    temp_extreme_cold_f: float = 32.0  # Very cold (extra heating)
    temp_extreme_hot_f: float = 95.0  # Very hot (extra AC)

    # 🆕 Temperature multipliers for idle consumption
    # These adjust the fallback GPH based on climate
    temp_extreme_cold_multiplier: float = 1.5  # 50% more fuel in extreme cold
    temp_cold_multiplier: float = 1.25  # 25% more in cold
    temp_comfort_multiplier: float = 1.0  # Baseline in comfort zone
    temp_hot_multiplier: float = 1.3  # 30% more for AC
    temp_extreme_hot_multiplier: float = 1.5  # 50% more in extreme heat


def get_temperature_factor(
    temperature_f: Optional[float], config: IdleConfig = IdleConfig()
) -> Tuple[float, str]:
    """
    🆕 v3.4.0: Calculate temperature adjustment factor for idle consumption.

    HVAC systems increase fuel consumption during idle:
    - Heating in cold weather requires engine heat
    - AC in hot weather puts extra load on engine

    Args:
        temperature_f: Ambient temperature in Fahrenheit (None if unavailable)
        config: Idle configuration with thresholds

    Returns:
        Tuple of (multiplier, reason)
        - multiplier: Factor to multiply base idle consumption
        - reason: Human-readable explanation

    Examples:
        >>> get_temperature_factor(25.0)  # Very cold
        (1.5, "EXTREME_COLD")

        >>> get_temperature_factor(70.0)  # Comfortable
        (1.0, "COMFORT_ZONE")

        >>> get_temperature_factor(100.0)  # Very hot
        (1.5, "EXTREME_HOT")
    """
    if temperature_f is None:
        return 1.0, "NO_TEMP_DATA"

    # Extreme cold (< 32°F)
    if temperature_f < config.temp_extreme_cold_f:
        return config.temp_extreme_cold_multiplier, "EXTREME_COLD"

    # Cold (32-60°F)
    if temperature_f < config.temp_comfort_low_f:
        return config.temp_cold_multiplier, "COLD"

    # Comfort zone (60-75°F)
    if temperature_f <= config.temp_comfort_high_f:
        return config.temp_comfort_multiplier, "COMFORT_ZONE"

    # Hot (75-95°F)
    if temperature_f < config.temp_extreme_hot_f:
        return config.temp_hot_multiplier, "HOT"

    # Extreme hot (> 95°F)
    return config.temp_extreme_hot_multiplier, "EXTREME_HOT"


def calculate_idle_consumption(
    truck_status: str,
    rpm: Optional[float],
    fuel_rate: Optional[float],
    current_fuel_L: Optional[float],
    previous_fuel_L: Optional[float],
    time_delta_hours: float,
    config: IdleConfig = IdleConfig(),
    truck_id: str = "UNKNOWN",
    temperature_f: Optional[float] = None,  # 🆕 Temperature parameter
    total_idle_fuel: Optional[
        float
    ] = None,  # 🆕 v5.3.3: ECU idle fuel counter (gallons)
    previous_total_idle_fuel: Optional[float] = None,  # 🆕 v5.3.3: Previous ECU value
) -> Tuple[float, IdleMethod]:
    """
    Calculate idle fuel consumption using hybrid four-tier method

    🆕 v5.3.3: Added ECU_IDLE_COUNTER as priority method (most accurate: ±0.1%)

    Args:
        truck_status: "STOPPED", "MOVING", or "OFFLINE"
        rpm: Engine RPM (None if unknown, 0 if off, >0 if on)
        fuel_rate: Fuel rate sensor in LPH (None if unavailable)
        current_fuel_L: Current fuel level in liters from Kalman
        previous_fuel_L: Previous fuel level in liters (stored separately!)
        time_delta_hours: Time since last reading in hours
        config: Idle configuration
        truck_id: Truck identifier for logging
        temperature_f: 🆕 Ambient temperature in Fahrenheit (for HVAC adjustment)
        total_idle_fuel: 🆕 v5.3.3 ECU cumulative idle fuel counter (gallons)
        previous_total_idle_fuel: 🆕 v5.3.3 Previous ECU counter value

    Returns:
        Tuple of (idle_gph, method)
        - idle_gph: 0.0 if not idle, otherwise consumption in gallons/hour
        - method: IdleMethod enum indicating calculation source

    Logic:
        0. 🆕 Try ECU_IDLE_COUNTER if available (most accurate: ±0.1%)
        1. Check if truck is STOPPED and engine ON (rpm > 0 or rpm=None)
        2. Try SENSOR_FUEL_RATE if available and valid (±2-5%)
        3. Try CALCULATED_DELTA if time window sufficient (±5-10%)
        4. Fall back to FALLBACK_CONSENSUS (🆕 with temperature adjustment)
    """

    # Not idle if moving
    if truck_status != "STOPPED":
        return 0.0, IdleMethod.NOT_IDLE

    # 🆕 v5.3.3: METHOD 0: ECU_IDLE_COUNTER (highest priority - most accurate)
    # The ECU tracks cumulative idle fuel with ±0.1% accuracy
    if (
        total_idle_fuel is not None
        and previous_total_idle_fuel is not None
        and time_delta_hours > 0.01  # At least ~36 seconds
    ):
        idle_fuel_delta = total_idle_fuel - previous_total_idle_fuel

        # Validate: should be positive and reasonable (< 5 gallons per sample)
        if 0 < idle_fuel_delta < 5.0:
            idle_gph = idle_fuel_delta / time_delta_hours

            # Sanity check: idle should be 0.3-3.0 GPH typically
            if 0.1 <= idle_gph <= 5.0:
                logger.debug(
                    f"[{truck_id}] Idle via ECU_COUNTER: {idle_gph:.3f} gph "
                    f"(delta: {idle_fuel_delta:.4f} gal in {time_delta_hours*60:.1f}min)"
                )
                return idle_gph, IdleMethod.ECU_IDLE_COUNTER
            else:
                logger.debug(
                    f"[{truck_id}] ECU_COUNTER {idle_gph:.2f} gph out of sane range"
                )
        elif idle_fuel_delta < 0:
            logger.warning(
                f"[{truck_id}] ECU idle counter went backwards: "
                f"{previous_total_idle_fuel:.2f} → {total_idle_fuel:.2f}"
            )

    # Check valid fuel rate first
    has_valid_fuel_rate = False
    if fuel_rate is not None:
        if config.fuel_rate_min_lph <= fuel_rate <= config.fuel_rate_max_lph:
            has_valid_fuel_rate = True

    # Engine off check (rpm=0 explicitly) - ONLY if no valid fuel rate
    # Fix for trucks like RT9127 that have RPM=0 but valid fuel_rate
    if rpm is not None and rpm == 0 and not has_valid_fuel_rate:
        return 0.0, IdleMethod.ENGINE_OFF

    # Engine is ON (rpm>0 or rpm=None means transmitting data)

    # METHOD 1: SENSOR_FUEL_RATE (priority)
    if has_valid_fuel_rate and fuel_rate is not None:
        # Convert LPH to GPH (1 gal = 3.78541 L)
        idle_gph = fuel_rate / 3.78541

        logger.debug(
            f"[{truck_id}] Idle via SENSOR: {idle_gph:.2f} gph "
            f"(fuel_rate: {fuel_rate:.2f} LPH)"
        )

        return idle_gph, IdleMethod.SENSOR_FUEL_RATE
    elif fuel_rate is not None:
        logger.debug(
            f"[{truck_id}] fuel_rate {fuel_rate:.2f} LPH out of valid range "
            f"[{config.fuel_rate_min_lph}, {config.fuel_rate_max_lph}]"
        )
    # METHOD 2: CALCULATED_DELTA (from Kalman filter)
    if (
        current_fuel_L is not None
        and previous_fuel_L is not None
        and time_delta_hours >= config.delta_min_time_hours
    ):

        fuel_consumed_L = previous_fuel_L - current_fuel_L

        # Only use if consumption is positive and reasonable
        if fuel_consumed_L > 0:
            fuel_consumed_lph = fuel_consumed_L / time_delta_hours

            if config.delta_min_lph <= fuel_consumed_lph <= config.delta_max_lph:
                idle_gph = fuel_consumed_lph / 3.78541

                logger.debug(
                    f"[{truck_id}] Idle via CALCULATED_DELTA: {idle_gph:.2f} gph "
                    f"(delta: {fuel_consumed_L:.2f}L in {time_delta_hours*60:.1f}min)"
                )

                return idle_gph, IdleMethod.CALCULATED_DELTA
            else:
                logger.debug(
                    f"[{truck_id}] CALCULATED_DELTA {fuel_consumed_lph:.2f} LPH "
                    f"out of range [{config.delta_min_lph}, {config.delta_max_lph}]"
                )
        else:
            logger.debug(
                f"[{truck_id}] CALCULATED_DELTA: negative or zero consumption "
                f"({fuel_consumed_L:.2f}L)"
            )

    # 🔧 FIX v3.9.4: METHOD 2.5 - RPM-based estimation when fuel_rate unavailable
    # Better than pure fallback because it accounts for actual engine load
    if rpm is not None and rpm > 0:
        # Linear approximation: baseline + RPM factor
        # At 600 RPM (idle): 0.3 + 0.6*0.2 = 0.42 GPH
        # At 1000 RPM (high idle): 0.3 + 1.0*0.2 = 0.50 GPH
        # At 1500 RPM (PTO active): 0.3 + 1.5*0.2 = 0.60 GPH
        rpm_factor = rpm / 1000.0
        estimated_gph = 0.3 + rpm_factor * 0.2

        # Apply temperature adjustment
        temp_factor, temp_reason = get_temperature_factor(temperature_f, config)
        estimated_gph *= temp_factor

        logger.debug(
            f"[{truck_id}] Idle via RPM_ESTIMATE: {estimated_gph:.2f} gph "
            f"(RPM={rpm:.0f}, factor={rpm_factor:.2f}, temp={temp_reason})"
        )

        return (
            estimated_gph,
            IdleMethod.FALLBACK_CONSENSUS,
        )  # Same method type for compatibility

    # METHOD 3: FALLBACK_CONSENSUS (conservative estimate)
    # 🆕 v3.4.0: Apply temperature adjustment
    temp_factor, temp_reason = get_temperature_factor(temperature_f, config)
    adjusted_fallback_gph = config.fallback_gph * temp_factor

    if temp_factor != 1.0:
        logger.debug(
            f"[{truck_id}] Idle via FALLBACK: {adjusted_fallback_gph:.2f} gph "
            f"(base {config.fallback_gph} × {temp_factor:.2f} for {temp_reason}, "
            f"temp={temperature_f:.0f}°F)"
        )
    else:
        logger.debug(
            f"[{truck_id}] Idle via FALLBACK: {adjusted_fallback_gph:.2f} gph "
            f"(no valid sensor or delta)"
        )

    return adjusted_fallback_gph, IdleMethod.FALLBACK_CONSENSUS


def detect_idle_mode(idle_gph: float, config: IdleConfig = IdleConfig()) -> IdleMode:
    """
    Classify idle mode based on GPH consumption

    Args:
        idle_gph: Idle consumption in gallons per hour
        config: Configuration with thresholds

    Returns:
        IdleMode enum

    Examples:
        0.0 → ENGINE_OFF
        0.8 → NORMAL
        1.8 → REEFER
        3.0 → HEAVY
    """
    if idle_gph <= 0.0:
        return IdleMode.ENGINE_OFF
    elif idle_gph <= config.normal_max_gph:
        return IdleMode.NORMAL
    elif idle_gph <= config.reefer_max_gph:
        return IdleMode.REEFER
    else:
        return IdleMode.HEAVY


def calculate_idle_cost(
    idle_gph: float, idle_hours: float, fuel_price_per_gallon: float
) -> float:
    """
    Calculate cost of idle time

    Args:
        idle_gph: Idle consumption in GPH
        idle_hours: Hours spent idling
        fuel_price_per_gallon: Price per gallon

    Returns:
        Total cost in dollars

    Example:
        >>> calculate_idle_cost(1.0, 8.0, 3.50)
        28.0  # $28 for 8 hours at 1 gph
    """
    if idle_gph <= 0 or idle_hours <= 0:
        return 0.0

    total_gallons = idle_gph * idle_hours
    return total_gallons * fuel_price_per_gallon


def get_idle_status(
    idle_gph: float,
    method: IdleMethod,
    mode: IdleMode,
    config: IdleConfig = IdleConfig(),
    temperature_f: Optional[float] = None,  # 🆕 Temperature parameter
) -> dict:
    """
    Get human-readable idle status for monitoring

    Args:
        idle_gph: Idle consumption in gallons per hour
        method: IdleMethod enum indicating calculation source
        mode: IdleMode enum indicating classification
        config: Idle configuration
        temperature_f: 🆕 Ambient temperature in Fahrenheit

    Returns:
        Dict with status information
    """
    if method == IdleMethod.NOT_IDLE:
        status = "NOT_IDLE"
        message = "Truck is moving"
    elif method == IdleMethod.ENGINE_OFF:
        status = "ENGINE_OFF"
        message = "Engine is off"
    elif idle_gph < config.normal_max_gph:
        status = "NORMAL"
        message = f"Normal idle: {idle_gph:.2f} gph"
    elif idle_gph < config.reefer_max_gph:
        status = "REEFER"
        message = f"Reefer mode: {idle_gph:.2f} gph"
    else:
        status = "HEAVY"
        message = f"Heavy idle (investigate): {idle_gph:.2f} gph"

    # 🆕 Add temperature context
    temp_factor, temp_reason = get_temperature_factor(temperature_f, config)

    result = {
        "status": status,
        "message": message,
        "idle_gph": idle_gph,
        "method": method.value,
        "mode": mode.value,
        "is_reliable": method
        in [IdleMethod.SENSOR_FUEL_RATE, IdleMethod.CALCULATED_DELTA],
    }

    # 🆕 Include temperature info if available
    if temperature_f is not None:
        result["temperature_f"] = temperature_f
        result["temperature_factor"] = temp_factor
        result["temperature_reason"] = temp_reason

        # Add context message for temperature-adjusted fallback
        if method == IdleMethod.FALLBACK_CONSENSUS and temp_factor != 1.0:
            result["message"] += f" (adjusted for {temp_reason})"

    return result


def estimate_hvac_impact(
    temperature_f: Optional[float],
    idle_hours: float,
    base_gph: float = 0.8,
    config: IdleConfig = IdleConfig(),
) -> dict:
    """
    🆕 v3.4.0: Estimate HVAC impact on idle fuel consumption.

    Calculates the additional fuel used for heating/AC during idle.

    Args:
        temperature_f: Ambient temperature in Fahrenheit
        idle_hours: Total hours spent idling
        base_gph: Base idle consumption in GPH
        config: Idle configuration

    Returns:
        Dict with HVAC impact analysis

    Example:
        >>> estimate_hvac_impact(20.0, 8.0)  # 8 hours idling in 20°F weather
        {
            'temperature_f': 20.0,
            'base_gallons': 6.4,           # Without HVAC
            'adjusted_gallons': 9.6,        # With HVAC
            'hvac_impact_gallons': 3.2,     # Additional from HVAC
            'hvac_impact_pct': 50.0,        # 50% increase
            'climate_zone': 'EXTREME_COLD'
        }
    """
    if temperature_f is None:
        return {
            "temperature_f": None,
            "base_gallons": base_gph * idle_hours,
            "adjusted_gallons": base_gph * idle_hours,
            "hvac_impact_gallons": 0.0,
            "hvac_impact_pct": 0.0,
            "climate_zone": "UNKNOWN",
        }

    temp_factor, climate_zone = get_temperature_factor(temperature_f, config)

    base_gallons = base_gph * idle_hours
    adjusted_gallons = base_gallons * temp_factor
    hvac_impact = adjusted_gallons - base_gallons
    hvac_pct = ((temp_factor - 1.0) * 100) if temp_factor > 0 else 0.0

    return {
        "temperature_f": temperature_f,
        "base_gallons": round(base_gallons, 2),
        "adjusted_gallons": round(adjusted_gallons, 2),
        "hvac_impact_gallons": round(hvac_impact, 2),
        "hvac_impact_pct": round(hvac_pct, 1),
        "climate_zone": climate_zone,
    }
