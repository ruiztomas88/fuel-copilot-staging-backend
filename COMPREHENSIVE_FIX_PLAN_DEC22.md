# 🔧 COMPREHENSIVE FIX PLAN - December 22, 2025

## 🚨 CRITICAL ISSUES IDENTIFIED

### 1. **ODOMETER CORRUPTION**

```sql
OM7769: 200,164,000 miles (impossible - should be ~2M max)
RT9127: 200,159,000 miles
MJ9547: 200,159,000 miles
```

**Root Cause**: Odometer values being multiplied or not validated
**Impact**: Miles driven calculations are completely wrong

### 2. **DATABASE NOT RESET**

- Data desde 2025-12-19 (3 días atrás)
- 26,175 registros acumulados
- Usuario piensa que limpiamos la DB pero NO lo hicimos
  **Impact**: Métricas de "Total Miles" y "Total Fuel" son irreales

### 3. **COST_PER_MILE ISSUES**

- Frontend muestra $0.00 arriba pero $0.82 abajo
- $0.82 es demasiado bajo vs benchmark $2.26
- Fórmula: `cost_per_mile = $3.50 / mpg`
- Si MPG=4.27 → cost=$0.82 ✅ (correcto matemáticamente)
- Si MPG=9-11 → cost=$0.32-$0.39 ❌ (MPG inflados)
  **Impact**: Cost analysis no tiene sentido

### 4. **MPG CALCULATION FLAWS**

#### Sensores Disponibles:

```sql
✅ fuel_level_pct (sensor de tanque)
✅ total_fuel_used_gal (ECU cumulative)
✅ fuel_rate_gph (consumo instantáneo CAN)
✅ odometer_mi
✅ speed_mph
✅ rpm
⚠️ fuel_pressure_psi (no se usa para MPG)
```

#### Problemas Detectados:

**A. DEPENDENCIA DE `consumption_gph` (fuel_rate_gph)**

```python
# Línea 1763-1770 wialon_sync_enhanced.py
elif consumption_gph and dt_hours > 0:
    if 0.5 <= consumption_gph <= 20:
        delta_gallons = consumption_gph * dt_hours
```

**Problema**: `fuel_rate_gph` es **instantáneo** y **ruidoso**

- Multiplicar por tiempo introduce error acumulativo
- No refleja consumo REAL del tanque
- Puede reportar 0 gph cuando está acelerando (lag de ECU)

**B. SENSOR DE FUEL LEVEL ES MEJOR**

```python
# Línea 1760-1765 - ESTE ES EL MÉTODO CORRECTO
fuel_drop_pct = last_fuel_lvl_pct - current_fuel_pct
delta_gallons = (fuel_drop_pct / 100) * tank_capacity_gal
```

**Por qué es mejor:**

- Mide cambio REAL en el tanque
- No tiene lag ni ruido de CAN
- Es físicamente correcto

**C. VALIDACIONES INSUFICIENTES**

```python
# mpg_engine.py configuración actual
min_mpg = 2.5
max_mpg = 8.5  # ✅ Realista para 44k lbs
min_miles = 8.0
min_fuel_gal = 2.0
```

**Problema**: Acepta MPG muy bajos (2.5) que indican errores de cálculo

#### Configuración Realista para Heavy Trucks (44,000 lbs):

```
Loaded (44k lbs):  4.0 - 6.5 MPG
Empty (10k lbs):   6.5 - 8.0 MPG
Average:           5.0 - 7.0 MPG
Flatbed:           5.5 - 7.5 MPG
Reefer (running):  4.0 - 5.5 MPG
Dry Van:           5.0 - 6.5 MPG
```

### 5. **LOSS ANALYSIS ERRORS**

- Millas irreales: 199,727,756 miles
- Probablemente por odometer corruption propagado

### 6. **CONFIDENCE SCORES ABSURDOS**

- 7500%, 9200% en Predictive Maintenance
- Debería ser 0-100%
  **Root Cause**: Multiplicación por 100 dos veces

### 7. **DTC/SPN UNKNOWN**

- Tenemos 3000+ SPNs en la DB
- Siguen apareciendo "SPN Unknown"
  **Root Cause**: Lookup table no se está consultando o falta cache

---

## 🛠️ COMPREHENSIVE FIX STRATEGY

### PHASE 1: DATABASE CLEANUP (IMMEDIATE)

#### 1.1 Fix Odometer Corruption

```sql
-- Identificar odometers corruptos (>10M miles = imposible)
SELECT truck_id, MAX(odometer_mi) as max_odom
FROM fuel_metrics
WHERE odometer_mi > 10000000
GROUP BY truck_id;

-- Opción A: Dividir por 100 (si es factor constante)
UPDATE fuel_metrics
SET odometer_mi = odometer_mi / 100
WHERE odometer_mi > 10000000;

-- Opción B: Invalidar y usar speed×time
UPDATE fuel_metrics
SET odometer_mi = NULL
WHERE odometer_mi > 10000000;
```

#### 1.2 Reset Database (Clean Start)

```sql
-- TRUNCATE todas las tablas de métricas
TRUNCATE TABLE fuel_metrics;
TRUNCATE TABLE daily_truck_metrics;
TRUNCATE TABLE refuel_events;
-- truck_sensors_cache se puede mantener (es snapshot actual)
```

### PHASE 2: MPG CALCULATION REDESIGN

#### 2.1 Hierarchía de Fuentes para Delta Fuel

```python
# PRIORITY 1: Sensor de nivel (más confiable)
if last_fuel_lvl_pct and current_fuel_pct:
    drop = last_fuel_lvl_pct - current_fuel_pct
    if drop > 0.1:  # Al menos 0.1% cambio
        delta_gal = (drop / 100) * tank_capacity
        source = "FUEL_SENSOR"

# PRIORITY 2: ECU total_fuel_used (cumulative)
elif last_total_fuel and current_total_fuel:
    delta_gal = current_total_fuel - last_total_fuel
    if 0 < delta_gal < 20:  # Sanity check
        source = "ECU_CUMULATIVE"

# PRIORITY 3: fuel_rate_gph (último recurso)
elif fuel_rate_gph and 0.5 < fuel_rate_gph < 20:
    delta_gal = fuel_rate_gph * dt_hours
    source = "FUEL_RATE_INSTANT"
else:
    # NO DATA - skip MPG calculation
    delta_gal = 0
```

#### 2.2 Validaciones Estrictas

```python
# Configuración conservadora
MPG_CONFIG = {
    "min_mpg": 3.5,  # Mínimo físico (muy cargado, subiendo montaña)
    "max_mpg": 8.5,  # Máximo físico (vacío, highway, viento a favor)
    "min_miles": 5.0,  # Al menos 5 millas para calcular
    "min_fuel_gal": 1.0,  # Al menos 1 galón consumido
    "max_delta_miles": 100,  # Por ventana (evitar resets)
    "max_delta_fuel": 25,  # Galones por ventana
}

# Validar deltas antes de calcular
if delta_miles > MPG_CONFIG["max_delta_miles"]:
    logger.warning(f"Delta miles too large: {delta_miles}")
    return  # Skip

if delta_fuel > MPG_CONFIG["max_delta_fuel"]:
    logger.warning(f"Delta fuel too large: {delta_fuel}")
    return  # Skip
```

#### 2.3 Detección de Load State

```python
# Usar RPM y engine_load para estimar si va cargado
def estimate_load_state(rpm, engine_load_pct, speed_mph):
    """
    Empty: Low RPM (1200-1500), Low Load (<40%), High speed possible
    Loaded: High RPM (1600-2000), High Load (>60%), Lower speed
    """
    if engine_load_pct and engine_load_pct > 70:
        return "HEAVY_LOAD"  # Expect 4-5.5 MPG
    elif engine_load_pct and engine_load_pct < 40:
        return "LIGHT_LOAD"  # Expect 6-8 MPG
    else:
        return "MEDIUM_LOAD"  # Expect 5-6.5 MPG
```

### PHASE 3: FRONTEND FIXES

#### 3.1 Cost Per Mile

```javascript
// Usar la misma fuente en ambos lugares
const costPerMile = truck.cost_per_mile || 0;
// No recalcular, usar el valor de la DB
```

#### 3.2 Confidence Scores

```python
# api_v2.py - NO multiplicar por 100 si ya es porcentaje
confidence = model_confidence  # Ya está en 0-100
# NO: confidence = model_confidence * 100
```

### PHASE 4: DTC/SPN LOOKUP

#### 4.1 Verificar Tabla SPN

```sql
SELECT COUNT(*) FROM spn_codes;
SELECT * FROM spn_codes WHERE spn = 100 LIMIT 1;
```

#### 4.2 Implementar Cache en Memoria

```python
# Cargar SPNs al inicio
SPN_CACHE = {}

def load_spn_cache():
    cursor.execute("SELECT spn, description, severity FROM spn_codes")
    for row in cursor:
        SPN_CACHE[row['spn']] = {
            'description': row['description'],
            'severity': row['severity']
        }

def lookup_spn(spn_code):
    return SPN_CACHE.get(spn_code, {
        'description': 'Unknown SPN',
        'severity': 'UNKNOWN'
    })
```

---

## 📋 IMPLEMENTATION CHECKLIST

### CRITICAL (Do Now)

- [ ] Fix odometer corruption in fuel_metrics
- [ ] Truncate tables for clean start
- [ ] Update MPG fuel source priority (sensor > ECU > rate)
- [ ] Add strict delta validations
- [ ] Fix cost_per_mile display consistency

### HIGH PRIORITY (Next 2 hours)

- [ ] Implement load state detection
- [ ] Update MPG thresholds per load state
- [ ] Fix confidence score calculation
- [ ] Load SPN cache at startup
- [ ] Test with 3-5 trucks for 1 hour

### MEDIUM PRIORITY (Next 24 hours)

- [ ] Create migration script for historical data
- [ ] Add monitoring dashboard for MPG sources
- [ ] Document sensor priority logic
- [ ] Create truck type classifier (flatbed/reefer/dry van)

### LOW PRIORITY (Next week)

- [ ] Machine learning for load state prediction
- [ ] Weather API integration for MPG adjustment
- [ ] Route grade analysis from GPS altitude

---

## 🧪 VALIDATION TESTS

```python
# Test 1: Odometer sanity
assert all(odom < 10_000_000 for odom in odometers)

# Test 2: MPG range
assert 3.5 <= mpg <= 8.5 for all trucks

# Test 3: Cost per mile
assert 0.40 <= cost_per_mile <= 1.00  # For MPG 3.5-8.5 @ $3.50/gal

# Test 4: Confidence scores
assert 0 <= confidence <= 100

# Test 5: SPN lookup
assert lookup_spn(100) != "Unknown SPN"
```

---

## 📊 EXPECTED RESULTS AFTER FIX

| Metric       | Before        | After         |
| ------------ | ------------- | ------------- |
| MPG Range    | 2.5 - 15.0    | 4.0 - 8.0     |
| Cost/Mile    | $0.23 - $1.40 | $0.44 - $0.88 |
| Odometer     | 200M miles    | <2M miles     |
| Confidence   | 7500%         | 75%           |
| Unknown SPNs | 50%           | <5%           |
| Data Age     | 3 days        | Fresh         |

---

## 🔍 ROOT CAUSE ANALYSIS

### Why MPG was inflated (9-11 MPG)?

1. **fuel_rate_gph underestimates** consumption during acceleration
2. **Sensor lag**: CAN reports 0 gph when actually consuming
3. **No load adjustment**: Empty truck gets same threshold as loaded

### Why cost_per_mile seems low?

- **Math is correct**: $3.50 / 4.27 MPG = $0.82
- **Problem is elsewhere**: MPG of 4.27 may still be inflated
- **Real issue**: Some trucks show $0.00 (no data)

### Why odometer corruption?

- **No input validation**: Values >10M accepted
- **Possible multiplier**: Data source sends cm or mm instead of miles
- **No bounds checking**: Should reject odom > realistic_max

---

## 💡 RECOMMENDATIONS

1. **Use `total_fuel_used_gal` (ECU cumulative) as PRIMARY source**

   - More reliable than instantaneous rate
   - Already implemented in truck ECU
   - Just needs delta calculation

2. **Implement truck profiling**

   - Learn each truck's normal MPG range
   - Flag anomalies >20% deviation
   - Adjust thresholds per truck type

3. **Add data quality metrics**

   - % of MPG from sensor vs CAN
   - % of records with valid odometer
   - Fuel source distribution

4. **Create admin dashboard**
   - Real-time MPG calculation monitoring
   - Fuel source breakdown
   - Outlier detection alerts
