# 🔍 AUDITORÍA EXHAUSTIVA: SISTEMA DE DETECCIÓN DE RECARGAS Y ROBOS
## Fuel-Analytics-Backend | Diciembre 2025

---

## 📋 RESUMEN EJECUTIVO

| Aspecto | Estado | Observaciones |
|---------|--------|---------------|
| **Detección de Refuels** | 🟢 ROBUSTO | Multi-algoritmo con Kalman baseline, gaps largos soportados |
| **Detección de Theft** | 🟡 MEJORABLE | Buen algoritmo multi-factor, pero faltan integraciones clave |
| **Falsos Positivos** | 🟢 BAJO | Recovery pattern y sensor health filtran bien |
| **Siphoning Lento** | 🔴 NO DETECTADO | <5 gal en >2h pasa como consumo |
| **Geofences** | 🟡 PARCIAL | SAFE_ZONES hardcoded, no gasolineras reales |
| **ML/Patrones** | 🟡 BÁSICO | TheftPatternAnalyzer existe pero es heurístico |

---

## 📁 ARCHIVOS ANALIZADOS

| Archivo | Propósito | Líneas |
|---------|-----------|--------|
| [theft_detection_engine.py](theft_detection_engine.py) | Motor principal de detección de robo | 1856 |
| [wialon_sync_enhanced.py](wialon_sync_enhanced.py) | Detección de refuels + theft inline | 2683 |
| [alert_service.py](alert_service.py) | FuelEventClassifier, alertas | 1546 |
| [estimator.py](estimator.py) | Kalman Filter, refuel reset | 973 |
| [refuel_prediction.py](refuel_prediction.py) | Predicción de próximo refuel | 559 |
| [database_mysql.py](database_mysql.py) | Queries refuel_events, geofences | 5334 |
| [settings.py](settings.py) | Configuración de thresholds | 519 |
| [fuel_stations.py](fuel_stations.py) | API gasolineras externas | 668 |

---

## 🛠️ ANÁLISIS DE ALGORITMOS

### 1️⃣ DETECCIÓN DE REFUELS

#### Ubicación: [wialon_sync_enhanced.py#L480-L590](wialon_sync_enhanced.py#L480-L590)

```python
def detect_refuel(sensor_pct, estimated_pct, last_sensor_pct, time_gap_hours, ...):
```

#### Thresholds Actuales:

| Parámetro | Valor Default | Variable Env | Observación |
|-----------|--------------|--------------|-------------|
| `min_refuel_jump_pct` | **10.0%** | `MIN_REFUEL_JUMP_PCT` | Antes era 15% - se bajó para mejor detección |
| `min_refuel_gallons` | **5.0 gal** | `MIN_REFUEL_GALLONS` | Antes era 10 gal |
| `max_gap_hours` | **96h** | `MAX_REFUEL_GAP_HOURS` | Extendido de 2h→24h→72h→96h |

#### Algoritmo:
1. **Baseline**: Usa Kalman estimate (NO el sensor anterior)
   - ✅ Más preciso que comparar dos lecturas ruidosas
   - `fuel_increase_pct = sensor_pct - estimated_pct`

2. **Validaciones**:
   - Gap entre 5 min y 96 horas
   - Incremento ≥ 10% Y ≥ 5 galones
   - Rechaza incrementos pequeños cerca de tanque lleno (>95% AND <10% AND <15gal)

3. **Factor de Calibración**: `refuel_factor` por camión (tanks.yaml)

#### ✅ Fortalezas:
- Kalman como baseline es robusto ante ruido
- Gaps largos soportados (noches/fines de semana)
- Factores de calibración por camión

#### 🐛 BUG POTENCIAL #1: Refuels Parciales No Detectados
```python
# Línea ~551: Si el salto es <10%, se ignora
if fuel_increase_pct >= min_increase_pct and increase_gal >= min_increase_gal:
```
**Problema**: Refuels de <10% (≈20 gal en tanque de 200) no se detectan.
**Impacto**: Recargas pequeñas frecuentes pasan desapercibidas.
**Severidad**: 🟡 MEDIA

#### 🐛 BUG POTENCIAL #2: Tank Capacity Hardcoded
```python
# Línea ~510: Default 200 gal
tank_capacity_gal: float = 200.0,
```
**Problema**: Si no se pasa capacity, asume 200 gal.
**Impacto**: Cálculo de galones incorrecto para tanques no estándar.
**Severidad**: 🟢 BAJA (tanks.yaml mitiga)

---

### 2️⃣ DETECCIÓN DE ROBOS (THEFT)

#### A) Sistema Principal: [theft_detection_engine.py](theft_detection_engine.py)

##### Thresholds Configurados (TheftDetectionConfig):

| Parámetro | Valor | Propósito |
|-----------|-------|-----------|
| `min_drop_pct` | **10.0%** | Mínimo % para considerar sospechoso |
| `min_drop_gallons` | **15.0 gal** | Mínimo galones |
| `max_time_window_hours` | **6.0h** | Caída debe ocurrir en este tiempo |
| `parked_max_miles` | **0.5 mi** | <0.5 mi = parqueado |
| `parked_max_speed` | **2.0 mph** | <2 mph = parqueado |
| `recovery_window_minutes` | **30 min** | Tiempo para detectar recuperación |
| `recovery_tolerance_pct` | **15%** | Margen para considerar "recuperado" |
| `theft_confirmed_threshold` | **85%** | Confianza para ROBO CONFIRMADO |
| `theft_suspected_threshold` | **60%** | Confianza para ROBO SOSPECHOSO |

##### Sistema de Scoring Multi-Factor:

```python
@dataclass
class ConfidenceFactors:
    movement_factor: float = 0.0    # -50 a +30 (MÁS IMPORTANTE)
    time_factor: float = 0.0        # 0 a +15
    sensor_factor: float = 0.0      # -40 a 0
    drop_size_factor: float = 0.0   # 0 a +25
    location_factor: float = 0.0    # -20 a +10
    pattern_factor: float = 0.0     # 0 a +20
    recovery_factor: float = 0.0    # -50 a 0
    
    # Base: 50% + factores = 0-100%
```

##### Desglose de Factores:

**1. MOVEMENT FACTOR (El más importante)**
```python
if trip_context.was_moving:
    if trip_context.distance_miles > 10: factors.movement_factor = -50  # Definitivamente consumo
    elif trip_context.distance_miles > 5: factors.movement_factor = -40
    elif trip_context.distance_miles > 1: factors.movement_factor = -30
    else: factors.movement_factor = -15
else:
    if trip_context.is_parked: factors.movement_factor = +30  # Máxima sospecha
    else: factors.movement_factor = +10
```
✅ **Excelente**: Correlación con datos de trip table de Wialon elimina la mayoría de falsos positivos.

**2. TIME FACTOR**
```python
if time_context.is_night: factors.time_factor += 10
if time_context.is_weekend: factors.time_factor += 5
if not time_context.is_business_hours: factors.time_factor += 3
# Cap: 15
```

**3. SENSOR FACTOR**
```python
if not sensor_health.is_connected: factors.sensor_factor = -40
elif sensor_health.volatility_score > 50: factors.sensor_factor = -30
elif sensor_health.volatility_score > 30: factors.sensor_factor = -20
elif sensor_health.volatility_score > 15: factors.sensor_factor = -10
```
✅ **Bueno**: Penaliza sensores ruidosos/desconectados.

**4. DROP SIZE FACTOR**
```python
if fuel_drop.drop_gal >= 50: factors.drop_size_factor = 25
elif fuel_drop.drop_gal >= 30: factors.drop_size_factor = 20
elif fuel_drop.drop_gal >= 20: factors.drop_size_factor = 15
elif fuel_drop.drop_gal >= 15: factors.drop_size_factor = 10
else: factors.drop_size_factor = 5
# +5 bonus si drop_pct >= 30%
```

**5. RECOVERY FACTOR (Anti-Sensor Glitch)**
```python
if sensor_health.has_recovery_pattern:
    if recovery_time_minutes < 10: factors.recovery_factor = -50  # Glitch de sensor
    elif recovery_time_minutes < 20: factors.recovery_factor = -40
    else: factors.recovery_factor = -30
```
✅ **Crítico**: Elimina falsos positivos por recuperación rápida de sensor.

**6. PATTERN FACTOR (TheftPatternAnalyzer)**
```python
# Si el camión tiene historial de robos
if len(history) >= 2: factor += 15
elif len(history) == 1: factor += 10
# Mismo día de semana: +5
# Misma hora (±2h): +5
# Evento reciente (<7 días): +5
```
✅ **Bueno**: Detecta patrones de robo recurrente.

---

#### B) Sistema Inline: [wialon_sync_enhanced.py#L790-L920](wialon_sync_enhanced.py#L790-L920)

```python
def detect_fuel_theft(sensor_pct, estimated_pct, last_sensor_pct, truck_status, ...):
```

##### Criterios de Detección:

| Tipo | Condición | Confianza Base |
|------|-----------|----------------|
| STOPPED_THEFT | Drop >10% while stopped | 90% |
| STOPPED_SUSPICIOUS | Drop >5% while stopped | 60% |
| RAPID_LOSS | Drop >20% in <1 hour | 85% |
| UNEXPLAINED_LOSS | Drop > expected consumption + 8% | 70% |
| IDLE_LOSS | Drop >8% while idling | 65% |

##### Factores de Ajuste v5.8.0:

**Time of Day Factor:**
```python
def get_time_of_day_factor(timestamp):
    # Night (10PM-5AM): 1.3x
    # Weekend night: 1.4x (más sospechoso)
    # Business hours: 0.8x (menos sospechoso)
    # Weekend day: 1.0x
```

**Sensor Health Factor:**
```python
def get_sensor_health_factor(voltage, gps_quality, sats):
    # Critical voltage (<11.5V): factor 0.3, status FAILING
    # Low voltage (11.5-12.5V): factor 0.6, status DEGRADED
    # Very poor GPS (<3 sats): factor 0.4, status FAILING
    # Weak GPS (3-4 sats): factor 0.7, status DEGRADED
```
✅ **Excelente**: Reduce falsos positivos cuando hay problemas de sensor.

**Geofence Safe Zone Factor:**
```python
def check_safe_zone(latitude, longitude):
    # Depots: trust_level 0.3 (70% reduction)
    # Gas stations: trust_level 0.4
    # Maintenance yard: trust_level 0.2 (80% reduction)
```

---

#### C) Alert Service Classifier: [alert_service.py#L95-L140](alert_service.py#L95-L140)

```python
class FuelEventClassifier:
    recovery_window_minutes = 10  # RECOVERY_WINDOW_MINUTES env
    recovery_tolerance_pct = 5.0  # RECOVERY_TOLERANCE_PCT env
    drop_threshold_pct = 10.0     # DROP_THRESHOLD_PCT env
    refuel_threshold_pct = 8.0    # REFUEL_THRESHOLD_PCT env
```

##### Flujo de Clasificación:
1. Detecta caída ≥10%
2. Bufferea como `pending_drop`
3. Espera 10 minutos
4. Si recupera a ±5% del original → **SENSOR_ISSUE**
5. Si sube >8% → **REFUEL_AFTER_DROP**
6. Si permanece bajo → **THEFT_CONFIRMED**

---

## 🐛 BUGS Y PROBLEMAS ENCONTRADOS

### CRÍTICOS 🔴

#### BUG #1: Siphoning Lento NO Detectado
**Ubicación**: [theft_detection_engine.py#L461](theft_detection_engine.py#L461)
```python
min_drop_pct: float = 10.0  # At least 10% drop
min_drop_gallons: float = 15.0  # At least 15 gallons
```
**Problema**: Robos de <10% o <15 galones no se detectan.
- Siphoning de 5 gal/hora durante 3 horas = 15 gal total pero cada medición individual es <5%
- Consumo gradual nocturno de 10 gal NO genera alerta

**Impacto**: Pérdida acumulada sin detección.
**Solución**: Implementar detección acumulativa de micro-caídas.

---

#### BUG #2: Drift del Sensor vs Robo Real - Confusión Potencial
**Ubicación**: [estimator.py#L320-L345](estimator.py#L320-L345)
```python
def auto_resync(self, sensor_pct: float):
    # Auto-resync on extreme drift (>15%)
    RESYNC_THRESHOLD = 15.0
    if drift_pct > RESYNC_THRESHOLD:
        self.initialize(sensor_pct=sensor_pct)  # BORRA el drift
```
**Problema**: Si hay robo de 15%+, el Kalman hace auto-resync y "acepta" el robo como nueva normalidad.
**Impacto**: Robos grandes pueden pasar como "drift del sensor".
**Severidad**: 🔴 ALTA

**Solución**: Verificar trip context ANTES de auto-resync.

---

### ALTOS 🟠

#### BUG #3: Geofences de Gasolineras Hardcoded
**Ubicación**: [wialon_sync_enhanced.py#L695-L745](wialon_sync_enhanced.py#L695-L745)
```python
SAFE_ZONES = {
    "GAS_STATION_SHELL_1": {
        "lat": 25.8500,
        "lon": -80.2000,
        "radius_miles": 0.2,
    },
    # Solo UNA gasolinera definida!
}
```
**Problema**: Solo hay 1 gasolinera en las zonas seguras. Los refuels en otras gasolineras podrían marcarse como sospechosos.
**Impacto**: Falsos positivos si hay caída de sensor cerca de gasolineras no listadas.

**Solución**: Integrar con `fuel_stations.py` API.

---

#### BUG #4: Recovery Window Muy Corto
**Ubicación**: [alert_service.py#L149](alert_service.py#L149)
```python
self.recovery_window_minutes = int(os.getenv("RECOVERY_WINDOW_MINUTES", "10"))
```
**Problema**: 10 minutos puede ser insuficiente si hay latencia de datos.
**Impacto**: Sensor glitches clasificados como theft si la recuperación tarda 12 minutos.

---

#### BUG #5: Falta Correlación con Receipts/Invoices
**Ubicación**: No existe.
**Problema**: No hay manera de verificar refuels detectados contra facturas reales.
**Impacto**: No se puede validar precisión del sistema.

---

### MEDIOS 🟡

#### BUG #6: Capacidad de Tanque Asumida
**Múltiples ubicaciones**
```python
tank_capacity_gal: float = 200.0  # Default en muchas funciones
```
**Problema**: Si no se carga `tanks.yaml`, los cálculos de galones son incorrectos.

---

#### BUG #7: Volatility Score Heurístico
**Ubicación**: [theft_detection_engine.py#L635-L700](theft_detection_engine.py#L635-L700)
```python
def get_sensor_health_fast(...):
    volatility_score = 5.0  # Default: assume reliable
    if time_gap_minutes < 5 and drop_pct > 20:
        volatility_score = 60.0  # Heurística
```
**Problema**: La volatilidad se estima heurísticamente, no se calcula con varianza real de últimas lecturas.
**Impacto**: Precisión reducida en clasificación de sensor issues.

---

## 📊 MATRIZ DE COBERTURA

| Escenario | Detectado | Método | Precisión |
|-----------|-----------|--------|-----------|
| Refuel >10% | ✅ Sí | detect_refuel() | Alta |
| Refuel <10% | ⚠️ Parcial | Solo si >5 gal | Media |
| Robo parqueado >15 gal | ✅ Sí | movement_factor +30 | Alta |
| Robo parqueado <15 gal | ❌ No | Bajo threshold | N/A |
| Robo en movimiento | ✅ No detecta | movement_factor -50 (correcto) | Alta |
| Siphoning lento | ❌ No | Sin detección acumulativa | N/A |
| Sensor disconnect | ✅ Sí | fuel_after ≤5% | Alta |
| Sensor glitch (recovery) | ✅ Sí | recovery_factor -50 | Alta |
| Robo nocturno | ✅ Bonus | time_factor +10 | Alta |
| Robo fin de semana | ✅ Bonus | time_factor +5 | Alta |
| Robo recurrente | ✅ Bonus | pattern_factor +20 | Media |
| En gasolinera conocida | ⚠️ Parcial | Solo 1 definida | Baja |
| En depot | ✅ Sí | SAFE_ZONES | Alta |

---

## 🗺️ ROADMAP DE MEJORAS

### PRIORIDAD 1 (Crítico) - Semana 1-2

#### M1: Detección de Siphoning Acumulativo
```python
# Propuesta: Nuevo módulo siphon_detector.py
class SiphonDetector:
    def __init__(self, window_hours=4, min_total_loss_gal=10):
        self.micro_drops = {}  # {truck_id: [(ts, drop_gal), ...]}
    
    def add_reading(self, truck_id, timestamp, fuel_pct, prev_fuel_pct):
        drop = prev_fuel_pct - fuel_pct
        if 0.5 < drop < 5:  # Micro-caída
            self.micro_drops[truck_id].append((timestamp, drop))
            self._check_accumulation(truck_id)
    
    def _check_accumulation(self, truck_id):
        recent = self._get_window(truck_id, hours=4)
        total_loss = sum(d[1] for d in recent)
        if total_loss > 10 and all parked:
            trigger_siphon_alert(truck_id, total_loss)
```
**Esfuerzo**: 3 días
**Impacto**: Detecta robos que actualmente pasan desapercibidos

---

#### M2: Protección de Auto-Resync
```python
# En estimator.py, modificar auto_resync():
def auto_resync(self, sensor_pct: float, trip_context: TripContext = None):
    if drift_pct > RESYNC_THRESHOLD:
        # NUEVO: Verificar si hay justificación
        if trip_context and trip_context.is_parked:
            # Posible robo! NO hacer resync automático
            logger.warning(f"[{self.truck_id}] RESYNC BLOQUEADO - posible robo")
            return False
        # Solo resync si hay justificación (refuel, trip, etc.)
        self.initialize(sensor_pct=sensor_pct)
```
**Esfuerzo**: 1 día
**Impacto**: Evita que robos grandes se "acepten" como drift

---

### PRIORIDAD 2 (Alto) - Semana 3-4

#### M3: Integración API Gasolineras
```python
# Modificar check_safe_zone() para consultar fuel_stations.py
async def check_safe_zone_enhanced(lat, lon):
    # Primero: Zonas estáticas (depots)
    static_result = check_safe_zone(lat, lon, SAFE_ZONES)
    if static_result[0]:
        return static_result
    
    # Segundo: API de gasolineras dinámicas
    from fuel_stations import FuelStationService
    service = FuelStationService()
    nearby = await service.get_nearby_stations(lat, lon, radius_miles=0.3)
    
    if nearby:
        return (True, 0.4, {"zone_name": nearby[0].name, "type": "GAS_STATION"})
    
    return (False, 1.0, None)
```
**Esfuerzo**: 2 días
**Impacto**: Reduce falsos positivos cerca de gasolineras reales

---

#### M4: Validación Cruzada Receipts
```python
# Nuevo endpoint y tabla
# POST /api/receipts/upload
# Campos: truck_id, date, gallons, station_name, receipt_image

# Correlación automática:
def validate_refuel_with_receipt(refuel_event):
    receipts = get_receipts(
        truck_id=refuel_event.truck_id,
        date=refuel_event.timestamp.date(),
        tolerance_hours=4
    )
    if receipts:
        match = find_best_match(refuel_event.gallons, receipts)
        if match:
            return {"validated": True, "receipt_id": match.id}
    return {"validated": False, "needs_review": True}
```
**Esfuerzo**: 5 días
**Impacto**: Permite auditoría y mejora confianza en datos

---

### PRIORIDAD 3 (Medio) - Mes 2

#### M5: ML para Patrones de Robo
```python
# Modelo de clasificación basado en features históricas
class TheftMLClassifier:
    features = [
        'drop_pct', 'drop_gal', 'time_of_day', 'day_of_week',
        'is_parked', 'park_duration_hours', 'distance_from_depot',
        'truck_age_days', 'previous_theft_count', 'sensor_volatility',
        'ambient_temp', 'battery_voltage'
    ]
    
    def train(self, historical_events, labels):
        # Labels: confirmed_theft, sensor_issue, consumption
        self.model = RandomForestClassifier()
        self.model.fit(X, y)
    
    def predict_proba(self, event):
        return self.model.predict_proba([self._extract_features(event)])[0]
```
**Esfuerzo**: 2 semanas
**Impacto**: Mejora precisión 15-25% sobre heurísticas

---

#### M6: Dashboard de Auditoría
- Vista de todos los eventos clasificados
- Filtros: truck, date, classification, confidence
- Override manual: "Marcar como falso positivo" / "Confirmar robo"
- Métricas: precision, recall, F1 por período

**Esfuerzo**: 1 semana
**Impacto**: Permite mejora continua del sistema

---

### PRIORIDAD 4 (Bajo) - Trimestre 2

#### M7: Detección de Anomalías con Isolation Forest
```python
from sklearn.ensemble import IsolationForest

class AnomalyDetector:
    def fit(self, normal_consumption_data):
        self.model = IsolationForest(contamination=0.05)
        self.model.fit(normal_consumption_data)
    
    def is_anomaly(self, current_reading):
        return self.model.predict([current_reading])[0] == -1
```

#### M8: Notificaciones en Tiempo Real
- WebSocket para alertas instantáneas
- Push notifications móviles
- Escalación automática si no se revisa en 30 min

#### M9: Correlación con Cámaras
- Integración con sistema de cámaras del fleet
- Timestamp matching para evidencia visual

---

## 📈 MÉTRICAS DE ÉXITO

| Métrica | Actual (Estimado) | Meta 3 meses | Meta 6 meses |
|---------|------------------|--------------|--------------|
| Falsos positivos | ~15% | <8% | <5% |
| Robos detectados | ~70% | >85% | >95% |
| Tiempo detección | ~30 min | <15 min | <5 min |
| Siphoning detectado | 0% | >50% | >80% |
| Refuels validados | 0% | >30% | >70% |

---

## 🔧 CONFIGURACIÓN RECOMENDADA

### Variables de Entorno Sugeridas:
```bash
# Refuel Detection
MIN_REFUEL_JUMP_PCT=8.0          # Bajar de 10 a 8 para mejor cobertura
MIN_REFUEL_GALLONS=3.0           # Bajar de 5 a 3
MAX_REFUEL_GAP_HOURS=120         # Extender a 5 días

# Theft Detection  
THEFT_MIN_DROP_PCT=7.0           # Bajar de 10 a 7 para siphoning
THEFT_MIN_DROP_GALLONS=10.0      # Bajar de 15 a 10
RECOVERY_WINDOW_MINUTES=20       # Subir de 10 a 20

# Confidence Thresholds
THEFT_CONFIDENCE_ALERT=55        # Alertar más temprano
THEFT_CONFIDENCE_CONFIRM=80      # Confirmar con más datos
```

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

### Semana 1
- [ ] Implementar SiphonDetector
- [ ] Agregar protección a auto_resync
- [ ] Aumentar RECOVERY_WINDOW_MINUTES a 20

### Semana 2
- [ ] Integrar fuel_stations API con check_safe_zone
- [ ] Bajar thresholds según recomendaciones
- [ ] Tests unitarios para nuevos módulos

### Semana 3-4
- [ ] Diseñar schema tabla receipts
- [ ] Endpoint upload receipts
- [ ] Correlación automática refuel-receipt

### Mes 2
- [ ] Entrenar modelo ML con datos históricos
- [ ] A/B test ML vs heurísticas
- [ ] Dashboard de auditoría

---

## 📝 CONCLUSIONES

El sistema actual de detección de refuels y robos es **robusto para casos estándar** pero tiene brechas importantes:

1. **Siphoning lento es invisible** - Prioridad crítica
2. **Geofences incompletas** - Solo 1 gasolinera definida
3. **Sin validación con receipts** - No hay ground truth
4. **Auto-resync puede ocultar robos** - Bug de diseño

La arquitectura multi-factor con Kalman filter es sólida. Las mejoras propuestas son incrementales y no requieren reescritura.

**Inversión estimada**: 4-6 semanas para prioridades 1-2 que resuelven ~80% de los problemas identificados.

---

*Auditoría realizada: Diciembre 17, 2025*
*Versión algoritmos: theft_detection_engine v4.1.0, wialon_sync_enhanced v3.12.21*
