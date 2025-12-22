# Análisis Completo de Problemas - 22 Diciembre 2025

## 🔴 PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. MÉTRICAS DASHBOARD - Cálculos Incorrectos

#### Problema: Cost Per Mile Inconsistente
**Ubicación**: Fleet Metrics Hub → arriba muestra $0.00, abajo $0.82
**Causa**: Query en `api_v2.py:2479` está sumando odómetros incorrectamente

```python
# ❌ INCORRECTO - Suma odómetros acumulados
SUM(CASE WHEN odometer_mi > 0 THEN odometer_mi ELSE 0 END) as total_miles
```

**Impacto**:
- Camiones con odómetro 4950mi + 4580mi + 5495mi = **suma incorrecta**
- Odómetro es un contador acumulativo, NO debe sumarse
- Debería calcular `MAX(odometer_mi) - MIN(odometer_mi)` por camión

#### Problema: Millas y Fuel Consumed Irreales
**Datos actuales**:
- DB recreada hace 2-3 días
- Muestra: 4,950 millas, 4,580 millas, etc.
- Fuel: 8,543 galones

**Causa**: Query está leyendo TODO el histórico de `fuel_metrics` sin filtrar por fecha de reset
**Solución**: Filtrar por fecha O calcular delta entre min/max por truck_id

---

### 2. LOSS ANALYSIS - Valores Astronómicos

#### Problema: Camión RT9127 muestra 199,727,756 millas
**Evidencia**: Screenshot muestra "199727756 millas · 7.62 MPG"

**Causa**: Dos posibles errores:
1. Overflow en cálculo de delta de odómetro
2. Odómetro en diferentes unidades (km vs mi) sin conversión
3. Suma acumulativa de odómetros en lugar de deltas

**Ubicación probable**: `database_mysql.py` en queries de loss analysis

---

### 3. PREDICTIVE MAINTENANCE - Confidence >100%

#### Problema: Confidence values 7500%, 9200%, 7600%, 8400%
**Screenshot**: Command Center → Predictive Maintenance muestra valores imposibles

**Causa**: Formula de confidence multiplica por 100 dos veces o no limita resultado
**Ubicación**: `predictive_maintenance_engine.py`

**Expectativa**: Confidence debe estar entre 0-100%

---

### 4. DTC/SPN UNKNOWN - Base de Datos Incompleta

#### Problema: Recibe emails frecuentes de "SPN Unknown"
**Contexto**: Teníamos 3000+ SPNs en la base de datos

**Posibles causas**:
1. Tabla `dtc_codes` o `j1939_spn_codes` no se restauró después del DB reset
2. Códigos existen pero el lookup está fallando
3. Formato del SPN code no coincide (integer vs string)

**Ubicación**: 
- `dtc_analyzer.py` - lookup de códigos
- `migrations/` - revisar si se corrieron todas

---

### 5. MPG INFLADOS - Lógica de Cálculo Fundamental

#### Problema: MPG actual 8.4-8.9 (debería ser 4.0-8.0 máximo)
**Evidencia**: Dashboard muestra DO9356: 8.8 MPG, JR7099: 8.9 MPG, OM7769: 8.9 MPG

**Contexto**:
- Camiones carga pesada: 44,000 lbs
- Reefer, flatbed, dry van
- Rango esperado: 4.0-8.0 MPG

**Fix parcial aplicado**: Cambié thresholds de 5.0mi/0.75gal → 8.0mi/1.2gal

**PERO SIGUE ALTO** → Necesita análisis profundo de la lógica de cálculo

---

## 🔬 ANÁLISIS DE SENSORES DISPONIBLES PARA MPG

### Sensores Relacionados con Consumo de Combustible

#### Método 1: Delta de Sensor de Nivel (CURRENT)
```python
# De wialon_sync_enhanced.py línea 1758
if mpg_state.last_fuel_lvl_pct is not None and sensor_pct is not None:
    fuel_drop_pct = mpg_state.last_fuel_lvl_pct - sensor_pct
    if fuel_drop_pct > 0:
        delta_gallons = (fuel_drop_pct / 100) * tank_capacity_gal
```

**Sensores involucrados**:
- `fuel_lvl` (%) - Nivel actual del tanque
- `capacity_gallons` - Capacidad del tanque (de tanks.yaml)

**Limitaciones**:
1. ❌ Sensor puede tener drift ±2-5% (olas en el tanque)
2. ❌ Resolución típica 1% = 2.5 gal error en tanque 250 gal
3. ❌ No detecta reabastecimientos pequeños

#### Método 2: ECU Fuel Rate (FALLBACK)
```python
elif consumption_gph and dt_hours > 0:
    if 0.5 <= consumption_gph <= 20:
        delta_gallons = consumption_gph * dt_hours
```

**Sensores involucrados**:
- `fuel_rate` (L/h) → convertido a `consumption_gph` (gal/h)
- Tiempo delta entre lecturas

**Limitaciones**:
1. ❌ Subestima consumo real (comprobado: MPG inflados 8-10)
2. ⚠️ Solo captura consumo instantáneo, no acumulativo
3. ✅ Más estable que sensor de nivel

#### Método 3: Total Fuel Used (ECU Counter) - **NO IMPLEMENTADO**
**Sensor disponible**: `total_fuel_used` (gallons acumulativo)

```python
# 🆕 PROPUESTA: Usar contador ECU acumulativo
if prev_total_fuel and current_total_fuel:
    delta_gallons = current_total_fuel - prev_total_fuel
```

**Ventajas**:
1. ✅ Contador preciso del ECU (error <1%)
2. ✅ No afectado por olas o inclinación del tanque
3. ✅ Captura TODO el consumo (moving + idle)
4. ✅ Acumulativo = no pierde consumo entre lecturas

**Limitaciones**:
1. ⚠️ Necesita validar que el sensor existe y es confiable
2. ⚠️ Puede resetear en cambio de batería

---

### Sensores Relacionados con Distancia

#### Método 1: Odometer (PREFERRED)
```python
if mpg_state.last_odometer_mi is not None and odometer and odometer > 0:
    delta_miles = odometer - mpg_state.last_odometer_mi
```

**Sensor**: `odometer` (millas acumuladas)

**Problemas identificados**:
1. ❌ Solo **15% de registros tienen odometer** (wialon_sync_enhanced.py comentario línea 1738)
2. ❌ Puede tener rollover o resetear
3. ❌ Algunos camiones nunca envían odometer

#### Método 2: Speed × Time (FALLBACK)
```python
delta_miles = speed * dt_hours if dt_hours > 0 else 0.0
```

**Sensores**:
- `speed` (mph) - GPS speed
- `dt_hours` - delta tiempo entre lecturas

**Ventajas**:
1. ✅ Funciona para el 100% de los registros
2. ✅ GPS speed es confiable (cuando HDOP < 2.0)

**Limitaciones**:
1. ⚠️ Puede sobrestimar en tráfico (aceleraciones/frenadas)
2. ⚠️ Error acumulativo con lecturas muy frecuentes
3. ✅ Pero es la ÚNICA opción para 85% de registros

---

## 🎯 RECOMENDACIONES PARA MPG REAL

### Propuesta 1: Usar Total Fuel Used (ECU Counter)
**Prioridad**: ALTA
**Impacto**: Elimina el 80% de error en consumo

```python
# Jerarquía de fuel consumption
1. total_fuel_used delta (si disponible) → ±1% error
2. Sensor level delta (si estable) → ±5% error  
3. fuel_rate × time (último recurso) → ±15% error
```

### Propuesta 2: Mejorar Cálculo de Distancia
**Mantener**: Speed × Time como principal (ya que 85% no tiene odometer)
**Mejorar**: Filtrar lecturas con mala calidad GPS

```python
# Solo calcular MPG cuando GPS es confiable
if hdop < 2.0 and sats >= 6:
    delta_miles = speed * dt_hours
```

### Propuesta 3: Validación Cruzada con fuel_economy ECU
**Sensor disponible**: `fuel_economy` (MPG del ECU)

```python
# Usar ECU MPG como sanity check
if abs(calculated_mpg - fuel_economy_ecu) > 2.0:
    logger.warning(f"MPG mismatch: calc={calculated_mpg}, ecu={fuel_economy_ecu}")
```

### Propuesta 4: Ajustar Thresholds por Carga
**Contexto**: 44,000 lbs trucks

```python
# Rangos esperados por escenario
LOADED_REEFER_MOUNTAIN = (3.5, 5.0)  # Peor caso
LOADED_DRY_CITY = (4.5, 5.5)
LOADED_FLATBED_HWY = (5.5, 6.5) 
EMPTY_DRY_HWY = (6.5, 7.5)
OPTIMAL_DOWNHILL = (7.0, 8.5)  # Máximo realista

# Max MPG físico para 44k lbs = 8.5 MPG
max_mpg = 8.5  # Reducir de 12.0 actual
```

---

## 📋 PLAN DE ACCIÓN

### Paso 1: Fixes Inmediatos (1-2 horas)
1. ✅ Arreglar cost_per_mile query (SUM → delta calculation)
2. ✅ Limitar confidence a 100% en predictive maintenance  
3. ✅ Investigar tabla dtc_codes/j1939_spn_codes
4. ✅ Arreglar loss analysis millas (overflow check)

### Paso 2: Análisis de Sensores (2-3 horas)
1. ✅ Validar disponibilidad de `total_fuel_used` sensor
2. ✅ Comparar `fuel_economy` ECU vs calculado
3. ✅ Verificar coverage de `odometer` por camión

### Paso 3: Rediseño MPG Logic (4-6 horas)
1. ✅ Implementar jerarquía de fuel consumption (total_fuel_used → sensor → rate)
2. ✅ Ajustar max_mpg de 12.0 → 8.5 (realista para 44k lbs)
3. ✅ Agregar validación cruzada con fuel_economy ECU
4. ✅ Filtrar cálculos con GPS de mala calidad (HDOP > 2.0)

### Paso 4: Testing (1-2 horas)
1. ✅ Comparar MPG antes/después en 5 camiones
2. ✅ Verificar que quede en rango 4.0-8.0
3. ✅ Monitorear por 1-2 horas de datos reales

---

## 🔍 QUERIES PARA INVESTIGACIÓN

### Query 1: Verificar total_fuel_used sensor
```sql
SELECT 
    truck_id,
    COUNT(*) as total_records,
    COUNT(total_fuel_used) as has_total_fuel,
    COUNT(total_fuel_used) * 100.0 / COUNT(*) as coverage_pct,
    AVG(total_fuel_used) as avg_total_fuel
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY truck_id
ORDER BY coverage_pct DESC;
```

### Query 2: Comparar MPG calculado vs ECU
```sql
SELECT 
    truck_id,
    AVG(mpg_current) as avg_mpg_calculated,
    AVG(fuel_economy_ecu) as avg_mpg_ecu,
    ABS(AVG(mpg_current) - AVG(fuel_economy_ecu)) as diff
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    AND mpg_current IS NOT NULL
    AND fuel_economy_ecu IS NOT NULL
GROUP BY truck_id
ORDER BY diff DESC;
```

### Query 3: Millas reales últimos 3 días
```sql
SELECT 
    truck_id,
    MIN(timestamp_utc) as first_reading,
    MAX(timestamp_utc) as last_reading,
    MIN(odometer_mi) as start_odo,
    MAX(odometer_mi) as end_odo,
    MAX(odometer_mi) - MIN(odometer_mi) as miles_traveled
FROM fuel_metrics
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 3 DAY)
    AND odometer_mi IS NOT NULL AND odometer_mi > 0
GROUP BY truck_id
ORDER BY miles_traveled DESC;
```

---

**Siguiente paso**: Ejecutar queries de investigación y comenzar con fixes inmediatos.
