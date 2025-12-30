# 🎯 Coverage Analysis & Action Plan
## Estado Actual vs. Commits 190h + 245h

**Fecha**: 25 Diciembre 2025  
**Objetivo**: Coverage 100% Backend + Frontend

---

## 📊 RESUMEN EJECUTIVO

### ✅ COMPLETADO (Commits 190h + 245h Backend)
- ✅ **HealthAnalyzer**: Risk scoring con tests 100%
- ✅ **DEFPredictor**: Predicción depleción con tests 100%
- ✅ **PatternAnalyzer**: Detección correlaciones con tests 100%
- ✅ **4 Endpoints API v2**: Todos funcionando y testeados
- ✅ **FleetOrchestrator**: Integración completa

### ⚠️ PENDIENTE - BACKEND

#### 1. Tests Faltantes (Coverage Actual ~15%)
```
Archivos Python SIN tests:
- main.py (4,921 líneas) - 0% coverage
- wialon_sync_enhanced.py (3,800+ líneas) - 0% coverage  
- database.py - 0% coverage
- database_mysql.py - 0% coverage
- truck_specs_engine.py - 0% coverage
- routers/* (todos los routers) - 0% coverage
- src/services/analytics_service_adapted.py - 0% coverage
- src/services/priority_engine.py - 0% coverage
- src/repositories/* (4 repos) - 0% coverage parcial

Total estimado: ~20,000 líneas SIN tests
```

#### 2. Deployment Scripts (Commit 245h)
```
PENDIENTE revisar commit 245h para:
- Scripts CI/CD
- Backup automation  
- Health checks
- Rollback procedures
- Docker/containerization (si aplica)
```

### ⚠️ PENDIENTE - FRONTEND

#### 1. Componentes NO Integrados con Nuevos Endpoints
```
FALTAN componentes React para:
- /api/v2/fleet/health/advanced
  → Widget "Fleet Health Score" con breakdown
  → Insights visualizados
  
- /api/v2/truck/{id}/risk  
  → Risk Analysis Card
  → Correlation warnings display
  
- /api/v2/fleet/def-predictions
  → DEF Predictions Dashboard
  → Days-to-derate timeline
  
- /api/v2/fleet/patterns
  → Pattern Detection Panel
  → Systemic Issues List
```

#### 2. Tests Frontend (Coverage Actual ~5%)
```
Archivos TypeScript/TSX SIN tests:
- src/pages/* - 0% coverage
- src/components/* (mayoría) - 0% coverage
- src/hooks/* - 0% coverage
- src/utils/* - 0% coverage
- src/contexts/* - 0% coverage

Solo 3 tests encontrados:
- NotificationSystem.test.tsx
- Skeleton.test.tsx
- InfoTooltip.test.tsx

Total estimado: ~15,000 líneas SIN tests
```

---

## 🎯 PLAN DE ACCIÓN - 100% COVERAGE

### FASE 1: Backend Core Tests (8-10 horas)
**Prioridad**: CRÍTICA

#### 1.1. Repository Tests (2 horas)
```python
# Crear: tests/repositories/test_truck_repository.py
- test_get_all_trucks()
- test_get_truck_by_id()
- test_get_trucks_offline()
- test_get_truck_specs()
- test_connection_pooling()

# Similar para:
- test_sensor_repository.py
- test_def_repository.py
- test_dtc_repository.py
```

#### 1.2. Service Tests (2 horas)
```python
# Crear: tests/services/test_analytics_service.py
- test_get_fleet_summary()
- test_get_truck_stats()
- test_calculate_fuel_efficiency()

# Crear: tests/services/test_priority_engine.py
- test_calculate_urgency()
- test_component_cost_lookup()
- test_priority_scoring()
```

#### 1.3. Main API Tests (3 horas)
```python
# Crear: tests/api/test_main_endpoints.py
- test_fleet_endpoint()
- test_truck_detail_endpoint()
- test_kpis_endpoint()
- test_refuel_events_endpoint()
- test_alerts_endpoints()
- test_all_routers()

# Usar pytest + httpx
```

#### 1.4. Database Tests (1 hora)
```python
# Crear: tests/test_database.py
- test_connection()
- test_queries()
- test_connection_pool()

# Crear: tests/test_database_mysql.py
- test_enhanced_queries()
- test_sensor_status()
- test_fuel_trends()
```

#### 1.5. Wialon Sync Tests (2 horas)
```python
# Crear: tests/test_wialon_sync.py
- test_sensor_mapping()
- test_fuel_calculation()
- test_theft_detection()
- test_mpg_validation()
- Mock Wialon API calls
```

**Meta Fase 1**: 85% coverage backend

---

### FASE 2: Frontend Components (6-8 horas)
**Prioridad**: ALTA

#### 2.1. Crear Componentes Nuevos (4 horas)

**FleetHealthAdvancedWidget.tsx**
```tsx
// Muestra /api/v2/fleet/health/advanced
- Health score gauge (0-100)
- Breakdown chart (sensors, DTCs, fuel, offline)
- Insights list con iconos
- Color coding: EXCELLENT/GOOD/FAIR/POOR
```

**TruckRiskCard.tsx**
```tsx
// Muestra /api/v2/truck/{id}/risk
- Risk score badge
- Contributing factors list
- Correlations warnings
- Sensor/DTC details expandible
```

**DEFPredictionsDashboard.tsx**
```tsx
// Muestra /api/v2/fleet/def-predictions
- Table: Truck | Current % | Days to Empty | Days to Derate
- Filters: CRITICAL / WARNING / NOTICE / OK
- Sort by urgency
- Visual timeline
```

**FleetPatternsPanel.tsx**
```tsx
// Muestra /api/v2/fleet/patterns
- Patterns table (tipo, affected count, severity)
- Systemic issues alerts
- Recommendations
- Truck list expandible
```

#### 2.2. Integrar en Dashboard (1 hora)
```tsx
// Modificar src/pages/Dashboard.tsx
- Agregar FleetHealthAdvancedWidget
- Agregar FleetPatternsPanel en sección de alertas

// Modificar src/pages/TruckDetail.tsx  
- Agregar TruckRiskCard
```

#### 2.3. Crear Hooks (1 hora)
```tsx
// src/hooks/useFleetHealth.ts
export function useFleetHealth() {
  // Fetch /api/v2/fleet/health/advanced
  // Return { data, loading, error, refetch }
}

// src/hooks/useTruckRisk.ts
// src/hooks/useDEFPredictions.ts
// src/hooks/useFleetPatterns.ts
```

**Meta Fase 2**: 4 componentes nuevos integrados

---

### FASE 3: Frontend Tests (8-10 horas)
**Prioridad**: ALTA

#### 3.1. Component Tests (4 horas)
```tsx
// tests/components/FleetHealthAdvancedWidget.test.tsx
- renders correctly with data
- shows CRITICAL status in red
- displays insights
- handles loading state
- handles error state

// Similar para:
- TruckRiskCard.test.tsx
- DEFPredictionsDashboard.test.tsx
- FleetPatternsPanel.test.tsx
```

#### 3.2. Page Tests (2 horas)
```tsx
// tests/pages/Dashboard.test.tsx
- renders all widgets
- fetches data on mount
- handles refresh

// tests/pages/TruckDetail.test.tsx
- renders truck info
- renders risk analysis
- handles truck not found
```

#### 3.3. Hook Tests (1 hora)
```tsx
// tests/hooks/useFleetHealth.test.tsx
- fetches data correctly
- handles errors
- refetches on demand

// Similar para otros hooks
```

#### 3.4. Integration Tests (2 horas)
```tsx
// tests/integration/fleet-health-flow.test.tsx
- Full user journey: dashboard → truck detail → risk analysis
- Mock API responses
- Test user interactions
```

**Meta Fase 3**: 80% coverage frontend

---

### FASE 4: E2E Tests (4-6 horas)
**Prioridad**: MEDIA

#### 4.1. Playwright E2E (3 horas)
```typescript
// e2e/advanced-features.spec.ts
test('Fleet health shows correct status', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-testid="fleet-health-score"]')).toBeVisible();
  // Verify data from API
});

test('Truck risk analysis loads', async ({ page }) => {
  await page.goto('/truck/JB6858');
  await expect(page.locator('[data-testid="risk-card"]')).toBeVisible();
});

test('DEF predictions dashboard works', async ({ page }) => {
  await page.goto('/def-predictions');
  // Verify table, filters, sorting
});

test('Pattern detection shows systemic issues', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="patterns-panel"]');
  // Verify patterns list
});
```

#### 4.2. Backend E2E (2 horas)
```python
# tests/e2e/test_full_flow.py
def test_truck_health_flow():
    # 1. Fetch fleet health
    # 2. Get truck risk for worst truck
    # 3. Get DEF predictions
    # 4. Verify correlations
    # 5. Check patterns
    pass
```

**Meta Fase 4**: Flows principales cubiertos

---

### FASE 5: Deployment Scripts (2-3 horas)
**Prioridad**: BAJA (si no están en commit 245h)

```bash
# scripts/deploy.sh
- Build frontend
- Restart backend
- Health check
- Rollback if fails

# scripts/backup.sh  
- Backup database
- Backup logs
- Upload to S3/storage

# scripts/health_check.sh
- Check all endpoints
- Verify database connection
- Check Wialon sync
```

---

## 📈 MÉTRICAS DE ÉXITO

### Backend Coverage Target
```
Current:  ~15% (solo servicios nuevos testeados)
Target:   95%+ (todos los archivos críticos)

Breakdown:
- Repositories: 95%+
- Services: 95%+
- Orchestrators: 95%+
- API Endpoints: 90%+
- Utils/Helpers: 85%+
```

### Frontend Coverage Target
```
Current:  ~5% (3 tests básicos)
Target:   85%+

Breakdown:
- Components: 85%+
- Pages: 80%+
- Hooks: 90%+
- Utils: 85%+
- Integration: 70%+
```

### E2E Coverage
```
Target: 80% de user flows principales cubiertos

Critical Flows:
- Fleet overview → truck detail
- Risk analysis workflow
- DEF predictions workflow
- Pattern detection workflow
- Alert management
```

---

## 🛠️ HERRAMIENTAS NECESARIAS

### Backend Testing
```bash
pip install pytest pytest-cov pytest-asyncio httpx faker freezegun

# Run coverage:
pytest --cov=src --cov=. --cov-report=html --cov-report=term
```

### Frontend Testing
```bash
npm install -D @testing-library/react @testing-library/jest-dom
npm install -D @testing-library/user-event vitest @vitest/ui
npm install -D @playwright/test

# Run coverage:
npm run test -- --coverage
```

---

## 📅 TIMELINE ESTIMADO

| Fase | Tiempo | Prioridad |
|------|--------|-----------|
| Fase 1: Backend Core Tests | 8-10h | CRÍTICA |
| Fase 2: Frontend Components | 6-8h | ALTA |
| Fase 3: Frontend Tests | 8-10h | ALTA |
| Fase 4: E2E Tests | 4-6h | MEDIA |
| Fase 5: Deployment Scripts | 2-3h | BAJA |
| **TOTAL** | **28-37h** | **~4-5 días** |

---

## 🚀 PRÓXIMOS PASOS INMEDIATOS

### Paso 1: Confirmar Prioridad
¿Qué atacamos primero?
1. Backend tests (coverage crítico)
2. Frontend components (visualización)
3. Ambos en paralelo

### Paso 2: Setup Testing
```bash
# Backend
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
pip install pytest pytest-cov pytest-asyncio httpx
mkdir -p tests/{repositories,services,api,e2e}

# Frontend
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend
npm install -D @testing-library/react @testing-library/jest-dom vitest
mkdir -p tests/{components,pages,hooks,integration}
```

### Paso 3: Empezar Testing
Orden sugerido:
1. ✅ Repositories (fundación)
2. ✅ Services (lógica core)
3. ✅ API endpoints (interfaz)
4. ✅ Frontend components (UX)
5. ✅ E2E (validación completa)

---

## 💡 RECOMENDACIONES

1. **Coverage Incremental**: No intentar 100% de golpe
   - Target inicial: 70% backend, 60% frontend
   - Luego aumentar gradualmente

2. **Mock Wialon API**: Para tests consistentes
   - Crear fixtures de respuestas reales
   - No depender de API externa

3. **CI/CD Integration**: Una vez con tests
   - GitHub Actions / GitLab CI
   - Run tests on every commit
   - Block merges if coverage drops

4. **Test Data**: Usar datos reales anonimizados
   - Exportar subset de fuel_copilot_local
   - Crear database de testing

5. **Documentation**: Tests sirven de documentación
   - Nombres descriptivos
   - Comments explicando edge cases

---

**¿Empezamos con Fase 1 (Backend Tests) o Fase 2 (Frontend Components)?**
