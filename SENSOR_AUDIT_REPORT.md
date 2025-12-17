# 🔍 SENSOR AUDIT REPORT - Wialon vs Dashboard
**Generated:** December 17, 2025  
**Purpose:** Identify ALL missing sensors between Wialon and Dashboard

---

## 📊 EXECUTIVE SUMMARY

**Problem:** Dashboard muestra N/A para muchos sensores que Beyond/Wialon SÍ reporta.

**Root Cause:** Múltiples archivos de sync con configuraciones diferentes + tabla incompleta.

**Files Involved:**
- `wialon_full_sync_service.py` (525 lines) - ⚠️ Más completo, 33 sensores
- `sensor_cache_updater.py` (349 lines) - ⚠️ Versión antigua, menos sensores
- `truck_sensors_cache` table - ❌ Tabla limitada (sin odometer, etc.)
- `api_v2.py` endpoint `/trucks/{id}/sensors` - ❌ No retorna todos los campos

---

## 🔴 SENSORES CONFIRMADOS FALTANTES

### **CRÍTICOS** (Mostrados en dashboard pero con N/A):
1. ✅ **odometer** - Dashboard muestra pero usa datos viejos de `/trucks`, NO de sensores real-time
2. ✅ **barometric_pressure** - Está en cache pero API no lo retorna correctamente

### **DE ALTO VALOR** (En Wialon pero no en dashboard):
3. ❌ **engine_load_pct** - Carga del motor (eficiencia)
4. ❌ **oil_pressure** - Presión de aceite (mantenimiento predictivo)
5. ❌ **oil_temp** - Temperatura aceite
6. ❌ **oil_level** - Nivel aceite
7. ❌ **def_temp** - Temperatura DEF
8. ❌ **def_quality** - Calidad DEF
9. ❌ **throttle_position** - Posición acelerador
10. ❌ **turbo_pressure** - Presión turbo
11. ❌ **fuel_pressure** - Presión combustible
12. ❌ **dpf_pressure** - Presión DPF
13. ❌ **dpf_soot_level** - Nivel hollín DPF
14. ❌ **dpf_ash_level** - Nivel ceniza DPF
15. ❌ **dpf_status** - Estado DPF
16. ❌ **egr_position** - Posición válvula EGR
17. ❌ **egr_temp** - Temperatura EGR
18. ❌ **alternator_status** - Estado alternador
19. ❌ **vehicle_speed** - Velocidad vehículo
20. ❌ **transmission_temp** - Temperatura transmisión
21. ❌ **transmission_pressure** - Presión transmisión
22. ❌ **current_gear** - Marcha actual
23. ❌ **heading** - Dirección GPS

---

## 📋 ANÁLISIS DETALLADO

### **Archivo: `wialon_full_sync_service.py`** (EL BUENO - 33 sensores)
```python
# Sensores que SÍ captura:
- oil_pressure, oil_temp
- coolant_temp
- def_level, def_temp, def_quality
- rpm, throttle_position, turbo_pressure, intake_temp
- fuel_rate, fuel_pressure, fuel_temp
- dpf_pressure, dpf_soot_level, dpf_ash_level, dpf_status
- egr_position, egr_temp
- ambient_temp, barometric_pressure
- battery_voltage, alternator_status
- vehicle_speed, odometer, engine_hours, idle_hours
- latitude, longitude, altitude, heading
- transmission_temp, transmission_pressure, current_gear
```

### **Tabla: `truck_sensors_cache`** (LIMITADA - ~25 campos)
```sql
-- Tiene:
oil_pressure_psi, oil_temp_f, oil_level_pct ✅
def_level_pct ✅
engine_load_pct, rpm, coolant_temp_f, coolant_level_pct ✅
gear, brake_active ✅
intake_pressure_bar, intake_temp_f, intercooler_temp_f ✅
fuel_temp_f, fuel_level_pct, fuel_rate_gph ✅
ambient_temp_f, barometric_pressure_inhg ✅
voltage, backup_voltage ✅
engine_hours, idle_hours, pto_hours ✅
total_idle_fuel_gal, total_fuel_used_gal ✅
dtc_count, dtc_code ✅
latitude, longitude, speed_mph, altitude_ft ✅

-- FALTAN:
odometer_mi ❌ (CRÍTICO - causa N/A en dashboard)
def_temp_f, def_quality ❌
throttle_position_pct ❌
turbo_pressure_psi ❌
fuel_pressure_psi ❌
dpf_pressure_psi, dpf_soot_pct, dpf_ash_pct, dpf_status ❌
egr_position_pct, egr_temp_f ❌
alternator_status ❌
transmission_temp_f, transmission_pressure_psi ❌
heading_deg ❌
```

### **API Endpoint: `/trucks/{id}/sensors`** (INCOMPLETO)
```python
# Retorna ~25 campos básicos
# NO retorna odometer ❌
# Mapeo de nombres inconsistente (barometric_pressure_inhg vs barometer)
```

---

## 🛠️ SOLUCIÓN PROPUESTA

### **Plan de Fix Universal:**

#### **PASO 1: Actualizar Tabla `truck_sensors_cache`**
```sql
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS odometer_mi DECIMAL(12,2) COMMENT 'Odometer miles';
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS def_temp_f DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS def_quality DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS throttle_position_pct DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS turbo_pressure_psi DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS fuel_pressure_psi DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_pressure_psi DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_soot_pct DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_ash_pct DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS dpf_status VARCHAR(20);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS egr_position_pct DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS egr_temp_f DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS alternator_status VARCHAR(20);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS transmission_temp_f DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS transmission_pressure_psi DECIMAL(10,2);
ALTER TABLE truck_sensors_cache ADD COLUMN IF NOT EXISTS heading_deg DECIMAL(10,2);
```

#### **PASO 2: Estandarizar en `wialon_full_sync_service.py`**
- ✅ Ya tiene todos los sensores
- Solo necesita actualizar el INSERT para incluir nuevos campos

#### **PASO 3: Actualizar API `/trucks/{id}/sensors`**
- Agregar TODOS los campos nuevos al response
- Mapeo consistente de nombres

#### **PASO 4: Eliminar `sensor_cache_updater.py`**
- Es redundante y está obsoleto
- Solo usar `wialon_full_sync_service.py`

---

## ⚙️ DEPLOYMENT

### **Servicios a Reiniciar (EN VM):**
```bash
# SSH a VM
ssh tomasruiz@20.127.200.135

# Detener servicio viejo
sudo systemctl stop sensor_cache_updater

# Ejecutar migration
cd /var/fuel-analytics-backend
python migrations/add_missing_sensors.py

# Reiniciar servicio correcto
sudo systemctl restart wialon_full_sync

# Verificar
sudo systemctl status wialon_full_sync
tail -f /var/log/wialon_sync.log
```

---

## ✅ RESULTADO ESPERADO

**Antes:**
- Dashboard muestra N/A para odometer, barometer, etc.
- DTCs sin descripciones (ya fixeado ✅)

**Después:**
- TODO sensor de Wialon visible en dashboard
- Sin N/A innecesarios
- Datos en tiempo real (<30 segundos)
- Frontend rebuildeado (ya hecho ✅)

---

## 📝 NOTAS

1. **Frontend ya rebuildeado** con TruckDTCs component ✅
2. **Backend necesita** migration + restart en VM
3. **Testing** verificar 2-3 camiones random en dashboard después del deploy
4. **Documentación** actualizar WIALON_SENSOR_MAPPING.py con estado final

---

**End of Report**
