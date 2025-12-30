# Plan de Integración - Quick Wins
**Guía paso a paso para integrar Quick Wins en wialon_sync_enhanced.py**

---

## 📋 Pre-requisitos

✅ Commit d0f1f8f aplicado  
✅ Backend corriendo en VM  
✅ Acceso a MySQL (fuel_admin)  

---

## Paso 1: Migración de Base de Datos (5 min)

### En VM PowerShell:
```powershell
cd C:\Users\devteam\Proyectos\fuel-analytics-backend
git pull origin main
git log -1 --oneline  # Verificar d0f1f8f

python migrate_add_confidence_columns.py
```

### Output esperado:
```
Connected to fuel_copilot database
Found X existing columns in fuel_metrics
Adding confidence_score column...
✓ confidence_score column added
Adding confidence_level column...
✓ confidence_level column added
Adding confidence_warnings column...
✓ confidence_warnings column added
Creating index on confidence_level...
✓ Index idx_confidence_level created

✅ Database migration completed successfully!
```

### Verificar:
```sql
mysql -u fuel_admin -pFuelCopilot2025! fuel_copilot -e "DESCRIBE fuel_metrics" | grep confidence
```

Debe mostrar:
```
confidence_score         DECIMAL(5,2)    YES     NULL
confidence_level         VARCHAR(20)     YES     NULL
confidence_warnings      TEXT            YES     NULL
```

✅ **Checkpoint 1:** Columnas creadas exitosamente

---

## Paso 2: Integrar en wialon_sync_enhanced.py

### 2.1 Agregar Imports (LÍNEA ~50, después de imports existentes)

```python
# Quick Wins Modules
from adaptive_refuel_thresholds import get_adaptive_thresholds
from confidence_scoring import calculate_estimation_confidence
from smart_refuel_notifications import get_refuel_notifier
from sensor_health_monitor import get_sensor_health_monitor
```

**Ubicación exacta:** Después de `from settings import _settings` y antes de primera función.

---

### 2.2 Sensor Health Monitor (LÍNEA ~1900, en process_truck())

**Ubicación:** Dentro de `process_truck()`, después de obtener sensor readings (speed, rpm, sensor_pct).

**Buscar esta sección:**
```python
        # Get sensor readings
        speed = wr.get_speed(unit_id, timestamp_posix)
        rpm = wr.get_rpm(unit_id, timestamp_posix)
        sensor_pct = wr.get_fuel_pct(unit_id, timestamp_posix)
```

**AGREGAR DESPUÉS:**
```python
        # =====================================================================
        # Quick Win #4: Sensor Health Monitoring
        # =====================================================================
        monitor = get_sensor_health_monitor()
        
        # Record fuel sensor
        monitor.record_sensor_reading(
            truck_id=truck_id,
            sensor_name="fuel_pct",
            value=sensor_pct,
            timestamp=timestamp,
            is_valid=sensor_pct is not None and 0 <= sensor_pct <= 100
        )
        
        # Record speed sensor
        monitor.record_sensor_reading(
            truck_id=truck_id,
            sensor_name="speed",
            value=speed,
            timestamp=timestamp,
            is_valid=speed is not None and speed >= 0
        )
        
        # Record RPM sensor
        monitor.record_sensor_reading(
            truck_id=truck_id,
            sensor_name="rpm",
            value=rpm,
            timestamp=timestamp,
            is_valid=rpm is not None and 0 <= rpm <= 5000
        )
```

---

### 2.3 Confidence Scoring (LÍNEA ~2027, en process_truck())

**Ubicación:** Después de calcular metrics dict, ANTES del INSERT.

**Buscar esta sección:**
```python
        metrics = {
            "truck_id": truck_id,
            "timestamp_utc": timestamp,
            "fuel_gallons": fuel_gallons,
            # ... más campos ...
            "cost_per_mile": cost_per_mile,
            "odom_delta_mi": odom_delta_mi
        }
```

**AGREGAR DESPUÉS (antes del INSERT):**
```python
        # =====================================================================
        # Quick Win #2: Confidence Scoring
        # =====================================================================
        confidence = calculate_estimation_confidence(
            sensor_pct=sensor_pct,
            time_gap_hours=time_gap_hours,
            gps_satellites=sats,
            battery_voltage=pwr_ext,
            kalman_variance=estimator.P,
            sensor_age_seconds=int(data_age_min * 60),
            ecu_available=total_fuel_used is not None,
            drift_pct=drift_pct,
            speed=speed,
            rpm=rpm
        )
        
        # Add to metrics dict
        metrics["confidence_score"] = confidence.score
        metrics["confidence_level"] = confidence.level.value
        metrics["confidence_warnings"] = "|".join(confidence.warnings) if confidence.warnings else None
        
        logger.debug(
            f"{truck_id} confidence: {confidence.score:.1f}% ({confidence.level.value}) "
            f"- warnings: {len(confidence.warnings)}"
        )
```

**MODIFICAR INSERT (agregar 3 columnas):**

Buscar:
```python
INSERT INTO fuel_metrics (
    truck_id, timestamp_utc, fuel_gallons, fuel_pct, fuel_tank_capacity,
    ...
    odom_delta_mi
) VALUES (%s, %s, %s, ...)
```

Cambiar a:
```python
INSERT INTO fuel_metrics (
    truck_id, timestamp_utc, fuel_gallons, fuel_pct, fuel_tank_capacity,
    ...
    odom_delta_mi,
    confidence_score, confidence_level, confidence_warnings
) VALUES (%s, %s, %s, ...)
```

**Y agregar a VALUES tuple:**
```python
values = (
    truck_id, timestamp, fuel_gallons, fuel_pct, fuel_tank_capacity,
    ...
    metrics.get("odom_delta_mi"),
    metrics.get("confidence_score"),
    metrics.get("confidence_level"),
    metrics.get("confidence_warnings")
)
```

---

### 2.4 Adaptive Refuel Thresholds (LÍNEA ~1260, en detect_refuel())

**Ubicación:** Al inicio de función `detect_refuel()`, reemplazar thresholds estáticos.

**Buscar:**
```python
def detect_refuel(
    truck_id,
    sensor_pct,
    last_sensor_pct,
    kalman_fuel,
    last_kalman_fuel,
    tank_capacity
):
    """Detects refuel using dual method"""
    
    min_refuel_gallons = _settings.min_refuel_gallons  # Static 3.0
    min_refuel_jump_pct = _settings.min_refuel_jump_pct  # Static 8.0
```

**REEMPLAZAR CON:**
```python
def detect_refuel(
    truck_id,
    sensor_pct,
    last_sensor_pct,
    kalman_fuel,
    last_kalman_fuel,
    tank_capacity
):
    """Detects refuel using dual method with adaptive thresholds"""
    
    # =====================================================================
    # Quick Win #1: Adaptive Refuel Thresholds
    # =====================================================================
    adaptive = get_adaptive_thresholds()
    adaptive_increase_pct, adaptive_increase_gal = adaptive.get_thresholds(truck_id)
    
    # Use adaptive if available, fallback to settings
    min_refuel_gallons = adaptive_increase_gal if adaptive_increase_gal else _settings.min_refuel_gallons
    min_refuel_jump_pct = adaptive_increase_pct if adaptive_increase_pct else _settings.min_refuel_jump_pct
    
    logger.debug(
        f"{truck_id} using thresholds: {min_refuel_gallons:.1f}gal, {min_refuel_jump_pct:.1f}% "
        f"(adaptive: {adaptive_increase_gal is not None})"
    )
```

---

### 2.5 Smart Refuel Notifications (LÍNEA ~1550, en save_refuel_event())

**Ubicación:** Dentro de `save_refuel_event()`, DESPUÉS del INSERT exitoso.

**Buscar:**
```python
        cursor.execute(query, values)
        conn.commit()
        
        logger.info(
            f"✅ REFUEL SAVED: {truck_id} +{gallons_added:.1f}gal "
            f"({fuel_before:.1f} → {fuel_after:.1f}) at {timestamp}"
        )
```

**AGREGAR DESPUÉS:**
```python
        # =====================================================================
        # Quick Win #3: Smart Refuel Notifications + Adaptive Learning
        # =====================================================================
        
        # Create notification
        notifier = get_refuel_notifier()
        
        # Calculate confidence for refuel (simple heuristic)
        # High confidence if both Kalman + sensor agree
        refuel_confidence = 90.0 if (
            sensor_jump and kalman_jump and 
            abs(sensor_increase_gal - kalman_increase_gal) < 5
        ) else 70.0 if (sensor_jump or kalman_jump) else 50.0
        
        notif = notifier.create_refuel_notification(
            truck_id=truck_id,
            truck_name=truck_name,
            timestamp=timestamp,
            fuel_before=fuel_before,
            fuel_after=fuel_after,
            gallons_added=gallons_added,
            increase_pct=increase_pct,
            location=f"{lat:.6f},{lng:.6f}" if lat and lng else "Unknown",
            confidence=refuel_confidence,
            detection_method="both" if sensor_jump and kalman_jump else "kalman" if kalman_jump else "sensor"
        )
        
        # Auto-confirm high confidence refuels AND record for adaptive learning
        if refuel_confidence >= 90.0:
            notifier.confirm_refuel(
                truck_id=truck_id,
                timestamp=timestamp.isoformat(),
                confirmed_by="auto",
                is_valid=True,
                notes="Auto-confirmed - both methods agree"
            )
            
            # Record for adaptive threshold learning
            adaptive = get_adaptive_thresholds()
            adaptive.record_confirmed_refuel(
                truck_id=truck_id,
                increase_pct=increase_pct,
                increase_gal=gallons_added,
                confidence=refuel_confidence / 100.0  # Convert to 0-1
            )
            
            logger.info(f"Auto-confirmed refuel + recorded for adaptive learning")
        else:
            logger.info(
                f"Refuel notification created - requires confirmation "
                f"(confidence: {refuel_confidence:.1f}%)"
            )
```

---

## Paso 3: Verificar Sintaxis (2 min)

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
python -m py_compile wialon_sync_enhanced.py
```

Si no hay errores → ✅ Sintaxis correcta

---

## Paso 4: Probar Localmente (10 min)

### Test 1: Quick Wins se importan correctamente
```bash
python -c "
from adaptive_refuel_thresholds import get_adaptive_thresholds
from confidence_scoring import calculate_estimation_confidence
from smart_refuel_notifications import get_refuel_notifier
from sensor_health_monitor import get_sensor_health_monitor
print('✅ All Quick Win modules import successfully')
"
```

### Test 2: Adaptive thresholds básico
```python
from adaptive_refuel_thresholds import get_adaptive_thresholds

adaptive = get_adaptive_thresholds()
pct, gal = adaptive.get_thresholds("TEST_TRUCK")
print(f"Default thresholds: {pct}% / {gal}gal")

# Simulate learning
adaptive.record_confirmed_refuel("TEST_TRUCK", 12.5, 20.0, 0.9)
adaptive.record_confirmed_refuel("TEST_TRUCK", 11.8, 19.5, 0.9)
adaptive.record_confirmed_refuel("TEST_TRUCK", 13.2, 21.0, 0.9)

pct, gal = adaptive.get_thresholds("TEST_TRUCK")
print(f"After 3 refuels: {pct}% / {gal}gal")
```

### Test 3: Confidence scoring básico
```python
from confidence_scoring import calculate_estimation_confidence

confidence = calculate_estimation_confidence(
    sensor_pct=75.0,
    time_gap_hours=0.5,
    gps_satellites=8,
    battery_voltage=13.2,
    kalman_variance=5.0,
    sensor_age_seconds=300,
    ecu_available=True,
    drift_pct=2.5,
    speed=45.0,
    rpm=1500
)

print(f"Confidence: {confidence.score:.1f}% ({confidence.level.value})")
print(f"Warnings: {confidence.warnings}")
```

---

## Paso 5: Commit y Deploy a VM (15 min)

### Commit cambios:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
git add wialon_sync_enhanced.py
git commit -m "integrate: Quick Wins modules into wialon_sync_enhanced.py

Integrated 4 Quick Win modules:
- Adaptive Refuel Thresholds in detect_refuel()
- Confidence Scoring in process_truck() with DB persistence
- Smart Refuel Notifications + auto-confirmation
- Sensor Health Monitor tracking all sensors

Added confidence_score, confidence_level, confidence_warnings to fuel_metrics INSERT

Auto-confirms high confidence refuels (>=90%) and records for adaptive learning"

git push origin main
```

### Deploy en VM:
```powershell
cd C:\Users\devteam\Proyectos\fuel-analytics-backend
git pull origin main
git log -2 --oneline  # Verificar commit de integración

# Reiniciar servicio
Restart-Service FuelAnalytics-WialonSync

# Monitorear logs
Get-Content logs\wialon-sync-stdout.log -Wait
```

### Verificar en logs:
Buscar líneas como:
```
[truck_id] confidence: 85.3% (high) - warnings: 1
[truck_id] using thresholds: 3.2gal, 9.1% (adaptive: True)
✅ REFUEL SAVED: [truck_id] +22.5gal ...
Auto-confirmed refuel + recorded for adaptive learning
Sensor issue detected: [truck_id]_fuel_pct - stuck at 75.0
```

---

## Paso 6: Validar Datos en DB (5 min)

### Query 1: Verificar confidence se está guardando
```sql
SELECT 
    truck_id,
    timestamp_utc,
    confidence_score,
    confidence_level,
    confidence_warnings
FROM fuel_metrics
WHERE timestamp_utc >= NOW() - INTERVAL 1 HOUR
ORDER BY timestamp_utc DESC
LIMIT 20;
```

**Esperado:** confidence_score entre 0-100, confidence_level en (high/medium/low/very_low)

### Query 2: Estadísticas de confianza
```sql
SELECT 
    confidence_level,
    COUNT(*) as count,
    AVG(confidence_score) as avg_score,
    MIN(confidence_score) as min_score,
    MAX(confidence_score) as max_score
FROM fuel_metrics
WHERE timestamp_utc >= NOW() - INTERVAL 24 HOUR
GROUP BY confidence_level
ORDER BY avg_score DESC;
```

### Query 3: Verificar refuels con alta confianza
```sql
SELECT 
    truck_id,
    timestamp_utc,
    gallons_added,
    confidence_score,
    detection_method
FROM refuel_events
WHERE timestamp_utc >= NOW() - INTERVAL 24 HOUR
ORDER BY timestamp_utc DESC
LIMIT 10;
```

---

## Paso 7: Crear API Endpoints (30 min)

### En main.py o api_v2.py, agregar:

```python
from smart_refuel_notifications import get_refuel_notifier
from sensor_health_monitor import get_sensor_health_monitor
from dataclasses import asdict
from typing import Optional

# =============================================================================
# Refuel Notifications Endpoints
# =============================================================================

@app.get("/api/refuel-notifications")
def get_refuel_notifications(truck_id: Optional[str] = None, hours: int = 24):
    """Get pending refuel notifications"""
    try:
        notifier = get_refuel_notifier()
        notifications = notifier.get_pending_notifications(
            truck_id=truck_id,
            since_hours=hours
        )
        return [asdict(n) for n in notifications]
    except Exception as e:
        logger.error(f"Error getting refuel notifications: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/refuel-notifications/confirm")
def confirm_refuel_notification(
    truck_id: str,
    timestamp: str,
    confirmed_by: str,
    is_valid: bool,
    notes: Optional[str] = None
):
    """Confirm or reject a refuel notification"""
    try:
        notifier = get_refuel_notifier()
        notifier.confirm_refuel(
            truck_id=truck_id,
            timestamp=timestamp,
            confirmed_by=confirmed_by,
            is_valid=is_valid,
            notes=notes
        )
        
        # If user confirms it's valid, record for adaptive learning
        if is_valid:
            from adaptive_refuel_thresholds import get_adaptive_thresholds
            # Get refuel details from notification
            notif_key = f"{truck_id}_{timestamp}"
            # Note: Need to get gallons/pct from notification before deleting
            # This is a TODO - refactor to get details before confirm_refuel
            
        return {"status": "ok", "message": "Refuel confirmation recorded"}
    except Exception as e:
        logger.error(f"Error confirming refuel: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/refuel-notifications/stats")
def get_confirmation_stats(days: int = 30):
    """Get refuel confirmation statistics"""
    try:
        notifier = get_refuel_notifier()
        stats = notifier.get_confirmation_stats(days=days)
        return stats
    except Exception as e:
        logger.error(f"Error getting confirmation stats: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# Sensor Health Endpoints
# =============================================================================

@app.get("/api/sensor-health/{truck_id}")
def get_truck_sensor_health(truck_id: str):
    """Get health report for all sensors of a truck"""
    try:
        monitor = get_sensor_health_monitor()
        reports = monitor.get_truck_sensor_health_summary(truck_id)
        return {sensor: asdict(report) for sensor, report in reports.items()}
    except Exception as e:
        logger.error(f"Error getting sensor health: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/sensor-health/{truck_id}/{sensor_name}")
def get_sensor_health_detail(truck_id: str, sensor_name: str):
    """Get detailed health report for a specific sensor"""
    try:
        monitor = get_sensor_health_monitor()
        report = monitor.get_sensor_health_report(truck_id, sensor_name)
        return asdict(report)
    except Exception as e:
        logger.error(f"Error getting sensor health detail: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
```

### Test endpoints:
```bash
# Test refuel notifications
curl http://localhost:8000/api/refuel-notifications

# Test sensor health
curl http://localhost:8000/api/sensor-health/DO9693

# Test stats
curl http://localhost:8000/api/refuel-notifications/stats
```

---

## Paso 8: Actualizar Frontend (Ver FRONTEND_INTEGRATION.md)

Crear componentes:
- `<ConfidenceBadge>` para mostrar confidence score
- `<RefuelNotificationsPanel>` para confirmar refuels
- `<SensorHealthIndicator>` para mostrar salud de sensores

---

## 🎯 Success Criteria

✅ **DB migrated:** confidence columns existen  
✅ **Quick Wins imported:** No import errors  
✅ **Sync running:** Logs muestran confidence scores  
✅ **DB populated:** confidence_score tiene valores  
✅ **Adaptive learning:** data/adaptive_refuel_thresholds.json se crea  
✅ **Notifications:** data/refuel_notifications.json se crea  
✅ **Sensor health:** data/sensor_issues.json se crea  
✅ **API endpoints:** Responden correctamente  

---

## 🐛 Troubleshooting

### Problema: Import errors
```
ModuleNotFoundError: No module named 'adaptive_refuel_thresholds'
```
**Solución:** Verificar que archivos .py estén en root del backend, no en subdirectorio.

### Problema: confidence_score = NULL en DB
**Solución:** Verificar que integration code esté ANTES del INSERT, y que columnas estén en INSERT query.

### Problema: Adaptive thresholds no aprende
**Solución:** Verificar que `record_confirmed_refuel()` se llama después de cada refuel auto-confirmado.

### Problema: Sensor health memory explodes
**Solución:** Verificar que `sensor_history` mantiene solo últimas 1000 lecturas (límite en código).

---

**🚀 READY TO INTEGRATE!**
