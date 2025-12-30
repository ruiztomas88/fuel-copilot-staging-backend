# REPORTE DE AUDITORÍA Y SOLUCIÓN - FUEL COPILOT
**Fecha:** 19 de Diciembre, 2025  
**Problema:** Sistema muestra N/A en sensores, trucks offline, Command Center vacío

---

## 🔴 PROBLEMAS IDENTIFICADOS

### 1. **SERVICIO PRINCIPAL NO ESTÁ CORRIENDO** ⚠️ CRÍTICO
- **fuel_copilot.py** NO está ejecutándose
- Sin este servicio:
  - ❌ No se recolectan datos de Wialon
  - ❌ No se actualiza tabla `fuel_metrics` 
  - ❌ No hay cálculos de MPG, consumo, estado
  - ❌ No se detectan refuels ni robos
  - ❌ Command Center no tiene datos

**IMPACTO:** Este es el 90% del problema. Sin fuel_copilot NADA funciona.

### 2. **API FastAPI (main.py) NO está corriendo** ⚠️ CRÍTICO
- El frontend hace requests a `/fuelAnalytics/api/v2/...`
- Si no está corriendo, todos los endpoints retornan error
- **EVIDENCIA:** Error 500 en `/api/v2/trucks/YM6023/sensors`

### 3. **Servicio sensor_cache_updater SÍ está corriendo** ✅ RESUELTO
- ✅ Iniciado durante esta sesión
- ✅ Actualizando 26 trucks cada 30 segundos
- ✅ Tabla `truck_sensors_cache` tiene datos frescos

### 4. **Solo 3 trucks tienen sensores completos OBD/J1939** ⚠️ CONFIGURACIÓN
```
COMPLETE (12/12 sensores críticos):
  - JC1282 (29 sensores totales)
  - RT9127 (29 sensores totales)
  - YM6023 (27 sensores totales)

PARTIAL (60-90% sensores):
  - RA9250 (24 sensores - faltan: oil_press, def_level, speed, odom)
  - RR1272 (23 sensores - faltan: fuel_lvl, oil_temp, def_level)
  - FF7702 (20 sensores - faltan: fuel_lvl, def_level, speed, odom)

GPS_ONLY (38 trucks):
  - Solo tienen GPS básico
  - NO tienen sensores de motor/combustible
  - Estos trucks necesitan configuración OBD en Wialon
```

**CAUSA:** Los ELD/trackers de estos 38 trucks no están configurados para leer datos OBD/J1939 en Wialon.

### 5. **Base de datos recreada - Tablas vacías**
```sql
-- truck_sensors_cache: ✅ 26 trucks (gracias a sensor_cache_updater)
-- fuel_metrics: ❓ Probablemente vacía o muy lenta
-- refuel_events: ❓ Desconocido
-- telemetry_data: ❓ Desconocido
```

---

## ✅ SOLUCIONES IMPLEMENTADAS

### 1. ✅ Script diagnóstico creado
**Archivo:** `diagnose_all_trucks.py`
```bash
python diagnose_all_trucks.py
```
**Muestra:**
- Estado online/offline de cada truck
- Nivel de sensores disponibles (COMPLETE/PARTIAL/LIMITED/GPS_ONLY)
- Sensores faltantes para cada truck
- Recomendaciones específicas

### 2. ✅ Servicio sensor_cache_updater iniciado
```bash
# Ya está corriendo en background
ps aux | grep sensor_cache_updater
```
**Resultado:** 26 trucks actualizándose cada 30 segundos

---

## 🔧 SOLUCIONES PENDIENTES (ACCIÓN REQUERIDA)

### **PASO 1: INICIAR SERVICIO PRINCIPAL fuel_copilot.py** ⚠️ URGENTE

Este es el servicio MÁS IMPORTANTE del sistema. Sin él, nada funciona.

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Opción 1: Ejecutar en foreground (para ver logs)
python fuel_copilot.py

# Opción 2: Ejecutar en background
nohup python fuel_copilot.py > fuel_copilot.log 2>&1 &

# Opción 3: Con screen (recomendado)
screen -S fuel_copilot
python fuel_copilot.py
# Ctrl+A, D para detach
```

**Qué hace fuel_copilot.py:**
1. Lee sensores de Wialon cada 15-30 segundos
2. Calcula Kalman filter para fuel level
3. Detecta refuels y robos
4. Calcula MPG, idle_gph, consumption
5. Determina estado (MOVING/STOPPED/OFFLINE)
6. Guarda todo en `fuel_metrics` table
7. Genera alertas de robo/DTC

**VERIFICAR QUE FUNCIONA:**
```bash
# Ver últimos registros en fuel_metrics
mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot -e \
  "SELECT truck_id, timestamp_utc, truck_status, mpg_current, consumption_gph 
   FROM fuel_metrics 
   ORDER BY timestamp_utc DESC 
   LIMIT 10;"
```

---

### **PASO 2: INICIAR API FastAPI (main.py)** ⚠️ URGENTE

El frontend necesita este API para funcionar.

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Opción 1: Development (con reload)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Opción 2: Production (con nohup)
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 > api.log 2>&1 &

# Opción 3: Con screen (recomendado)
screen -S fuel_api
uvicorn main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D para detach
```

**VERIFICAR QUE FUNCIONA:**
```bash
# Test endpoint de sensores
curl http://localhost:8000/fuelAnalytics/api/v2/trucks/YM6023/sensors | jq

# Debería retornar JSON con sensores (no error 500)
```

---

### **PASO 3: CONFIGURAR SENSORES OBD EN WIALON** (No urgente, pero importante)

38 trucks solo tienen GPS. Necesitan configuración OBD en Wialon.

**Trucks GPS_ONLY (priorizar los que están ONLINE):**
```
ONLINE GPS_ONLY:
- NQ6975, DO9356, DO9693, MJ9547, OS3717

RECENT GPS_ONLY:
- VD3579, GP9677, JB6858, JP3281, RH1522, CO0681, 
  DR6664, MO0195, PC1280, FM3363, LC6799, RC6625, 
  OM7769, LH1141
```

**Acción en Wialon:**
1. Ir a configuración del tracker/ELD
2. Verificar que esté conectado al puerto OBD del camión
3. Habilitar lectura de parámetros J1939:
   - fuel_lvl (Fuel Level %)
   - fuel_rate (Fuel Rate L/h o gal/h)
   - rpm (Engine RPM)
   - engine_load (Engine Load %)
   - oil_press (Oil Pressure)
   - oil_temp (Oil Temperature)
   - cool_temp (Coolant Temperature)
   - def_level (DEF Level %)
   - speed (Vehicle Speed)
   - odom (Odometer)

**Consultar con proveedor ELD:**
- Algunos ELD solo soportan GPS (Geotab GO7, algunos modelos viejos)
- Otros necesitan activación de OBD (costo adicional)
- Verificar modelo de cada truck

---

### **PASO 4: CONFIGURAR SYSTEMD PARA AUTO-START** (Recomendado)

Para que los servicios se inicien automáticamente al reiniciar el servidor:

**Archivo:** `/etc/systemd/system/fuel-copilot.service`
```ini
[Unit]
Description=Fuel Copilot Data Collector
After=network.target mysql.service

[Service]
Type=simple
User=tomasruiz
WorkingDirectory=/Users/tomasruiz/Desktop/Fuel-Analytics-Backend
Environment="PATH=/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/anaconda3/bin/python fuel_copilot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Archivo:** `/etc/systemd/system/fuel-api.service`
```ini
[Unit]
Description=Fuel Copilot API (FastAPI)
After=network.target mysql.service

[Service]
Type=simple
User=tomasruiz
WorkingDirectory=/Users/tomasruiz/Desktop/Fuel-Analytics-Backend
Environment="PATH=/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/anaconda3/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Comandos:**
```bash
# Recargar systemd
sudo systemctl daemon-reload

# Habilitar auto-start
sudo systemctl enable fuel-copilot
sudo systemctl enable fuel-api

# Iniciar servicios
sudo systemctl start fuel-copilot
sudo systemctl start fuel-api

# Ver status
sudo systemctl status fuel-copilot
sudo systemctl status fuel-api

# Ver logs
sudo journalctl -u fuel-copilot -f
sudo journalctl -u fuel-api -f
```

---

## 📊 RESUMEN DE SERVICIOS REQUERIDOS

| Servicio | Estado Actual | Función | Urgencia |
|----------|---------------|---------|----------|
| **fuel_copilot.py** | ❌ DETENIDO | Recolecta datos de Wialon, calcula métricas | 🔴 CRÍTICO |
| **main.py (uvicorn)** | ❌ DETENIDO | API FastAPI para frontend | 🔴 CRÍTICO |
| **sensor_cache_updater.py** | ✅ CORRIENDO | Cache de sensores en tiempo real | ✅ OK |
| **MySQL** | ✅ CORRIENDO | Base de datos | ✅ OK |

---

## 🎯 ORDEN DE EJECUCIÓN RECOMENDADO

1. **Iniciar fuel_copilot.py** (esperar 2-3 minutos para que recolecte datos)
2. **Verificar fuel_metrics** tiene registros nuevos
3. **Iniciar main.py (uvicorn)**
4. **Probar frontend** - debería mostrar trucks online/offline correctamente
5. **Verificar Command Center** - debería tener reportes
6. **Configurar systemd** para auto-start
7. **Planear configuración OBD** en Wialon (no urgente)

---

## 🔍 COMANDOS DE VERIFICACIÓN

```bash
# Ver todos los servicios corriendo
ps aux | grep -E "fuel_copilot|sensor_cache|uvicorn" | grep -v grep

# Ver últimas actualizaciones en cache de sensores
mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot -e \
  "SELECT truck_id, timestamp, data_age_seconds, rpm, fuel_level_pct 
   FROM truck_sensors_cache 
   ORDER BY timestamp DESC 
   LIMIT 10;"

# Ver últimos fuel_metrics (después de iniciar fuel_copilot.py)
mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot -e \
  "SELECT truck_id, timestamp_utc, truck_status, mpg_current 
   FROM fuel_metrics 
   ORDER BY timestamp_utc DESC 
   LIMIT 10;"

# Test API endpoint
curl http://localhost:8000/fuelAnalytics/api/v2/trucks/YM6023/sensors | jq '.truck_id, .rpm, .fuel_level_pct'

# Diagnóstico completo de trucks
python diagnose_all_trucks.py
```

---

## 📝 NOTAS ADICIONALES

### Por qué YM6023 mostraba OFFLINE en detalle pero ONLINE en overview:
- **Fleet Overview** lee de `truck_sensors_cache` (actualizada por sensor_cache_updater)
- **Truck Detail** lee de `fuel_metrics` (actualizada por fuel_copilot.py)
- Como fuel_copilot NO estaba corriendo → fuel_metrics vacía → OFFLINE
- Pero sensor_cache SÍ tenía datos → ONLINE en overview

### Por qué el Command Center está vacío:
- Command Center lee estadísticas agregadas de `fuel_metrics`
- Sin fuel_copilot corriendo, no hay datos para agregar
- Necesita al menos 24 horas de datos para mostrar tendencias

### Por qué recibías emails de DTCs:
- Las alertas de DTC se envían directamente desde Wialon (configuración externa)
- NO dependen de fuel_copilot
- Por eso siguen funcionando aunque el sistema esté "apagado"

---

## 🚨 CONTACTO SI HAY PROBLEMAS

Si después de iniciar fuel_copilot.py y main.py siguen habiendo errores:

1. **Revisar logs de fuel_copilot:**
   ```bash
   tail -f fuel_copilot.log  # si usaste nohup
   # O ver directamente si está en foreground
   ```

2. **Revisar logs del API:**
   ```bash
   tail -f api.log  # si usaste nohup
   ```

3. **Errores comunes:**
   - **MySQL connection refused:** Verificar que MySQL está corriendo
   - **Wialon DB timeout:** Verificar conexión a 20.127.200.135:3306
   - **ImportError:** Instalar dependencias faltantes con `pip install -r requirements.txt`

---

**Creado por:** GitHub Copilot (Claude Sonnet 4.5)  
**Fecha:** 19 de Diciembre, 2025 04:22 AM
