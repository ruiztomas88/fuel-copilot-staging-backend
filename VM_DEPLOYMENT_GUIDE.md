# 🚀 Deployment en VM - Wialon Full Sync

## ✅ Ya Completado en VM

- ✅ Tabla `truck_sensors_cache` creada
- ✅ Backend API corriendo

---

## 📋 Pasos para Deployar el Nuevo Commit

### Paso 1: Pull los Cambios del Backend

```bash
# Conectar a la VM
ssh usuario@tu-vm-ip

# Ir al directorio del backend
cd /path/to/Fuel-Analytics-Backend

# Pull los últimos cambios
git pull origin main
```

**Commits nuevos que se bajarán:**
- `16cb028` - feat: Add comprehensive Wialon data sync (trips, speeding, driver behavior)
- `0344edc` - docs: Add Wialon sync deployment guide
- `21b47c2` - docs: Add comprehensive Wialon sync implementation summary

---

### Paso 2: Crear las Nuevas Tablas

```bash
# Ejecutar la migración para las nuevas tablas
python3 migrations/create_wialon_sync_tables.py
```

**Salida esperada:**
```
Creating Wialon sync tables...
✅ Created truck_trips table
✅ Created truck_speeding_events table
✅ Created truck_ignition_events table
✅ All tables created!
```

---

### Paso 3: Verificar las Tablas

```bash
mysql -u root -p fuel_copilot
```

```sql
-- Ver todas las tablas
SHOW TABLES;

-- Debería mostrar:
-- truck_sensors_cache (ya existente)
-- truck_trips (nueva)
-- truck_speeding_events (nueva)
-- truck_ignition_events (nueva)

-- Ver estructura de las nuevas tablas
DESCRIBE truck_trips;
DESCRIBE truck_speeding_events;
DESCRIBE truck_ignition_events;

-- Salir
EXIT;
```

---

### Paso 4: Iniciar el Servicio de Sincronización

**Opción A: Ejecutar en foreground (para testing - 5 minutos)**

```bash
# Ejecutar y ver los logs en tiempo real
python3 wialon_full_sync_service.py
```

Verás algo como:
```
🚀 Starting Wialon Full Sync Service
   Wialon DB: 20.127.200.135:3306/wialon_collect
   Local DB: localhost:3306/fuel_copilot
   Sensors: Every 30 seconds
   Trips/Events: Every 60 seconds
============================================================

============================================================
🔄 Sync Cycle #1 - 2025-01-03 10:30:00
============================================================
🔄 Starting sensor sync...
📊 Retrieved 45 trucks from Wialon sensors
✅ Synced 45 trucks' sensor data
🔄 Starting trips sync...
📊 Retrieved 1247 trips from last 7 days
✅ Synced 1247 trips
🔄 Starting speeding events sync...
📊 Retrieved 342 speeding events from last 7 days
✅ Synced 342 speeding events
🔄 Starting ignition events sync...
📊 Retrieved 628 ignition events from last 7 days
✅ Synced 628 ignition events

✅ Sync cycle #1 completed
   Last sensor sync: 10:30:15
   Last trips sync: 10:30:22
   Last events sync: 10:30:25
```

**Presiona Ctrl+C** después de 2-3 ciclos para verificar que funciona.

**Opción B: Ejecutar en background (producción)**

```bash
# Iniciar como servicio en background
nohup python3 wialon_full_sync_service.py > wialon_sync.log 2>&1 &

# Guardar el PID para poder detenerlo después
echo $! > wialon_sync.pid

# Ver los logs en tiempo real
tail -f wialon_sync.log

# Para salir de los logs: Ctrl+C (el servicio sigue corriendo)
```

---

### Paso 5: Verificar que los Datos se Están Sincronizando

Espera 2-3 minutos y luego verifica:

```bash
mysql -u root -p fuel_copilot
```

```sql
-- Verificar sensores (debe tener datos recientes)
SELECT COUNT(*) as cached_trucks, 
       MAX(last_updated) as last_sync
FROM truck_sensors_cache;

-- Verificar viajes
SELECT COUNT(*) as total_trips,
       MIN(start_time) as earliest,
       MAX(start_time) as latest,
       MAX(created_at) as last_synced
FROM truck_trips;

-- Verificar eventos de speeding
SELECT COUNT(*) as total_events,
       SUM(CASE WHEN severity='minor' THEN 1 ELSE 0 END) as minor,
       SUM(CASE WHEN severity='moderate' THEN 1 ELSE 0 END) as moderate,
       SUM(CASE WHEN severity='severe' THEN 1 ELSE 0 END) as severe,
       MAX(created_at) as last_synced
FROM truck_speeding_events;

-- Ver datos de ejemplo de un truck
SELECT truck_id, start_time, end_time, distance_miles, avg_speed,
       speeding_count, harsh_accel_count, harsh_brake_count
FROM truck_trips
WHERE truck_id = 'GS5030'  -- Usar un truck_id real
ORDER BY start_time DESC
LIMIT 5;

-- Ver eventos de speeding de un truck
SELECT truck_id, start_time, max_speed, speed_limit, 
       speed_over_limit, severity, driver_name
FROM truck_speeding_events
WHERE truck_id = 'GS5030'  -- Usar un truck_id real
ORDER BY start_time DESC
LIMIT 5;
```

---

### Paso 6: Probar los Nuevos API Endpoints

```bash
# Endpoint 1: Fleet Driver Behavior
curl -X GET "http://localhost:8008/fuelAnalytics/api/v2/fleet/driver-behavior?days=7"

# Endpoint 2: Trips de un truck específico
curl -X GET "http://localhost:8008/fuelAnalytics/api/v2/trucks/GS5030/trips?days=7"

# Endpoint 3: Speeding events de un truck
curl -X GET "http://localhost:8008/fuelAnalytics/api/v2/trucks/GS5030/speeding-events?days=7"
```

**Si obtienes JSON con datos:** ✅ Todo funciona correctamente!

---

### Paso 7: Configurar el Servicio para Auto-Start (Opcional pero Recomendado)

Para que el servicio se inicie automáticamente cuando la VM se reinicie:

```bash
# Crear un servicio systemd
sudo nano /etc/systemd/system/wialon-sync.service
```

Pegar este contenido:
```ini
[Unit]
Description=Wialon Full Data Sync Service
After=network.target mysql.service

[Service]
Type=simple
User=tu-usuario
WorkingDirectory=/path/to/Fuel-Analytics-Backend
ExecStart=/usr/bin/python3 /path/to/Fuel-Analytics-Backend/wialon_full_sync_service.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/wialon_sync.log
StandardError=append:/var/log/wialon_sync.log

[Install]
WantedBy=multi-user.target
```

**Guardar:** Ctrl+X, Y, Enter

```bash
# Recargar systemd
sudo systemctl daemon-reload

# Habilitar para auto-start
sudo systemctl enable wialon-sync.service

# Iniciar el servicio
sudo systemctl start wialon-sync.service

# Ver estado
sudo systemctl status wialon-sync.service

# Ver logs
sudo journalctl -u wialon-sync.service -f
```

**Comandos útiles:**
```bash
# Detener el servicio
sudo systemctl stop wialon-sync.service

# Reiniciar el servicio
sudo systemctl restart wialon-sync.service

# Ver logs
tail -f /var/log/wialon_sync.log
```

---

### Paso 8: Monitoreo Continuo

```bash
# Ver logs en tiempo real
tail -f wialon_sync.log

# Ver últimos 50 logs
tail -50 wialon_sync.log

# Buscar errores
grep "❌" wialon_sync.log

# Ver ciclos de sincronización
grep "Sync Cycle" wialon_sync.log | tail -10

# Verificar proceso corriendo
ps aux | grep wialon_full_sync_service
```

---

## 🔧 Troubleshooting

### El servicio no inicia

**Verificar Python y dependencias:**
```bash
python3 --version  # Debe ser 3.7+
pip3 install pymysql
```

**Verificar conexión a Wialon:**
```bash
mysql -h 20.127.200.135 -u wialonro -p wialon_collect -e "SELECT COUNT(*) FROM sensors;"
# Password: KjmAqwertY1#2024!@Wialon
```

**Verificar conexión local:**
```bash
mysql -u root -p fuel_copilot -e "SELECT COUNT(*) FROM truck_sensors_cache;"
```

### No aparecen datos en las tablas

**Verificar logs:**
```bash
tail -50 wialon_sync.log | grep "❌"
```

**Verificar que el servicio esté corriendo:**
```bash
ps aux | grep wialon_full_sync_service
```

Si no está corriendo, iniciarlo:
```bash
python3 wialon_full_sync_service.py
```

### Datos muy viejos (no se actualizan)

**Verificar freshness de los datos:**
```sql
SELECT MAX(last_updated) as last_sync,
       TIMESTAMPDIFF(SECOND, MAX(last_updated), NOW()) as age_seconds
FROM truck_sensors_cache;
```

Si `age_seconds > 120`: El servicio está detenido o hay error de conexión.

---

## ✅ Checklist de Deployment

- [ ] Git pull exitoso (commits 16cb028, 0344edc, 21b47c2)
- [ ] Migración ejecutada (truck_trips, truck_speeding_events, truck_ignition_events creadas)
- [ ] Tablas verificadas con `SHOW TABLES`
- [ ] Servicio iniciado (foreground o background)
- [ ] Logs muestran sync cycles exitosos
- [ ] Datos aparecen en las 3 nuevas tablas (verificado con SQL)
- [ ] API endpoints responden correctamente (curl tests)
- [ ] Servicio configurado para auto-start (systemd)
- [ ] Monitoreo establecido (logs, SQL queries)

---

## 📊 Resultados Esperados

Después del deployment, deberías tener:

✅ **4 tablas sincronizadas:**
- `truck_sensors_cache` - ~45 trucks (última lectura de cada uno)
- `truck_trips` - ~1,000-1,500 trips (últimos 7 días)
- `truck_speeding_events` - ~300-400 eventos (últimos 7 días)
- `truck_ignition_events` - ~600-700 eventos (últimos 7 días)

✅ **Sincronización automática:**
- Sensores cada 30 segundos
- Trips/Events cada 60 segundos
- Logs detallados en `wialon_sync.log`

✅ **3 endpoints nuevos funcionando:**
- `/api/v2/fleet/driver-behavior` - Safety scores y métricas
- `/api/v2/trucks/{id}/trips` - Historial de viajes
- `/api/v2/trucks/{id}/speeding-events` - Violaciones de velocidad

---

## 📞 Soporte

Si hay algún problema durante el deployment:

1. **Verificar logs:** `tail -f wialon_sync.log`
2. **Verificar SQL:** Ejecutar las queries de verificación arriba
3. **Verificar proceso:** `ps aux | grep wialon`
4. **Reintentar:** `sudo systemctl restart wialon-sync.service`

---

**Tiempo estimado de deployment:** 10-15 minutos  
**Última actualización:** 03 de Enero 2025
