# COMPARACIÓN DE BASES DE DATOS - fuel_copilot

## RESUMEN EJECUTIVO

**Base HISTÓRICA**: `C:\ProgramData\MySQL\MySQL Server 8.0\Data\fuel_copilot\`
- **28 tablas** (última actualización: 19-dic-2025 9:08 AM)
- **fuel_metrics.ibd**: 140 MB
- Estado: **INACCESIBLE** (MySQL crashea al intentar leerla)

**Base ACTUAL**: `C:\ProgramData\MySQL\data\fuel_copilot\`
- **10 tablas** (creadas: 19-dic-2025 7:38 AM)
- **fuel_metrics.ibd**: 9 MB (386 registros)
- Estado: **FUNCIONANDO**

---

## TABLAS EN BASE HISTÓRICA (28 tablas)

### 1. Tablas de Command Center (7 tablas)
```
✓ cc_algorithm_state            (0.14 MB) - Estado de algoritmos CC
✓ cc_anomaly_history            (0.17 MB) - Historial de anomalías  
✓ cc_correlation_events         (0.16 MB) - Eventos correlacionados
✓ cc_def_history                (0.14 MB) - Historial DEF
✓ cc_maintenance_events         (0.17 MB) - Eventos de mantenimiento
✓ cc_risk_history               (0.16 MB) - Historial de riesgos
✓ command_center_config         (0.16 MB) - Configuración CC
```

### 2. Tablas de Engine Health (5 tablas)
```
✓ engine_health_alerts          (0.19 MB) - Alertas de salud motor
✓ engine_health_baselines       (0.17 MB) - Líneas base
✓ engine_health_notifications   (0.16 MB) - Notificaciones
✓ engine_health_snapshots       (0.17 MB) - Snapshots de salud
✓ engine_health_thresholds      (0.16 MB) - Umbrales configurados
```

### 3. Tablas de Predictive Maintenance (3 tablas)
```
✓ pm_predictions                (0.16 MB) - Predicciones PM
✓ pm_sensor_daily_avg           (0.14 MB) - Promedios diarios sensores
✓ pm_sensor_history             (0.16 MB) - Historial sensores PM
```

### 4. Tablas Principales (6 tablas)
```
✓ fuel_metrics                  (140 MB) ⭐ DATOS PRINCIPALES
✓ dtc_events                    (0.17 MB) - DTCs
✓ refuel_events                 (0.14 MB) - Recargas combustible
✓ truck_history                 (0.14 MB) - Historial camiones
✓ telemetry_data                (0.19 MB) - Datos telemetría
✓ trips                         (0.19 MB) - Viajes
```

### 5. Tablas de Soporte (7 tablas)
```
✓ gps_quality_events            (0.14 MB) - Calidad GPS
✓ j1939_spn_lookup              (0.17 MB) - Lookup códigos J1939
✓ maintenance_alerts            (0.17 MB) - Alertas mantenimiento
✓ maintenance_predictions       (0.17 MB) - Predicciones mantenimiento
✓ truck_health_history          (0.14 MB) - Historial salud camión
✓ truck_sensors_cache           (0.16 MB) - Cache sensores
✓ voltage_events                (0.16 MB) - Eventos de voltaje
```

---

## TABLAS EN BASE ACTUAL (10 tablas)

```
✓ command_center_history                 - Historial CC (versión simplificada)
✓ dtc_events                             - DTCs ✅ EXISTE EN HISTÓRICA
✓ fuel_metrics                           - Datos principales ✅ EXISTE EN HISTÓRICA  
✓ kalman_state                           - Estado Kalman filter
✓ mpg_baseline                           - Línea base MPG
✓ predictive_maintenance_sensor_history  - Sensores PM
✓ refuel_events                          - Recargas ✅ EXISTE EN HISTÓRICA
✓ sensor_cache                           - Cache sensores
✓ theft_events                           - Robos combustible
✓ truck_history                          - Historial ✅ EXISTE EN HISTÓRICA
```

---

## TABLAS EXCLUSIVAS

### Solo en BASE HISTÓRICA (18 tablas únicas):
```
❌ cc_algorithm_state
❌ cc_anomaly_history
❌ cc_correlation_events
❌ cc_def_history
❌ cc_maintenance_events
❌ cc_risk_history
❌ command_center_config
❌ engine_health_alerts
❌ engine_health_baselines
❌ engine_health_notifications
❌ engine_health_snapshots
❌ engine_health_thresholds
❌ gps_quality_events
❌ j1939_spn_lookup
❌ maintenance_alerts
❌ maintenance_predictions
❌ pm_predictions
❌ pm_sensor_daily_avg
❌ pm_sensor_history
❌ telemetry_data
❌ trips
❌ truck_health_history
❌ voltage_events
```

### Solo en BASE ACTUAL (5 tablas únicas):
```
✓ kalman_state
✓ mpg_baseline
✓ predictive_maintenance_sensor_history
✓ sensor_cache (diferente de truck_sensors_cache)
✓ theft_events
```

---

## ANÁLISIS

### ⚠️ Tablas Faltantes Importantes:
1. **j1939_spn_lookup** - Lookup de códigos DTC (necesaria para diagnósticos)
2. **truck_sensors_cache** - Cache de sensores Wialon (necesaria para sincronización)
3. **trips** - Datos de viajes (análisis de rutas)
4. **telemetry_data** - Datos de telemetría adicional
5. Todas las tablas de **Command Center avanzado** (cc_*)
6. Todas las tablas de **Engine Health** (engine_health_*)

### 📊 Datos Perdidos Estimados:
- **fuel_metrics histórico**: ~140 MB vs 9 MB actual = **131 MB de datos**
- **Periodo estimado**: 12 días (según usuario)
- **Registros estimados**: ~50,000-100,000 registros (basado en tamaño)

### 🔴 Problema Principal:
La base histórica tiene **datos corruptos o incompatibles** que causan crash de MySQL Server 8.0.

---

## RECOMENDACIONES

1. **INMEDIATO**: Continuar con base actual (ya funciona correctamente)
2. **CORTO PLAZO**: Crear las tablas faltantes si son necesarias:
   - `j1939_spn_lookup` 
   - `truck_sensors_cache`
   - Tablas de Command Center si se usa esa funcionalidad
3. **MEDIANO PLAZO**: Implementar backups automáticos diarios
4. **LARGO PLAZO**: Considerar recuperación profesional de datos históricos si son críticos

---

**Fecha del reporte**: 19-diciembre-2025 9:10 AM
**Estado**: Base actual funcionando ✅ | Base histórica inaccesible ❌
