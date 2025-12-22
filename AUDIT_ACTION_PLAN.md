# 🔧 PLAN DE ACCIÓN - AUDITORÍA DIC 22, 2025

## ✅ COMPLETADO (Hoy)

### 1. MPG Calculation Fix
- **Problema**: Consumption fallback muy bajo (25 L/h → MPG inflado 9-10)
- **Solución**: Actualizado fallback realista para camiones pesados:
  - Highway (60+ mph): 44 L/h → 6 MPG ✅
  - Mixed (40-60 mph): 27 L/h → 5.6 MPG ✅
  - City (<40 mph): 18 L/h → 5.2 MPG ✅
- **Commit**: `4e0423c` - fix(mpg): Correct consumption calculation
- **Estado**: Pusheado a main, necesita restart en VM

### 2. Cleanup Script Deshabilitado
- **Problema**: `cleanup_inflated_mpg.py` capea MPG a 7.8
- **Solución**: Renombrado a `.DISABLED` 
- **Commit**: Próximo push
- **Prevención**: Nunca ejecutar este script nuevamente

## 🚨 CRÍTICO - ESTA SEMANA

### FIX-001: Reiniciar Servicio en VM
```bash
# En Windows VM:
cd C:\FuelAnalytics\Backend
git pull origin main
nssm restart FuelSyncService
# Esperar 15-20 min para ver MPG actualizado
```

### SEC-001: Credenciales Hardcodeadas (4-8 horas)
**Archivos afectados** (8 archivos):
- check_lc6799_db.py
- recreate_table.py
- check_metrics_tables.py
- add_idle_gph_column.py
- fix_refuel_events_schema.py
- diagnose_do9693_detailed.py
- full_diagnostic.py
- tools/debug/*.py

**Solución**:
```python
import os
from dotenv import load_dotenv

load_dotenv()
password = os.getenv("LOCAL_DB_PASS")
if not password:
    raise ValueError("LOCAL_DB_PASS not set in environment")
```

### BUG-REF-001: Schema Compatibility VM/Mac (4-6 horas)
**Problema**: Columnas diferentes entre ambientes
- VM: refuel_time, before_pct, after_pct
- Mac: timestamp_utc, fuel_before, fuel_after

**Solución**: Auto-detect environment
```python
def get_schema_config():
    """Detect DB schema version"""
    cursor.execute("SHOW COLUMNS FROM refuel_events")
    columns = [col[0] for col in cursor.fetchall()]
    if 'refuel_time' in columns:
        return 'VM'
    return 'MAC'
```

## 🔶 ALTA PRIORIDAD - ESTE MES

### MEJORA-PM-001: LSTM para RUL Prediction (40-60h)
- Implementar modelo LSTM para Days-to-Failure
- Datasets: oil_pressure, coolant_temp últimos 90 días
- Precision target: >85%

### MEJORA-THEFT-001: ML Isolation Forest (20-30h)
- Reducir falsos positivos en detección de robo
- Features: fuel_drop_gal, time_of_day, geofence, gps_quality
- Target: <5% FP rate

### BUG-MPG-002: Window Thresholds (2-4h)
**Problema actual**:
```python
min_miles: float = 5.0   # Muy restrictivo
min_fuel_gal: float = 0.75
```

**Solución propuesta**:
```python
min_miles: float = 3.0   # Updates más frecuentes
min_fuel_gal: float = 0.5
```

## 📊 MÉTRICAS DE PROGRESO

| Categoría | Bugs Total | Corregidos | Pendientes |
|-----------|-----------|------------|------------|
| Críticos | 12 | 2 | 10 |
| Altos | 28 | 0 | 28 |
| Medios | 45+ | 0 | 45+ |
| Seguridad | 8 | 1 | 7 |

## 🎯 OBJETIVOS SEMANA 1
- [x] Fix MPG calculation
- [x] Disable cleanup script  
- [ ] Restart VM service
- [ ] Remove hardcoded credentials
- [ ] Fix schema compatibility

## 📅 ROADMAP

**Semana 2-3**: Refactoring grande
- Dividir main.py (6,822 líneas)
- Dividir database_mysql.py (6,246 líneas)
- Extraer constantes de magic numbers

**Mes 2**: ML Enhancements
- LSTM para maintenance prediction
- Isolation Forest para theft detection
- Extended Kalman Filter

**Mes 3**: Testing & Observability
- Incrementar coverage a 80%
- Prometheus metrics
- Structured logging

---
**Última Actualización**: Dec 22, 2025 06:30 UTC  
**Responsable**: Tomás Ruiz / Fleet Booster
