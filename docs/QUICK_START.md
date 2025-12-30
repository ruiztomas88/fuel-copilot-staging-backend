# ⚡ QUICK START - INICIAR SISTEMA FUEL COPILOT

## 🚀 OPCIÓN RÁPIDA (RECOMENDADA)

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./start_all_services.sh
```

Este script automáticamente:
- ✅ Detecta qué servicios ya están corriendo
- ✅ Inicia solo los que faltan
- ✅ Crea logs en `logs/` directory
- ✅ Muestra el estado final de todos los servicios

---

## 📋 VERIFICAR QUE TODO FUNCIONA

### 1. Ver que los servicios están corriendo:
```bash
ps aux | grep -E "wialon_sync|uvicorn|sensor_cache" | grep -v grep
```

Deberías ver 3 procesos:
- `python wialon_sync_enhanced.py` (recolección de datos)
- `uvicorn main:app` (API FastAPI)
- `python sensor_cache_updater.py` (cache de sensores)

### 2. Ver logs en tiempo real:
```bash
# Wialon Sync (el más importante)
tail -f logs/wialon_sync.log

# API
tail -f logs/api.log

# Sensor Cache
tail -f logs/sensor_cache.log
```

### 3. Verificar que hay datos nuevos en MySQL:
```bash
mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot -e \
  "SELECT truck_id, timestamp_utc, truck_status, mpg_current 
   FROM fuel_metrics 
   ORDER BY timestamp_utc DESC 
   LIMIT 5;"
```

Deberías ver registros con timestamps recientes (últimos minutos).

### 4. Probar el API:
```bash
# Health check
curl http://localhost:8000/fuelAnalytics/api/health

# Endpoint de sensores
curl http://localhost:8000/fuelAnalytics/api/v2/trucks/YM6023/sensors | jq
```

### 5. Abrir el frontend:
Abre tu navegador en: https://fuelanalytics.fleetbooster.net

Deberías ver:
- ✅ Trucks con estado ONLINE/MOVING/STOPPED (no todos OFFLINE)
- ✅ Sensores con valores (no N/A)
- ✅ Command Center con reportes y estadísticas

---

## 🛑 DETENER TODOS LOS SERVICIOS

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./stop_all_services.sh
```

---

## 🔧 INICIO MANUAL (Si el script automático falla)

### Paso 1: Iniciar Wialon Sync
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
nohup python wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &

# Esperar 30 segundos para que recolecte datos iniciales
sleep 30
```

### Paso 2: Iniciar FastAPI
```bash
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 > logs/api.log 2>&1 &

# Esperar 3 segundos
sleep 3
```

### Paso 3: Iniciar Sensor Cache
```bash
nohup python sensor_cache_updater.py > logs/sensor_cache.log 2>&1 &
```

### Paso 4: Verificar
```bash
ps aux | grep -E "wialon_sync|uvicorn|sensor_cache" | grep -v grep
```

---

## 📊 DIAGNÓSTICO AVANZADO

### Ver diagnóstico completo de todos los trucks:
```bash
python diagnose_all_trucks.py
```

Esto muestra:
- Estado de cada truck (ONLINE/OFFLINE)
- Nivel de sensores (COMPLETE/PARTIAL/GPS_ONLY)
- Sensores faltantes
- Recomendaciones específicas

### Ver estado del Command Center:
```bash
python diagnose_command_center.py
```

---

## ⚠️ TROUBLESHOOTING

### Problema: "No hay datos en fuel_metrics después de 5 minutos"

**Verificar conexión a Wialon:**
```bash
mysql -h20.127.200.135 -utomas -p'Tomas2025' wialon_collect -e \
  "SELECT COUNT(*) FROM sensors WHERE m >= UNIX_TIMESTAMP() - 300;"
```

Si retorna 0, hay un problema de conexión con Wialon.

**Verificar logs de wialon_sync:**
```bash
tail -100 logs/wialon_sync.log | grep -i error
```

### Problema: "API retorna 500 errors"

**Ver errores en API log:**
```bash
tail -100 logs/api.log | grep -i error
```

**Reiniciar API:**
```bash
pkill -f "uvicorn.*main:app"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload  # Mode development para ver errores
```

### Problema: "Trucks siguen mostrando OFFLINE"

1. **Verificar que wialon_sync está corriendo:**
   ```bash
   ps aux | grep wialon_sync
   ```

2. **Verificar que está insertando datos:**
   ```bash
   tail -f logs/wialon_sync.log
   ```
   
   Deberías ver líneas como:
   ```
   ✅ Inserted/Updated YM6023: MOVING, MPG: 6.2, Fuel: 34.8%
   ```

3. **Si wialon_sync está corriendo pero no inserta datos:**
   - Revisar conexión a Wialon DB
   - Revisar que los unit_ids en tanks.yaml son correctos
   - Verificar que hay datos en Wialon para esos trucks

---

## 🔄 REINICIO COMPLETO

Si todo falla, reinicio completo:

```bash
# 1. Detener todo
./stop_all_services.sh

# 2. Esperar 5 segundos
sleep 5

# 3. Iniciar todo
./start_all_services.sh

# 4. Ver logs en tiempo real
tail -f logs/wialon_sync.log
```

---

## 📞 CONTACTO

Si después de seguir estos pasos sigue sin funcionar:

1. Captura los logs:
   ```bash
   tail -100 logs/wialon_sync.log > debug_wialon.txt
   tail -100 logs/api.log > debug_api.txt
   ```

2. Ejecuta diagnóstico:
   ```bash
   python diagnose_all_trucks.py > debug_trucks.txt
   ```

3. Envía estos archivos para análisis

---

**Última actualización:** 19 de Diciembre, 2025  
**Versión del sistema:** Fuel Copilot v3.12.21
