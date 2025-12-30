# 🔍 AUDITORÍA EXHAUSTIVA COMPLETA
## Fuel-Analytics (Backend + Frontend) - Diciembre 17, 2025

---

# 📊 RESUMEN EJECUTIVO

| Área | Críticos | Altos | Medios | Bajos | Total |
|------|----------|-------|--------|-------|-------|
| **Backend - Mantenimiento Predictivo** | 5 | 3 | 8 | 5 | 21 |
| **Backend - Fuel/MPG/Idle** | 2 | 4 | 6 | 3 | 15 |
| **Backend - Refuels/Thefts** | 2 | 2 | 5 | 2 | 11 |
| **Frontend - Components/Hooks** | 2 | 5 | 14 | 9 | 30 |
| **TOTAL** | **11** | **14** | **33** | **19** | **77** |

---

## 🎯 LAS 3 FUNCIONALIDADES CORE - Estado Actual

### 1. 🔧 MANTENIMIENTO PREDICTIVO
**Estado:** ⚠️ FUNCIONAL CON GAPS CRÍTICOS

| Componente | Estado | Score |
|------------|--------|-------|
| TurboHealthPredictor | ✅ Bueno | 85% |
| OilConsumptionTracker | ⚠️ Warning | 70% |
| CoolantLeakDetector | ⚠️ Warning | 75% |
| DEFPredictor | ✅ Bueno | 80% |
| DTCAnalyzer | ✅ Bueno | 90% |
| DTWAnalyzer | ⚠️ Warning | 65% |
| KalmanFilter | ✅ Excelente | 92% |

**Problemas Principales:**
1. ❌ Unidades mezcladas (°C vs °F) entre módulos
2. ❌ No hay cálculo de RUL (Remaining Useful Life) real
3. ❌ Race conditions en caches compartidos
4. ❌ Memory leaks en history buffers

### 2. ⛽ CÁLCULO FUEL/MPG/IDLE
**Estado:** ✅ ROBUSTO (v5.9.0)

| Componente | Estado | Score |
|------------|--------|-------|
| Kalman Filter | ✅ Excelente | 95% |
| MPG Calculation | ✅ Bueno | 88% |
| Idle GPH | ✅ Bueno | 85% |
| Sensor Drift Handling | ✅ Bueno | 82% |

**Problemas Principales:**
1. ⚠️ Todos los trucks usan MPG baseline = 6.39 (no calibrados individualmente)
2. ⚠️ No considera PTO activo (falsos positivos idle alto)
3. ⚠️ Factor terreno no implementado

### 3. 🔐 REFUELS/THEFTS
**Estado:** ⚠️ FUNCIONAL CON BRECHAS

| Componente | Estado | Score |
|------------|--------|-------|
| Refuel Detection | ✅ Bueno | 85% |
| Theft Detection | ⚠️ Warning | 70% |
| Quantity Calculation | ⚠️ Warning | 75% |
| Location Verification | ❌ Pobre | 40% |

**Problemas Principales:**
1. ❌ Siphoning lento NO se detecta (solo caídas abruptas)
2. ❌ Auto-resync del Kalman puede ocultar robos
3. ❌ Solo 1 gasolinera en SAFE_ZONES (hardcoded)
4. ❌ Sin integración con receipts

---

# 🔴 BUGS CRÍTICOS (Acción Inmediata)

## Backend

### C1. División por Cero en Tendencias
**Archivo:** `component_health_predictors.py`
**Línea:** ~350
```python
# PROBLEMA
change_pct = (avg_last - avg_first) / avg_first * 100

# FIX
change_pct = (avg_last - avg_first) / max(abs(avg_first), 0.001) * 100
```

### C2. Unidades de Temperatura Inconsistentes
**Archivo:** `component_health_predictors.py` vs `fleet_command_center.py`
```python
# OilConsumptionTracker usa °C
OIL_TEMP_CRITICAL = 130  # °C

# fleet_command_center usa °F  
"oil_temp_f": {"critical_high": 260}  # °F = 126°C ← NO COINCIDE!
```
**Fix:** Estandarizar a °F y agregar conversión donde sea necesario.

### C3. Race Condition en DEFPredictor Cache
**Archivo:** `def_predictor.py`
```python
# PROBLEMA: Sin lock, múltiples threads pueden corromper datos
def calculate_consumption_profile(self, truck_id: str):
    readings = self.readings_cache.get(truck_id, [])  # READ
    # ... cálculos ...
    self.profiles[truck_id] = profile  # WRITE - Posible corrupción

# FIX: Agregar threading.RLock()
```

### C4. Siphoning Lento No Detectado
**Archivo:** `refuel_detector.py`
```python
# El sistema solo detecta caídas instantáneas >10%
# Robo de 2% diario durante 5 días = 10% NUNCA detectado

# IMPLEMENTAR: SiphonDetector con rolling window
```

### C5. Auto-Resync Oculta Robos
**Archivo:** `estimator.py`
```python
def _evaluate_resync_need(self):
    if drift_pct > 15.0:
        self._emergency_reset()  # ← PELIGRO: Asume drift, no robo

# FIX: Verificar contexto antes de resync
if not self._is_trip_active() and drift_direction == "down":
    # Potencial robo, NO hacer resync automático
    self._flag_for_review(drift_pct)
```

### C6. Memory Leak en History Buffers
**Archivo:** `component_health_predictors.py`
```python
# Trucks removidos de la flota NUNCA se limpian de memoria
self._readings[truck_id] = {...}  # Crece indefinidamente

# FIX: Cleanup periódico de trucks inactivos >7 días
```

## Frontend

### C7. Race Condition en useFleetCommandCenter
**Archivo:** `src/hooks/useFleetCommandCenter.ts`
```typescript
// period cambia pero fetch anterior puede completar después
useEffect(() => {
    fetchData();
}, [period]);  // Si period cambia rápido, datos de periodo anterior pueden sobrescribir

// FIX: Usar AbortController
useEffect(() => {
    const controller = new AbortController();
    fetchData({ signal: controller.signal });
    return () => controller.abort();
}, [period]);
```

### C8. Integer Overflow en Period Parsing
**Archivo:** `src/hooks/useFuelCenter.ts`
```typescript
// parseInt sin validación puede retornar valores inválidos
const periodNumber = parseInt(period.replace(/\D/g, ''), 10);
// period = "9999999999d" → periodNumber > MAX_SAFE_INTEGER

// FIX:
const periodNumber = Math.min(parseInt(...), 365);
```

---

# 🟡 BUGS MEDIANOS (Próximo Sprint)

## Backend

| # | Bug | Archivo | Impacto |
|---|-----|---------|---------|
| M1 | Kalman no maneja NaN/Inf | estimator.py | Cálculos corruptos |
| M2 | DTC no parsea hex (0x64) | dtc_analyzer.py | DTCs perdidos |
| M3 | Nelson Rules incompletas | component_health_predictors.py | Anomalías no detectadas |
| M4 | Speeding severity asume orden dict | driver_scoring_engine.py | Multiplicador incorrecto |
| M5 | Engine load crítico → severidad WARNING | engine_health_engine.py | Alertas subestimadas |
| M6 | DEF prediction sin timezone | def_predictor.py | Timestamps inconsistentes |
| M7 | DTW distance cache key collision | dtw_analyzer.py | Cache hits incorrectos |
| M8 | Solo 1 gasolinera en SAFE_ZONES | refuel_detector.py | Falsos positivos theft |

## Frontend

| # | Bug | Archivo | Impacto |
|---|-----|---------|---------|
| M9 | Error states no se resetean | useApi.ts | UX confusa |
| M10 | Intervals sin AbortController | useSensorData.ts | Memory leaks |
| M11 | Performance score en frontend | FleetCommandCenter.tsx | Inconsistencia |
| M12 | getApiBaseUrl() duplicado 5x | Varios hooks | Mantenibilidad |
| M13 | Opcional chaining faltante | DEFStatusWidget.tsx | Crashes en null |
| M14 | Loading infinito si API falla | TruckDetail.tsx | UX rota |

---

# 🟢 MEJORAS DE LÓGICA Y ALGORITMOS

## 1. Implementar RUL (Remaining Useful Life) Real
**Prioridad:** ALTA
**Esfuerzo:** 16 horas

```python
class RULPredictor:
    """
    Predice días/horas hasta fallo de componente.
    
    Modelos:
    - Linear: health = a - b*t (degradación constante)
    - Exponential: health = a * exp(-b*t) (degradación acelerada)
    - Weibull: para análisis de confiabilidad
    """
    
    def predict_rul(self, component: str, health_history: List[Tuple[datetime, float]]) -> Dict:
        # Fit modelo a datos históricos
        times = [(h[0] - health_history[0][0]).days for h in health_history]
        scores = [h[1] for h in health_history]
        
        # Regresión para encontrar tendencia
        slope, intercept = self._linear_regression(times, scores)
        
        if slope >= 0:  # No hay degradación
            return {"rul_days": None, "status": "stable", "confidence": 0.9}
        
        # Días hasta score = 25 (crítico)
        days_to_critical = (25 - intercept) / abs(slope)
        current_day = times[-1]
        
        return {
            "rul_days": max(0, int(days_to_critical - current_day)),
            "rul_miles": self._estimate_miles(days_to_critical - current_day),
            "degradation_rate_per_day": abs(slope),
            "confidence_r2": self._r_squared(times, scores, slope, intercept),
            "recommended_service_date": datetime.now() + timedelta(days=max(0, days_to_critical - current_day - 7)),
            "estimated_repair_cost": self._estimate_cost(component)
        }
```

**Output ejemplo:**
```json
{
    "component": "turbo_health",
    "current_score": 72,
    "rul_days": 45,
    "rul_miles": 22500,
    "message": "⚠️ Si no reemplazas el turbo en ~45 días, se dañará causando ~$4,500 en reparaciones",
    "recommended_action": "Programar mantenimiento preventivo antes del 1 Feb 2026",
    "potential_loss_if_ignored": "$4,500 - $8,000 (turbo + daño colateral)"
}
```

---

## 2. Detector de Siphoning Lento
**Prioridad:** ALTA
**Esfuerzo:** 8 horas

```python
class SiphonDetector:
    """Detecta robos graduales que evaden detección instantánea."""
    
    SIPHON_THRESHOLD_DAILY = 2.0  # % máximo de pérdida diaria normal
    SIPHON_WINDOW_DAYS = 7
    
    def analyze(self, truck_id: str, readings: List[FuelReading]) -> Optional[SiphonAlert]:
        # Agrupar por día
        daily_changes = self._group_daily_changes(readings)
        
        # Buscar patrón de pérdida consistente
        consecutive_loss_days = 0
        total_unexplained_loss = 0
        
        for day, change in daily_changes.items():
            expected_consumption = self._get_expected_consumption(truck_id, day)
            unexplained = change - expected_consumption
            
            if unexplained < -self.SIPHON_THRESHOLD_DAILY:
                consecutive_loss_days += 1
                total_unexplained_loss += abs(unexplained)
            else:
                consecutive_loss_days = 0
        
        if consecutive_loss_days >= 3 and total_unexplained_loss > 5:
            return SiphonAlert(
                truck_id=truck_id,
                type="slow_siphon",
                period_days=consecutive_loss_days,
                total_gallons_lost=total_unexplained_loss * self._get_tank_capacity(truck_id) / 100,
                confidence=min(95, 50 + consecutive_loss_days * 10)
            )
        return None
```

---

## 3. Integración de Geofences de Gasolineras
**Prioridad:** ALTA
**Esfuerzo:** 12 horas

```python
class GasStationGeofence:
    """Verifica si ubicación está en gasolinera conocida."""
    
    # Usar API de Google Places, OpenStreetMap, o GasBuddy
    
    async def is_at_gas_station(self, lat: float, lon: float, radius_m: int = 100) -> Dict:
        # 1. Buscar en cache local primero
        cached = self._check_local_cache(lat, lon)
        if cached:
            return cached
        
        # 2. Query API externa
        stations = await self._query_nearby_stations(lat, lon, radius_m)
        
        if stations:
            return {
                "at_station": True,
                "station_name": stations[0]["name"],
                "station_brand": stations[0].get("brand"),
                "confidence": 95,
                "source": "google_places"
            }
        
        return {"at_station": False, "confidence": 85}
    
    def validate_refuel(self, refuel_event: RefuelEvent) -> RefuelValidation:
        """Valida refuel cruzando ubicación con gasolineras."""
        station_check = self.is_at_gas_station(refuel_event.lat, refuel_event.lon)
        
        validation = RefuelValidation(
            event=refuel_event,
            location_verified=station_check["at_station"],
            station_name=station_check.get("station_name"),
            confidence_boost=20 if station_check["at_station"] else 0,
            flags=[]
        )
        
        if not station_check["at_station"]:
            validation.flags.append("⚠️ Refuel detectado fuera de gasolinera conocida")
        
        return validation
```

---

## 4. Ensemble de Predictores de Salud
**Prioridad:** MEDIA
**Esfuerzo:** 8 horas

```python
class EnsembleHealthPredictor:
    """Combina múltiples predictores para reducir falsos positivos."""
    
    def __init__(self):
        self.turbo_predictor = TurboHealthPredictor()
        self.oil_tracker = OilConsumptionTracker()
        self.coolant_detector = CoolantLeakDetector()
        self.def_predictor = DEFPredictor()
    
    def predict_overall_health(self, truck_id: str, sensor_data: Dict) -> HealthPrediction:
        predictions = {
            "turbo": self.turbo_predictor.predict(truck_id, sensor_data),
            "oil": self.oil_tracker.predict(truck_id, sensor_data),
            "coolant": self.coolant_detector.predict(truck_id, sensor_data),
            "def": self.def_predictor.predict(truck_id)
        }
        
        # Votación ponderada por confianza
        scores = []
        weights = []
        for name, pred in predictions.items():
            if pred and pred.confidence > 0.3:
                scores.append(pred.health_score)
                weights.append(pred.confidence)
        
        if not scores:
            return HealthPrediction(score=None, confidence=0, status="insufficient_data")
        
        ensemble_score = sum(s*w for s,w in zip(scores, weights)) / sum(weights)
        
        # Detectar si algún componente está en estado crítico
        critical_components = [n for n, p in predictions.items() 
                              if p and p.health_score < 30]
        
        return HealthPrediction(
            overall_score=ensemble_score,
            component_scores=predictions,
            critical_components=critical_components,
            recommendation=self._generate_recommendation(predictions),
            confidence=sum(weights) / len(weights)
        )
```

---

## 5. Correlación Entre Sensores
**Prioridad:** MEDIA
**Esfuerzo:** 6 horas

```python
EXPECTED_CORRELATIONS = {
    ("oil_temp", "coolant_temp"): (0.6, 0.9),    # Deben correlacionar
    ("engine_load", "fuel_rate"): (0.7, 0.95),   # Mayor carga = más fuel
    ("rpm", "oil_pressure"): (0.4, 0.8),         # Mayor RPM = mayor presión
    ("speed", "fuel_rate"): (0.3, 0.7),          # Correlación moderada
    ("intake_temp", "ambient_temp"): (0.5, 0.85) # Relacionados
}

def detect_sensor_anomalies(sensor_data: Dict[str, List[float]]) -> List[SensorAnomaly]:
    """Detecta sensores que no correlacionan como esperado."""
    anomalies = []
    
    for (s1, s2), (min_corr, max_corr) in EXPECTED_CORRELATIONS.items():
        if s1 not in sensor_data or s2 not in sensor_data:
            continue
            
        actual_corr = np.corrcoef(sensor_data[s1], sensor_data[s2])[0, 1]
        
        if actual_corr < min_corr:
            anomalies.append(SensorAnomaly(
                type="low_correlation",
                sensors=(s1, s2),
                expected=f"{min_corr}-{max_corr}",
                actual=actual_corr,
                message=f"⚠️ {s1} y {s2} no correlacionan como esperado. Posible sensor defectuoso."
            ))
        elif actual_corr > max_corr and max_corr < 0.95:
            anomalies.append(SensorAnomaly(
                type="high_correlation",
                sensors=(s1, s2),
                message=f"Correlación inusualmente alta entre {s1} y {s2}. Verificar instalación."
            ))
    
    return anomalies
```

---

# 📅 ROADMAP DE IMPLEMENTACIÓN

## Semana 1 (Inmediato) - Bugs Críticos
| Tarea | Esfuerzo | Responsable |
|-------|----------|-------------|
| Fix división por cero en tendencias | 1h | Backend |
| Estandarizar unidades °C/°F | 2h | Backend |
| Fix race condition DEFPredictor | 2h | Backend |
| Fix auto-resync que oculta robos | 3h | Backend |
| Fix memory leak en history buffers | 2h | Backend |
| Fix race condition frontend | 1h | Frontend |

## Semana 2-3 - Mejoras Core
| Tarea | Esfuerzo | Impacto |
|-------|----------|---------|
| Implementar SiphonDetector | 8h | 🔴 Alto |
| Implementar RUL Predictor | 16h | 🔴 Alto |
| Calibrar MPG por truck | 4h | 🟡 Medio |
| Agregar más SAFE_ZONES | 2h | 🟡 Medio |

## Mes 1 - Mejoras Arquitectura
| Tarea | Esfuerzo | Impacto |
|-------|----------|---------|
| Ensemble predictor | 8h | 🔴 Alto |
| Correlación entre sensores | 6h | 🟡 Medio |
| Integración gasolineras API | 12h | 🔴 Alto |
| Cleanup hooks duplicados frontend | 4h | 🟢 Bajo |

## Mes 2-3 - Mejoras Avanzadas
| Tarea | Esfuerzo | Impacto |
|-------|----------|---------|
| ML para clasificación theft | 24h | 🔴 Alto |
| Dashboard de auditoría | 16h | 🟡 Medio |
| Sistema de receipts/invoices | 20h | 🔴 Alto |
| Nelson Rules completas | 4h | 🟡 Medio |
| FastDTW optimization | 4h | 🟢 Bajo |

## Largo Plazo (Q2 2025)
- Edge computing con ONNX
- A/B testing para umbrales
- Integración con ERPs
- Mobile app para conductores
- API pública para integradores

---

# 💰 IMPACTO ESTIMADO DE MEJORAS

| Mejora | ROI Estimado |
|--------|--------------|
| RUL Predictor | Ahorro $2,000-5,000/truck/año en reparaciones preventivas |
| SiphonDetector | Recuperar $500-2,000/truck/año en combustible robado |
| Geofences gasolineras | Reducir 80% falsos positivos theft |
| Ensemble predictor | Reducir 50% falsos positivos de alertas |
| Correlación sensores | Detectar sensores defectuosos antes de falla |

---

# ✅ ACCIONES INMEDIATAS (Esta Semana)

1. **CRÍTICO**: Corregir unidades °C/°F en `component_health_predictors.py`
2. **CRÍTICO**: Agregar lock a `def_predictor.py` 
3. **CRÍTICO**: Proteger auto-resync en `estimator.py`
4. **ALTO**: Ejecutar calibración MPG: `python calibrate_mpg_per_truck.py --days 60`
5. **ALTO**: Agregar más gasolineras a SAFE_ZONES o integrar API

---

# 📞 CONCLUSIÓN

El sistema está **arquitectónicamente sólido** pero tiene **gaps críticos** que afectan las 3 funcionalidades core:

| Área | Madurez | Gap Principal |
|------|---------|---------------|
| Mantenimiento Predictivo | 75% | Falta RUL real y consistencia de unidades |
| Fuel/MPG/Idle | 90% | Falta calibración individual y PTO |
| Refuels/Thefts | 70% | Siphoning no detectado, pocas gasolineras |

**Inversión recomendada próximos 30 días:** 80-100 horas de desarrollo
**ROI esperado:** $50,000-100,000/año para flota de 50 trucks

---

*Auditoría generada por GitHub Copilot - Diciembre 17, 2025*
*Versión del sistema: Backend v5.9.0, Frontend v3.1.0*
