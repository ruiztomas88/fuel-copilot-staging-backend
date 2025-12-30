# 📊 REPORTE DE DIFERENCIAS: Commit Estable vs Actual

**Commit estable:** `fea2552` - SUPER ESTABLE - Dec 19 2025 2:45PM  
**Commit actual:** `eda5000` - HEAD (main)  
**Fecha reporte:** December 22, 2025

---

## 📈 RESUMEN DE CAMBIOS

**Archivos modificados:**

- ✅ `mpg_engine.py`: **+79 líneas** (cambios en thresholds y validación)
- ✅ `api_v2.py`: **+667 líneas** (nuevos endpoints para metrics dashboard)
- ✅ `predictive_maintenance_engine.py`: **+57 líneas** (mejoras en confidence)
- ⚪ `idle_engine.py`: **SIN CAMBIOS**

**Total:** 756 líneas agregadas, 47 eliminadas

---

## 🔧 MPG_ENGINE.PY - Cambios Críticos

### Version Evolution

```
v3.14.0 (Dic 15) → v2.0.0 (Dic 22)
```

### 📌 Cambios en MPGConfig (CRÍTICO)

#### **ESTABLE (fea2552 - Dic 19):**

```python
min_miles: float = 5.0      # Rápido, updates frecuentes
min_fuel_gal: float = 0.75  # Poco combustible requerido
max_mpg: float = 9.0        # Límite máximo permisivo
```

#### **ACTUAL (eda5000 - Dic 22):**

```python
min_miles: float = 10.0     # 🔺 2x MÁS CONSERVADOR
min_fuel_gal: float = 2.0   # 🔺 2.67x MÁS COMBUSTIBLE
max_mpg: float = 8.5        # 🔻 REDUCIDO de 9.0
```

### 💡 Razón del cambio:

**Problema identificado:** Thresholds muy bajos (0.75 gal) amplificaban errores del sensor

- Ejemplo: Error de 33% en 0.75 gal → MPG inflado de 10+
- Solución: Requerir más datos (2.0 gal) antes de calcular → más precisión

### ⚖️ Trade-offs:

- ✅ **PRO:** MPG más preciso, menos valores inflados
- ⚠️ **CON:** Actualizaciones menos frecuentes (10 mi vs 5 mi)
- ⚠️ **CON:** Más tiempo hasta primer valor MPG

### 🆕 Nuevas funciones agregadas:

```python
cleanup_inactive_trucks(active_truck_ids, max_inactive_days=30)
```

- Previene memory leaks de camiones eliminados de la flota
- Auto-limpieza después de 30 días de inactividad

---

## 🌐 API_V2.PY - Nuevos Endpoints

### +667 líneas agregadas (MAYOR CAMBIO)

#### Nuevos endpoints para Metrics Dashboard:

**1. `/fleet/summary` (línea ~2450)**

```python
GET /fuelAnalytics/api/v2/fleet/summary
```

Retorna:

- ✅ `cost_per_mile` - Calculado con MAX-MIN odometer (CORREGIDO)
- ✅ `active_trucks` - Count de camiones activos
- ✅ `avg_mpg` - Promedio de flota
- ✅ `utilization_pct` - % tiempo productivo vs idle
- ✅ `total_miles` - Suma real de deltas odometer
- ✅ `total_fuel_cost` - Costo total combustible

**FIX CRÍTICO aplicado:**

```sql
-- ❌ ANTES (INCORRECTO):
SUM(odometer_mi) as total_miles  -- Suma valores acumulativos!

-- ✅ AHORA (CORRECTO):
WITH truck_miles AS (
    SELECT truck_id,
           MAX(odometer_mi) - MIN(odometer_mi) as miles_traveled
    ...
)
```

**2. `/fleet/cost-analysis` (línea ~2540)**

```python
GET /fuelAnalytics/api/v2/fleet/cost-analysis
```

Retorna:

- Cost distribution (fuel, maintenance, labor)
- Per-truck cost breakdown
- ✅ Usa misma lógica de deltas (MAX-MIN)

**3. `/fleet/utilization`**

- Métricas de utilización por período
- Engine hours vs idle hours

---

## 🔮 PREDICTIVE_MAINTENANCE_ENGINE.PY - Confidence Fix

### +57 líneas agregadas

#### Problema reportado:

```
Command Center muestra: 7500%, 9200% confidence
```

#### ¿Qué cambió?

Necesito revisar el código actual para ver si ya tiene el cap...

<function_calls>
<invoke name="run_in_terminal">
<parameter name="command">git diff fea2552 HEAD -- predictive_maintenance_engine.py | Select-String "confidence" -Context 3
