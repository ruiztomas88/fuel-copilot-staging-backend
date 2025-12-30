# 🔍 AUDITORÍA DE CONSISTENCIA DE SENSORES - Dic 20, 2025

## ✅ VALIDACIÓN COMPLETADA

### 1. Estructura de Columnas ✅
- **INSERT (wialon_sync_enhanced.py)**: 52 columnas
- **SELECT (api_v2.py)**: 35 columnas  
- **Compatibilidad**: 100% - Todas las columnas del API están siendo insertadas
- **Columnas adicionales**: 17 (disponibles para uso futuro)

### 2. Nombres de Sensores Wialon Corregidos ✅

Se identificaron y corrigieron 4 inconsistencias entre los nombres RAW de Wialon:

| Columna DB | ❌ Nombre Incorrecto | ✅ Nombre Correcto (Wialon) |
|------------|---------------------|----------------------------|
| `odometer_mi` | `odometer` | `odom` |
| `turbo_pressure_psi` | `boost` | `turbo_press` |
| `dpf_pressure_psi` | `dpf_diff_press` | `dpf_press` |
| `alternator_status` | `alternator` | `alternator_status` |

**Referencia**: Los nombres correctos provienen de `sensor_cache_updater.py` que ha estado funcionando correctamente.

### 3. Mapeo Completo de Sensores Wialon → Database

```
📡 SENSORES WIALON (RAW) → 🗄️ COLUMNAS DATABASE

Aceite:
  oil_press → oil_pressure_psi
  oil_temp → oil_temp_f
  oil_lvl → oil_level_pct

DEF:
  def_level → def_level_pct
  def_temp → def_temp_f
  def_quality → def_quality

Motor:
  engine_load → engine_load_pct
  rpm → rpm
  cool_temp → coolant_temp_f
  cool_lvl → coolant_level_pct

Transmisión & Frenos:
  gear → gear
  brake_switch → brake_active (convertido a 0/1)

Aire/Intake:
  intake_pressure → intake_pressure_bar
  intk_t → intake_temp_f
  intrclr_t → intercooler_temp_f

Combustible:
  fuel_t → fuel_temp_f
  fuel_lvl → fuel_level_pct
  fuel_rate → fuel_rate_gph
  fuel_press → fuel_pressure_psi

Ambiental:
  ambient_temp → ambient_temp_f
  barometer → barometric_pressure_inhg

Eléctrico:
  pwr_ext → voltage
  pwr_int → backup_voltage

Operacional:
  engine_hours → engine_hours
  idle_hours → idle_hours
  pto_hours → pto_hours
  total_idle_fuel → total_idle_fuel_gal
  total_fuel_used → total_fuel_used_gal

DTC:
  dtc → dtc_count
  dtc_code → dtc_code

GPS:
  latitude → latitude
  longitude → longitude
  speed → speed_mph
  altitude → altitude_ft
  odom → odometer_mi ✅ CORREGIDO
  course → heading_deg

Performance:
  throttle_pos → throttle_position_pct
  turbo_press → turbo_pressure_psi ✅ CORREGIDO

DPF:
  dpf_press → dpf_pressure_psi ✅ CORREGIDO
  dpf_soot → dpf_soot_pct
  dpf_ash → dpf_ash_pct
  dpf_status → dpf_status

EGR:
  egr_pos → egr_position_pct
  egr_temp → egr_temp_f

Sistemas Eléctricos:
  alternator_status → alternator_status ✅ CORREGIDO

Transmisión:
  trans_temp → transmission_temp_f
  trans_press → transmission_pressure_psi
```

### 4. Consolidación de Servicios ✅

**Antes (REDUNDANTE):**
- `wialon_sync_enhanced.py` → lee Wialon cada 15s → guarda en `fuel_metrics`
- `sensor_cache_updater.py` → lee Wialon cada 30s → guarda en `truck_sensors_cache`

**Ahora (EFICIENTE):**
- `wialon_sync_enhanced.py` → lee Wialon cada 15s → guarda en **AMBAS** tablas
- `sensor_cache_updater.py` → **YA NO ES NECESARIO** ✅

### 5. Archivos que Leen truck_sensors_cache

1. **api_v2.py** (línea 585)
   - Endpoint: `/v2/real_time_truck_data/{truck_id}`
   - Usa 35 columnas
   - ✅ Consistencia validada

2. **diagnose_data_flow.py** (línea 185)
   - Script de diagnóstico
   - Lee toda la tabla
   - ✅ No afectado

### 6. Estado Actual del Sistema

```bash
✅ wialon_sync_enhanced.py está corriendo (PID verificado)
✅ truck_sensors_cache se está actualizando cada 15s
✅ Logs muestran: "📋 Updated truck_sensors_cache for {truck_id}"
✅ Datos recientes verificados en la tabla
```

### 7. Próximos Pasos Recomendados

1. ✅ **COMPLETADO**: Corregir nombres de sensores Wialon
2. ✅ **COMPLETADO**: Consolidar actualización de cache en wialon_sync_enhanced.py
3. 🔜 **PENDIENTE**: Detener y deprecar sensor_cache_updater.py
4. 🔜 **PENDIENTE**: Mover sensor_cache_updater.py a carpeta `_deprecated/`
5. 🔜 **PENDIENTE**: Actualizar documentación del sistema

### 8. Validación Final

Ejecutar los siguientes scripts para confirmar todo:

```bash
# Validar estructura de columnas
python3 validate_sensor_names.py

# Verificar datos recientes
mysql -u fuel_admin -p'FuelCopilot2025!' fuel_copilot \
  -e "SELECT truck_id, timestamp, rpm, odometer_mi 
      FROM truck_sensors_cache 
      WHERE timestamp > DATE_SUB(NOW(), INTERVAL 5 MINUTE) 
      LIMIT 5"

# Confirmar proceso activo
ps aux | grep wialon_sync | grep -v grep
```

---

**Generado**: Diciembre 20, 2025  
**Autor**: GitHub Copilot  
**Estado**: ✅ Validación Completa - Sin Conflictos
