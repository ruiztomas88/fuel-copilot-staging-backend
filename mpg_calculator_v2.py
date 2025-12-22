"""
MPG Calculation Engine V2.0 - Complete Redesign for 44k lbs Trucks
═══════════════════════════════════════════════════════════════════════════════

PROBLEMA IDENTIFICADO:
- MPG actual: 8.4-8.9 (INFLADO)
- MPG esperado: 4.0-8.0 para camiones 44,000 lbs
- Causa: Jerarquía incorrecta de sensores + thresholds inadecuados

SENSORES DISPONIBLES (de wialon_reader.py):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FUEL CONSUMPTION:
1. ✅ total_fuel_used (gallons) - ECU acumulativo - ERROR: ±1%
2. ✅ fuel_economy (MPG) - ECU directo - Puede usarse como validación
3. ✅ fuel_lvl (%) - Sensor tanque - ERROR: ±2-5% (olas, inclinación)
4. ✅ fuel_rate (L/h) → consumption_gph - ERROR: ±10-15% (subestima)

DISTANCIA:
1. ⚠️ odometer (mi) - Solo 15% coverage
2. ✅ speed (mph) - 100% coverage - ERROR: ±2% con buen GPS

GPS QUALITY:
1. ✅ hdop - Horizontal Dilution of Precision (< 2.0 = bueno)
2. ✅ sats - Satellites count (>= 6 = confiable)

NUEVA JERARQUÍA (Prioridad ALTA → BAJA):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MÉTODO 1: ECU Fuel Economy Directo (si disponible y realista)
- Sensor: fuel_economy
- Condición: 3.5 <= fuel_economy <= 8.5
- Ventaja: Valor directo del ECU, muy confiable
- Uso: Tomar directo SIN calcular

MÉTODO 2: Total Fuel Used Counter (si disponible)
- Sensores: total_fuel_used (delta) + speed × time
- Ventaja: Contador ECU preciso (±1%) vs sensor (±5%)
- Cálculo: delta_fuel = current - previous
           delta_miles = speed × dt_hours
           MPG = delta_miles / delta_fuel

MÉTODO 3: Sensor Level (solo si estable)
- Sensores: fuel_lvl (delta) + speed × time  
- Condición: No refuel recent, sensor stable
- Problema: Error ±5% en tanque 250 gal = 12.5 gal error
- Cálculo: fuel_drop = (last_pct - curr_pct) / 100 * capacity

MÉTODO 4: Consumption Rate (último recurso)
- Sensores: consumption_gph + speed × time
- Problema: Subestima consumo → MPG inflados
- Solo usar si nada más disponible

VALIDACIONES CRÍTICAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. GPS QUALITY CHECK:
   - hdop <= 2.0
   - sats >= 6
   - speed: 5-85 mph (realista)

2. FUEL CONSUMPTION CHECK:
   - delta_gallons: 0.01-50 gal (evita errores y refuels)
   - No negativos
   
3. DISTANCE CHECK:
   - delta_miles > 0
   - delta_miles < 100 (no puede recorrer 100mi en 15-20 seg)

4. MPG RANGE (44,000 lbs trucks):
   - MIN: 3.5 MPG (Reefer loaded, mountain, city)
   - MAX: 8.5 MPG (Empty flatbed, highway, downhill)
   
5. CROSS-VALIDATION:
   - Si tenemos fuel_economy ECU Y calculado:
     - Si |calc - ecu| < 1.5 → AMBOS válidos, usar promedio
     - Si |calc - ecu| >= 1.5 → Usar ECU (más confiable)

CONFIGURACIÓN ACTUALIZADA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

min_miles: 10.0 (era 5.0, aumentado para menos ruido)
min_fuel_gal: 2.0 (era 0.75, aumentado para menos error %)
min_mpg: 3.5 (realista para 44k lbs)
max_mpg: 8.5 (era 12.0, reducido a realista)
max_speed_mph: 85.0
max_hdop: 2.0
min_satellites: 6
use_ecu_validation: True
max_ecu_calc_diff: 1.5

ESCENARIOS ESPERADOS (44,000 lbs trucks):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WORST CASE (3.5-4.5 MPG):
- Reefer (refrigerated)
- Cargado 44k lbs
- Mountain/uphill
- City traffic
- Temperatura extrema

TYPICAL LOADED (4.5-5.5 MPG):
- Dry van cargado
- City/suburban
- Terreno normal

HIGHWAY LOADED (5.5-6.5 MPG):
- Flatbed cargado
- Highway constante
- Terreno llano

EMPTY HIGHWAY (6.5-7.5 MPG):
- Vacío
- Highway
- Terreno llano

OPTIMAL (7.0-8.5 MPG):
- Vacío
- Downhill/descent
- Highway
- Temperatura ideal

IMPLEMENTACIÓN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ver código en wialon_sync_enhanced.py y mpg_engine.py
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class MPGConfigV2:
    """Configuración MPG para camiones 44,000 lbs"""
    
    # Window thresholds - MÁS CONSERVADORES
    min_miles: float = 10.0  # Mayor distancia = menos error %
    min_fuel_gal: float = 2.0  # Más combustible = menos error %
    
    # Physical limits para 44k lbs trucks
    min_mpg: float = 3.5  # Reefer loaded uphill city
    max_mpg: float = 8.5  # Empty downhill highway (NO 12.0)
    
    # GPS quality thresholds
    max_hdop: float = 2.0  # Horizontal Dilution of Precision
    min_satellites: int = 6
    max_speed_mph: float = 85.0
    min_speed_mph: float = 5.0
    
    # ECU validation
    use_ecu_validation: bool = True
    max_ecu_calc_diff: float = 1.5  # MPG difference threshold
    
    # EMA smoothing
    ema_alpha: float = 0.4
    fallback_mpg: float = 5.7


def calculate_mpg_v2(
    truck_id: str,
    # Fuel consumption sensors
    fuel_economy_ecu: Optional[float],
    total_fuel_used: Optional[float],
    prev_total_fuel: Optional[float],
    fuel_lvl_pct: Optional[float],
    prev_fuel_lvl_pct: Optional[float],
    consumption_gph: Optional[float],
    tank_capacity_gal: float,
    # Distance sensors
    speed_mph: Optional[float],
    dt_hours: float,
    odometer_mi: Optional[float],
    prev_odometer_mi: Optional[float],
    # GPS quality
    hdop: Optional[float],
    satellites: Optional[int],
    # Config
    config: MPGConfigV2 = MPGConfigV2()
) -> Tuple[Optional[float], str]:
    """
    Calculate MPG using new hierarchical approach.
    
    Returns:
        (mpg_value, fuel_source) tuple
        fuel_source can be: "ECU_DIRECT", "ECU_COUNTER", "SENSOR", "RATE", "INVALID"
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 0: GPS QUALITY CHECK
    # ═══════════════════════════════════════════════════════════════════════
    
    if hdop and hdop > config.max_hdop:
        logger.debug(f"[{truck_id}] GPS quality poor: HDOP={hdop:.1f} > {config.max_hdop}")
        return None, "INVALID"
    
    if satellites and satellites < config.min_satellites:
        logger.debug(f"[{truck_id}] GPS quality poor: {satellites} sats < {config.min_satellites}")
        return None, "INVALID"
    
    if not speed_mph or speed_mph < config.min_speed_mph:
        return None, "INVALID"  # Not moving
    
    if speed_mph > config.max_speed_mph:
        logger.warning(f"[{truck_id}] Speed unrealistic: {speed_mph:.1f} mph > {config.max_speed_mph}")
        return None, "INVALID"
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: TRY ECU FUEL ECONOMY (Direct MPG from ECU)
    # ═══════════════════════════════════════════════════════════════════════
    
    if fuel_economy_ecu and config.min_mpg <= fuel_economy_ecu <= config.max_mpg:
        logger.debug(f"[{truck_id}] Using ECU direct MPG: {fuel_economy_ecu:.2f}")
        return fuel_economy_ecu, "ECU_DIRECT"
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: CALCULATE DISTANCE (speed × time)
    # ═══════════════════════════════════════════════════════════════════════
    
    delta_miles = speed_mph * dt_hours if dt_hours > 0 else 0.0
    
    # Sanity check
    if delta_miles <= 0 or delta_miles > 100:  # Can't drive 100mi in 15-20 sec
        logger.debug(f"[{truck_id}] Delta miles unrealistic: {delta_miles:.2f}")
        return None, "INVALID"
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: TRY ECU TOTAL FUEL USED (Cumulative counter)
    # ═══════════════════════════════════════════════════════════════════════
    
    if total_fuel_used is not None and prev_total_fuel is not None:
        delta_gallons = total_fuel_used - prev_total_fuel
        
        if 0.01 <= delta_gallons <= 50:  # Reasonable range
            mpg_calc = delta_miles / delta_gallons
            
            if config.min_mpg <= mpg_calc <= config.max_mpg:
                # Cross-validate with ECU if available
                if fuel_economy_ecu and config.use_ecu_validation:
                    diff = abs(mpg_calc - fuel_economy_ecu)
                    if diff < config.max_ecu_calc_diff:
                        # Both agree, use average
                        mpg_avg = (mpg_calc + fuel_economy_ecu) / 2
                        logger.debug(
                            f"[{truck_id}] ECU counter validated by ECU direct: "
                            f"calc={mpg_calc:.2f}, ecu={fuel_economy_ecu:.2f}, avg={mpg_avg:.2f}"
                        )
                        return mpg_avg, "ECU_COUNTER"
                    else:
                        # Differ significantly, trust ECU direct more
                        logger.warning(
                            f"[{truck_id}] ECU mismatch (>{config.max_ecu_calc_diff}): "
                            f"calc={mpg_calc:.2f}, ecu={fuel_economy_ecu:.2f}, using ECU"
                        )
                        return fuel_economy_ecu, "ECU_DIRECT"
                
                # No ECU or validation disabled, use calculated
                logger.debug(f"[{truck_id}] Using ECU counter: {mpg_calc:.2f} MPG")
                return mpg_calc, "ECU_COUNTER"
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: TRY SENSOR LEVEL (if stable and no refuel)
    # ═══════════════════════════════════════════════════════════════════════
    
    if fuel_lvl_pct is not None and prev_fuel_lvl_pct is not None:
        fuel_drop_pct = prev_fuel_lvl_pct - fuel_lvl_pct
        
        # Only use if dropping (consuming), not increasing (refuel)
        if fuel_drop_pct > 0:
            delta_gallons = (fuel_drop_pct / 100) * tank_capacity_gal
            
            if 0.01 <= delta_gallons <= 50:
                mpg_calc = delta_miles / delta_gallons
                
                if config.min_mpg <= mpg_calc <= config.max_mpg:
                    # Cross-validate
                    if fuel_economy_ecu and config.use_ecu_validation:
                        diff = abs(mpg_calc - fuel_economy_ecu)
                        if diff >= config.max_ecu_calc_diff:
                            logger.warning(
                                f"[{truck_id}] Sensor disagrees with ECU: "
                                f"calc={mpg_calc:.2f}, ecu={fuel_economy_ecu:.2f}, using ECU"
                            )
                            return fuel_economy_ecu, "ECU_DIRECT"
                    
                    logger.debug(f"[{truck_id}] Using sensor level: {mpg_calc:.2f} MPG")
                    return mpg_calc, "SENSOR"
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5: FALLBACK TO CONSUMPTION RATE (least accurate)
    # ═══════════════════════════════════════════════════════════════════════
    
    if consumption_gph and 0.5 <= consumption_gph <= 20:
        delta_gallons = consumption_gph * dt_hours
        
        if delta_gallons > 0.01:
            mpg_calc = delta_miles / delta_gallons
            
            if config.min_mpg <= mpg_calc <= config.max_mpg:
                logger.debug(f"[{truck_id}] Using consumption rate: {mpg_calc:.2f} MPG")
                return mpg_calc, "RATE"
    
    # ═══════════════════════════════════════════════════════════════════════
    # NO VALID CALCULATION POSSIBLE
    # ═══════════════════════════════════════════════════════════════════════
    
    logger.debug(f"[{truck_id}] No valid MPG calculation method available")
    return None, "INVALID"
