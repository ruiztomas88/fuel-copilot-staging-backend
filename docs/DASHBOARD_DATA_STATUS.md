# 📊 DASHBOARD DATA STATUS - Real vs Mock Data
**Generated:** December 30, 2025

## ✅ DATOS 100% REALES (de Wialon)

### Sensors (/trucks/{id}/sensors)
- ✅ RPM
- ✅ Speed (MPH)
- ✅ Fuel Level %
- ✅ Oil Pressure/Temp
- ✅ Coolant Temp
- ✅ DEF Level
- ✅ Engine Load
- ✅ Intake Temp/Pressure
- ✅ **GEAR** (decodificado de J1939)
- ✅ **BAROMETER** (presión barométrica)
- ✅ **OIL LEVEL %** (para algunos camiones)
- ✅ Engine Hours
- ✅ Latitude/Longitude
- ✅ Battery Voltage

### Metrics (Dashboard principal)
- ✅ MPG Current (Kalman-filtered from speed+fuel)
- ✅ Fuel Consumption GPH
- ✅ Engine Hours
- ✅ Idle Hours
- ✅ Distance (odometer)
- ✅ Refuels (detección automática)
- ✅ Fuel Cost (calculado de consumption + precio)

## ⚠️ COMPORTAMIENTO - PARCIALMENTE REAL

### Driving Behavior Scores (DriverHub)
**Fuente:** Tabla `fuel_metrics` (readings cada 15 segundos)

**Lo que SÍ es REAL:**
- ✅ **RPM Management**: Calcula minutos con RPM > 1800 (datos reales de sensores)
- ✅ **Speed Control**: Calcula minutos con velocidad > 65 mph (datos reales GPS)
- ✅ **Low MPG Events**: Detecta MPG < 4 a velocidad > 20 mph (Kalman real)

**Lo que NO está implementado (falta):**
- ❌ **Acceleration Score**: NO detecta aceleraciones fuertes reales
  - **Por qué**: Falta calcular `accel_rate_mpss` y `harsh_accel` flag
  - **Cómo debería ser**: Comparar speed entre readings consecutivos
  - **Umbral**: accel > 4 mph/s = harsh acceleration
  
- ❌ **Braking Score**: NO detecta frenadas fuertes reales  
  - **Por qué**: Falta calcular `harsh_brake` flag
  - **Cómo debería ser**: Detectar decel < -4 mph/s entre readings
  - **Sensor disponible**: `engine_brake_active` existe pero NO se guarda

- ❌ **Gear Usage Score**: NO usa datos de GEAR real
  - **Por qué**: Columna `gear` NO se está guardando en `fuel_metrics`
  - **Sensor disponible**: ✅ GEAR está en API pero NO en historical data
  - **Cómo debería ser**: Detectar wrong gear (RPM alto en gear bajo)

### Heavy Foot Scores (por driver)
**Fuente:** `driver_behavior_engine.py`
- ⚠️ **Calculado** pero sin detectar eventos REALES de harsh accel/brake
- ✅ Usa MPG real y RPM real
- ❌ No tiene acceso a cambios bruscos de velocidad

## 🔧 LO QUE FALTA IMPLEMENTAR

### 1. Guardar nuevos sensores en fuel_metrics
**Estado:** ✅ Columnas agregadas, ❌ NO se están poblando

Columnas agregadas pero vacías:
```sql
- obd_speed_mph       -- De sensor obd_speed
- engine_brake_active -- De sensor engine_brake
- gear                -- De sensor gear (decodificado)
- oil_level_pct       -- De sensor oil_level
- barometric_pressure_inhg -- De sensor barometer
- pto_hours           -- De sensor pto_hours
```

**Acción requerida:**
Actualizar `wialon_sync_enhanced.py` función `process_truck()` para extraer estos valores de `sensor_data` y agregarlos al dict `metrics` antes de `save_to_fuel_metrics()`.

### 2. Calcular aceleraciones/frenadas
**Estado:** ❌ NO implementado

Columnas agregadas pero vacías:
```sql
- accel_rate_mpss  -- Tasa de aceleración en mph/s
- harsh_accel      -- Flag: accel > 4 mph/s
- harsh_brake      -- Flag: decel < -4 mph/s
```

**Acción requerida:**
1. En `wialon_sync_enhanced.py`, antes de INSERT:
   - Obtener speed anterior del mismo truck (última reading)
   - Calcular: `accel_rate = (speed_new - speed_old) / time_delta_seconds`
   - Marcar `harsh_accel = 1` si accel_rate > 4
   - Marcar `harsh_brake = 1` si accel_rate < -4

2. Actualizar `driver_behavior_engine.py` query para contar:
   ```sql
   SUM(harsh_accel) as harsh_accel_count,
   SUM(harsh_brake) as harsh_brake_count
   ```

### 3. Actualizar behavior scores con datos reales
**Archivo:** `driver_behavior_engine.py` línea ~1015

**Query actual:**
```python
# 🔧 PROBLEMA: No cuenta harsh accel/brake porque no existen
SUM(CASE WHEN rpm > 1800 THEN 0.25 ELSE 0 END) as high_rpm_minutes
```

**Query que debería ser:**
```python
SUM(harsh_accel) as harsh_accel_count,
SUM(harsh_brake) as harsh_brake_count,
SUM(CASE WHEN rpm > 1800 THEN 0.25 ELSE 0 END) as high_rpm_minutes,
SUM(CASE WHEN gear > 0 AND rpm > 1600 AND gear <= 4 THEN 1 ELSE 0 END) as wrong_gear_events
```

**Scores que debería calcular:**
```python
behavior_scores = {
    "acceleration": 100 - (harsh_accel_count / active_days * 8),  # Real harsh accel
    "braking": 100 - (harsh_brake_count / active_days * 6),       # Real harsh brake
    "rpm_mgmt": 100 - (high_rpm_minutes * 2),                     # Ya es real
    "gear_usage": 100 - (wrong_gear_events / active_days * 5),    # Usar gear real
    "speed_control": 100 - (overspeed_minutes * 1)                # Ya es real
}
```

## 📋 PLAN DE ACCIÓN

### Prioridad CRÍTICA (para tener 100% datos reales)

1. **Paso 1:** Actualizar INSERT en `wialon_sync_enhanced.py`
   - Agregar columnas nuevas al INSERT statement
   - Extraer valores de `sensor_data` dict
   - Agregar a tuple `values`

2. **Paso 2:** Implementar cálculo de aceleración
   - Crear función `calculate_acceleration_rate()`
   - Guardar última speed por truck en memoria
   - Calcular delta y marcar harsh events

3. **Paso 3:** Actualizar behavior scoring query
   - Modificar SQL en `_get_behavior_summary_from_database()`
   - Usar conteos reales de harsh_accel/harsh_brake
   - Usar datos de gear para wrong_gear detection

4. **Paso 4:** Restart services
   - Reiniciar `wialon_sync_enhanced.py`
   - Esperar ~15 minutos para acumular nuevos datos
   - Verificar behavior scores reflejen datos reales

## 🎯 RESULTADO ESPERADO

Después de implementar:
- ✅ **Acceleration score**: Basado en detección REAL de harsh accelerations
- ✅ **Braking score**: Basado en detección REAL de harsh braking  
- ✅ **Gear Usage score**: Basado en análisis de gear position vs RPM REAL
- ✅ **RPM Management**: Ya usa datos reales (sin cambios)
- ✅ **Speed Control**: Ya usa datos reales (sin cambios)

**GARANTÍA:** 0% mock data, 100% datos reales de sensores Wialon procesados por nuestro sistema.
