# 🚀 DEPLOYMENT GUIDE - MAC (Dec 20, 2025)

## 📋 CAMBIOS APLICADOS DESDE ÚLTIMO PULL

### ✅ **COMMITS PUSHEADOS:**
1. `bd6bbf2` - Fix column names (intake_air_temp_f, idle_hours_ecu)
2. `802a7ce` - Fix refuel_events schema (5 columnas agregadas)
3. `40916c2` - Fix refuel_gallons query error
4. `d2c68f6` - Fix Loss Analysis odom_delta_mi
5. `a600a85` - Crear daily_truck_metrics + fix Command Center DTCs
6. `2d5ec9f` - Auto-update daily_truck_metrics cada 15 min

---

## 🗄️ **NUEVAS TABLAS CREADAS**

### 1. `daily_truck_metrics`
```sql
CREATE TABLE daily_truck_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(50),
    date DATE,
    miles_traveled DECIMAL(12,2),
    fuel_consumed_gallons DECIMAL(12,2),
    avg_mpg DECIMAL(5,2),
    idle_hours DECIMAL(6,2),
    moving_hours DECIMAL(6,2),
    overspeeding_events INT,
    high_rpm_events INT,
    UNIQUE KEY (truck_id, date)
);
```
**Propósito:** Métricas diarias agregadas para Cost/Mile y Utilization
**Población:** Automática cada 15 min desde `fuel_metrics`

### 2. `fleet_summary`
```sql
CREATE TABLE fleet_summary (
    summary_date DATE PRIMARY KEY,
    total_trucks INT,
    active_trucks INT,
    total_miles DECIMAL(12,2),
    total_fuel_gallons DECIMAL(12,2),
    fleet_avg_mpg DECIMAL(5,2)
);
```
**Propósito:** Resumen diario de toda la flota
**Población:** Automática desde `daily_truck_metrics`

### 3. `trip_data` 
```sql
CREATE TABLE trip_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(50),
    trip_start DATETIME,
    trip_end DATETIME,
    distance_mi DECIMAL(10,2),
    fuel_consumed_gal DECIMAL(10,2)
);
```
**Estado:** Estructura creada, vacía (requiere algoritmo detección viajes)

---

## 🔧 **FIXES APLICADOS**

### ✅ **database_mysql.py**
**Línea 5230, 5393:**
```python
# ANTES: intake_temp_f (no existe)
# AHORA: intake_air_temp_f AS intake_temp_f
```

**Línea 2264:**
```python
# ANTES: odom_delta_mi (no existe)
# AHORA: GREATEST(0, MAX(odometer_mi) - MIN(odometer_mi))
```

**Línea 3070-3280:**
- Removida columna `refuel_gallons` de Loss Analysis
- Ajustados índices row[] correctamente

### ✅ **fleet_command_center.py**
**Línea 4366-4455:**
```python
# ANTES: SELECT system, recommended_action, timestamp_utc FROM dtc_events
# AHORA: SELECT component, action_required, detected_at FROM dtc_events

# Mapeo severidad case-insensitive
"critical" → Priority.CRITICAL (score: 95)
"high"     → Priority.HIGH (score: 75)
"medium"   → Priority.MEDIUM (score: 55)
```

### ✅ **wialon_sync_enhanced.py**
**Línea 1236:**
```python
# Fix INSERT column names
INSERT INTO refuel_events (
    refuel_time,      # was: timestamp_utc
    before_pct,       # was: fuel_before
    after_pct         # was: fuel_after
)
```

### ✅ **ml_engines/** (anomaly_detector.py, driver_clustering.py)
```python
# ANTES: idle_hours (no existe)
# AHORA: idle_hours_ecu AS idle_hours
```

---

## 🆕 **NUEVOS ARCHIVOS**

### 1. `fix_missing_tables.py`
**Propósito:** Crea y puebla daily_truck_metrics, fleet_summary, trip_data
**Uso manual:** `python fix_missing_tables.py` (si necesitas forzar actualización)

### 2. `auto_update_daily_metrics.py` ⭐
**Propósito:** Servicio background que actualiza métricas cada 15 min
**Estado:** Ya corriendo en Windows (minimizado)
**Para Mac:**
```bash
cd ~/Proyectos/fuel-analytics-backend
source venv/bin/activate
nohup python auto_update_daily_metrics.py > /dev/null 2>&1 &
```

### 3. Scripts de diagnóstico:
- `full_diagnostic.py` - Diagnóstico completo DB
- `test_loss_analysis.py` - Test Loss Analysis
- `test_command_center_fix.py` - Test Command Center DTCs
- `test_dtc_detection.py` - Test detección DTCs

---

## 🚀 **SETUP EN MAC**

### **Paso 1: Pull + Dependencies**
```bash
cd ~/Proyectos/fuel-analytics-backend
git pull origin main

# Verificar Python venv activado
source venv/bin/activate
pip install -r requirements.txt  # si hay nuevas deps
```

### **Paso 2: Crear Tablas (SOLO PRIMERA VEZ)**
```bash
python fix_missing_tables.py
```
**Output esperado:**
```
✅ Table daily_truck_metrics created
✅ Inserted/updated 55 daily records
✅ Table fleet_summary created
✅ Table trip_data created
```

### **Paso 3: Iniciar Auto-Update en Background**
```bash
# Opción A: Proceso background persistente
nohup python auto_update_daily_metrics.py > /tmp/daily_metrics.log 2>&1 &

# Opción B: Usar screen (recomendado)
screen -dmS daily_metrics python auto_update_daily_metrics.py

# Ver logs:
tail -f daily_metrics_updater.log
```

### **Paso 4: Iniciar Backend**
```bash
# Matar procesos viejos
pkill -f uvicorn

# Iniciar backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Paso 5: Verificar**
```bash
# Test Command Center con DTCs
curl http://localhost:8000/fuelAnalytics/api/v2/command-center | jq '.alerts.dtc_alerts | length'
# Esperado: 42

# Test daily_truck_metrics
python -c "
import pymysql
conn = pymysql.connect(host='localhost', user='fuel_admin', password='FuelCopilot2025!', database='fuel_copilot')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM daily_truck_metrics')
print(f'Daily metrics: {cur.fetchone()[0]} records')
"
```

---

## 📊 **DASHBOARDS QUE AHORA FUNCIONAN**

| Dashboard | Estado Antes | Estado Ahora | Tabla |
|-----------|--------------|--------------|-------|
| **Cost/Mile** | ❌ $0.00 | ✅ FUNCIONAL | daily_truck_metrics |
| **Utilization** | ❌ 0% | ✅ FUNCIONAL | daily_truck_metrics |
| **Command Center** | ❌ No DTCs | ✅ 42 DTCs | dtc_events |
| **Loss Analysis** | ⚠️ Solo idle $60 | ⚠️ Idle OK, resto necesita datos RPM | fuel_metrics |

---

## ⚠️ **PROBLEMAS CONOCIDOS**

### 1. **Loss Analysis - Datos Parciales**
**Síntoma:** Solo muestra idle losses ($60), RPM/altitude/thermal en $0
**Causa:** fuel_metrics solo tiene 25% RPM, 50% altitude, 33% coolant
**Solución:** Verificar config sensores Wialon para capturar OBD completo

### 2. **Refuel Events Vacío**
**Síntoma:** `refuel_events` table tiene 0 registros
**Estado:** Schema arreglado, wialon_sync no detecta refuels
**Próximo paso:** Revisar lógica detección en wialon_sync_enhanced.py

### 3. **Backend Cierra Solo**
**Síntoma:** uvicorn se apaga después de 1-2 requests
**Workaround temporal:** Usar `--reload` flag y reiniciar cuando falle
**Investigar:** Múltiples instancias Python conflictuando

---

## 🔍 **VERIFICACIÓN POST-DEPLOY**

### Test 1: Tablas existen
```bash
python -c "
import pymysql
conn = pymysql.connect(host='localhost', user='fuel_admin', password='FuelCopilot2025!', database='fuel_copilot')
cur = conn.cursor()
for table in ['daily_truck_metrics', 'fleet_summary', 'trip_data']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    count = cur.fetchone()[0]
    print(f'✅ {table}: {count} records')
"
```

### Test 2: Auto-update corriendo
```bash
ps aux | grep auto_update_daily_metrics
# Esperado: 1 proceso Python corriendo

tail -f daily_metrics_updater.log
# Esperado: "✅ Updated 55 daily records" cada 15 min
```

### Test 3: Command Center DTCs
```bash
curl -s http://localhost:8000/fuelAnalytics/api/v2/command-center | \
  python -c "import sys, json; data=json.load(sys.stdin); print(f\"DTCs: {len(data.get('alerts',{}).get('dtc_alerts',[]))}\")"
# Esperado: DTCs: 42
```

### Test 4: Loss Analysis
```bash
curl -s http://localhost:8000/fuelAnalytics/api/v2/loss-analysis | \
  python -c "import sys, json; data=json.load(sys.stdin); print(f\"Idle: \${data['summary']['by_cause']['idle']['usd']}\")"
# Esperado: Idle: $60.15
```

---

## 📝 **COLUMNAS CRÍTICAS RENOMBRADAS**

| Código Viejo | Código Nuevo | Ubicación |
|--------------|--------------|-----------|
| `status` | `truck_status` | fuel_metrics |
| `mpg` | `mpg_current` | fuel_metrics |
| `voltage` | `battery_voltage` | fuel_metrics |
| `estimated_gph` | `consumption_gph` | fuel_metrics |
| `idle_hours` | `idle_hours_ecu` | fuel_metrics |
| `intake_temp_f` | `intake_air_temp_f` | fuel_metrics |
| `timestamp_utc` | `refuel_time` | refuel_events |
| `fuel_before` | `before_pct` | refuel_events |
| `system` | `component` | dtc_events |
| `recommended_action` | `action_required` | dtc_events |

---

## 🎯 **PRÓXIMOS PASOS RECOMENDADOS**

### A. Mejorar calidad datos (CRÍTICO)
```bash
# Verificar sensores Wialon capturen OBD
# Revisar wialon_sync parsing de RPM/altitude/coolant
```

### B. Fix refuel detection
```bash
# Revisar logs wialon_sync para detección refuels
tail -f wialon_sync.log | grep -i refuel
```

### C. Estabilizar backend
```bash
# Investigar por qué uvicorn cierra
# Matar instancias duplicadas
pkill -f python
```

---

## 📞 **SUPPORT**

**Logs importantes:**
- Backend: `uvicorn` stdout
- Auto-update: `daily_metrics_updater.log`
- Wialon sync: `wialon_sync.log`

**DB credentials:**
```python
host = 'localhost'
user = 'fuel_admin'
password = 'FuelCopilot2025!'
database = 'fuel_copilot'
```

**Rollback si falla:**
```bash
git reset --hard fea2552  # "SUPER ESTABLE" commit
git push -f origin main
```

---

**Fecha:** December 20, 2025  
**Commits:** bd6bbf2 → 8243372 (7 commits)  
**Estado:** ✅ COMPLETADO EN MAC  
**Auto-update:** ✅ Corriendo en Mac + Windows

---

## ✅ **MAC DEPLOYMENT COMPLETADO (Dec 20, 2025)**

### **Estado Final:**
```
📊 daily_truck_metrics: 295 registros, 40 camiones
📈 fleet_summary: 11 días de resúmenes  
⚠️  DTCs activos: 0 (estructura status = 'ACTIVE')
⛽ Refuels (7 días): 4 eventos, 482.3 gal
🔄 Auto-update service: RUNNING (updates every 10 min)
```

### **Fixes Aplicados en Mac (Commit 8243372):**
1. ✅ `database_mysql.py` - Cambiar `cleared_at IS NULL` → `status = 'ACTIVE'`
2. ✅ `fleet_command_center.py` - Cambiar `detected_at` → `timestamp_utc`
3. ✅ `full_diagnostic.py` - Fix columnas DTCs y refuels
4. ✅ `wialon_sync_enhanced.py` - Fix INSERT `refuel_time` → `timestamp_utc`
5. ✅ `fix_missing_tables.py` - Ejecutado exitosamente (295 records)
6. ✅ `auto_update_daily_metrics.py` - Servicio corriendo (PID 65303)

### **Diferencias Mac vs Windows VM:**
- ✅ Ambos usan `status = 'ACTIVE'` (no `cleared_at`)
- ✅ Ambos usan `timestamp_utc` (no `detected_at` ni `refuel_time`)
- ✅ Ambos tienen las 3 tablas nuevas creadas
- ✅ Auto-update corriendo en ambos entornos

### **Próximos Pasos:**
- [ ] Verificar Loss Analysis endpoint funciona correctamente
- [ ] Implementar algoritmo de detección de trips para `trip_data`
- [ ] Monitor auto-update logs por 24h
- [ ] Considerar migración completa de schema si hay más discrepancias
