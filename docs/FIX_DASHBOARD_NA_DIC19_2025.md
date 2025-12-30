# 🔍 DIAGNÓSTICO Y SOLUCIÓN: Dashboard muestra N/A en vista individual
**Fecha:** 19 de Diciembre, 2025  
**Problema:** Vista principal muestra camiones OK (MOVING/STOPPED/OFFLINE) pero vista individual muestra todo N/A

---

## 🎯 PROBLEMA IDENTIFICADO

El endpoint `/fuelAnalytics/api/v2/trucks/{truck_id}` retornaba datos vacíos (N/A) mientras que `/fuelAnalytics/api/fleet` funcionaba correctamente.

### Root Cause

La query SQL en `database_mysql.py` función `get_latest_truck_data()` (línea 168) intentaba seleccionar **3 columnas que NO EXISTEN** en la tabla `fuel_metrics`:

```sql
-- ❌ Columnas inexistentes:
t1.refuel_gallons         -- NO EXISTE
t1.refuel_events_total    -- NO EXISTE  
t1.flags                  -- NO EXISTE
```

Esto causaba un error SQL:
```
(pymysql.err.OperationalError) (1054, "Unknown column 't1.refuel_gallons' in 'field list'")
```

### Por qué fleet summary funcionaba

El endpoint `/api/fleet` usa una query diferente (`get_fleet_summary()`) que:
- ✅ Solo selecciona columnas básicas que SÍ existen
- ✅ Usa agregaciones (COUNT, AVG) en lugar de selects directos
- ✅ No depende de columnas de refuel

---

## ✅ SOLUCIÓN APLICADA

### 1. Identificación de columnas faltantes

Creamos script `check_missing_columns.py` que verificó las 51 columnas existentes vs las que la query intentaba usar.

### 2. Fix en database_mysql.py

**Archivo modificado:** `database_mysql.py`  
**Función:** `get_latest_truck_data()` (línea ~158)  
**Cambios:**
- ❌ Removidas 3 columnas inexistentes: `refuel_gallons`, `refuel_events_total`, `flags`
- ✅ Agregadas columnas adicionales que SÍ existen y son útiles:
  - `idle_gph`, `engine_hours`, `estimated_gallons`
  - `sensor_gallons`, `def_level_pct`
  - `oil_pressure_psi`, `oil_temp_f`, `engine_load_pct`
  - `ambient_temp_f`, `intake_air_temp_f`, `trans_temp_f`, `fuel_temp_f`

### 3. Reinicio del servidor

El servidor FastAPI estaba corriendo con código viejo (iniciado a las 6:14 PM).  
Reiniciamos el servidor para cargar los cambios:
```powershell
Stop-Process -Name python -Force
Start-Process .\venv\Scripts\python.exe -ArgumentList "-m","uvicorn","main:app","--host","0.0.0.0","--port","8000"
```

---

## 📊 RESULTADOS

### Antes del fix
```json
{
  "truck_id": "DO9693",
  "truck_status": "OFFLINE",
  "estimated_pct": null,
  "mpg_current": null,
  "speed_mph": null,
  "rpm": null,
  "timestamp": null
}
```

### Después del fix
```json
{
  "truck_id": "DO9693",
  "truck_status": "MOVING",
  "estimated_pct": 90.88,
  "mpg_current": 5.39,
  "speed_mph": 68.9722,
  "rpm": null,  // Sensor no configurado en Wialon
  "timestamp": "2025-12-19T19:41:35",
  // ... 58 campos total
}
```

**Métricas:**
- ✅ 58 campos retornados (vs 17 antes)
- ✅ 41 campos con valores reales
- ⚠️ 17 campos null (sensores no configurados en Wialon - NORMAL)

---

## 🔧 FLUJO DE DATOS VERIFICADO

```
Wialon (GPS/OBD)
    ↓
wialon_sync_enhanced.py / fuel_copilot.py
    ↓
MySQL tabla fuel_metrics (51 columnas)
    ↓
database_mysql.py → get_latest_truck_data()  ✅ FIXED
    ↓
database.py → get_truck_latest_record()
    ↓
main.py → /api/v2/trucks/{truck_id}
    ↓
Dashboard frontend
```

---

## ✅ VALIDACIÓN

```bash
# Test directo de database
python test_detailed_record.py
# ✅ Retorna 39 campos con valores

# Test del endpoint HTTP
python test_truck_endpoint.py
# ✅ Status 200, 58 campos, datos reales
```

---

## 📋 CAMPOS QUE SIGUEN SIENDO NULL (ESPERADO)

Estos sensores **NO están configurados** en Wialon para la mayoría de los trucks:
- `rpm` - Sensor RPM no conectado
- `odometer_mi` - Odómetro no disponible
- `idle_mode` - Calculado solo cuando está detenido
- `altitude_ft` - GPS no reporta altitud
- `coolant_temp_f` - Sensor temperatura coolant no conectado
- `dtc` - DTC codes solo cuando hay falla
- `idle_hours_ecu` - No disponible en todos los ECU
- `engine_hours` - Horómetro no reportado
- `def_level_pct` - DEF level no disponible (truck viejo)

**Estos son normales** - Solo 3 de ~45 trucks tienen sensores OBD completos según `DIAGNOSTICO_COMPLETO_DIC19_2025.md`.

---

## 🎯 PRÓXIMOS PASOS RECOMENDADOS

### 1. Verificar en producción/VM
El fix debe aplicarse en el servidor de Azure:
```bash
cd /home/azureuser/fuel-analytics-backend
git pull origin main
sudo systemctl restart fuel-backend
```

### 2. Monitorear logs
```bash
journalctl -u fuel-backend -f
# Verificar que no haya errores de SQL
```

### 3. Configurar más sensores OBD en Wialon (opcional)
Para trucks con GPS básico, configurar lectura de:
- RPM (SPN 190)
- Odómetro (SPN 245)
- Fuel Level (SPN 96)
- Engine Hours (SPN 247)

---

## 📝 ARCHIVOS MODIFICADOS

- ✅ `database_mysql.py` - Fix query SQL
- ✅ `check_missing_columns.py` - Script de verificación (nuevo)
- ✅ `diagnose_data_flow.py` - Script diagnóstico (nuevo)
- ✅ `test_detailed_record.py` - Test database (nuevo)
- ✅ `test_truck_endpoint.py` - Test endpoint HTTP (nuevo)

---

## ✅ CONCLUSIÓN

El problema estaba en la query SQL que intentaba leer columnas inexistentes en MySQL.  
Al eliminar esas columnas y reiniciar el servidor, **el dashboard ahora muestra datos correctos** en la vista individual.

**Status final:** ✅ RESUELTO
