# DIAGNÓSTICO: Dashboard Frontend Mostrando N/A

**Fecha:** 19 Diciembre 2025, 04:35 AM  
**Estado:** Backend funcionando correctamente, Frontend NO renderizando datos

---

## 🔍 INVESTIGACIÓN COMPLETADA

### ✅ Backend (Funcionando Correctamente)

1. **Servicios activos:**
   - `wialon_sync_enhanced.py` (PID 45460) - Insertando datos cada 15-30s
   - `FastAPI` (PID 36469) - API respondiendo en puerto 8000
   - `sensor_cache_updater.py` (PID 52453) - Actualizando 27 trucks cada 30s, 0 errores

2. **Base de datos:**
   - 32 tablas operacionales
   - `fuel_metrics`: Datos cada 15-30s con timestamps frescos (09:31:xx UTC)
   - `truck_sensors_cache`: 27 trucks actualizándose correctamente
   - `dtc_events`: 23 DTCs registrados en últimas 24 horas

3. **Endpoint `/api/fleet`:**
   ```json
   {
     "total_trucks": 28,
     "active_trucks": 14,
     "offline_trucks": 14,
     "avg_mpg": 0.0,           ← NULL en fuel_metrics
     "avg_idle_gph": 4.46,     ← ✅ Funcionando
     "truck_details": [...]
   }
   ```

4. **Datos en `fuel_metrics` (últimos 5 min):**
   ```
   truck_id | status  | mpg  | idle_gph | sensor% | estimated% | drift%
   ---------|---------|------|----------|---------|------------|--------
   LC6799   | STOPPED | NULL | 0.22     | 99.20   | 99.46      | -0.26
   YM6023   | STOPPED | NULL | 0.21     | 34.80   | 34.76      | +0.04
   RT9127   | MOVING  | NULL | NULL     | 99.20   | 99.17      | +0.03
   RH1522   | STOPPED | NULL | 0.31     | 70.40   | 69.12      | +1.28
   GP9677   | STOPPED | NULL | 0.21     | 62.40   | 62.16      | +0.24
   ```

   **Conclusiones:**
   - ✅ Kalman SÍ está funcionando (estimated_pct vs sensor_pct con drift)
   - ✅ idle_gph tiene valores correctos para trucks STOPPED
   - ❌ mpg_current está en NULL para TODOS los trucks (incluso MOVING)

---

## ❌ PROBLEMAS IDENTIFICADOS

### Problema 1: MPG en NULL
**Observación:** `mpg_current` en fuel_metrics está NULL para todos los trucks, incluso los que están MOVING.

**Causa:** El cálculo de MPG requiere:
1. Truck en movimiento (speed > 5 mph)
2. Sensor de fuel_rate (GPH) funcional
3. Distancia recorrida

**Trucks afectados:** TODOS (28/28)
- MOVING trucks: RT9127, RR1272, DO9356 - deberían tener MPG pero muestran NULL
- STOPPED trucks: Correcto que sea NULL

**Acción requerida:**
- Verificar por qué wialon_sync_enhanced.py no está calculando MPG
- Revisar logs de wialon_sync para ver si hay errores en cálculo MPG

---

### Problema 2: Frontend Muestra N/A a Pesar de Datos Disponibles

**Endpoint:** `/api/fleet` SÍ devuelve datos correctamente  
**Frontend:** `DashboardPro.tsx` usando `useFleetSummary()` hook  
**Hook location:** `/hooks/useApi.ts` línea 147

**Datos enviados por backend:**
```json
{
  "truck_id": "RT9127",
  "status": "MOVING",
  "fuel_level": "99.2",
  "estimated_pct": "99.2",
  "sensor_pct": "99.2",
  "drift": "-0.0",
  "drift_pct": "-0.0",
  "mpg": null,
  "idle_gph": null,
  "speed": "59.6",
  "speed_mph": "59.6",
  "rpm": 1216
}
```

**Posibles causas:**
1. Frontend esperando campos con nombres diferentes
2. Frontend tratando `"99.2"` (string) como NULL porque espera número
3. Frontend filtrando trucks OFFLINE y mostrando N/A por defecto
4. Cache del navegador mostrando datos viejos

---

### Problema 3: Kalman Mostrando 0.0% en Frontend

**Backend devuelve:**
- `drift`: "-0.0"
- `drift_pct`: "-0.0"  
- `estimated_pct`: "99.2"
- `sensor_pct`: "99.2"

**Frontend muestra:**
- Drift: 0.0% para TODOS los trucks

**Causa probable:**
- Frontend parseando `"-0.0"` (string) y convirtiéndolo a 0
- Frontend redondeando valores pequeños (<1%) a 0
- Frontend no mostrando drift si está por debajo de threshold

---

### Problema 4: Command Center 100/100 con 23 DTCs

**Backend tiene:**
- 23 DTCs en tabla `dtc_events` (últimas 24 horas)
- Sensores funcionando correctamente
- Voltage warnings, DTC críticos detectados

**Frontend muestra:**
- 0 Issues Detected
- 100/100 Excelente
- 0 Critical, 0 High, 0 Medium

**Causa:**
- Command Center probablemente consultando tabla `cc_anomaly_history` o similar
- Las tablas de Command Center están vacías (recién creadas)
- No hay integración entre `dtc_events` y Command Center

---

## 🎯 DATOS QUE SÍ ESTÁN FUNCIONANDO

1. ✅ **Estado de trucks** - MOVING/STOPPED/OFFLINE correcto
2. ✅ **idle_gph** - Valores correctos (0.16-0.31 GPH) para trucks STOPPED
3. ✅ **Kalman filtering** - estimated_pct vs sensor_pct con drift calculado
4. ✅ **Datos GPS** - Latitude, longitude, speed_mph, heading
5. ✅ **Sensores básicos** - RPM, voltage, speed para trucks con OBD
6. ✅ **DTCs** - 23 eventos registrados correctamente
7. ✅ **sensor_cache_updater** - 27 trucks, 0 errors, actualizándose cada 30s

---

## 🔧 SOLUCIONES PROPUESTAS

### Solución Inmediata (Frontend)
1. Verificar que frontend esté haciendo fetch a URL correcta:
   - Producción: `https://fleetbooster.net/fuelAnalytics/api/fleet`
   - Local: `http://localhost:8000/fuelAnalytics/api/fleet`

2. Verificar conversión de tipos en `normalizeTruckData()` (useApi.ts):
   ```typescript
   fuel_level: parseFloat(t.fuel_level) || 0,
   drift_pct: parseFloat(t.drift_pct) || 0,
   ```

3. Limpiar cache del navegador:
   - Ctrl+Shift+R (hard reload)
   - Clear localStorage/sessionStorage

### Solución de MPG (Backend)
1. Revisar logs de wialon_sync_enhanced.py:
   ```bash
   tail -200 nohup.out | grep -i mpg
   ```

2. Verificar que trucks MOVING tienen fuel_rate sensor:
   ```sql
   SELECT truck_id, speed_mph, rpm, fuel_rate_gph 
   FROM truck_sensors_cache 
   WHERE speed_mph > 5;
   ```

3. Si fuel_rate es NULL, MPG no se puede calcular → Configurar sensor en Wialon

### Solución de Command Center
1. Poblar tabla `cc_anomaly_history` con DTCs de `dtc_events`
2. Configurar alertas basadas en tabla `voltage_events`
3. Crear reglas de correlación entre tablas

---

## 📊 RESUMEN EJECUTIVO

| Componente | Estado | Detalles |
|------------|--------|----------|
| **wialon_sync** | ✅ Funcionando | Insertando datos cada 15-30s |
| **sensor_cache** | ✅ Funcionando | 27 trucks, 0 errors |
| **FastAPI** | ✅ Funcionando | /api/fleet devolviendo datos |
| **fuel_metrics** | ⚠️ Parcial | Kalman ✅, MPG ❌ |
| **truck_sensors_cache** | ✅ Funcionando | Datos GPS + algunos OBD |
| **DTCs** | ✅ Funcionando | 23 eventos registrados |
| **Frontend Dashboard** | ❌ NO Renderiza | Muestra N/A a pesar de datos |
| **Command Center** | ❌ Vacío | No lee de dtc_events |

---

## 🚨 ACCIÓN INMEDIATA REQUERIDA

1. **PRODUCCIÓN:** wialon_sync_enhanced.py NO está corriendo o no inserta a fuel_metrics
   - `/api/fleet` funciona (usa truck_sensors_cache) ✅
   - `/api/trucks/{id}` falla (usa fuel_metrics, no hay datos < 24h) ❌
   - **FIX:** Reiniciar wialon_sync en servidor de producción

2. **sensor_cache_updater:** Aplicar fix de 12-hour deep search (commit 1283f23)
   - ANTES: 1 hora → sensores lentos en NULL
   - AHORA: 12 horas → captura barometer, idle_hours, coolant_temp, etc.

3. **MPG:** Investigar por qué mpg_current está NULL en todos los trucks
   - Requiere sensor fuel_rate funcional
   - Trucks MOVING deberían calcular MPG

4. **Command Center:** 100/100 con 23 DTCs en tabla
   - Conectar dtc_events con cc_anomaly_history
   - Poblar alertas desde voltage_events

**Prioridad:** Producción (wialon_sync detenido)
