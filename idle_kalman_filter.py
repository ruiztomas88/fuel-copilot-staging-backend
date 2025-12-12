"""
🔥 IDLE CONSUMPTION KALMAN FILTER v1.0
═══════════════════════════════════════════════════════════════════════════════

Sophisticated idle consumption estimation using Kalman filtering - same philosophy
as our fuel level Kalman filter but specialized for idle GPH.

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-SENSOR IDLE CONSUMPTION FUSION                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Sensors:                                                                    │
│  1. fuel_rate (Wialon) - Direct ECU reading (most reliable when available)  │
│  2. ECU idle_fuel counter - Cumulative idle fuel                            │
│  3. Kalman fuel delta - Calculated from fuel level changes                  │
│  4. RPM + Load - Physics-based estimation                                   │
│                                                                              │
│  Output:                                                                     │
│  - idle_kalman_gph: Smoothed, accurate idle consumption                     │
│  - confidence: 0-100% how confident we are in the estimate                  │
│  - method: Which sensor(s) contributed                                      │
└─────────────────────────────────────────────────────────────────────────────┘

WHY KALMAN FOR IDLE?
- fuel_rate sensor is noisy (jumps 0.5 → 2.0 → 0.8 GPH)
- ECU counter only updates every few minutes
- Fuel delta works but affected by refuels/sloshing
- Kalman smooths all sources → accurate, stable estimate

Author: Fuel Copilot Team
Created: December 12, 2025
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)


class IdleSource(str, Enum):
    """Source of idle consumption data"""
    FUEL_RATE = "fuel_rate"  # Wialon fuel_rate sensor
    ECU_COUNTER = "ecu_counter"  # ECU cumulative idle fuel
    FUEL_DELTA = "fuel_delta"  # Calculated from Kalman fuel changes
    RPM_MODEL = "rpm_model"  # Physics-based from RPM + load
    FALLBACK = "fallback"  # Conservative estimate
    MULTI_SENSOR = "multi_sensor"  # Kalman fusion of multiple sources


@dataclass
class IdleKalmanState:
    """Kalman filter state for idle consumption"""
    
    # State estimate
    idle_gph: float = 0.8  # Current estimate (gallons per hour)
    uncertainty: float = 0.5  # Estimate uncertainty (variance)
    
    # Process model
    Q: float = 0.01  # Process noise (how much idle can change naturally)
    
    # Measurement noise by source (how much we trust each sensor)
    R_fuel_rate: float = 0.15  # fuel_rate sensor variance
    R_ecu_counter: float = 0.05  # ECU counter variance (most reliable)
    R_fuel_delta: float = 0.25  # Fuel delta variance (affected by sloshing)
    R_rpm_model: float = 0.35  # RPM model variance (least reliable)
    
    # Metadata
    last_update_time: Optional[float] = None
    samples_count: int = 0
    
    # Temperature adjustment
    temp_factor: float = 1.0
    temp_reason: str = "unknown"


class IdleKalmanFilter:
    """
    Kalman filter for idle consumption estimation.
    
    Similar to fuel level Kalman but specialized for idle GPH:
    - Multi-sensor fusion (fuel_rate, ECU counter, fuel delta, RPM)
    - Adaptive noise based on operating conditions
    - Temperature-adjusted estimates
    - Confidence scoring
    """
    
    def __init__(self):
        self.states: Dict[str, IdleKalmanState] = {}
        
    def get_or_create_state(self, truck_id: str) -> IdleKalmanState:
        """Get existing state or create new one for truck"""
        if truck_id not in self.states:
            self.states[truck_id] = IdleKalmanState()
        return self.states[truck_id]
    
    def predict(self, state: IdleKalmanState, time_delta: float) -> IdleKalmanState:
        """
        Prediction step: idle consumption changes slowly over time.
        
        Process model: idle_{k+1} = idle_k + process_noise
        - Idle stays relatively constant (engine at fixed RPM)
        - Small changes from HVAC load, alternator, etc.
        """
        # State doesn't change much (idle RPM is stable)
        # idle_gph stays the same
        
        # Uncertainty increases with time (we're less confident)
        state.uncertainty += state.Q * time_delta
        
        return state
    
    def update_fuel_rate(
        self,
        state: IdleKalmanState,
        fuel_rate_lph: float,
        is_valid: bool = True
    ) -> IdleKalmanState:
        """
        Update with fuel_rate sensor reading.
        
        Args:
            state: Current Kalman state
            fuel_rate_lph: Fuel rate from Wialon sensor (liters per hour)
            is_valid: Whether sensor reading passed validation
        """
        if not is_valid or fuel_rate_lph <= 0:
            return state
        
        # Convert LPH to GPH
        measurement_gph = fuel_rate_lph / 3.78541
        
        # Kalman gain: how much to trust this measurement
        K = state.uncertainty / (state.uncertainty + state.R_fuel_rate)
        
        # Update estimate
        innovation = measurement_gph - state.idle_gph
        state.idle_gph += K * innovation
        
        # Update uncertainty (gets smaller with measurements)
        state.uncertainty = (1 - K) * state.uncertainty
        
        state.samples_count += 1
        
        logger.debug(
            f"Idle Kalman: fuel_rate update {measurement_gph:.3f} gph, "
            f"K={K:.3f}, new estimate={state.idle_gph:.3f} gph"
        )
        
        return state
    
    def update_ecu_counter(
        self,
        state: IdleKalmanState,
        idle_fuel_delta_gal: float,
        time_delta_hours: float
    ) -> IdleKalmanState:
        """
        Update with ECU idle fuel counter delta.
        
        Most reliable source (±0.1% accuracy from ECU).
        """
        if idle_fuel_delta_gal <= 0 or time_delta_hours <= 0:
            return state
        
        measurement_gph = idle_fuel_delta_gal / time_delta_hours
        
        # Very low noise for ECU counter (most reliable)
        K = state.uncertainty / (state.uncertainty + state.R_ecu_counter)
        
        innovation = measurement_gph - state.idle_gph
        state.idle_gph += K * innovation
        state.uncertainty = (1 - K) * state.uncertainty
        
        state.samples_count += 1
        
        logger.debug(
            f"Idle Kalman: ECU counter update {measurement_gph:.3f} gph, "
            f"K={K:.3f}, new estimate={state.idle_gph:.3f} gph"
        )
        
        return state
    
    def update_fuel_delta(
        self,
        state: IdleKalmanState,
        fuel_consumed_gal: float,
        time_delta_hours: float,
        confidence: float = 1.0
    ) -> IdleKalmanState:
        """
        Update with calculated fuel delta from Kalman fuel level.
        
        Args:
            state: Current state
            fuel_consumed_gal: Fuel consumed (from Kalman fuel level change)
            time_delta_hours: Time period
            confidence: 0-1 how confident we are (lower near refuels/sloshing)
        """
        if fuel_consumed_gal <= 0 or time_delta_hours <= 0:
            return state
        
        measurement_gph = fuel_consumed_gal / time_delta_hours
        
        # Adjust noise based on confidence (higher noise = less trust)
        adjusted_R = state.R_fuel_delta / confidence
        
        K = state.uncertainty / (state.uncertainty + adjusted_R)
        
        innovation = measurement_gph - state.idle_gph
        state.idle_gph += K * innovation
        state.uncertainty = (1 - K) * state.uncertainty
        
        state.samples_count += 1
        
        logger.debug(
            f"Idle Kalman: fuel_delta update {measurement_gph:.3f} gph "
            f"(confidence={confidence:.2f}), K={K:.3f}, "
            f"new estimate={state.idle_gph:.3f} gph"
        )
        
        return state
    
    def update_rpm_model(
        self,
        state: IdleKalmanState,
        rpm: float,
        engine_load_pct: float = 0.0,
        ambient_temp_f: Optional[float] = None
    ) -> IdleKalmanState:
        """
        Update with physics-based RPM model.
        
        Args:
            state: Current state
            rpm: Engine RPM
            engine_load_pct: Engine load percentage (0-100)
            ambient_temp_f: Temperature for HVAC adjustment
        """
        if rpm <= 0:
            return state
        
        # Base model: GPH = f(RPM, Load)
        # Typical diesel idle: 600-800 RPM = 0.5-0.8 GPH
        # Higher RPM (PTO, HVAC): 1000-1500 RPM = 0.8-1.5 GPH
        
        rpm_factor = rpm / 1000.0  # Normalize
        load_factor = engine_load_pct / 100.0
        
        # Base consumption from RPM
        base_gph = 0.4 + (rpm_factor * 0.3)
        
        # Add load factor (alternator, HVAC, PTO)
        load_gph = load_factor * 0.5
        
        measurement_gph = base_gph + load_gph
        
        # Apply temperature adjustment
        temp_factor = self._get_temp_factor(ambient_temp_f)
        measurement_gph *= temp_factor
        
        # High noise for model (least reliable)
        K = state.uncertainty / (state.uncertainty + state.R_rpm_model)
        
        innovation = measurement_gph - state.idle_gph
        state.idle_gph += K * innovation
        state.uncertainty = (1 - K) * state.uncertainty
        
        state.samples_count += 1
        
        logger.debug(
            f"Idle Kalman: RPM model update {measurement_gph:.3f} gph "
            f"(RPM={rpm:.0f}, load={engine_load_pct:.0f}%, temp_factor={temp_factor:.2f}), "
            f"K={K:.3f}, new estimate={state.idle_gph:.3f} gph"
        )
        
        return state
    
    def _get_temp_factor(self, temp_f: Optional[float]) -> float:
        """Temperature adjustment for HVAC load"""
        if temp_f is None:
            return 1.0
        
        # Comfort zone: 60-75°F = no extra load
        if 60 <= temp_f <= 75:
            return 1.0
        
        # Cold: heating needed
        if temp_f < 32:
            return 1.5  # Extreme cold
        elif temp_f < 60:
            return 1.25  # Cold
        
        # Hot: AC needed
        if temp_f > 95:
            return 1.5  # Extreme heat
        elif temp_f > 75:
            return 1.3  # Hot
        
        return 1.0
    
    def get_estimate(
        self,
        truck_id: str,
        truck_status: str,
        rpm: Optional[float],
        fuel_rate_lph: Optional[float],
        total_idle_fuel_gal: Optional[float],
        prev_total_idle_fuel_gal: Optional[float],
        fuel_level_delta_gal: Optional[float],
        time_delta_hours: float,
        engine_load_pct: Optional[float] = None,
        ambient_temp_f: Optional[float] = None,
        confidence_fuel_delta: float = 1.0
    ) -> Tuple[float, float, IdleSource, int]:
        """
        Get idle consumption estimate using all available sensors.
        
        Returns:
            Tuple of (idle_gph, confidence_pct, source, samples_used)
        """
        # Not idle if moving
        if truck_status != "STOPPED":
            return 0.0, 100.0, IdleSource.FALLBACK, 0
        
        # Engine off check
        if rpm is not None and rpm == 0:
            return 0.0, 100.0, IdleSource.FALLBACK, 0
        
        state = self.get_or_create_state(truck_id)
        
        # Predict step
        if time_delta_hours > 0:
            state = self.predict(state, time_delta_hours)
        
        sensors_used = []
        
        # Update with all available sensors (sensor fusion!)
        
        # 1. ECU counter (highest priority - most accurate)
        if (total_idle_fuel_gal is not None and 
            prev_total_idle_fuel_gal is not None):
            delta = total_idle_fuel_gal - prev_total_idle_fuel_gal
            if 0 < delta < 5.0 and time_delta_hours > 0.01:
                state = self.update_ecu_counter(state, delta, time_delta_hours)
                sensors_used.append("ECU")
        
        # 2. fuel_rate sensor
        if fuel_rate_lph is not None and 1.5 <= fuel_rate_lph <= 12.0:
            state = self.update_fuel_rate(state, fuel_rate_lph, is_valid=True)
            sensors_used.append("fuel_rate")
        
        # 3. Fuel delta from Kalman fuel level
        if fuel_level_delta_gal is not None and fuel_level_delta_gal > 0:
            if time_delta_hours >= 0.2:  # At least 12 minutes
                state = self.update_fuel_delta(
                    state, 
                    fuel_level_delta_gal, 
                    time_delta_hours,
                    confidence_fuel_delta
                )
                sensors_used.append("fuel_delta")
        
        # 4. RPM model (fallback but still useful)
        if rpm is not None and rpm > 0:
            state = self.update_rpm_model(
                state,
                rpm,
                engine_load_pct or 0.0,
                ambient_temp_f
            )
            sensors_used.append("RPM")
        
        # Calculate confidence (0-100%)
        # Lower uncertainty = higher confidence
        confidence_pct = max(0, min(100, 100 * (1 - state.uncertainty)))
        
        # Determine source
        if len(sensors_used) >= 2:
            source = IdleSource.MULTI_SENSOR
        elif sensors_used:
            source = IdleSource[sensors_used[0].upper().replace("_", "_")]
        else:
            source = IdleSource.FALLBACK
        
        logger.info(
            f"[{truck_id}] Idle Kalman: {state.idle_gph:.3f} gph, "
            f"confidence={confidence_pct:.0f}%, sensors={sensors_used}, "
            f"samples={state.samples_count}"
        )
        
        return state.idle_gph, confidence_pct, source, len(sensors_used)
    
    def reset_truck(self, truck_id: str):
        """Reset Kalman state for a truck (e.g., after refuel or maintenance)"""
        if truck_id in self.states:
            del self.states[truck_id]
            logger.info(f"[{truck_id}] Idle Kalman state reset")


# Global instance
_idle_kalman = IdleKalmanFilter()


def get_idle_kalman_estimate(
    truck_id: str,
    truck_status: str,
    rpm: Optional[float],
    fuel_rate_lph: Optional[float],
    total_idle_fuel_gal: Optional[float],
    prev_total_idle_fuel_gal: Optional[float],
    fuel_level_delta_gal: Optional[float],
    time_delta_hours: float,
    engine_load_pct: Optional[float] = None,
    ambient_temp_f: Optional[float] = None,
    confidence_fuel_delta: float = 1.0
) -> Tuple[float, float, str, int]:
    """
    Convenience function to get idle estimate.
    
    Returns:
        Tuple of (idle_gph, confidence_pct, source, sensors_used)
    """
    idle_gph, confidence, source, sensors = _idle_kalman.get_estimate(
        truck_id=truck_id,
        truck_status=truck_status,
        rpm=rpm,
        fuel_rate_lph=fuel_rate_lph,
        total_idle_fuel_gal=total_idle_fuel_gal,
        prev_total_idle_fuel_gal=prev_total_idle_fuel_gal,
        fuel_level_delta_gal=fuel_level_delta_gal,
        time_delta_hours=time_delta_hours,
        engine_load_pct=engine_load_pct,
        ambient_temp_f=ambient_temp_f,
        confidence_fuel_delta=confidence_fuel_delta
    )
    
    return idle_gph, confidence, source.value, sensors
