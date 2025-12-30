# FIXES COMPREHENSIVOS - 22 Diciembre 2025

## ✅ FIXES APLICADOS

### 1. Cost Per Mile - Queries Incorrectas
**Problema**: Sumaba odómetros acumulativos en lugar de calcular deltas
**Archivo**: `api_v2.py`
**Fix**: Cambié queries a usar `MAX(odometer_mi) - MIN(odometer_mi)` per truck

**Antes**:
```sql
SUM(CASE WHEN odometer_mi > 0 THEN odometer_mi ELSE 0 END) as total_miles
-- Resultado: 4950 + 4580 + 5495 = 15,025 millas (INCORRECTO)
```

**Después**:
```sql
SELECT truck_id,
       MAX(odometer_mi) - MIN(odometer_mi) as miles_traveled
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY truck_id
-- Resultado: Miles realmente recorridas por cada camión
```

---

## 🔧 FIXES PENDIENTES (implementar a continuación)

### 2. Loss Analysis - Millas Irreales (199M)
**Problema**: Camión RT9127 muestra 199,727,756 millas
**Causa**: Speed_mph sin sanitizar puede tener valores absurdos que se acumulan

**Fix Required in** `database_mysql.py línea ~1235`:
```sql
-- AGREGAR VALIDACIÓN DE SPEED
SUM(CASE 
    WHEN truck_status = 'MOVING' 
    AND speed_mph > 5 AND speed_mph < 100  -- 🆕 AGREGAR LÍMITE SUPERIOR
    THEN speed_mph * (15.0/3600.0)
    ELSE 0 
END) as calculated_miles
```

**También agregar en Python** (línea ~1323):
```python
calculated_miles = float(row[9] or 0)
# 🆕 SANITY CHECK
if calculated_miles > 10000:  # Imposible en 30 días
    logger.warning(f"[{truck_id}] Calculated miles absurdas: {calculated_miles}, usando 0")
    calculated_miles = 0
```

### 3. Predictive Maintenance - Confidence >100%
**Problema**: Muestra 7500%, 9200%, etc.

**Investigación necesaria**: Buscar dónde se multiplica confidence * 100

**Posibles ubicaciones**:
1. `predictive_maintenance_engine.py` - confidence es string "HIGH", "MEDIUM", "LOW"
2. Router o endpoint que convierte a porcentaje
3. Frontend que muestra mal el valor

**Fix temporal**: Agregar límite en cualquier cálculo:
```python
confidence_pct = min(100, max(0, confidence_value))
```

### 4. SPN Unknown - Códigos No Identificados
**Problema**: Emails frecuentes de "SPN Unknown"

**Investigación**:
1. Verificar tabla `j1939_spn_codes` existe y tiene datos
2. Verificar formato de búsqueda (int vs string)
3. Ver si DB reset borró la tabla

**Query para verificar**:
```sql
SELECT COUNT(*) FROM j1939_spn_codes;
SELECT * FROM j1939_spn_codes LIMIT 10;
```

**Fix**: Si tabla vacía, re-importar SPNs desde archivo JSON

---

## 🎯 MPG LOGIC - REDISEÑO COMPLETO

### Análisis de Sensores Disponibles

**Sensores Fuel Consumption**:
1. ✅ `total_fuel_used` (gallons) - ECU acumulativo **[MEJOR OPCIÓN]**
2. ✅ `fuel_lvl` (%) - Sensor de nivel tanque
3. ✅ `fuel_rate` (L/h) → `consumption_gph` (gal/h)
4. ✅ `fuel_economy` (MPG) - ECU directo **[VALIDACIÓN CRUZADA]**

**Sensores Distancia**:
1. ⚠️ `odometer` (mi) - Solo 15% coverage
2. ✅ `speed` (mph) + tiempo - 100% coverage

### Problema Actual del MPG

**Código actual** (`wialon_sync_enhanced.py línea 1758`):
```python
# Prioridad INCORRECTA: Sensor level primero
if mpg_state.last_fuel_lvl_pct is not None and sensor_pct is not None:
    fuel_drop_pct = mpg_state.last_fuel_lvl_pct - sensor_pct
    if fuel_drop_pct > 0:
        delta_gallons = (fuel_drop_pct / 100) * tank_capacity_gal
```

**Problemas**:
1. Sensor level tiene ±2-5% error (olas, inclinación)
2. En tanque 250 gal: 1% error = 2.5 galones = 25% error en MPG
3. No usa `total_fuel_used` que es más preciso

### Nueva Jerarquía Propuesta

```python
# JERARQUÍA DE FUEL CONSUMPTION (mejor → peor)
# 1. ECU Total Fuel Used (acumulativo) - ±1% error
if prev_total_fuel and current_total_fuel:
    delta_gallons = current_total_fuel - prev_total_fuel
    fuel_source = "ECU_COUNTER"
    
# 2. Fuel Economy ECU directo - usar como validación
elif fuel_economy_ecu and 3.5 < fuel_economy_ecu < 8.5:
    # No calcular, usar directo
    mpg_current = fuel_economy_ecu
    fuel_source = "ECU_DIRECT"
    
# 3. Sensor Level (solo si estable y no hay ECU)
elif sensor_stable and no_refuel:
    fuel_drop_pct = last_pct - current_pct
    delta_gallons = (fuel_drop_pct / 100) * capacity
    fuel_source = "SENSOR"
    
# 4. Fuel Rate × Time (último recurso)
else:
    delta_gallons = consumption_gph * dt_hours
    fuel_source = "RATE_FALLBACK"
```

### Validaciones Propuestas

```python
# 1. VALIDAR DISTANCIA
if speed_mph < 5 or speed_mph > 85:
    continue  # Skip, no es válido

if hdop > 2.0 or sats < 6:
    continue  # GPS de mala calidad

# 2. VALIDAR COMBUSTIBLE
if delta_gallons < 0.01 or delta_gallons > 50:
    continue  # Error o refuel

# 3. VALIDAR MPG CALCULADO
calculated_mpg = delta_miles / delta_gallons

# Para 44,000 lbs trucks:
MIN_MPG = 3.5  # Reefer loaded uphill
MAX_MPG = 8.5  # Empty flatbed downhill

if not (MIN_MPG <= calculated_mpg <= MAX_MPG):
    # Validación cruzada con ECU
    if fuel_economy_ecu:
        if abs(calculated_mpg - fuel_economy_ecu) < 1.5:
            # ECU confirma, usar calculado
            pass
        else:
            # ECU difiere mucho, usar ECU
            calculated_mpg = fuel_economy_ecu
    else:
        # Sin ECU, descartar
        continue

# 4. CROSS-VALIDATION
if fuel_economy_ecu:
    diff = abs(calculated_mpg - fuel_economy_ecu)
    if diff > 2.0:
        logger.warning(f"MPG mismatch: calc={calculated_mpg:.2f}, ecu={fuel_economy_ecu:.2f}")
```

### Configuración para 44k lbs Trucks

```python
@dataclass
class MPGConfig:
    # Distancia mínima para cálculo preciso
    min_miles: float = 10.0  # Más conservador
    min_fuel_gal: float = 2.0  # Más combustible = menos error %
    
    # Rangos físicos para 44,000 lbs trucks
    min_mpg: float = 3.5  # Reefer loaded mountain
    max_mpg: float = 8.5  # Empty downhill highway (NO 12.0)
    
    # Thresholds GPS quality
    max_hdop: float = 2.0
    min_satellites: int = 6
    max_speed_mph: float = 85.0
    
    # ECU validation
    use_ecu_mpg_when_available: bool = True
    max_ecu_calc_diff: float = 2.0  # Si difieren >2 MPG, usar ECU
```

---

## 📝 PLAN DE IMPLEMENTACIÓN

### Fase 1: Fixes Críticos (1-2 horas)
1. ✅ Cost per mile queries - HECHO
2. ⏳ Loss analysis millas validation
3. ⏳ Predictive maintenance confidence limit
4. ⏳ SPN codes investigation

### Fase 2: MPG Rediseño (3-4 horas)
1. ⏳ Investigar cobertura `total_fuel_used` sensor
2. ⏳ Implementar nueva jerarquía fuel consumption
3. ⏳ Agregar validación cruzada con `fuel_economy` ECU
4. ⏳ Ajustar max_mpg de 12.0 → 8.5
5. ⏳ Agregar filtros GPS quality (HDOP, sats)

### Fase 3: Testing (1-2 horas)
1. ⏳ Hacer commit y push
2. ⏳ Pull en VM y restart services
3. ⏳ Monitorear 1-2 horas de datos
4. ⏳ Verificar MPG queda en 4.0-8.0 rango
5. ⏳ Verificar cost/mile consistente
6. ⏳ Verificar loss analysis valores reales

---

**SIGUIENTE ACCIÓN**: Aplicar fixes 2, 3, 4 y comenzar rediseño MPG
