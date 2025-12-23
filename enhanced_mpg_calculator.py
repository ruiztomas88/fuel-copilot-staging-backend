"""
Enhanced MPG Calculation with Environmental Adjustments
═══════════════════════════════════════════════════════════════════════════════

Adjusts MPG calculations based on:
- Altitude (terrain impact)
- Ambient temperature
- Load (if available from weight sensors)

Author: Fuel Analytics Team
Version: 1.0.0
Date: December 23, 2025
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentalFactors:
    """Environmental factors affecting MPG"""
    altitude_ft: Optional[float] = None
    ambient_temp_f: Optional[float] = None
    load_lbs: Optional[float] = None
    
    # Calculated adjustment factors
    altitude_factor: float = 1.0
    temperature_factor: float = 1.0
    load_factor: float = 1.0
    total_adjustment: float = 1.0


class EnhancedMPGCalculator:
    """
    Enhanced MPG calculator that adjusts for environmental conditions
    
    Adjustment factors based on industry research:
    - Altitude: ~3% MPG loss per 1000ft elevation gain
    - Temperature: Peak efficiency at 70°F, degradation at extremes
    - Load: Linear impact based on weight vs. GVWR
    """
    
    # Configuration
    BASELINE_ALTITUDE_FT = 1000.0  # Sea level reference
    BASELINE_TEMP_F = 70.0  # Optimal temperature
    BASELINE_LOAD_LBS = 22000.0  # Half-loaded truck (44k GVWR)
    MAX_GVWR_LBS = 44000.0  # Class 8 truck typical GVWR
    
    # Adjustment coefficients (from industry studies)
    ALTITUDE_LOSS_PER_1000FT = 0.03  # 3% per 1000ft
    TEMP_LOSS_PER_10F_FROM_OPTIMAL = 0.02  # 2% per 10°F deviation
    LOAD_LOSS_PER_10K_LBS = 0.15  # 15% per 10k lbs above baseline
    
    def __init__(self):
        """Initialize enhanced MPG calculator"""
        logger.info("✅ EnhancedMPGCalculator initialized")
    
    def calculate_altitude_factor(self, altitude_ft: Optional[float]) -> float:
        """
        Calculate altitude adjustment factor
        
        Higher altitude = lower air density = less engine power = worse MPG
        Formula: factor = 1 - (altitude_gain / 1000) * 0.03
        
        Args:
            altitude_ft: Current altitude in feet
            
        Returns:
            Adjustment factor (< 1.0 = worse MPG, > 1.0 = better MPG)
        """
        if altitude_ft is None or altitude_ft < 0:
            return 1.0
        
        # Calculate altitude gain from baseline
        altitude_gain = max(0, altitude_ft - self.BASELINE_ALTITUDE_FT)
        
        # Apply loss rate
        loss_factor = (altitude_gain / 1000.0) * self.ALTITUDE_LOSS_PER_1000FT
        adjustment = 1.0 - loss_factor
        
        # Cap adjustment (don't go below 0.7 or above 1.1)
        adjustment = max(0.7, min(1.1, adjustment))
        
        logger.debug(f"Altitude: {altitude_ft:.0f}ft → adjustment: {adjustment:.3f}")
        return adjustment
    
    def calculate_temperature_factor(self, temp_f: Optional[float]) -> float:
        """
        Calculate temperature adjustment factor
        
        Extreme cold/heat reduces efficiency due to:
        - Cold: Engine warmup, thicker oil, battery load
        - Heat: AC load, reduced air density
        
        Optimal range: 60-80°F
        
        Args:
            temp_f: Ambient temperature in Fahrenheit
            
        Returns:
            Adjustment factor (< 1.0 = worse MPG)
        """
        if temp_f is None:
            return 1.0
        
        # Calculate deviation from optimal
        temp_deviation = abs(temp_f - self.BASELINE_TEMP_F)
        
        # Apply loss rate (every 10°F deviation)
        loss_factor = (temp_deviation / 10.0) * self.TEMP_LOSS_PER_10F_FROM_OPTIMAL
        adjustment = 1.0 - loss_factor
        
        # Cap adjustment (don't go below 0.75 for extreme temps)
        adjustment = max(0.75, min(1.05, adjustment))
        
        logger.debug(f"Temperature: {temp_f:.1f}°F → adjustment: {adjustment:.3f}")
        return adjustment
    
    def calculate_load_factor(self, load_lbs: Optional[float]) -> float:
        """
        Calculate load adjustment factor
        
        Heavier load = more fuel consumption
        Baseline: 22,000 lbs (half-loaded)
        
        Args:
            load_lbs: Current load weight in pounds
            
        Returns:
            Adjustment factor (< 1.0 = worse MPG with heavy load)
        """
        if load_lbs is None or load_lbs < 0:
            return 1.0
        
        # Cap load at GVWR
        load_lbs = min(load_lbs, self.MAX_GVWR_LBS)
        
        # Calculate load difference from baseline
        load_diff = load_lbs - self.BASELINE_LOAD_LBS
        
        # Apply loss/gain rate (per 10k lbs)
        adjustment_factor = (load_diff / 10000.0) * self.LOAD_LOSS_PER_10K_LBS
        adjustment = 1.0 - adjustment_factor
        
        # Cap adjustment (0.6 to 1.2 range)
        adjustment = max(0.6, min(1.2, adjustment))
        
        logger.debug(f"Load: {load_lbs:.0f}lbs → adjustment: {adjustment:.3f}")
        return adjustment
    
    def calculate_environmental_factors(
        self,
        altitude_ft: Optional[float] = None,
        ambient_temp_f: Optional[float] = None,
        load_lbs: Optional[float] = None
    ) -> EnvironmentalFactors:
        """
        Calculate all environmental adjustment factors
        
        Args:
            altitude_ft: Current altitude in feet
            ambient_temp_f: Ambient temperature in Fahrenheit
            load_lbs: Current load weight in pounds
            
        Returns:
            EnvironmentalFactors with individual and total adjustments
        """
        factors = EnvironmentalFactors(
            altitude_ft=altitude_ft,
            ambient_temp_f=ambient_temp_f,
            load_lbs=load_lbs
        )
        
        # Calculate individual factors
        factors.altitude_factor = self.calculate_altitude_factor(altitude_ft)
        factors.temperature_factor = self.calculate_temperature_factor(ambient_temp_f)
        factors.load_factor = self.calculate_load_factor(load_lbs)
        
        # Combine factors (multiplicative)
        factors.total_adjustment = (
            factors.altitude_factor *
            factors.temperature_factor *
            factors.load_factor
        )
        
        logger.debug(
            f"Environmental adjustment: {factors.total_adjustment:.3f} "
            f"(alt:{factors.altitude_factor:.2f} × "
            f"temp:{factors.temperature_factor:.2f} × "
            f"load:{factors.load_factor:.2f})"
        )
        
        return factors
    
    def adjust_mpg(
        self,
        raw_mpg: float,
        altitude_ft: Optional[float] = None,
        ambient_temp_f: Optional[float] = None,
        load_lbs: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Adjust raw MPG for environmental conditions
        
        Args:
            raw_mpg: Raw MPG calculated from fuel/distance
            altitude_ft: Current altitude in feet
            ambient_temp_f: Ambient temperature in Fahrenheit
            load_lbs: Current load weight in pounds
            
        Returns:
            Dict with raw_mpg, adjusted_mpg, and environmental_factors
        """
        if raw_mpg <= 0:
            return {
                "raw_mpg": raw_mpg,
                "adjusted_mpg": raw_mpg,
                "environmental_factors": None,
                "adjustment_applied": False
            }
        
        # Calculate environmental factors
        factors = self.calculate_environmental_factors(
            altitude_ft=altitude_ft,
            ambient_temp_f=ambient_temp_f,
            load_lbs=load_lbs
        )
        
        # Adjust MPG (divide by total adjustment to normalize)
        # If adjustment < 1.0 (bad conditions), adjusted MPG will be higher
        # This represents what the MPG WOULD BE under baseline conditions
        adjusted_mpg = raw_mpg / factors.total_adjustment
        
        # Cap adjusted MPG to realistic range (3.5 - 8.5)
        adjusted_mpg = max(3.5, min(8.5, adjusted_mpg))
        
        logger.info(
            f"MPG adjustment: {raw_mpg:.2f} → {adjusted_mpg:.2f} "
            f"(factor: {factors.total_adjustment:.3f})"
        )
        
        return {
            "raw_mpg": round(raw_mpg, 2),
            "adjusted_mpg": round(adjusted_mpg, 2),
            "environmental_factors": {
                "altitude_ft": factors.altitude_ft,
                "altitude_factor": round(factors.altitude_factor, 3),
                "ambient_temp_f": factors.ambient_temp_f,
                "temperature_factor": round(factors.temperature_factor, 3),
                "load_lbs": factors.load_lbs,
                "load_factor": round(factors.load_factor, 3),
                "total_adjustment": round(factors.total_adjustment, 3)
            },
            "adjustment_applied": True
        }
    
    def get_baseline_conditions(self) -> Dict[str, float]:
        """
        Get baseline environmental conditions for reference
        
        Returns:
            Dict with baseline values
        """
        return {
            "altitude_ft": self.BASELINE_ALTITUDE_FT,
            "ambient_temp_f": self.BASELINE_TEMP_F,
            "load_lbs": self.BASELINE_LOAD_LBS,
            "max_gvwr_lbs": self.MAX_GVWR_LBS
        }


# Singleton instance for global use
_enhanced_mpg_calculator: Optional[EnhancedMPGCalculator] = None


def get_enhanced_mpg_calculator() -> EnhancedMPGCalculator:
    """Get or create singleton instance of EnhancedMPGCalculator"""
    global _enhanced_mpg_calculator
    if _enhanced_mpg_calculator is None:
        _enhanced_mpg_calculator = EnhancedMPGCalculator()
    return _enhanced_mpg_calculator
