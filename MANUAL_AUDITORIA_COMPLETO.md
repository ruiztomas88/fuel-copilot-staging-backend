# 📋 Manual de Auditoría Completo - Fuel Analytics System
**Versión:** 1.0  
**Fecha:** 22 Diciembre 2025  
**Proyecto:** Fleet Fuel Analytics Backend + Frontend

---

## 🎯 Objetivo de la Auditoría

Este manual guía una revisión exhaustiva del sistema de analíticas de combustible para identificar y corregir:
- Algoritmos con lógica incorrecta o inflación de valores
- Bugs en cálculos de métricas críticas
- Problemas de rendimiento y estabilidad
- Inconsistencias entre frontend y backend
- Issues de UX y visualización de datos

---

## 📊 Áreas Críticas a Auditar

### 1. 🚗 MPG (Miles Per Gallon) - MÁXIMA PRIORIDAD

#### 1.1 Backend - Algoritmo de Cálculo
**Archivo:** `mpg_engine.py` (líneas 236-500)

**Problemas Conocidos:**
- ✅ **RESUELTO:** Inflación de valores (10.3 MPG, 8.9 MPG) por EMA smoothing reteniendo estados viejos
- ✅ **RESUELTO:** Thresholds muy altos (8mi/1.5gal) causaban lag en actualización
- ✅ **RESUELTO:** Max MPG sin cap permitía valores físicamente imposibles

**Checklist de Auditoría:**
```python
# 1. Verificar configuración actual en MPGConfig
# Ubicación: mpg_engine.py líneas 236-239
- [ ] min_miles debe ser 5.0 (NO 8.0)
- [ ] min_fuel_gal debe ser 0.75 (NO 1.5)
- [ ] max_mpg debe ser 8.2 (NO >9.0 para Class 8 trucks 44k lbs)
- [ ] min_mpg debe ser 3.8 (límite inferior realista)
- [ ] ema_alpha debe ser 0.4 (balance suavizado/respuesta)
- [ ] fallback_mpg debe ser 5.7 (promedio flota)

# 2. Verificar método de cálculo primario
# Ubicación: mpg_engine.py calculate_mpg()
- [ ] Usar SIEMPRE delta odómetro / delta ECU fuel (NO fuel_rate)
- [ ] Formula: mpg = (odom_end - odom_start) / (fuel_ecu_end - fuel_ecu_start)
- [ ] Validar que delta_miles > min_miles ANTES de calcular
- [ ] Validar que delta_fuel > min_fuel_gal ANTES de calcular
- [ ] Aplicar cap: min(calculated_mpg, max_mpg) en return

# 3. Verificar métodos fallback (en orden de prioridad)
- [ ] 1º: ECU total_fuel_used (76% cobertura flota) ⭐
- [ ] 2º: fuel_rate integration (87% cobertura)
- [ ] 3º: fuel_lvl delta con refuel detection (76% cobertura, menos preciso)

# 4. Verificar persistencia de estado
# Ubicación: data/mpg_states.json
- [ ] Archivo debe recrearse desde 0 si valores >8.2
- [ ] NO debe retener estados >7 días
- [ ] Debe incluir timestamp de última actualización
```

**Archivo:** `wialon_sync_enhanced.py` (líneas 1940-1950)

```python
# 5. Verificar output capping en wialon_sync
# Ubicación: líneas 1946-1948
- [ ] mpg_current debe tener: min(value, 8.2)
- [ ] mpg_baseline debe tener cap similar
- [ ] Log warning si mpg calculado >8.2 antes de cap

# 6. Verificar sensor mapping
# Ubicación: líneas 1495, wialon_reader.py línea 68
- [ ] odometer debe mapear a "odom" (NO "odometer_mi")
- [ ] total_fuel_used debe ser ECU cumulative counter
- [ ] fuel_rate debe ser instantáneo en L/h
```

**Tests a Ejecutar:**
```bash
# Test 1: Verificar MPG realista para RH1522
python quick_mpg_sensor_check.py RH1522
# Esperado: 6.0-6.5 MPG (basado en 129.56mi / 20.74gal histórico)

# Test 2: Verificar que no hay inflación
SELECT truck_id, mpg_current FROM truck_sensors_cache WHERE mpg_current > 8.2;
# Esperado: 0 rows

# Test 3: Verificar actualización rápida (5 millas)
# Manejar camión 5 millas, esperar <2 min para ver cambio en dashboard
```

#### 1.2 Frontend - Visualización MPG

**Problemas Conocidos:**
- Muestra valores fallback (5.7) cuando backend no tiene suficientes datos
- No indica visualmente si MPG es calculado vs. fallback

**Checklist de Auditoría:**
```
Dashboard: Vista de Flota
- [ ] Verificar que MPG mostrado coincide con API /fleet/summary
- [ ] Rango esperado: 4.0 - 8.0 MPG para Class 8 trucks
- [ ] Color coding: Verde (6-8), Amarillo (4-6), Rojo (<4 o >8)
- [ ] Tooltip debe mostrar: "Calculado" vs "Fallback" vs "Insuficientes datos"

Dashboard: Vista Individual Camión
- [ ] Gráfico de tendencia MPG últimas 24h
- [ ] Debe mostrar timestamp de última actualización
- [ ] Debe indicar método de cálculo (ECU/fuel_rate/fuel_lvl)
- [ ] Rango Y-axis fijo 0-10 MPG (NO auto-scale que exagera)
```

---

### 2. ⏱️ Idle Time & Fuel - ALTA PRIORIDAD

#### 2.1 Backend - Detección de Idle
**Archivo:** `idle_engine.py`

**Problemas Conocidos:**
- Configuración de thresholds puede ser muy sensible
- No distingue idle productivo (waiting to load) vs. idle improductivo

**Checklist de Auditoría:**
```python
# Ubicación: idle_engine.py IdleConfig
- [ ] idle_speed_threshold: 0.5 mph (ajustar según vibración GPS)
- [ ] idle_min_duration: 5 minutos (NO <3 min para evitar falsos positivos)
- [ ] idle_rpm_threshold: 600-800 RPM (depende de motor)
- [ ] idle_fuel_rate_min: 1.5 gal/h (consumo mínimo para considerar idle)

# Cálculo de consumo idle
- [ ] Usar fuel_rate sensor en L/h convertido a gal/h
- [ ] NO usar delta fuel_lvl (muy impreciso para idle)
- [ ] Acumular: idle_fuel += (fuel_rate_gph * (duration_sec / 3600))
- [ ] Validar que idle_fuel < 50 gal/día por camión (físicamente imposible >50)
```

**Tests a Ejecutar:**
```sql
-- Test 1: Verificar idle fuel realista
SELECT truck_id, 
       SUM(idle_fuel_gal) as total_idle_fuel,
       SUM(idle_duration_min) as total_idle_min,
       (SUM(idle_fuel_gal) / (SUM(idle_duration_min)/60)) as avg_idle_gph
FROM daily_truck_metrics 
WHERE date >= CURDATE() - INTERVAL 7 DAY
GROUP BY truck_id
HAVING total_idle_fuel > 50; -- Identificar anomalías
-- Esperado: 0-5 rows, investigar si >50 gal/día

-- Test 2: Verificar proporción idle time
SELECT AVG(idle_duration_min / (24*60)) as pct_idle FROM daily_truck_metrics;
-- Esperado: 10-25% (0.10-0.25)
```

#### 2.2 Frontend - Visualización Idle

**Checklist:**
```
Dashboard: Idle Analysis
- [ ] Mostrar top 10 camiones con mayor idle time
- [ ] Gráfico: Idle time vs. Mileage (correlación)
- [ ] Costo estimado: idle_fuel_gal * $3.50/gal
- [ ] Filtro por rango de fechas funcional
- [ ] Exportar CSV con detalles de eventos idle >30min
```

---

### 3. 📊 Metrics Tab - ALTA PRIORIDAD

#### 3.1 Backend - Cálculos de Métricas
**Archivo:** `api_v2.py` (líneas 2450-2630)

**Problemas Conocidos:**
- ❌ **BUG:** Cost per mile muestra $0.00 en un lugar, $0.82 en otro
- ❌ **BUG:** Mileage muestra 4950, 4580 millas en 2-3 días (físicamente imposible)
- ❌ **BUG:** Usa odómetros absolutos en vez de deltas

**Checklist de Auditoría:**
```python
# Endpoint: /fleet/summary
# Ubicación: api_v2.py líneas 2450-2530

# BUG CRÍTICO: Mileage calculation
- [ ] DEBE usar: MAX(odometer_mi) - MIN(odometer_mi) per truck
- [ ] NO DEBE usar: SUM(odometer_mi) (suma valores absolutos!)
- [ ] Ejemplo correcto:
      SELECT truck_id, 
             MAX(odometer_mi) - MIN(odometer_mi) as miles_traveled
      FROM fuel_metrics 
      WHERE timestamp >= CURDATE() - INTERVAL 7 DAY
      GROUP BY truck_id

# BUG CRÍTICO: Cost per mile
- [ ] Formula: (total_fuel_gal * fuel_price_per_gal) / miles_traveled
- [ ] Validar que miles_traveled > 0 antes de dividir
- [ ] Rango esperado: $0.40 - $1.20 por milla
- [ ] Si muestra $0.00 → verificar que endpoint correcto se usa en frontend

# Validación de rangos realistas (Class 8 trucks)
- [ ] Miles per day: 200-500 (NO >800)
- [ ] Fuel per day: 40-120 gallons (NO >150)
- [ ] Cost per mile: $0.40-$1.20 (NO $0.00 o >$2.00)
- [ ] MPG: 4.0-8.0 (NO >8.5)
```

**Tests SQL:**
```sql
-- Test 1: Verificar mileage realista últimos 7 días
SELECT truck_id,
       MAX(odometer_mi) - MIN(odometer_mi) as miles_7d,
       (MAX(odometer_mi) - MIN(odometer_mi)) / 7.0 as miles_per_day
FROM fuel_metrics
WHERE timestamp >= CURDATE() - INTERVAL 7 DAY
GROUP BY truck_id
HAVING miles_per_day > 600; -- Identificar valores imposibles
-- Esperado: 0 rows (600 mi/día = 25 mph promedio 24/7, imposible)

-- Test 2: Verificar cost per mile
SELECT truck_id,
       (SUM(fuel_consumed_gal) * 3.50) / NULLIF(MAX(odometer_mi) - MIN(odometer_mi), 0) as cost_per_mile
FROM fuel_metrics
WHERE timestamp >= CURDATE() - INTERVAL 7 DAY
GROUP BY truck_id
HAVING cost_per_mile NOT BETWEEN 0.40 AND 1.50;
-- Esperado: investigar outliers
```

#### 3.2 Frontend - Dashboard Metrics

**Checklist:**
```
Tab: Metrics
- [ ] Verificar que llama a endpoint correcto: /fleet/summary
- [ ] Cost per mile debe coincidir en todos los componentes
- [ ] Mileage debe mostrar delta, NO acumulado lifetime
- [ ] Fuel consumed debe tener tooltip con método (ECU/fuel_lvl)
- [ ] Filtro de fecha debe refrescar todos los KPIs simultáneamente
- [ ] Loading states durante fetch de datos
```

---

### 4. 🔧 Loss Analysis - CRÍTICO

**Archivo:** `api_v2.py` `/loss-analysis` endpoint

**Problemas Conocidos:**
- ❌ **BUG CRÍTICO:** Muestra 199,000,000 millas (suma odómetros absolutos)
- ❌ Usa MPG de estado en vez de calcular desde datos reales

**Checklist de Auditoría:**
```python
# Endpoint: /loss-analysis
# Ubicación: api_v2.py (buscar "loss_analysis")

# BUG CRÍTICO 1: Total mileage
- [ ] DEBE calcular: SUM(MAX(odom) - MIN(odom)) per truck
- [ ] NO: SUM(odometer_mi) directamente
- [ ] Validación: Total mileage flota debe ser <50,000 mi/día (45 trucks)

# BUG CRÍTICO 2: Expected vs Actual Fuel
- [ ] Expected fuel: miles_traveled / baseline_mpg_per_truck
- [ ] Actual fuel: SUM(fuel_consumed_gal) from ECU
- [ ] Loss: (actual_fuel - expected_fuel) * fuel_price
- [ ] Validar baseline_mpg es realista (6.0-7.0 para flota)

# BUG 3: Refuel detection
- [ ] NO contar refuels como "pérdida"
- [ ] Detectar fuel_lvl jumps >20% como refuel
- [ ] Excluir esos períodos del cálculo de loss

# Rangos esperados
- [ ] Total fleet loss: $500-$3,000/día (NO $50,000+)
- [ ] Loss per truck: $10-$100/día
- [ ] Mileage total: 5,000-20,000 mi/día para 45 trucks
```

**Tests SQL:**
```sql
-- Test 1: Verificar mileage calculation
SELECT DATE(timestamp) as date,
       COUNT(DISTINCT truck_id) as trucks,
       SUM(daily_miles) as total_miles,
       SUM(daily_miles) / COUNT(DISTINCT truck_id) as avg_miles_per_truck
FROM (
    SELECT truck_id, 
           DATE(timestamp) as date,
           MAX(odometer_mi) - MIN(odometer_mi) as daily_miles
    FROM fuel_metrics
    WHERE timestamp >= CURDATE() - INTERVAL 7 DAY
    GROUP BY truck_id, DATE(timestamp)
) daily
GROUP BY DATE(timestamp)
HAVING total_miles > 30000; -- Imposible >30k millas/día
-- Esperado: 0 rows

-- Test 2: Verificar loss calculation
SELECT truck_id,
       miles / baseline_mpg as expected_fuel,
       actual_fuel,
       (actual_fuel - miles/baseline_mpg) * 3.50 as loss_usd
FROM (
    SELECT truck_id,
           MAX(odometer_mi) - MIN(odometer_mi) as miles,
           SUM(fuel_consumed_gal) as actual_fuel,
           6.5 as baseline_mpg
    FROM fuel_metrics
    WHERE timestamp >= CURDATE() - INTERVAL 1 DAY
    GROUP BY truck_id
) t
HAVING ABS(loss_usd) > 200; -- Investigar pérdidas >$200/día
```

---

### 5. 🔮 Predictive Maintenance - ALTA PRIORIDAD

**Archivo:** `predictive_maintenance_engine.py`

**Problemas Conocidos:**
- ❌ **BUG:** Confidence score muestra >100% (7500%, 9200%)
- Algoritmo no valida límites superiores

**Checklist de Auditoría:**
```python
# Ubicación: predictive_maintenance_engine.py

# BUG CRÍTICO: Confidence score sin cap
- [ ] Confidence DEBE estar entre 0-100%
- [ ] Aplicar: confidence = min(max(calculated_confidence, 0), 100)
- [ ] Si raw calculation >100, investigar fórmula (probablemente error)

# Validación de umbrales
- [ ] Coolant temp threshold: 200-220°F (NO <190 o >230)
- [ ] Oil pressure min: 30-40 PSI en idle (NO <20)
- [ ] Engine hours para maintenance: cada 15,000-25,000 mi
- [ ] DPF regeneration: cada 300-500 mi si equipado

# Algoritmo de score
- [ ] Usar weighted average de múltiples sensores
- [ ] Weights: coolant_temp (30%), oil_pressure (25%), 
              voltage (15%), engine_hours (20%), DTCs (10%)
- [ ] Score 0-40: Good (verde)
- [ ] Score 41-70: Warning (amarillo)
- [ ] Score 71-100: Critical (rojo)
```

**Tests:**
```sql
-- Test 1: Verificar confidence scores
SELECT truck_id, confidence_score, status
FROM predictive_maintenance
WHERE confidence_score > 100 OR confidence_score < 0;
-- Esperado: 0 rows

-- Test 2: Verificar correlación sensors vs. score
SELECT truck_id,
       coolant_temp_f,
       oil_pressure_psi,
       voltage,
       confidence_score
FROM predictive_maintenance
WHERE (coolant_temp_f > 220 AND confidence_score < 60)
   OR (oil_pressure_psi < 25 AND confidence_score < 60);
-- Esperado: 0 rows (scores deben reflejar problemas)
```

---

### 6. 🚨 DTC (Diagnostic Trouble Codes) - MEDIA PRIORIDAD

**Archivo:** `api_v2.py` `/dtc-events` endpoint

**Problemas Conocidos:**
- ❌ **BUG:** Muestra "Unknown" en description a pesar de tener 3000+ SPNs en j1939_spn_lookup
- Query no está usando la tabla de lookup correctamente

**Checklist de Auditoría:**
```python
# Endpoint: /dtc-events
# Verificar query actual

# BUG: DTC description lookup
- [ ] Query debe hacer JOIN con j1939_spn_lookup
- [ ] Usar SPN code para buscar description
- [ ] Fallback a "Unknown SPN {code}" solo si NO existe en tabla
- [ ] Ejemplo query correcto:
      SELECT d.truck_id, d.spn_code, d.fmi_code,
             COALESCE(l.description, CONCAT('Unknown SPN ', d.spn_code)) as description
      FROM dtc_events d
      LEFT JOIN j1939_spn_lookup l ON d.spn_code = l.spn
      WHERE d.timestamp >= ?

# Validación de DTCs
- [ ] SPN codes deben ser numéricos (0-524287)
- [ ] FMI codes deben ser 0-31
- [ ] Severity: 0 (info), 1 (warning), 2 (critical)
- [ ] Active vs. Historical flag correcto
```

**Tests SQL:**
```sql
-- Test 1: Verificar coverage de DTC lookup
SELECT COUNT(*) as total_dtcs,
       SUM(CASE WHEN description = 'Unknown' THEN 1 ELSE 0 END) as unknown_dtcs,
       (SUM(CASE WHEN description = 'Unknown' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as pct_unknown
FROM (
    SELECT d.spn_code,
           COALESCE(l.description, 'Unknown') as description
    FROM dtc_events d
    LEFT JOIN j1939_spn_lookup l ON d.spn_code = l.spn
    WHERE d.timestamp >= CURDATE() - INTERVAL 7 DAY
) t;
-- Esperado: pct_unknown <10%

-- Test 2: Verificar SPNs más comunes sin descripción
SELECT spn_code, COUNT(*) as occurrences
FROM dtc_events
WHERE spn_code NOT IN (SELECT spn FROM j1939_spn_lookup)
AND timestamp >= CURDATE() - INTERVAL 30 DAY
GROUP BY spn_code
ORDER BY occurrences DESC
LIMIT 20;
-- Acción: Agregar estos SPNs a j1939_spn_lookup
```

---

### 7. 🎯 Kalman Filter - MEDIA PRIORIDAD

**Archivo:** `estimator.py` (Kalman implementation)

**Problemas Conocidos:**
- Puede sobre-suavizar datos causando lag en alertas
- No valida valores físicamente imposibles antes de filtrar

**Checklist de Auditoría:**
```python
# Ubicación: estimator.py KalmanEstimator class

# Parámetros del filtro
- [ ] process_noise (Q): Muy bajo causa lag, muy alto causa jitter
- [ ] measurement_noise (R): Ajustar según precisión sensor
- [ ] Valores típicos: Q=0.01-0.1, R=0.1-1.0

# Validación pre-filtro
- [ ] Rechazar valores fuera de rango físico ANTES de Kalman
- [ ] Ejemplo: fuel_lvl debe ser 0-100%, rechazar -5% o 120%
- [ ] Ejemplo: speed debe ser 0-90 mph, rechazar >100 mph

# Aplicación correcta
- [ ] Usar Kalman SOLO para: fuel_lvl, speed, coolant_temp
- [ ] NO usar para: odometer (acumulativo), engine_hours, DTCs
- [ ] Resetear filtro después de 24h sin datos (camión apagado)
```

**Tests:**
```python
# Test 1: Verificar lag del filtro
# Simular cambio abrupto (refuel) y medir tiempo de convergencia
# Esperado: <5 minutos para estabilizar

# Test 2: Verificar rechazo de outliers
# Inyectar valor imposible (fuel_lvl = 500%)
# Esperado: Filtro debe ignorar y mantener último valor válido
```

---

### 8. 📡 Wialon Integration - ALTA PRIORIDAD

**Archivo:** `wialon_reader.py`, `wialon_sync_enhanced.py`

**Problemas Conocidos:**
- Sensor name mapping inconsistente (odometer_mi vs. odom)
- No todos los camiones tienen todos los sensores

**Checklist de Auditoría:**
```python
# Archivo: wialon_reader.py línea 68 SENSOR_PARAMS

# Verificar mapping correcto
- [ ] "odometer": "odom" (NO "odometer_mi")
- [ ] "total_fuel_used": "total_fuel_used" (ECU cumulative)
- [ ] "fuel_rate": "fuel_rate" (instantáneo L/h)
- [ ] "fuel_lvl": "fuel_lvl" (tanque %)
- [ ] "engine_rpm": "eng_rpm" (NO "rpm" o "engine_speed")
- [ ] "coolant_temp": "cool_temp" (Wialon usa nombres cortos!)

# Cobertura de sensores por camión
- [ ] Ejecutar: python comprehensive_sensor_analysis.py
- [ ] Verificar que >80% de flota tiene sensores críticos:
      * odom: 87% ✓
      * total_fuel_used: 76% ✓
      * fuel_rate: 87% ✓
      * engine_rpm: esperado >70%
      * coolant_temp: esperado >60%

# Manejo de datos faltantes
- [ ] Si camión no tiene total_fuel_used → usar fuel_rate integration
- [ ] Si no tiene fuel_rate → usar fuel_lvl delta (menos preciso)
- [ ] Log warning en wialon_sync cuando usa método fallback
```

**Tests:**
```sql
-- Test 1: Verificar timestamp freshness
SELECT truck_id, 
       MAX(last_update) as last_seen,
       TIMESTAMPDIFF(MINUTE, MAX(last_update), NOW()) as minutes_ago
FROM truck_sensors_cache
GROUP BY truck_id
HAVING minutes_ago > 60; -- Camiones sin datos >1h
-- Esperado: 0-2 rows (camiones apagados OK)

-- Test 2: Verificar que sensores críticos están poblados
SELECT COUNT(*) as trucks_missing_critical
FROM truck_sensors_cache
WHERE odometer_mi IS NULL 
   OR fuel_lvl_pct IS NULL;
-- Esperado: <5 trucks (algunos pueden no tener ECU moderno)
```

---

### 9. 🗄️ Database Schema - BAJA PRIORIDAD

**Problemas Conocidos:**
- Algunas tablas tienen columnas obsoletas o duplicadas
- Indexes faltantes en queries frecuentes

**Checklist de Auditoría:**
```sql
-- Verificar indexes en tablas críticas

-- fuel_metrics (tabla más grande)
- [ ] INDEX en (truck_id, timestamp) para queries temporales
- [ ] INDEX en (timestamp) para agregaciones de flota
- [ ] PARTITION por mes si >10M rows

-- truck_sensors_cache
- [ ] PRIMARY KEY en truck_id
- [ ] INDEX en last_update para detectar camiones offline

-- dtc_events
- [ ] INDEX en (truck_id, timestamp, active_flag)
- [ ] INDEX en (spn_code) para lookups

-- Verificar integridad referencial
- [ ] Todos los truck_id en fuel_metrics existen en trucks table
- [ ] No hay NULLs en columnas críticas (truck_id, timestamp)

-- Test performance queries lentos
EXPLAIN SELECT ... ; -- Verificar que usa indexes
-- Query debe ejecutar en <1 segundo para 7 días de datos
```

---

### 10. 🎨 Frontend - UX/UI

**Problemas Conocidos:**
- Loading states inconsistentes
- Algunos gráficos no muestran labels
- Color coding no intuitivo

**Checklist de Auditoría:**
```
General UX
- [ ] Loading spinners durante fetch de datos
- [ ] Error messages informativos (NO solo "Error 500")
- [ ] Tooltips en todos los KPIs explicando cálculo
- [ ] Responsive design funciona en tablet/mobile
- [ ] Refresh automático cada 30-60 segundos

Dashboard Principal
- [ ] Fleet overview card con 4 KPIs principales
- [ ] Mapa con ubicación en tiempo real de camiones
- [ ] Lista de alertas activas (top 5)
- [ ] Gráfico de tendencia MPG últimas 24h

Truck Detail View
- [ ] Breadcrumb navigation (Fleet > Truck > Details)
- [ ] Tabs: Overview, Metrics, Maintenance, DTCs
- [ ] Sensor readings con timestamp de última actualización
- [ ] Botón "Export PDF Report"

Charts & Graphs
- [ ] Ejes con labels claros (unidades incluidas)
- [ ] Legend visible y descriptiva
- [ ] Color blind friendly palette
- [ ] Zoom/pan habilitado en gráficos temporales
- [ ] Hover tooltips con valores exactos
```

---

## 🧪 Plan de Testing Completo

### Test Suite 1: MPG Accuracy
```bash
# 1. Test cálculo básico
python quick_mpg_sensor_check.py RH1522
# Verificar: 6.0-6.5 MPG

# 2. Test múltiples camiones
python comprehensive_sensor_analysis.py
# Verificar: 0 camiones con MPG >8.2

# 3. Test actualización tiempo real
# Manejar camión 10 millas, verificar dashboard actualiza en <3 min
```

### Test Suite 2: Metrics Consistency
```sql
-- Test 1: Verificar cost per mile
SELECT AVG((fuel_consumed * 3.50) / NULLIF(miles, 0)) as avg_cpm
FROM (
    SELECT truck_id,
           MAX(odometer_mi) - MIN(odometer_mi) as miles,
           SUM(fuel_consumed_gal) as fuel_consumed
    FROM fuel_metrics
    WHERE timestamp >= CURDATE()
    GROUP BY truck_id
) t;
-- Esperado: $0.50-$0.90

-- Test 2: Verificar mileage diario
SELECT DATE(timestamp), SUM(daily_miles) as total
FROM daily_truck_metrics
WHERE date >= CURDATE() - INTERVAL 7 DAY
GROUP BY DATE(timestamp)
HAVING total > 25000;
-- Esperado: 0 rows
```

### Test Suite 3: End-to-End Frontend
```
Manual Testing Checklist:
1. [ ] Login y autenticación funciona
2. [ ] Dashboard carga en <3 segundos
3. [ ] Todos los KPIs muestran valores (NO "N/A")
4. [ ] Click en camión individual abre detail view
5. [ ] Filtro de fechas actualiza todos los componentes
6. [ ] Exportar CSV genera archivo válido
7. [ ] Alertas muestran timestamp y descripción
8. [ ] Gráficos renderizan correctamente (NO errores console)
```

---

## 🚀 Priorización de Fixes

### P0 - CRÍTICO (Fix Inmediato)
1. Loss Analysis mileage (199M → cálculo delta correcto)
2. Predictive Maintenance confidence >100% (aplicar cap)
3. Metrics tab cost per mile inconsistencia ($0.00 vs $0.82)
4. DTC "Unknown" descriptions (usar j1939_spn_lookup)

### P1 - ALTA (Fix en 1-2 días)
5. MPG validation ranges (aplicar caps 3.8-8.2)
6. Idle fuel calculation (validar <50 gal/día)
7. Metrics mileage físicamente imposible (4950 mi/2 días)
8. Sensor mapping inconsistencias (odom vs odometer_mi)

### P2 - MEDIA (Fix en 1 semana)
9. Kalman filter tuning (reducir lag)
10. Database indexes en queries lentos
11. Frontend loading states y error handling
12. Refuel detection en loss analysis

### P3 - BAJA (Backlog)
13. UI/UX improvements (tooltips, color coding)
14. Export features (PDF reports)
15. Mobile responsive design
16. Documentación API endpoints

---

## 📝 Formato de Reporte de Bugs

Al encontrar un bug, documentar así:

```markdown
### BUG-XXX: [Título descriptivo]

**Severidad:** P0/P1/P2/P3  
**Componente:** Backend/Frontend/Database  
**Archivo:** path/to/file.py (línea X)

**Descripción:**
[Qué está mal]

**Evidencia:**
[Screenshot, query SQL, o log output]

**Impacto:**
[Cómo afecta a usuarios/datos]

**Root Cause:**
[Análisis técnico de la causa]

**Fix Propuesto:**
```python
# Código propuesto
```

**Tests de Validación:**
[Cómo verificar que el fix funciona]

**Estimación:** X horas/días
```

---

## ✅ Checklist Final Pre-Producción

Antes de marcar auditoría como completa:

```
Backend
- [ ] Todos los tests SQL pasan (0 rows anómalas)
- [ ] Coverage >50% en pytest
- [ ] 0 errores en logs última 24h
- [ ] API response time <500ms p95
- [ ] Database queries <1 segundo
- [ ] Documentación actualizada en README

Frontend
- [ ] 0 errores en browser console
- [ ] Lighthouse score >80
- [ ] Todos los KPIs muestran valores realistas
- [ ] Gráficos renderizan correctamente
- [ ] Mobile responsive funciona

Integración
- [ ] Wialon sync actualiza cada 15 segundos
- [ ] Dashboard refleja cambios en <1 minuto
- [ ] Alertas se disparan correctamente
- [ ] Backup automático DB funciona

Seguridad
- [ ] Credenciales en .env (NO hardcoded)
- [ ] API endpoints requieren autenticación
- [ ] SQL queries usan prepared statements
- [ ] Logs NO incluyen datos sensibles
```

---

## 📞 Contactos y Escalación

**Issues Críticos (P0):**  
Reportar inmediatamente a: [Lead Developer]

**Issues Alta/Media (P1/P2):**  
Crear ticket en: [Sistema de tracking]

**Preguntas sobre Algoritmos:**  
Consultar documentación en: `/docs` folder

**Acceso a Logs:**  
Servidor: `ssh user@server`  
Logs ubicación: `/var/log/fuel-analytics/`

---

## 📚 Referencias Adicionales

1. **MPG Calculation Deep Dive:** `COMPREHENSIVE_FIX_PLAN.md`
2. **Sensor Coverage Analysis:** `comprehensive_sensor_analysis.py` output
3. **Database Schema:** `check_table_structure.py`
4. **API Documentation:** `api_v2.py` docstrings
5. **Git History:** `git log --grep="FIX|BUG" --since="30 days ago"`

---

**Última Actualización:** 22 Diciembre 2025  
**Versión Backend:** beca578  
**Autor:** Fuel Analytics Team
