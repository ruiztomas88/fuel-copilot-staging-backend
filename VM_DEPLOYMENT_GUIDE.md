# 🚀 Deployment en VM Windows - Wialon Full Sync

## ✅ Ya Completado en VM

- ✅ Tabla `truck_sensors_cache` creada
- ✅ Backend API corriendo

---

## 📋 Pasos para Deployar el Nuevo Commit

### Paso 1: Pull los Cambios del Backend

```powershell
# Conectar a la VM (Remote Desktop o PowerShell remoting)
# Abrir PowerShell como Administrador

# Ir al directorio del backend
cd C:\path\to\Fuel-Analytics-Backend

# Pull los últimos cambios
git pull origin main
```

**Commits nuevos que se bajarán:**
- `16cb028` - feat: Add comprehensive Wialon data sync (trips, speeding, driver behavior)
- `0344edc` - docs: Add Wialon sync deployment guide
- `21b47c2` - docs: Add comprehensive Wialon sync implementation summary

---

### Paso 2: Crear las Nuevas Tablas

```powershell
# Ejecutar la migración para las nuevas tablas
python migrations\create_wialon_sync_tables.py
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

```powershell
# Conectar a MySQL (ajusta la ruta según tu instalación)
mysql -u root -p fuel_copilot
# O si MySQL está en el PATH:
# C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe -u root -p fuel_copilot
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
powershell
# Ejecutar y ver los logs en tiempo real
python
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

```powershell
# Iniciar como proceso en background con PowerShell
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "wialon_full_sync_service.py" -RedirectStandardOutput "wialon_sync.log" -RedirectStandardError "wialon_sync_errors.log"

# Ver los logs en tiempo real
Get-Content wialon_sync.log -Wait -Tail 50

# Para salir de los logs: Ctrl+C (el servicio sigue corriendo)
```

---

### Paso 5: Verificar que los Datos se Están Sincronizando

Espera 2-3 minutos y luego verifica:

```bash
mysql -u root -p fuel_copilot
```
powershell
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
powershell
# Endpoint 1: Fleet Driver Behavior
Invoke-WebRequest -Uri "http://localhost:8008/fuelAnalytics/api/v2/fleet/driver-behavior?days=7" -Method GET | Select-Object -ExpandProperty Content

# Endpoint 2: Trips de un truck específico
Invoke-WebRequest -Uri "http://localhost:8008/fuelAnalytics/api/v2/trucks/GS5030/trips?days=7" -Method GET | Select-Object -ExpandProperty Content

# Endpoint 3: Speeding events de un truck
Invoke-WebRequest -Uri "http://localhost:8008/fuelAnalytics/api/v2/trucks/GS5030/speeding-events?days=7" -Method GET | Select-Object -ExpandProperty Content

# Alternativa más simple (si tienes curl instalado en Windows):
curl http://localhost:8008/fuelAnalytics/api/v2/fleet/driver-behavior?days=7

---

### Paso 7: Configurar el Servicio para Auto-Start (Opcional pero Recomendado)
**Opción A: Usar NSSM (Non-Sucking Service Manager) - Recomendado**

```powershell
# 1. Descargar NSSM desde https://nssm.cc/download
# 2. Extraer nssm.exe a C:\tools\nssm\ (o cualquier ubicación)

# Instalar el servicio con NSSM
C:\tools\nssm\nssm.exe install WialonSync python "C:\path\to\Fuel-Analytics-Backend\wialon_full_sync_service.py"

# Configurar el directorio de trabajo
C:\tools\nssm\nssm.exe set WialonSync AppDirectory "C:\path\to\Fuel-Analytics-Backend"

# Configurar los logs
C:\tools\nssm\nssm.exe set WialonSync AppStdout "C:\path\to\Fuel-Analytics-Backend\wialon_sync.log"
C:\tools\nssm\nssm.exe set WialonSync AppStderr "C:\path\to\Fuel-Analytics-Backend\wialon_sync_errors.log"

# Configurar auto-restart
C:\tools\nssm\nssm.exe set WialonSync AppRestartDelay 10000

# Iniciar el servicio
Start-Service WialonSync

# Ver estado
Get-Service WialonSync

# Ver logs
Get-Content C:\path\to\Fuel-Analytics-Backend\wialon_sync.log -Wait -Tail 50
```

**Opción B: Usar Scheduled Task**

```powershell
# Crear una tarea programada que inicie al arrancar
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\Fuel-Analytics-Backend\wialon_full_sync_service.py" -WorkingDirectory "C:\path\to\Fuel-Analytics-Backend"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "WialonSyncService" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Wialon Full Data Sync Service"

# Iniciar la tarea manualmente
Start-ScheduledTask -TaskName "WialonSyncService"

# Ver estado
Get-ScheduledTask -TaskName "WialonSyncService" | Get-ScheduledTaskInfo
```

**Comandos útiles para NSSM:**
```powershell
# Detener el servicio
Stop-Service WialonSync

# Reiniciar el servicio
Restart-Service WialonSync

# Desinstalar el servicio
C:\tools\nssm\nssm.exe remove WialonSync confirm

# Ver logs
Get-Content wialon_sync.log -Wait -Tail 50
```powershell
# Ver logs en tiempo real
Get-Content wialon_sync.log -Wait -Tail 50

# Ver últimos 50 logs
Get-Content wialon_sync.log -Tail 50

# Buscar errores
Select-String -Path wialon_sync.log -Pattern "❌"

# Ver ciclos de sincronización
Select-String -Path wialon_sync.log -Pattern "Sync Cycle" | Select-Object -Last 10

# Verificar proceso corriendo
Get-Process | Where-Object {$_.ProcessName -like "*python*"}

# Verificar servicio (si usas NSSM)
Get-Service WialonSync

# Ver detalles del proceso Python
Get-Process python | Format-List *
tail -f /var/log/wialon_sync.log
```

---powershell
python --version  # Debe ser 3.7+
pip install pymysql
```

**Verificar conexión a Wialon:**
```powershell
mysql -h 20.127.200.135 -u wialonro -p wialon_collect -e "SELECT COUNT(*) FROM sensors;"
# Password: KjmAqwertY1#2024!@Wialon
```

**Verificar conexión local:**
```powershell
mysql -u root -p fuel_copilot -e "SELECT COUNT(*) FROM truck_sensors_cache;"
```

**Verificar firewall:**
```powershell
# Ver reglas de firewall para Python
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*Python*"}

# Agregar regla si es necesario
New-NetFirewallRule -DisplayName "Python MySQL" -Direction Outbound -Program "C:\path\to\python.exe" -Action Allow
```

### No aparecen datos en las tablas

**Verificar logs:**
```powershell
Get-Content wialon_sync.log -Tail 50 | Select-String "❌"
```

**Verificar que el servicio esté corriendo:**
```powershell
# Si usas NSSM:
Get-Service WialonSync

# Si usas Scheduled Task:
Get-ScheduledTask -TaskName "WialonSyncService" | Get-ScheduledTaskInfo

# Verificar proceso Python:
Get-Process | Where-Object {$_.ProcessName -eq "python"}
```

Si no está corriendo, iniciarlo:
```powershell
# Si usas NSSM:
Start-Service WialonSync

# Si usas Scheduled Task:
Start-ScheduledTask -TaskName "WialonSyncService"

# O ejecutar directamente:
pythonstall pymysql
```

**Verificar conexión a Wialon:**
```bashInvoke-WebRequest tests)
- [ ] Servicio configurado para auto-start (NSSM o Scheduled Task)
- [ ] Monitoreo establecido (logs, SQL queries)
- [ ] Firewall configurado (si es necesario
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
SELECT MAX(last_updated)Get-Content wialon_sync.log -Wait -Tail 50`
2. **Verificar SQL:** Ejecutar las queries de verificación arriba
3. **Verificar proceso:** `Get-Process | Where-Object {$_.ProcessName -eq "python"}`
4. **Reintentar:** 
   - NSSM: `Restart-Service WialonSync`
   - Scheduled Task: `Stop-ScheduledTask -TaskName "WialonSyncService"; Start-ScheduledTask -TaskName "WialonSyncService"`

---

**Plataforma:** Windows Server  
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
