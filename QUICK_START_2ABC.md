# QUICK START - Fases 2A, 2B, 2C
## Guía Rápida de Integración (5 minutos)

---

## 🚀 PASO 1: Instalar Dependencias

```bash
pip install tensorflow scikit-learn numpy
# O
pip install -r requirements.txt
```

---

## 🔧 PASO 2: Integrar en main.py

```python
# En la sección de imports (antes de crear FastAPI):
from ekf_integration import get_ekf_manager, initialize_ekf_manager
from ekf_diagnostics_endpoints import router as ekf_router
from kafka_event_bus import initialize_event_bus, get_event_bus
from microservices_orchestrator import get_orchestrator

# En la función lifespan (startup):
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Iniciando Phases 2A, 2B, 2C...")
    initialize_ekf_manager(state_dir="data/ekf_states")
    initialize_event_bus()
    _ = get_orchestrator()
    logger.info("✅ Ready")
    
    yield
    
    # Shutdown
    logger.info("💾 Persistiendo...")
    get_ekf_manager().persist_all()

# Después de crear app:
app = FastAPI(lifespan=lifespan)

# Registrar routers
app.include_router(ekf_router)

# (Opcional) Agregar endpoints ML:
@app.get("/fuelAnalytics/api/services/status")
async def services_status():
    return get_orchestrator().get_service_status()
```

---

## 🔌 PASO 3: Integrar en wialon_sync_enhanced.py

```python
# En la sección de imports:
from ekf_integration import get_ekf_manager
from kafka_event_bus import get_event_bus, EventType
from anomaly_detection_v2 import get_anomaly_detector

# En el loop principal de sincronización:
def process_truck_data(truck_id, wialon_data):
    manager = get_ekf_manager()
    bus = get_event_bus()
    
    # Actualizar EKF (reemplaza FuelEstimator)
    ekf_result = manager.update_with_fusion(
        truck_id=truck_id,
        fuel_lvl_pct=wialon_data.get('fuel_level_pct'),
        ecu_fuel_used_L=wialon_data.get('ecu_fuel_used'),
        ecu_fuel_rate_gph=wialon_data.get('ecu_fuel_rate'),
        speed_mph=wialon_data.get('speed', 0),
        rpm=wialon_data.get('rpm', 0),
        engine_load_pct=wialon_data.get('engine_load', 0),
        altitude_ft=wialon_data.get('altitude', 0),
    )
    
    # Publicar eventos
    if ekf_result.get('refuel_detected'):
        bus.publish_fuel_event(
            truck_id=truck_id,
            event_type=EventType.REFUEL_DETECTED,
            fuel_level_pct=ekf_result['level_pct'],
            consumption_gph=ekf_result['consumption_gph']
        )
    
    # Detectar anomalías
    detector = get_anomaly_detector()
    anomaly = detector.detect_anomalies(
        truck_id=truck_id,
        consumption_gph=ekf_result['consumption_gph'],
        speed_mph=wialon_data.get('speed', 0),
        idle_pct=wialon_data.get('idle_pct', 0),
    )
    
    if anomaly['is_anomaly']:
        bus.publish_anomaly_event(
            truck_id=truck_id,
            anomaly_type=anomaly['anomaly_type'],
            severity='warning',
            message=f"{anomaly['anomaly_type']} detected",
            confidence=anomaly['confidence']
        )
    
    # Guardar en MySQL (mantener código existente)
    db.update_fuel_metrics(truck_id, ekf_result)
```

---

## ✅ PASO 4: Testear en Staging

```bash
# 1. Iniciar backend
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
python main.py

# 2. En otra terminal, verificar endpoints
curl http://localhost:8000/fuelAnalytics/api/ekf/health/fleet | jq

# 3. Verificar servicios
curl http://localhost:8000/fuelAnalytics/api/services/status | jq

# 4. Simular datos
python -c "
import requests
data = {
    'truck_id': 'JC1282',
    'fuel_level_pct': 45.5,
    'speed_mph': 65,
    'rpm': 1400
}
# Enviar a tu endpoint de sync
"
```

---

## 📊 ENDPOINTS DISPONIBLES

```
Fase 2A - EKF:
  GET  /fuelAnalytics/api/ekf/health/fleet
  GET  /fuelAnalytics/api/ekf/health/{truck_id}
  GET  /fuelAnalytics/api/ekf/diagnostics/{truck_id}?detailed=true
  GET  /fuelAnalytics/api/ekf/trends/{truck_id}?hours=24
  POST /fuelAnalytics/api/ekf/reset/{truck_id}?force=true

Fase 2C - Services:
  GET  /fuelAnalytics/api/services/status
```

---

## 🎯 VALIDACIÓN RÁPIDA

```python
from ekf_integration import get_ekf_manager

manager = get_ekf_manager()

# Crear estimador
estimator = manager.get_or_create_estimator(
    truck_id="TEST_TRUCK",
    capacity_liters=120
)

# Actualizar
result = manager.update_with_fusion(
    truck_id="TEST_TRUCK",
    fuel_lvl_pct=50.0,
    speed_mph=60,
    rpm=1400
)

print(f"Fuel: {result['level_pct']:.1f}%")
print(f"Consumption: {result['consumption_gph']:.2f} gph")
print(f"Health: {manager.get_health_status('TEST_TRUCK')}")
```

---

## 📁 ESTRUCTURA ESPERADA

```
/Fuel-Analytics-Backend/
├── ekf_integration.py ............................ ✅
├── ekf_diagnostics_endpoints.py ................. ✅
├── lstm_fuel_predictor.py ....................... ✅
├── anomaly_detection_v2.py ...................... ✅
├── driver_behavior_scoring_v2.py ............... ✅
├── kafka_event_bus.py ........................... ✅
├── microservices_orchestrator.py ............... ✅
├── route_optimization_engine.py ................ ✅
├── PHASE_2ABC_IMPLEMENTATION.md ............... ✅
│
├── main.py (modificado) ......................... 🔧
├── wialon_sync_enhanced.py (modificado) ........ 🔧
│
├── data/
│   └── ekf_states/ (nuevo) ...................... ✅
│
└── ml_models/ (nuevo) ........................... ✅
```

---

## 🐛 Troubleshooting

**Error: ModuleNotFoundError: No module named 'tensorflow'**
```bash
pip install tensorflow
# O para CPU only:
pip install tensorflow-cpu
```

**Error: "No data for truck_id"**
- Normal si el truck no ha sido sincronizado. Espera a que Wialon envíe datos.

**Endpoints lento**
- Verificar logs: `tail -f logs/api_staging.log`
- Aumentar workers: `uvicorn main:app --workers 4`

**Estado EKF no persiste**
- Verificar permisos: `chmod 755 data/ekf_states/`
- Revisar logs de escritura

---

## 📚 REFERENCIAS

- Documentación completa: `PHASE_2ABC_IMPLEMENTATION.md` (1047 líneas)
- API reference: http://localhost:8000/docs (Swagger)
- GitHub: [Link al repo]

---

## ✅ Checklist de Integración

- [ ] Dependencias instaladas
- [ ] Imports agregados a main.py
- [ ] Lifespan configurado
- [ ] Routers registrados
- [ ] wialon_sync actualizado
- [ ] Testing en staging
- [ ] Endpoints verificados
- [ ] Performance validado
- [ ] Alertas funcionando
- [ ] Dashboard actualizado

---

**Tiempo total de integración: ~30-60 minutos**
**Tiempo de testing: ~30-60 minutos**
**Tiempo total: ~2 horas para full deployment**
