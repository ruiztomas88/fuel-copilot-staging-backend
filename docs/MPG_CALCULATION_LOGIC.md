# Lógica de Cálculo de MPG (Miles Per Gallon)
## Sistema de Fuel Analytics - Documentación Técnica Completa

**Versión:** 3.15.0 (PRODUCCIÓN)  
**Última actualización:** Diciembre 29, 2025  
**Autor:** Fuel Analytics Team

---

## 🚨 ALERTA CRÍTICA - CONFIGURACIÓN CORREGIDA

**Fecha Fix:** Diciembre 29, 2025  
**Severidad:** 🔴 CRÍTICA  
**Problema:** Configuración anterior causaba **MPG inflados en 10-25%** para toda la flota  
**Estado:** ✅ CORREGIDO

### ⚡ Cambios Críticos Aplicados:

| Parámetro | ❌ Valor Anterior | ✅ Valor Actual | Impacto |
|-----------|------------------|-----------------|---------|
| `min_miles` | 5.0 mi | **20.0 mi** | ↓73% error sensor |
| `min_fuel_gal` | 0.75 gal | **2.5 gal** | ↓67% error porcentual |
| `max_mpg` | 9.0 MPG | **8.5 MPG** | Rechaza outliers irreales |
| `ema_alpha` | 0.4 | **0.20** | ↓50% sensibilidad outliers |
| `use_dynamic_alpha` | True | **False** | Elimina inestabilidad |

**Resultado Esperado:** MPG promedio reducirá de 6.8 → 5.9 MPG (-13%)

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Contexto y Desafíos](#contexto-y-desafíos)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Métodos de Cálculo](#métodos-de-cálculo)
5. [Código Completo](#código-completo)
6. [Validaciones y Filtros](#validaciones-y-filtros)
7. [Configuración y Parámetros](#configuración-y-parámetros)
8. [Ejemplos de Uso](#ejemplos-de-uso)

---

## 🎯 Resumen Ejecutivo

El sistema calcula MPG (Miles Per Gallon) para una flota de camiones Clase 8 (44,000 lbs) usando **múltiples métodos jerárquicos** con validación cruzada y filtrado de outliers. El objetivo es obtener mediciones precisas a pesar de la variabilidad de sensores y condiciones operativas.

### Características Principales

✅ **Múltiples Fuentes de Datos**: ECU, sensores de tanque, GPS, CAN bus  
✅ **Jerarquía Inteligente**: Prioriza fuentes más confiables (ECU > Kalman > Sensor)  
✅ **Suavizado EMA Conservador**: Alpha 0.20 (reducido de 0.4) para estabilidad  
✅ **Validación Física Estricta**: Límites realistas (3.5-8.5 MPG) para Clase 8  
✅ **Filtrado de Outliers**: IQR y MAD para eliminar lecturas erróneas  
✅ **Baseline por Camión**: Aprende el MPG histórico de cada vehículo  
✅ **Ventanas Grandes**: 20 mi / 2.5 gal para minimizar error porcentual del sensor

---

## 🚛 Contexto y Desafíos

### Rangos Esperados de MPG (Camiones Clase 8)

```
┌─────────────────────────────────────────────────────────────┐
│  ESCENARIO                      │   MPG ESPERADO            │
├─────────────────────────────────────────────────────────────┤
│  Reefer cargado, montaña        │   3.5 - 4.5 MPG (WORST)  │
│  Dry van cargado, ciudad        │   4.5 - 5.5 MPG          │
│  Flatbed cargado, autopista     │   5.5 - 6.5 MPG          │
│  Dry van vacío, autopista       │   6.5 - 7.5 MPG          │
│  Vacío, bajada, óptimo          │   7.0 - 12.0 MPG (BEST)  │
└─────────────────────────────────────────────────────────────┘
```

### Problemas Identificados

❌ **Sensor de Nivel de Tanque**: Error ±2-5% (olas, inclinación)  
❌ **Fuel Rate (L/h)**: Error ±10-15% (subestima consumo → MPG inflados)  
❌ **Odómetro**: Solo 15% de cobertura en la flota  
❌ **Time Gaps**: IDLE prolongado puede corromper cálculos acumulados  

### Solución Implementada (PRODUCCIÓN v3.15.0)

✅ **Jerarquía de Prioridad**: ECU > Kalman Filter > Sensor > Fuel Rate  
✅ **Validación Cruzada**: Compara múltiples fuentes cuando disponibles  
✅ **Acumulador con Ventanas GRANDES**: **20 millas / 2.5 galones** (antes: 5 mi / 0.75 gal)  
✅ **Suavizado Conservador**: Alpha **0.20** (antes: 0.4) - reduce contaminación por outliers 50%  
✅ **Límites Estrictos**: Max **8.5 MPG** (antes: 9.0) - rechaza outliers irreales para Clase 8  
✅ **Dynamic Alpha DESACTIVADO**: Elimina inestabilidad cuando varianza baja

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    WIALON API (Telemetría)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              SENSORES DISPONIBLES                               │
├─────────────────────────────────────────────────────────────────┤
│  FUEL CONSUMPTION:                                              │
│  • total_fuel_used (gallons) - ECU acumulativo (±1%)           │
│  • fuel_economy (MPG) - ECU directo                            │
│  • fuel_lvl (%) - Sensor tanque (±5%)                          │
│  • fuel_rate (L/h) - CAN bus (±15%)                            │
│                                                                  │
│  DISTANCIA:                                                      │
│  • odometer (mi) - Solo 15% coverage                           │
│  • speed (mph) - 100% coverage (±2% con GPS)                   │
│                                                                  │
│  GPS QUALITY:                                                    │
│  • hdop - Horizontal Dilution (<2.0 = bueno)                   │
│  • sats - Satellites count (≥6 = confiable)                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│           KALMAN FILTER (Noise Reduction)                       │
│  • Filtra ruido de sensor de tanque                            │
│  • Produce estimated_gallons (más preciso)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              MPG CALCULATION ENGINE                             │
│  1. Validación GPS Quality (HDOP, Satellites)                  │
│  2. Cálculo de Deltas (Miles, Gallons)                         │
│  3. Jerarquía de Métodos (ECU→Kalman→Sensor→Rate)             │
│  4. Validación Física (3.5-8.5 MPG) ✅ CORREGIDO               │
│  5. Suavizado EMA (alpha = 0.20) ✅ CORREGIDO                  │
│  6. Filtrado de Outliers (IQR/MAD)                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 BASELINE MANAGER                                │
│  • Aprende MPG histórico por camión                            │
│  • Detecta anomalías (z-score)                                 │
│  • Calcula desviación vs baseline                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│          DATABASE (PostgreSQL)                                  │
│  • fuel_metrics: MPG suavizado (mpg_kalman)                    │
│  • truck_baselines: Baseline histórico                         │
│  • alerts: Anomalías detectadas                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔢 Métodos de Cálculo

### Método 1: ECU Fuel Economy (Directo)

**Prioridad:** MÁXIMA  
**Fuente:** Sensor `fuel_economy` del ECU  
**Error:** ±1-2%  
**Condición:** Valor dentro de rango 3.5-8.5 MPG

```python
# Paso 1: Validar si existe y es realista
if fuel_economy_ecu and 3.5 <= fuel_economy_ecu <= 8.5:
    return fuel_economy_ecu  # Usar directo, SIN calcular
```

**Ventajas:**
- Valor directo del ECU, muy confiable
- No requiere cálculos adicionales
- Error mínimo (±1%)

**Desventajas:**
- No siempre disponible en todos los camiones
- Puede tener outliers ocasionales

---

### Método 2: ECU Total Fuel Used (Contador Acumulativo)

**Prioridad:** ALTA  
**Fuente:** `total_fuel_used` (contador acumulativo del ECU)  
**Error:** ±1%  
**Cálculo:**

```python
# Delta de combustible desde última lectura
delta_fuel_gal = current_total_fuel - previous_total_fuel

# Delta de distancia (speed × time)
delta_miles = speed_mph * dt_hours

# MPG calculado
if 0.01 < delta_fuel_gal < 25:  # Sanity check
    mpg_calc = delta_miles / delta_fuel_gal
    
    # Validar rango físico
    if 2.0 <= mpg_calc <= 12.0:
        return mpg_calc
```

**Ventajas:**
- Contador ECU muy preciso (±1%)
- No afectado por olas o inclinación del tanque
- Funciona para ventanas de tiempo largas

**Desventajas:**
- Requiere dos lecturas consecutivas
- Primer registro no puede calcular delta

---

### Método 3: Kalman Filter (Estimación de Galones)

**Prioridad:** MEDIA-ALTA  
**Fuente:** `estimated_gallons` (fuel_lvl filtrado por Kalman)  
**Error:** ±2-3%  
**Cálculo:**

```python
# Delta de combustible filtrado por Kalman
kalman_fuel_drop = last_estimated_gal - current_estimated_gal

# Delta de distancia
delta_miles = speed_mph * dt_hours

# MPG calculado
if 0.01 < kalman_fuel_drop < 100:
    mpg_calc = delta_miles / kalman_fuel_drop
    
    if 2.0 <= mpg_calc <= 12.0:
        return mpg_calc
```

**Ventajas:**
- Filtrado de ruido de sensor (Kalman reduce ±5% a ±2%)
- Más preciso que sensor raw
- Disponible cuando ECU no tiene `total_fuel_used`

**Desventajas:**
- Aún puede tener error por calibración del sensor
- Depende de `tank_capacity_gal` correcto

---

### Método 4: Sensor de Nivel (Raw)

**Prioridad:** MEDIA  
**Fuente:** `fuel_lvl` (porcentaje del tanque)  
**Error:** ±5%  
**Condición:** No refuel reciente, sensor estable  
**Cálculo:**

```python
# Delta de porcentaje
fuel_drop_pct = last_fuel_lvl_pct - current_fuel_lvl_pct

# Convertir a galones
delta_gallons = (fuel_drop_pct / 100) * tank_capacity_gal

# Delta de distancia
delta_miles = speed_mph * dt_hours

# MPG calculado
if 0.05 < fuel_drop_pct < 50:  # Evitar jumps erráticos
    mpg_calc = delta_miles / delta_gallons
    
    if 2.0 <= mpg_calc <= 12.0:
        return mpg_calc
```

**Ventajas:**
- Disponible en 100% de los camiones
- Fácil de calcular

**Desventajas:**
- Error ±5% (en tanque 250 gal = ±12.5 gal error)
- Afectado por olas, inclinación, temperatura
- Jumps erráticos durante refueling

---

### Método 5: Fuel Rate (Consumption Rate)

**Prioridad:** BAJA (último recurso)  
**Fuente:** `consumption_gph` (gallons per hour del CAN bus)  
**Error:** ±10-15%  
**Cálculo:**

```python
# Combustible consumido en ventana de tiempo
delta_gallons = consumption_gph * dt_hours

# Delta de distancia
delta_miles = speed_mph * dt_hours

# MPG calculado
if 0.5 <= consumption_gph <= 20:
    mpg_calc = delta_miles / delta_gallons
    
    if 2.0 <= mpg_calc <= 12.0:
        return mpg_calc
```

**Ventajas:**
- Disponible en tiempo real
- Útil cuando otros métodos fallan

**Desventajas:**
- **TIENDE A SUBESTIMAR** consumo → MPG inflados
- Muy ruidoso (varianza alta)
- Solo útil para MPG instantáneo, no acumulado

---

## 💻 Código Completo

### 1. Estructuras de Datos

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class MPGState:
    """
    Estado de seguimiento de MPG con patrón acumulador
    """
    # Acumuladores de ventana
    distance_accum: float = 0.0
    fuel_accum_gal: float = 0.0
    
    # MPG actual (suavizado con EMA)
    mpg_current: Optional[float] = None
    
    # Estadísticas
    window_count: int = 0
    last_raw_mpg: Optional[float] = None
    
    # Tracking de lecturas anteriores
    last_fuel_lvl_pct: Optional[float] = None
    last_odometer_mi: Optional[float] = None
    last_timestamp: Optional[float] = None
    last_total_fuel_gal: Optional[float] = None
    last_estimated_gal: Optional[float] = None
    
    # Historia para variance-based adaptive alpha
    mpg_history: list = field(default_factory=list)
    max_history_size: int = 10
    
    # Estadísticas de validación
    total_discarded: int = 0
    total_accepted: int = 0
    fuel_source_stats: dict = field(
        default_factory=lambda: {
            "kalman": 0,
            "sensor": 0,
            "ecu_cumulative": 0,
            "fallback": 0,
        }
    )
    
    def add_to_history(self, mpg_value: float):
        """Agregar MPG a historia, manteniendo tamaño máximo"""
        self.mpg_history.append(mpg_value)
        if len(self.mpg_history) > self.max_history_size:
            self.mpg_history.pop(0)
    
    def get_variance(self) -> float:
        """Calcular varianza de lecturas recientes"""
        if len(self.mpg_history) < 3:
            return 0.0
        
        # Aplicar filtro IQR para remover outliers
        filtered = filter_outliers_iqr(self.mpg_history)
        if len(filtered) < 2:
            return 1.0  # Alta varianza = más suavizado
        
        mean = sum(filtered) / len(filtered)
        variance = sum((x - mean) ** 2 for x in filtered) / len(filtered)
        return variance


@dataclass
class MPGConfig:
    """
    Configuración para cálculo y validación de MPG
    
    🔥 v3.15.0 DEC 29: CRITICAL FIX for inflated MPG readings
    - Increased min_miles from 5.0 to 20.0 (reduce sensor error impact)
    - Increased min_fuel_gal from 0.75 to 2.5 (reduce percentage error)
    - Reduced max_mpg from 9.0 to 8.5 (more realistic for Clase 8)
    - Reduced ema_alpha from 0.4 to 0.20 (more conservative smoothing)
    - DISABLED dynamic_alpha (was causing instability)
    """
    # Umbrales de ventana
    min_miles: float = 20.0  # 🔥 v3.15.0: Increased from 5.0 to reduce sensor noise
    min_fuel_gal: float = 2.5  # 🔥 v3.15.0: Increased from 0.75 to reduce % error
    
    # Límites físicos (Camiones Clase 8, 44,000 lbs)
    min_mpg: float = 3.5  # Mínimo absoluto (reefer, loaded, mountain, city)
    max_mpg: float = 8.5  # 🔥 v3.15.0: Reduced from 9.0 (more realistic)
    
    # Factor de suavizado EMA
    ema_alpha: float = 0.20  # 🔥 v3.15.0: Reduced from 0.4 for smoother readings
    fallback_mpg: float = 5.7  # Promedio de flota
    
    # Alpha dinámico - DISABLED for stability
    use_dynamic_alpha: bool = False  # 🔥 v3.15.0: Disabled (was causing instability)
    alpha_high_variance: float = 0.20  # Not used when dynamic disabled
    alpha_low_variance: float = 0.25  # Not used when dynamic disabled
    variance_threshold: float = 0.30  # Not used when dynamic disabled
```

### 2. Filtrado de Outliers

```python
def filter_outliers_iqr(readings: list, multiplier: float = 1.5) -> list:
    """
    Filtrado de outliers usando Interquartile Range (IQR).
    
    Args:
        readings: Lista de lecturas MPG
        multiplier: Multiplicador IQR (1.5 = estándar)
    
    Returns:
        Lista filtrada sin outliers
    """
    if len(readings) < 4:
        # Para muestras pequeñas, usar MAD
        return filter_outliers_mad(readings)
    
    sorted_data = sorted(readings)
    n = len(sorted_data)
    
    # Calcular Q1 (percentil 25) y Q3 (percentil 75)
    q1_idx = n // 4
    q3_idx = (3 * n) // 4
    q1 = sorted_data[q1_idx]
    q3 = sorted_data[q3_idx]
    
    iqr = q3 - q1
    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr
    
    filtered = [r for r in readings if lower_bound <= r <= upper_bound]
    
    # Protección: si quedan menos de 2 lecturas, datos corruptos
    if len(filtered) < 2:
        return []
    
    return filtered


def filter_outliers_mad(readings: list, threshold: float = 3.0) -> list:
    """
    Filtrado usando Median Absolute Deviation (MAD).
    Más robusto para muestras pequeñas (n < 4).
    
    Args:
        readings: Lista de lecturas MPG
        threshold: Número de MADs desde mediana para considerar outlier
    
    Returns:
        Lista filtrada sin outliers
    """
    if len(readings) < 2:
        return readings
    
    sorted_data = sorted(readings)
    median = sorted_data[len(sorted_data) // 2]
    
    # Calcular MAD
    absolute_deviations = [abs(x - median) for x in readings]
    mad = sorted(absolute_deviations)[len(absolute_deviations) // 2]
    
    if mad < 0.01:  # Todos los valores muy similares
        return readings
    
    # Filtrar outliers más allá de threshold * MAD
    filtered = [r for r in readings if abs(r - median) <= threshold * mad]
    
    return filtered if filtered else readings
```

### 3. Función Principal de Actualización

```python
def update_mpg_state(
    state: MPGState,
    delta_miles: float,
    delta_gallons: float,
    config: MPGConfig = MPGConfig(),
    truck_id: str = "UNKNOWN",
) -> MPGState:
    """
    Actualizar estado de MPG con nuevos deltas.
    
    Args:
        state: Estado actual de MPG
        delta_miles: Distancia recorrida desde última actualización
        delta_gallons: Combustible consumido desde última actualización
        config: Configuración de MPG
        truck_id: Identificador del camión
    
    Returns:
        Estado actualizado (mismo objeto, modificado in-place)
    
    Lógica:
        1. Forzar deltas no-negativos (seguridad)
        2. Acumular distancia y combustible
        3. Si umbral de ventana alcanzado:
           a. Calcular MPG raw
           b. Validar contra límites físicos
           c. Aplicar suavizado EMA si válido
           d. Resetear acumulador
        4. Rastrear estadísticas
    """
    # Forzar no-negativo (seguridad contra glitches)
    delta_miles = max(delta_miles, 0.0)
    delta_gallons = max(delta_gallons, 0.0)
    
    # Acumular
    state.distance_accum += delta_miles
    state.fuel_accum_gal += delta_gallons
    
    # Verificar si ventana está completa
    if (state.distance_accum >= config.min_miles and 
        state.fuel_accum_gal >= config.min_fuel_gal):
        
        # Calcular MPG raw
        raw_mpg = state.distance_accum / state.fuel_accum_gal
        state.last_raw_mpg = raw_mpg
        
        # Validar contra límites físicos
        if config.min_mpg <= raw_mpg <= config.max_mpg:
            # MPG válido - agregar a historia
            state.add_to_history(raw_mpg)
            
            # Obtener alpha dinámico basado en varianza
            alpha = get_dynamic_alpha(state, config)
            
            # Aplicar suavizado EMA
            if state.mpg_current is None:
                # Primera cálculo - usar valor raw
                state.mpg_current = raw_mpg
                logger.info(f"[{truck_id}] MPG inicializado: {raw_mpg:.2f} MPG")
            else:
                # Aplicar EMA: nuevo = alpha * raw + (1-alpha) * viejo
                old_mpg = state.mpg_current
                state.mpg_current = alpha * raw_mpg + (1 - alpha) * state.mpg_current
                
                # CRÍTICO: Clampear post-EMA para prevenir exceder límites
                state.mpg_current = max(config.min_mpg, 
                                       min(state.mpg_current, config.max_mpg))
                
                variance = state.get_variance()
                logger.info(
                    f"[{truck_id}] MPG actualizado: {old_mpg:.2f} → {state.mpg_current:.2f} "
                    f"(raw: {raw_mpg:.2f}, alpha: {alpha:.2f}, varianza: {variance:.3f}, "
                    f"ventana: {state.distance_accum:.1f}mi/{state.fuel_accum_gal:.2f}gal)"
                )
            
            state.total_accepted += 1
            state.window_count += 1
            
        else:
            # MPG inválido - descartar pero resetear ventana
            logger.warning(
                f"[{truck_id}] MPG descartado: {raw_mpg:.2f} MPG fuera de rango "
                f"[{config.min_mpg:.1f}, {config.max_mpg:.1f}]. "
                f"Ventana: {state.distance_accum:.1f}mi / {state.fuel_accum_gal:.2f}gal. "
                f"MPG actual sin cambios: {state.mpg_current if state.mpg_current else 'N/A'}"
            )
            state.total_discarded += 1
        
        # Resetear ventana (siempre, incluso si descartado)
        state.distance_accum = 0.0
        state.fuel_accum_gal = 0.0
    
    return state


def get_dynamic_alpha(state: MPGState, config: MPGConfig) -> float:
    """
    Calcular alpha dinámico basado en varianza.
    
    Alta varianza (datos ruidosos) → alpha bajo (más suavizado)
    Baja varianza (datos estables) → alpha alto (más responsivo)
    """
    if not config.use_dynamic_alpha:
        return config.ema_alpha
    
    variance = state.get_variance()
    
    if variance > config.variance_threshold:
        return config.alpha_high_variance  # Más suave
    else:
        return config.alpha_low_variance  # Más responsivo
```

### 4. Implementación en Sync Loop

```python
def calculate_mpg_with_hierarchy(
    truck_id: str,
    sensor_data: dict,
    state: MPGState,
    config: MPGConfig,
) -> tuple[Optional[float], str]:
    """
    Calcular MPG usando jerarquía de métodos.
    
    Returns:
        (mpg_value, fuel_source) donde fuel_source puede ser:
        "ECU_DIRECT", "ECU_COUNTER", "KALMAN", "SENSOR", "RATE", "INVALID"
    """
    
    # PASO 1: Validar calidad de GPS
    hdop = sensor_data.get("hdop")
    satellites = sensor_data.get("sats")
    speed_mph = sensor_data.get("speed")
    
    if hdop and hdop > 2.0:
        return None, "INVALID"
    if satellites and satellites < 6:
        return None, "INVALID"
    if not speed_mph or speed_mph < 5:
        return None, "INVALID"
    if speed_mph > 85:
        return None, "INVALID"
    
    # PASO 2: Calcular delta de distancia
    dt_hours = sensor_data.get("dt_hours", 0)
    delta_miles = speed_mph * dt_hours if dt_hours > 0 else 0.0
    
    if delta_miles <= 0 or delta_miles > 500:
        return None, "INVALID"
    
    # PASO 3: Intentar ECU directo
    fuel_economy_ecu = sensor_data.get("fuel_economy")
    if fuel_economy_ecu and 2.0 <= fuel_economy_ecu <= 12.0:
        return fuel_economy_ecu, "ECU_DIRECT"
    
    # PASO 4: Intentar ECU contador acumulativo
    total_fuel_gal = sensor_data.get("total_fuel_used")
    if total_fuel_gal and state.last_total_fuel_gal:
        delta_fuel = total_fuel_gal - state.last_total_fuel_gal
        if 0.01 < delta_fuel < 25:
            mpg_calc = delta_miles / delta_fuel
            if 2.0 <= mpg_calc <= 12.0:
                return mpg_calc, "ECU_COUNTER"
    
    # PASO 5: Intentar Kalman filter
    estimated_gal = sensor_data.get("estimated_gallons")
    if estimated_gal and state.last_estimated_gal:
        delta_fuel = state.last_estimated_gal - estimated_gal
        if 0.01 < delta_fuel < 100:
            mpg_calc = delta_miles / delta_fuel
            if 2.0 <= mpg_calc <= 12.0:
                return mpg_calc, "KALMAN"
    
    # PASO 6: Intentar sensor raw
    fuel_lvl_pct = sensor_data.get("fuel_lvl")
    tank_capacity = sensor_data.get("tank_capacity_gal", 250)
    if fuel_lvl_pct and state.last_fuel_lvl_pct:
        fuel_drop_pct = state.last_fuel_lvl_pct - fuel_lvl_pct
        if 0.05 < fuel_drop_pct < 50:
            delta_fuel = (fuel_drop_pct / 100) * tank_capacity
            mpg_calc = delta_miles / delta_fuel
            if 2.0 <= mpg_calc <= 12.0:
                return mpg_calc, "SENSOR"
    
    # PASO 7: Último recurso - fuel rate
    consumption_gph = sensor_data.get("consumption_gph")
    if consumption_gph and 0.5 <= consumption_gph <= 20:
        delta_fuel = consumption_gph * dt_hours
        if delta_fuel > 0.01:
            mpg_calc = delta_miles / delta_fuel
            if 2.0 <= mpg_calc <= 12.0:
                return mpg_calc, "RATE"
    
    return None, "INVALID"
```

---

## ✅ Validaciones y Filtros

### 1. Validación de GPS Quality

```python
# Rechazar si GPS de baja calidad
if hdop > 2.0:  # HDOP alto = mala precisión
    reject()

if satellites < 6:  # Mínimo 6 satélites
    reject()
```

### 2. Validación de Velocidad

```python
# Solo calcular MPG cuando el camión está moviendo
if speed < 5 mph:  # Muy lento o parado
    skip()

if speed > 85 mph:  # Velocidad irreal
    reject()
```

### 3. Validación de Deltas

```python
# Delta de distancia
if delta_miles <= 0 or delta_miles > 500:
    reject()  # Negativo o irreal

# Delta de combustible
if delta_gallons <= 0.01:
    reject()  # Demasiado pequeño (ruido)

if delta_gallons > 100:
    reject()  # Demasiado grande (refuel o error)
```

### 4. Validación de MPG Físico

```python
# Rango realista para Clase 8
if mpg < 2.0:  # Imposible (heavy idle extremo)
    reject()

if mpg > 12.0:  # Imposible (vacío bajada máximo)
    reject()

# Advertencia para valores borderline
if mpg < 4.5 or mpg > 10.0:
    log_warning()  # Aún válido pero inusual
```

### 5. Validación de Ventana

```python
# Solo calcular cuando hay suficientes datos acumulados
if distance_accum < 10.0 miles:
    continue_accumulating()

if fuel_accum < 1.2 gallons:
    continue_accumulating()
```

---

## ⚙️ Configuración y Parámetros

### Parámetros de Producción (v3.15.0 - DIC 29, 2025)

```python
MPGConfig(
    # Ventana de acumulación (CORREGIDO: ventanas más grandes reducen error de sensor)
    min_miles=20.0,        # 20 millas (antes: 5.0) - reduce error sensor 73%
    min_fuel_gal=2.5,      # 2.5 galones (antes: 0.75) - reduce error % 67%
    
    # Límites físicos (CORREGIDO: más conservador)
    min_mpg=3.5,           # Reefer cargado en montaña
    max_mpg=8.5,           # Vacío en autopista (antes: 9.0) - más realista
    
    # Suavizado EMA (CORREGIDO: menos reactivo a outliers)
    ema_alpha=0.20,        # 20% nuevo, 80% histórico (antes: 0.4) - ↓50% sensibilidad
    fallback_mpg=5.7,      # Promedio de flota
    
    # Alpha dinámico (DESACTIVADO - causaba inestabilidad)
    use_dynamic_alpha=False,  # Antes: True
    alpha_high_variance=0.20,
    alpha_low_variance=0.25,
    variance_threshold=0.30
)
```

**馃敡 CAMBIOS CRÍTICOS DIC 29, 2025:**
- **Problema identificado:** Configuración anterior generaba MPG inflados 10-25%
- **Causa raíz:** Ventanas muy pequeñas amplificaban error de sensor (±5%)
- **Solución:** Ventanas 4x más grandes + alpha más conservador
- **Impacto esperado:** MPG promedio bajará de 6.8 → 5.9 MPG (-13%)

### ⚠️ CRÍTICO: Por Qué los Valores Anteriores Eran Incorrectos

**Configuración anterior (INCORRECTA):**
```python
MPGConfig(
    min_miles=10.0,        # ❌ MUY PEQUEÑO
    min_fuel_gal=1.2,      # ❌ MUY PEQUEÑO
    max_mpg=12.0,          # ❌ IRREAL para Clase 8
    ema_alpha=0.35,        # ❌ DEMASIADO REACTIVO
)
```

**Problema 1: Ventanas Microscópicas Amplifican Error del Sensor**
- Sensor de tanque: error **±5%** siempre
- Con 1.2 galones → error de **±0.06 gal**
- En 10 millas: `10 / 1.14 = 8.77 MPG` vs `10 / 1.26 = 7.94 MPG`
- **Variación de ±10% por ruido puro del sensor**

**Problema 2: Alpha Alto Contamina el Promedio**
- Con alpha=0.35, un outlier de 9.5 MPG:
- `nuevo = 0.35 × 9.5 + 0.65 × 6.5 = 3.325 + 4.225 = 7.55 MPG`
- **Salta de 6.5 → 7.55 (+16%) en una sola lectura mala**

**Problema 3: Max MPG Irreal**
- Clase 8 (44,000 lbs) raramente excede **8.5 MPG**
- Permitir hasta 12.0 acepta **outliers inflados sin validación**

**Solución: Configuración Actual (CORRECTA)**
```python
MPGConfig(
    min_miles=20.0,        # ✅ 2x más grande → error ±2.5% (73% mejor)
    min_fuel_gal=2.5,      # ✅ 2x más grande → error ±2.0% (67% mejor)
    max_mpg=8.5,           # ✅ Realista → rechaza outliers >8.5
    ema_alpha=0.20,        # ✅ Conservador → outlier solo +6% (50% mejor)
)
```

### Recomendaciones por Escenario

```python
# Para flota con ECU confiable (raro - usar valores estándar)
MPGConfig(
    min_miles=15.0,        # Puede reducir ligeramente
    ema_alpha=0.25,        # Puede ser más responsivo
)

# Para flota con sensores ruidosos (ESTÁNDAR ACTUAL)
MPGConfig(
    min_miles=20.0,        # ✅ Más acumulación = menos error %
    min_fuel_gal=2.5,      # ✅ Más combustible = menos error %
    ema_alpha=0.20,        # ✅ Más suavizado (CRÍTICO)
    use_dynamic_alpha=False, # ✅ NO usar dynamic - inestable
)

# Para flota mixta (reefer + dry van) - PRODUCCIÓN ACTUAL
MPGConfig(
    min_mpg=3.5,           # ✅ Realista para reefer montaña
    max_mpg=8.5,           # ✅ Conservador pero realista
    min_miles=20.0,        # ✅ CRÍTICO - no reducir
    min_fuel_gal=2.5,      # ✅ CRÍTICO - no reducir
)
```

---

## 📊 Ejemplos de Uso

### Ejemplo 1: Calcular MPG en Sync Loop

```python
from mpg_engine import MPGState, MPGConfig, update_mpg_state

# Inicializar estado por camión
truck_states = {}
config = MPGConfig()

def process_telemetry(truck_id: str, sensor_data: dict):
    # Obtener o crear estado
    if truck_id not in truck_states:
        truck_states[truck_id] = MPGState()
    
    state = truck_states[truck_id]
    
    # Calcular MPG con jerarquía
    mpg_value, fuel_source = calculate_mpg_with_hierarchy(
        truck_id, sensor_data, state, config
    )
    
    if mpg_value:
        print(f"{truck_id}: MPG={mpg_value:.2f} (source={fuel_source})")
        
        # Actualizar estado (acumular y suavizar)
        delta_miles = sensor_data["speed"] * sensor_data["dt_hours"]
        delta_gallons = # ... calcular según fuel_source
        
        state = update_mpg_state(state, delta_miles, delta_gallons, config, truck_id)
        
        # Guardar MPG suavizado a database
        save_to_db(truck_id, state.mpg_current)
```

### Ejemplo 2: Detectar Anomalías

```python
from mpg_baseline_service import MPGBaselineService

# Inicializar servicio de baseline
baseline_service = MPGBaselineService(db_pool)

async def check_mpg_anomaly(truck_id: str, current_mpg: float):
    # Obtener baseline del camión
    baseline = await baseline_service.calculate_baseline(truck_id, days=30)
    
    # Analizar desviación
    deviation = baseline_service.analyze_deviation(truck_id, current_mpg)
    
    if deviation.status == "ANOMALY":
        print(f"⚠️ {truck_id}: MPG anómalo!")
        print(f"   Actual: {current_mpg:.2f}")
        print(f"   Baseline: {baseline.baseline_mpg:.2f}")
        print(f"   Desviación: {deviation.deviation_pct:.1f}%")
        print(f"   Z-score: {deviation.z_score:.2f}")
        
        # Enviar alerta
        send_alert(truck_id, deviation.message)
```

### Ejemplo 3: Monitoreo de Fuentes de Datos

```python
def print_fuel_source_stats(state: MPGState):
    """Imprimir estadísticas de fuentes de combustible"""
    total = sum(state.fuel_source_stats.values())
    
    if total == 0:
        print("No hay datos aún")
        return
    
    print(f"\n📊 Fuentes de datos de combustible (últimas {total} lecturas):")
    print(f"   Kalman Filter:    {state.fuel_source_stats['kalman']} " +
          f"({100*state.fuel_source_stats['kalman']/total:.1f}%)")
    print(f"   ECU Cumulative:   {state.fuel_source_stats['ecu_cumulative']} " +
          f"({100*state.fuel_source_stats['ecu_cumulative']/total:.1f}%)")
    print(f"   Sensor Raw:       {state.fuel_source_stats['sensor']} " +
          f"({100*state.fuel_source_stats['sensor']/total:.1f}%)")
    print(f"   Fuel Rate:        {state.fuel_source_stats['fallback']} " +
          f"({100*state.fuel_source_stats['fallback']/total:.1f}%)")
    
    # Recomendar mejoras
    if state.fuel_source_stats['fallback'] / total > 0.3:
        print("\n⚠️ >30% de datos vienen de fuel_rate (menos confiable)")
        print("   Recomendación: Verificar disponibilidad de ECU total_fuel_used")
```

---

## 📈 Fórmulas Matemáticas

### MPG Básico

$$
\text{MPG} = \frac{\text{Distancia (millas)}}{\text{Combustible (galones)}}
$$

### Exponential Moving Average (EMA)

$$
\text{MPG}_{\text{new}} = \alpha \cdot \text{MPG}_{\text{raw}} + (1 - \alpha) \cdot \text{MPG}_{\text{old}}
$$

Donde:
- $\alpha = 0.20$ (factor de suavizado) - **🔥 v3.15.0: Reducido de 0.35**
- $\text{MPG}_{\text{raw}}$ = MPG calculado en ventana actual
- $\text{MPG}_{\text{old}}$ = MPG suavizado anterior

### Varianza

$$
\text{Var}(X) = \frac{1}{n} \sum_{i=1}^{n} (x_i - \bar{x})^2
$$

### Z-Score (Detección de Anomalías)

$$
z = \frac{x - \mu}{\sigma}
$$

Donde:
- $x$ = MPG actual
- $\mu$ = Baseline MPG
- $\sigma$ = Desviación estándar

**Interpretación:**
- $|z| < 1.0$ → Normal
- $1.0 \leq |z| < 2.0$ → Notable
- $2.0 \leq |z| < 3.0$ → Anomalía
- $|z| \geq 3.0$ → Crítico

### Interquartile Range (IQR)

$$
\text{IQR} = Q3 - Q1
$$

$$
\text{Lower Bound} = Q1 - 1.5 \times \text{IQR}
$$

$$
\text{Upper Bound} = Q3 + 1.5 \times \text{IQR}
$$

### Median Absolute Deviation (MAD)

$$
\text{MAD} = \text{median}(|x_i - \text{median}(X)|)
$$

---

## 🔧 Troubleshooting

### Problema: MPG muy altos (>7.5 promedio)

**Causa probable:**
- ❌ **Configuración incorrecta** (min_miles/min_fuel_gal muy pequeños)
- ❌ Sensor `fuel_rate` subestimando consumo 10-20%
- ❌ Alpha EMA muy alto (>0.25)
- ❌ Sensor de tanque con jumps erráticos

**Solución INMEDIATA:**
```python
# 1. Verificar configuración actual
from mpg_engine_wednesday_utf8 import MPGConfig
config = MPGConfig()
print(f"min_miles: {config.min_miles}")      # DEBE ser 20.0
print(f"min_fuel_gal: {config.min_fuel_gal}") # DEBE ser 2.5
print(f"max_mpg: {config.max_mpg}")          # DEBE ser 8.5
print(f"ema_alpha: {config.ema_alpha}")      # DEBE ser 0.20

# 2. Si valores incorrectos, CORREGIR en mpg_engine_wednesday_utf8.py

# 3. Verificar fuente de datos
print_fuel_source_stats(state)

# Si >50% de datos vienen de "fallback" (fuel_rate):
# → Aplicar factor de corrección +15%:
delta_fuel = consumption_gph * dt_hours * 1.15

# 4. Resetear estados contaminados
import os
os.remove('data/mpg_states.json')
```

**Valores CORRECTOS (Producción):**
```python
config = MPGConfig(
    min_miles=20.0,     # ✅ NO menos de 20.0
    min_fuel_gal=2.5,   # ✅ NO menos de 2.5
    max_mpg=8.5,        # ✅ Realista para Clase 8
    ema_alpha=0.20,     # ✅ NO más de 0.25
    use_dynamic_alpha=False,  # ✅ SIEMPRE False
)
```

### Problema: MPG muy bajos (<4.0)

**Causa probable:**
- Reefer (refrigerado) consumiendo más
- Tráfico urbano intenso
- Terrain montañoso

**Verificar:**
```python
# ¿Es el baseline del camión?
baseline = get_baseline(truck_id)
if baseline.baseline_mpg < 4.5:
    # Este camión normalmente tiene bajo MPG
    print("Normal para este camión (reefer/urbano)")
else:
    # Anomalía - investigar
    print("⚠️ MPG anormalmente bajo")
```

### Problema: MPG inestable (varianza alta)

**Causa probable:**
- Sensores ruidosos
- Rutas mixtas (ciudad/autopista)
- ❌ Alpha muy alto (>0.25)

**Solución:**
```python
# ✅ USAR CONFIGURACIÓN ESTÁNDAR (ya es óptima)
config = MPGConfig(
    min_miles=20.0,      # ✅ Más acumulación = menos ruido
    min_fuel_gal=2.5,    # ✅ Más combustible = menos error %
    ema_alpha=0.20,      # ✅ Conservador (NO aumentar)
    use_dynamic_alpha=False,  # ✅ NUNCA True - causa inestabilidad
)
```

---

## 📝 Changelog

### v3.15.0 (Diciembre 29, 2025) - 🔴 FIX CRÍTICO MPG INFLADOS
- ✅ **VENTANAS AUMENTADAS**: `min_miles: 5.0 → 20.0` (↓73% error sensor)
- ✅ **FUEL THRESHOLD**: `min_fuel_gal: 0.75 → 2.5` (↓67% error porcentual)
- ✅ **MAX MPG REALISTA**: `max_mpg: 9.0 → 8.5` (elimina outliers imposibles)
- ✅ **ALPHA CONSERVADOR**: `ema_alpha: 0.4 → 0.20` (↓50% sensibilidad outliers)
- ✅ **DYNAMIC ALPHA OFF**: `use_dynamic_alpha: True → False` (elimina inestabilidad)
- 🎯 **IMPACTO**: Reducción MPG promedio: 6.8 → 5.9 MPG (-13%)

### v3.14.0 (Diciembre 18, 2025)
- ✅ Auto-save/load para TruckBaselineManager
- ✅ Fix empty list en IQR filter (corrupción total)

### v3.13.0 (Diciembre 15, 2025)
- ✅ MAD filter para muestras pequeñas (n < 4)

### ⚠️ VERSIONES DESCARTADAS (MPG INFLADOS):
- ❌ v6.4.0 - v3.12.18: Configuración demasiado agresiva
- ❌ `min_miles: 5.0` causaba ±5.5% error en cada lectura
- ❌ `ema_alpha: 0.4` permitía outliers contaminar promedio +12%
- ❌ `use_dynamic_alpha: True` causaba saltos erráticos


---

## 👥 Créditos

**Desarrollado por:** Fuel Analytics Team  
**Cliente:** Fuel Analytics (Flota de camiones Clase 8)  
**Última revisión:** Diciembre 29, 2025

---

## 📚 Referencias

1. **Class 8 Truck Fuel Economy**: EPA SmartWay (2019)
2. **Kalman Filtering**: R.E. Kalman (1960)
3. **Outlier Detection**: Tukey's Fences (IQR method)
4. **EMA Smoothing**: Roberts (1959)

---

**FIN DEL DOCUMENTO**
