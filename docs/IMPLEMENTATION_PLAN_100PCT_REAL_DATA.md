# 🎯 IMPLEMENTATION PLAN: 100% Real Data

**Status:** ✅ Columnas agregadas | 🔄 Código en progreso | ⏳ Pendiente testing

## ✅ COMPLETADO

### 1. Schema Updates
- ✅ Agregadas columnas a `fuel_metrics`:
  - `obd_speed_mph`, `engine_brake_active`, `gear`
  - `oil_level_pct`, `barometric_pressure_inhg`, `pto_hours`
  - `accel_rate_mpss`, `harsh_accel`, `harsh_brake`

### 2. Bug Fixes
- ✅ **GEAR**: gear=0 ahora retorna None (N/A) en lugar de 0 (Neutral)
- ✅ **Coolant Level**: Warning solo se muestra cuando hay dato real

## 🔄 EN PROGRESO

### Paso 1: Actualizar wialon_sync_enhanced.py - INSERT Statement

**Archivo:** `wialon_sync_enhanced.py` línea ~2796

**Agregar a las columnas del INSERT:**
```python
# Después de coolant_temp_f:
 coolant_temp_f,
 gear, engine_brake_active, obd_speed_mph,          # 🆕 NEW SENSORS
 oil_level_pct, barometric_pressure_inhg, pto_hours, # 🆕 NEW SENSORS  
 accel_rate_mpss, harsh_accel, harsh_brake,         # 🆕 BEHAVIOR TRACKING
 idle_gph, idle_method, idle_mode,
```

**Agregar placeholders (%s) correspondientes**

**Agregar al tuple `values` (línea ~2865):**
```python
metrics["coolant_temp_f"],
# 🆕 NEW SENSORS
metrics.get("gear"),
metrics.get("engine_brake_active"),
metrics.get("obd_speed_mph"),
metrics.get("oil_level_pct"),
metrics.get("barometric_pressure_inhg"),
metrics.get("pto_hours"),
# 🆕 BEHAVIOR TRACKING
metrics.get("accel_rate_mpss"),
metrics.get("harsh_accel", 0),
metrics.get("harsh_brake", 0),
# 🔧 FIX v5.4.7: Added idle_gph value (was missing - BUG #1)
metrics.get("idle_gph"),
```

**Agregar al ON DUPLICATE KEY UPDATE:**
```python
coolant_temp_f = VALUES(coolant_temp_f),
gear = VALUES(gear),
engine_brake_active = VALUES(engine_brake_active),
obd_speed_mph = VALUES(obd_speed_mph),
oil_level_pct = VALUES(oil_level_pct),
barometric_pressure_inhg = VALUES(barometric_pressure_inhg),
pto_hours = VALUES(pto_hours),
accel_rate_mpss = VALUES(accel_rate_mpss),
harsh_accel = VALUES(harsh_accel),
harsh_brake = VALUES(harsh_brake),
idle_gph = VALUES(idle_gph),
```

### Paso 2: Extraer Sensores en process_truck()

**Archivo:** `wialon_sync_enhanced.py` función `process_truck()`

**Buscar donde se construye el dict metrics** (después de Kalman processing)

**Agregar extracción de nuevos sensores:**
```python
# 🆕 DEC 30 2025: Extract new sensors from sensor_data
from api_v2 import decode_j1939_gear

# Gear (decoded)
gear_raw = sensor_data.get("gear")
metrics["gear"] = decode_j1939_gear(gear_raw) if gear_raw is not None else None

# Engine brake
metrics["engine_brake_active"] = int(sensor_data.get("engine_brake", 0)) if sensor_data.get("engine_brake") else None

# OBD Speed
metrics["obd_speed_mph"] = sensor_data.get("obd_speed")

# Oil Level %
metrics["oil_level_pct"] = sensor_data.get("oil_level") or sensor_data.get("oil_lvl")

# Barometric Pressure
metrics["barometric_pressure_inhg"] = sensor_data.get("barometer")

# PTO Hours
metrics["pto_hours"] = sensor_data.get("pto_hours")
```

### Paso 3: Calcular Harsh Accel/Brake

**Agregar al inicio de wialon_sync_enhanced.py (después de imports):**

```python
# 🆕 DEC 30 2025: Track previous speed for acceleration calculation
PREVIOUS_SPEEDS = {}  # truck_id -> (speed_mph, timestamp)

def calculate_acceleration(truck_id: str, current_speed: float, current_time: datetime) -> Tuple[Optional[float], bool, bool]:
    """
    Calculate acceleration rate and detect harsh events.
    
    Returns:
        (accel_rate_mpss, harsh_accel, harsh_brake)
    """
    if truck_id not in PREVIOUS_SPEEDS:
        # First reading, no previous data
        PREVIOUS_SPEEDS[truck_id] = (current_speed, current_time)
        return (None, False, False)
    
    prev_speed, prev_time = PREVIOUS_SPEEDS[truck_id]
    
    # Calculate time delta in seconds
    time_delta = (current_time - prev_time).total_seconds()
    
    # Avoid division by zero
    if time_delta <= 0 or time_delta > 60:  # Max 60s between readings
        PREVIOUS_SPEEDS[truck_id] = (current_speed, current_time)
        return (None, False, False)
    
    # Calculate acceleration rate in mph/second
    accel_rate = (current_speed - prev_speed) / time_delta
    
    # Detect harsh events
    # 🔧 Thresholds based on industry standards:
    # - Harsh acceleration: > 4 mph/s (0-60 in 15 seconds)
    # - Harsh braking: < -4 mph/s (60-0 in 15 seconds)
    harsh_accel = accel_rate > 4.0
    harsh_brake = accel_rate < -4.0
    
    # Update tracking
    PREVIOUS_SPEEDS[truck_id] = (current_speed, current_time)
    
    return (accel_rate, harsh_accel, harsh_brake)
```

**En process_truck(), después de extraer speed:**

```python
# 🆕 DEC 30 2025: Calculate acceleration and detect harsh events
speed_mph = sensor_data.get("speed", 0)
timestamp_utc = sensor_data.get("timestamp")

accel_rate, harsh_accel, harsh_brake = calculate_acceleration(
    truck_id, 
    speed_mph, 
    timestamp_utc
)

metrics["accel_rate_mpss"] = accel_rate
metrics["harsh_accel"] = 1 if harsh_accel else 0
metrics["harsh_brake"] = 1 if harsh_brake else 0
```

### Paso 4: Actualizar Behavior Engine Query

**Archivo:** `driver_behavior_engine.py` línea ~1015

**REEMPLAZAR la query actual con:**

```python
query = """
    SELECT 
        truck_id,
        -- 🆕 DEC 30 2025: Real harsh accel/brake from sensors
        SUM(harsh_accel) as harsh_accel_count,
        SUM(harsh_brake) as harsh_brake_count,
        
        -- High RPM: count minutes where RPM > 1800 (excessive)
        SUM(CASE WHEN rpm > 1800 THEN 0.25 ELSE 0 END) as high_rpm_minutes,
        
        -- Wrong gear: high RPM in low gear
        SUM(CASE 
            WHEN gear > 0 AND gear <= 4 AND rpm > 1600 AND speed_mph > 30 
            THEN 1 ELSE 0 
        END) as wrong_gear_events,
        
        -- Overspeeding: count minutes where speed > 65
        SUM(CASE WHEN speed_mph > 65 THEN 0.25 ELSE 0 END) as overspeed_minutes,
        
        -- MPG data for scoring
        AVG(CASE WHEN speed_mph > 10 THEN mpg_current END) as avg_mpg,
        
        -- Low MPG events (could indicate aggressive driving)
        SUM(CASE WHEN mpg_current < 4 AND speed_mph > 20 THEN 1 ELSE 0 END) as low_mpg_events,
        
        COUNT(DISTINCT DATE(timestamp_utc)) as active_days,
        COUNT(*) as total_readings
    FROM fuel_metrics
    WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 7 DAY)
    GROUP BY truck_id
    HAVING active_days >= 1
    ORDER BY (harsh_accel_count + harsh_brake_count) DESC
"""
```

**ACTUALIZAR el cálculo de behavior_scores:**

```python
# Calculate behavior scores using REAL data
avg_daily_accel = total_accel_events / n_trucks if n_trucks > 0 else 0
avg_daily_brake = total_brake_events / n_trucks if n_trucks > 0 else 0
avg_daily_rpm = total_rpm_minutes / n_trucks if n_trucks > 0 else 0
avg_daily_wrong_gear = total_wrong_gear_events / n_trucks if n_trucks > 0 else 0
avg_daily_speed = total_speed_minutes / n_trucks if n_trucks > 0 else 0

behavior_scores = {
    # 🆕 DEC 30 2025: Using REAL harsh accel/brake counts
    "acceleration": round(max(0, min(100, 100 - (avg_daily_accel * 8))), 1),
    "braking": round(max(0, min(100, 100 - (avg_daily_brake * 6))), 1),
    "rpm_mgmt": round(max(0, min(100, 100 - (avg_daily_rpm * 2))), 1),
    # 🆕 Using REAL gear data
    "gear_usage": round(max(0, min(100, 100 - (avg_daily_wrong_gear * 5))), 1),
    "speed_control": round(max(0, min(100, 100 - (avg_daily_speed * 1))), 1),
}
```

## ⏳ TESTING PLAN

1. **Restart wialon_sync**
   ```bash
   pkill -f wialon_sync_enhanced.py
   /opt/anaconda3/bin/python wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &
   ```

2. **Wait 2 minutes** for new data to accumulate

3. **Verify new columns populated:**
   ```sql
   SELECT truck_id, gear, engine_brake_active, harsh_accel, harsh_brake, accel_rate_mpss
   FROM fuel_metrics 
   WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
   LIMIT 10;
   ```

4. **Check behavior scores:**
   ```bash
   curl http://localhost:8000/fuelAnalytics/api/v2/behavior/fleet | jq '.behavior_scores'
   ```

5. **Verify DriverHub dashboard** shows real data

## 🎯 SUCCESS CRITERIA

- ✅ All new sensor columns populated in fuel_metrics
- ✅ harsh_accel and harsh_brake flags set correctly (when accel > ±4 mph/s)
- ✅ Behavior scores reflect REAL harsh events (not all 100)
- ✅ Gear usage score uses actual gear data
- ✅ Dashboard shows realistic behavior scores with variation

## 📊 EXPECTED RESULTS

**Before (Mock):**
- Acceleration: 100, Braking: 98, RPM: 100, Gear: 100, Speed: 97

**After (Real):**
- Acceleration: 85-95 (detecting real harsh accels)
- Braking: 88-96 (detecting real harsh brakes)
- RPM: 92-98 (already real)
- Gear: 90-98 (detecting wrong gear usage)
- Speed: 94-98 (already real)

**GUARANTEE:** 0% mock, 100% real sensor data from Wialon.
