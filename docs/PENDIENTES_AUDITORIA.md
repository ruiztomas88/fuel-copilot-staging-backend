# 📋 PENDIENTES DE AUDITORÍA - Fuel Copilot

**Última actualización:** 26 Diciembre 2025  
**Auditoría base:** AUDITORIA_COMPLETA_FUEL_COPILOT.md

---

## ✅ COMPLETADO (Última semana)

### 1. MPG EMA Alpha Fix ✅
- **Fecha:** 26 Dic 2025
- **Problema:** `ema_alpha = 0.15` demasiado conservador
- **Fix:** Cambiado a `0.35` en [mpg_engine.py](mpg_engine.py#L233)
- **Impacto:** MPG converge en 1-2 días (vs semanas)
- **Archivos:** mpg_engine.py

### 2. DTCs "UNKNOWN" Fix ✅
- **Fecha:** 25 Dic 2025
- **Problema:** Dual DTC processing systems
- **Fix:** Disabled old system, fixed field mappings
- **Impacto:** 100% decode rate
- **Archivos:** wialon_sync_enhanced.py, alert_service.py, dtc_decoder.py

---

## 🔴 CRÍTICOS - SEMANA 1-2

### 1. Blocking I/O en Async Functions
**Prioridad:** P0  
**Severidad:** CRÍTICA  
**Impacto:** -60% performance actual  
**Tiempo estimado:** 2-3 días  
**ROI:** +200-300% performance

**Problema:**
- 24 ubicaciones en `main.py` usando `cursor.execute()` síncronos
- Event loop bloqueado esperando DB responses
- Response times: 800ms (debería ser <100ms)

**Ubicaciones:**
```
main.py:922   - get_fleet_summary()
main.py:936   - get_fleet_summary()
main.py:984   - get_all_trucks()
main.py:989   - get_all_trucks()
main.py:1007  - get_fleet_data()
main.py:1845  - get_truck_detail()
main.py:2325  - get_theft_analysis()
main.py:2530  - get_predictive_maintenance()
main.py:2547  - get_predictive_maintenance()
main.py:3648  - health check endpoint
...y 14 más
```

**Fix necesario:**
```bash
# 1. Instalar dependencia
pip install aiomysql

# 2. Crear pool async
# archivo: database_async.py
import aiomysql

async def create_pool():
    return await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        minsize=5,
        maxsize=20,
        autocommit=True
    )

# 3. Reemplazar todos los cursor.execute()
# ANTES:
async def get_data():
    cursor.execute("SELECT * FROM trucks")
    return cursor.fetchall()

# DESPUÉS:
async def get_data():
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM trucks")
            return await cursor.fetchall()
```

**Archivos a modificar:**
- [ ] main.py (24 ubicaciones)
- [ ] api_v2.py (múltiples)
- [ ] database.py (agregar métodos async)
- [ ] Crear database_async.py

**Testing:**
- [ ] Unit tests para nuevos métodos async
- [ ] Load testing para verificar performance
- [ ] Verificar no hay memory leaks en pool

**Validación:**
- API response time (p95): 800ms → <200ms
- Throughput: +200% requests/segundo
- Memory usage: estable

---

### 2. Database Indexes (Missing)
**Prioridad:** P0  
**Severidad:** ALTA  
**Impacto:** Queries 10-50x más lentos  
**Tiempo estimado:** 1 día  
**ROI:** +1000-5000% query speed

**Problema:**
- Full table scans en queries frecuentes
- Query times: 150ms+ (debería ser <20ms)
- Sin indexes en columnas usadas en WHERE, JOIN, ORDER BY

**SQL a ejecutar:**
```sql
-- =====================================================
-- TRUCKS TABLE INDEXES
-- =====================================================
CREATE INDEX idx_trucks_status 
    ON trucks(truck_status);

CREATE INDEX idx_trucks_updated 
    ON trucks(updated_at DESC);

CREATE INDEX idx_trucks_compound 
    ON trucks(truck_status, updated_at DESC);

CREATE INDEX idx_trucks_company 
    ON trucks(company_id);

-- =====================================================
-- FUEL_METRICS TABLE INDEXES
-- =====================================================
CREATE INDEX idx_fuel_truck_time 
    ON fuel_metrics(truck_id, created_at DESC);

CREATE INDEX idx_fuel_status 
    ON fuel_metrics(truck_status);

CREATE INDEX idx_fuel_created 
    ON fuel_metrics(created_at DESC);

CREATE INDEX idx_fuel_compound 
    ON fuel_metrics(truck_id, truck_status, created_at DESC);

-- =====================================================
-- FUEL_EVENTS TABLE INDEXES
-- =====================================================
CREATE INDEX idx_fuel_events_truck_time 
    ON fuel_events(truck_id, timestamp DESC);

CREATE INDEX idx_fuel_events_type 
    ON fuel_events(event_type);

CREATE INDEX idx_fuel_events_timestamp 
    ON fuel_events(timestamp DESC);

-- =====================================================
-- REFUEL_EVENTS TABLE INDEXES
-- =====================================================
CREATE INDEX idx_refuel_truck_time 
    ON refuel_events(truck_id, refuel_time DESC);

CREATE INDEX idx_refuel_validated 
    ON refuel_events(validated);

-- =====================================================
-- DTC_EVENTS TABLE INDEXES
-- =====================================================
CREATE INDEX idx_dtc_truck 
    ON dtc_events(truck_id);

CREATE INDEX idx_dtc_active 
    ON dtc_events(is_active);

CREATE INDEX idx_dtc_severity 
    ON dtc_events(severity);

CREATE INDEX idx_dtc_compound 
    ON dtc_events(truck_id, is_active, severity);

CREATE INDEX idx_dtc_timestamp 
    ON dtc_events(created_at DESC);

-- =====================================================
-- TRUCK_SENSORS_CACHE TABLE INDEXES
-- =====================================================
CREATE INDEX idx_sensors_truck 
    ON truck_sensors_cache(truck_id);

CREATE INDEX idx_sensors_updated 
    ON truck_sensors_cache(last_updated DESC);
```

**Validación post-deployment:**
```sql
-- Verificar indexes creados
SHOW INDEXES FROM trucks;
SHOW INDEXES FROM fuel_metrics;
SHOW INDEXES FROM fuel_events;
SHOW INDEXES FROM dtc_events;

-- Verificar query plans (ANTES vs DESPUÉS)
EXPLAIN SELECT * FROM fuel_metrics 
WHERE truck_id = 'CO0681' 
  AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC;

-- Debería mostrar "Using index" en lugar de "Using filesort"
```

**Tareas:**
- [ ] Backup database antes de crear indexes
- [ ] Ejecutar SQL en staging primero
- [ ] Monitorear query performance
- [ ] Ejecutar en production (ventana de mantenimiento)
- [ ] Actualizar documentación

---

### 3. N+1 Query Problem
**Prioridad:** P1  
**Severidad:** ALTA  
**Impacto:** 79 queries → 1 query (para 39 trucks)  
**Tiempo estimado:** 2 horas  
**ROI:** +78x faster

**Problema:**
```python
# database.py::get_fleet_summary()
trucks = get_all_trucks()  # 1 query
for truck in trucks:
    details = get_truck_details(truck.id)  # N queries
    sensors = get_truck_sensors(truck.id)  # N queries
# Total: 1 + 2N queries para N trucks
```

**Fix:**
```python
# ✅ CORRECTO - Single query con JOINs
def get_fleet_summary_optimized(self) -> Dict:
    """Get fleet summary with single query"""
    query = """
        SELECT 
            t.truck_id,
            t.truck_status,
            fm.estimated_pct,
            fm.sensor_pct,
            fm.drift_pct,
            fm.mpg_current,
            fm.idle_gph,
            fm.speed_mph,
            fm.created_at,
            ts.total_fuel_used_gal,
            ts.odometer_mi,
            ts.engine_hours
        FROM trucks t
        LEFT JOIN fuel_metrics fm ON (
            t.truck_id = fm.truck_id 
            AND fm.created_at = (
                SELECT MAX(created_at) 
                FROM fuel_metrics 
                WHERE truck_id = t.truck_id
            )
        )
        LEFT JOIN truck_sensors_cache ts ON t.truck_id = ts.truck_id
        WHERE t.truck_id IN ('VD3579', 'JC1282', ... lista completa)
        ORDER BY t.truck_id
    """
    
    result = cursor.execute(query)
    # Procesar result una sola vez
    return self._build_fleet_summary(result)
```

**Archivos a modificar:**
- [ ] database.py::get_fleet_summary()
- [ ] database.py::_get_truck_details_from_mysql()

**Testing:**
- [ ] Verificar mismo output que versión actual
- [ ] Benchmark: queries antes/después
- [ ] Load testing con 100+ trucks

---

## 🟠 ALTOS - SEMANA 3-4

### 4. Global Variables sin Thread Safety
**Prioridad:** P1  
**Severidad:** ALTA  
**Tiempo estimado:** 3 días

**Archivos afectados:**
- `wialon_sync_enhanced.py` (líneas 169-176)
- `alert_service.py`
- `fleet_command_center.py`

**Problema:**
```python
# ❌ INCORRECTO - Global mutable state
_settings = get_settings()
enhanced_mpg_calculator = EnhancedMPGCalculator()
_wialon_2abc = get_wialon_integration()
```

**Riesgos:**
- Race conditions en multi-threading
- Testing difícil (state compartido)
- No escalable (solo 1 instancia)

**Fix - Dependency Injection:**
```python
# services.py
from fastapi import Depends
from typing import Annotated

class ServiceContainer:
    def __init__(self):
        self.settings = get_settings()
        self.mpg_calculator = EnhancedMPGCalculator()
        self.wialon = get_wialon_integration()
        self.alert_service = AlertService()

def get_services() -> ServiceContainer:
    """FastAPI dependency"""
    return ServiceContainer()

Services = Annotated[ServiceContainer, Depends(get_services)]

# Usage en endpoints
@app.get("/api/truck/{truck_id}")
async def get_truck(truck_id: str, services: Services):
    mpg = services.mpg_calculator.calculate(...)
    return {"mpg": mpg}
```

**Tareas:**
- [ ] Crear services.py con ServiceContainer
- [ ] Refactorizar endpoints para usar Depends()
- [ ] Eliminar globals de wialon_sync_enhanced.py
- [ ] Tests para ServiceContainer
- [ ] Documentar nuevo patrón

---

### 5. Connection Pooling
**Prioridad:** P1  
**Severidad:** MEDIA  
**Tiempo estimado:** 4 horas

**Problema:**
- Nueva connection cada request
- Connection overhead ~50ms
- No reuse de connections

**Fix:**
```python
# database_pool.py
import aiomysql
from contextlib import asynccontextmanager

class DatabasePool:
    def __init__(self):
        self.pool = None
    
    async def initialize(self):
        """Create connection pool on startup"""
        self.pool = await aiomysql.create_pool(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            minsize=5,      # Min connections
            maxsize=20,     # Max connections
            autocommit=True,
            pool_recycle=3600  # Recycle after 1h
        )
    
    @asynccontextmanager
    async def acquire(self):
        """Get connection from pool"""
        async with self.pool.acquire() as conn:
            yield conn
    
    async def close(self):
        """Close all connections"""
        self.pool.close()
        await self.pool.wait_closed()

# Global pool instance
db_pool = DatabasePool()

# Startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db_pool.initialize()
    yield
    # Shutdown
    await db_pool.close()

app = FastAPI(lifespan=lifespan)
```

**Tareas:**
- [ ] Crear database_pool.py
- [ ] Integrar en lifespan()
- [ ] Migrar queries a usar pool
- [ ] Monitorear pool utilization

---

### 6. Large Functions Refactoring
**Prioridad:** P2  
**Severidad:** MEDIA  
**Tiempo estimado:** 1 semana

**Peores offenders:**
```
main.py:191   - lifespan()                    412 líneas 🔴
main.py:608   - check_rate_limit()            419 líneas 🔴
main.py:2474  - get_predictive_maintenance()  245 líneas 🔴
main.py:2267  - get_theft_analysis()          207 líneas 🔴
main.py:1510  - get_truck_detail()            167 líneas 🟡
main.py:1205  - batch_fetch()                 147 líneas 🟡
```

**Guía de refactoring:**
- Funciones <50 líneas idealmente
- Max 100 líneas aceptable
- Extraer lógica a clases/módulos

**Ejemplo - lifespan():**
```python
# ANTES: 412 líneas monolíticas
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 412 líneas ...

# DESPUÉS: Modular
class LifecycleManager:
    async def initialize_database(self): ...
    async def initialize_cache(self): ...
    async def initialize_monitoring(self): ...
    async def cleanup(self): ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = LifecycleManager()
    await manager.initialize_database()
    await manager.initialize_cache()
    await manager.initialize_monitoring()
    
    yield
    
    await manager.cleanup()
```

**Tareas:**
- [ ] Refactorizar lifespan() (412 → ~50 líneas)
- [ ] Refactorizar check_rate_limit() (419 → ~50)
- [ ] Refactorizar get_predictive_maintenance() (245 → ~100)
- [ ] Refactorizar get_theft_analysis() (207 → ~100)

---

## 🟡 MEDIOS - MES 2

### 7. Test Coverage
**Prioridad:** P2  
**Actual:** ~30%  
**Target:** >80%  
**Tiempo:** 2-3 semanas

**Áreas sin coverage:**
- Endpoints críticos (fleet, truck detail)
- Kalman filter edge cases
- Alert service
- MPG calculator

**Plan:**
```bash
# Setup
pip install pytest pytest-asyncio pytest-cov

# Estructura
tests/
  unit/
    test_mpg_calculator.py
    test_kalman_filter.py
    test_dtc_decoder.py
  integration/
    test_api_endpoints.py
    test_database.py
  e2e/
    test_full_flow.py
```

**Tareas:**
- [ ] Setup pytest + coverage tools
- [ ] Unit tests para MPG calculator
- [ ] Unit tests para Kalman filter
- [ ] Integration tests para API
- [ ] E2E tests para flujos críticos
- [ ] CI/CD integration

---

### 8. Type Hints Complete
**Prioridad:** P2  
**Tiempo:** 1 semana

**Estado actual:**
- Type hints parciales
- Muchas funciones sin tipos
- No mypy compliance

**Fix:**
```python
# ANTES
def calculate_mpg(distance, fuel):
    return distance / fuel

# DESPUÉS
def calculate_mpg(distance: float, fuel: float) -> float:
    """Calculate miles per gallon"""
    if fuel <= 0:
        raise ValueError("Fuel must be positive")
    return distance / fuel
```

**Tareas:**
- [ ] Agregar type hints a funciones principales
- [ ] Configurar mypy
- [ ] Fix mypy errors
- [ ] Agregar type hints a classes
- [ ] CI check para mypy

---

### 9. Multi-Layer Caching
**Prioridad:** P2  
**Tiempo:** 3 días

**Actual:** Redis básico  
**Target:** L1 (memoria) + L2 (Redis) + L3 (DB)

**Implementación:**
```python
from functools import lru_cache
import redis

class MultiLayerCache:
    def __init__(self):
        self.redis = redis.Redis()
    
    @lru_cache(maxsize=1000)  # L1: Memory
    def get_cached(self, key: str):
        # Try L2: Redis
        value = self.redis.get(key)
        if value:
            return value
        
        # L3: Database
        value = self.fetch_from_db(key)
        self.redis.setex(key, 300, value)  # Cache 5min
        return value
```

**Tareas:**
- [ ] Implementar MultiLayerCache
- [ ] Integrar en endpoints críticos
- [ ] Configurar TTLs apropiados
- [ ] Monitorear hit rates

---

### 10. Pandas Optimization
**Prioridad:** P2  
**Tiempo:** 2 días

**Problema:**
```python
# ❌ SLOW - iterrows()
for index, row in df.iterrows():
    result = process(row)
```

**Fix:**
```python
# ✅ FAST - Vectorized
df['result'] = df.apply(process, axis=1)

# Mejor aún - Pure vectorization
df['result'] = df['col1'] * df['col2'] + df['col3']
```

**Archivos:**
- database.py
- predictive_maintenance_engine.py
- analytics modules

---

## 📊 MÉTRICAS DE ÉXITO

### Performance Targets

| Métrica | Actual | Target Mes 1 | Target Mes 2 |
|---------|--------|--------------|--------------|
| API Response (p95) | 800ms | 200ms | 100ms |
| DB Query Time (p95) | 150ms | 50ms | 20ms |
| Uptime | 98.5% | 99.5% | 99.9% |
| Error Rate | 2% | 0.5% | 0.1% |
| Test Coverage | 30% | 70% | 85% |

### Completion Timeline

**Semana 1-2 (Críticos):**
- ✅ Blocking I/O fix
- ✅ Database indexes
- ✅ N+1 queries fix

**Semana 3-4 (Altos):**
- ✅ Global variables → DI
- ✅ Connection pooling
- ✅ Large functions refactoring

**Mes 2 (Medios):**
- ✅ Test coverage >70%
- ✅ Type hints complete
- ✅ Multi-layer caching
- ✅ Pandas optimization

---

## 💰 ROI ESTIMADO

### Inversión
- **Tiempo:** 120 horas (~3 semanas dev time)
- **Costo:** ~$12,000 (@ $100/hr)

### Retorno
- **Performance:** +200-300% improvement
- **Reliability:** Menos crashes, mejor uptime
- **Maintainability:** Código más limpio, testeable
- **Scalability:** Ready para 100+ trucks

**ROI:** 500-1000% en 3 meses

---

## 📅 CALENDARIO

### Enero 2026
- Semana 1-2: Críticos (Blocking I/O, indexes, N+1)
- Semana 3-4: Altos (DI, pooling, refactoring)

### Febrero 2026
- Semana 1-2: Testing + Type hints
- Semana 3-4: Caching + Optimizations

### Marzo 2026
- Monitoring & fine-tuning
- Documentation
- Knowledge transfer

---

## 🚦 CRITERIOS DE ACEPTACIÓN

Cada fix debe cumplir:

✅ **Código:**
- [ ] Tests escritos (unit + integration)
- [ ] Type hints agregados
- [ ] Code review aprobado
- [ ] Documentación actualizada

✅ **Performance:**
- [ ] Benchmark muestra mejora
- [ ] No regression en otras áreas
- [ ] Memory usage estable

✅ **Deployment:**
- [ ] Tested en staging
- [ ] Rollback plan documentado
- [ ] Monitoring configurado
- [ ] Production deployment exitoso

---

## 📞 PRÓXIMOS PASOS

1. **Esta semana:**
   - [ ] Review este documento con equipo
   - [ ] Priorizar fixes críticos
   - [ ] Asignar developer resources
   - [ ] Setup proyecto en Jira/Trello

2. **Próxima semana:**
   - [ ] Comenzar Sprint 1 (Blocking I/O)
   - [ ] Daily standups
   - [ ] Progress tracking

3. **Mes 1:**
   - [ ] Completar P0-P1 fixes
   - [ ] Performance validation
   - [ ] Preparar Sprint 2

---

**¿Listo para comenzar?** 🚀

---

_Actualizado: 26 Diciembre 2025_
