# 🚀 Deployment en VM Windows - Fuel Analytics v7.0.0

**Fecha:** 22 Diciembre 2025  
**Build:** ✅ Backend dd94dbb | ✅ Frontend f9629c7  
**Features:** ML v7.0.0 (LSTM + Isolation Forest) + MPG fix

---

## ✅ Prerequisitos en VM Windows

- ✅ Windows Server 2019/2022 o Windows 10/11 Pro
- ✅ Python 3.10+ instalado
- ✅ MySQL 8.0+ instalado y corriendo
- ✅ Git instalado
- ✅ IIS o Nginx para Windows (frontend)
- ✅ Acceso RDP a la VM

---

## 1️⃣ Actualizar Backend en VM

### Conectar a VM
```powershell
# Via Remote Desktop (RDP)
mstsc /v:YOUR_VM_IP

# O via PowerShell remoting
Enter-PSSession -ComputerName YOUR_VM_IP -Credential $cred
```

### Pull Últimos Cambios
```powershell
# Abrir PowerShell como Administrador
cd C:\FuelAnalytics\Backend

# Pull cambios desde GitHub
git pull origin main

# Verificar commit actual
git log --oneline -1
# Esperado: dd94dbb feat: Security & ML Enhancement v7.0.0
```

**Cambios incluidos:**
- ✅ ML v7.0.0: LSTM maintenance + Isolation Forest theft detection
- ✅ MPG fix: Restored miércoles config (5.0mi/0.75gal/9.0max)
- ✅ Security: API key auth + rate limiting
- ✅ 13 nuevas APIs para ML predictions

---

## 2️⃣ Limpiar MPG Inflados

```powershell
# Ejecutar script de limpieza
python reset_inflated_mpg.py
```

**Salida esperada:**
```
🔍 Found 13 trucks with MPG > 9.0
✅ Reset 3611 records with MPG > 9.0
📊 Trucks will recalculate MPG on next sync cycle
```

---

## 3️⃣ Instalar Dependencias ML

```powershell
# Activar entorno virtual (si usas uno)
.\venv\Scripts\Activate.ps1

# O instalar directo
pip install --upgrade pip
pip install scikit-learn tensorflow pandas numpy joblib

# Verificar instalación
python -c "import sklearn, tensorflow; print('✅ ML libs OK')"
```

---

## 4️⃣ Entrenar Modelos ML

```powershell
# Entrenar modelo de robo (Isolation Forest)
# Tarda ~2-3 minutos
python train_theft_model.py
```

**Salida esperada:**
```
🎯 Training Theft Detection Model (Isolation Forest)
📊 Loading training data from last 30 days...
✅ Loaded 45,231 fuel events
🔧 Training model...
✅ Model trained! Accuracy: 94.2%
💾 Model saved to: ml_models/theft_detector.pkl
```

```powershell
# Entrenar modelo de mantenimiento (LSTM)
# Tarda ~5-8 minutos
python train_maintenance_model.py
```

**Salida esperada:**
```
🎯 Training Maintenance Prediction Model (LSTM)
📊 Loading sensor data from last 90 days...
✅ Loaded 128,445 sensor readings
🔧 Training LSTM neural network...
Epoch 1/10 ████████████████████ 100% - Loss: 0.045
Epoch 2/10 ████████████████████ 100% - Loss: 0.032
...
Epoch 10/10 ████████████████████ 100% - Loss: 0.018
✅ Model trained! Validation Accuracy: 91.7%
💾 Model saved to: ml_models/maintenance_predictor.h5
```

---

## 5️⃣ Reiniciar Servicios

### Opción A: Servicios Windows (Recomendado)

```powershell
# Si tienes configurado como servicio Windows
Restart-Service FuelAnalytics-API
Restart-Service FuelAnalytics-Sync

# Ver estado
Get-Service FuelAnalytics-*
```

### Opción B: Proceso Manual

```powershell
# Detener procesos actuales
Get-Process python | Where-Object {$_.MainWindowTitle -like "*wialon*"} | Stop-Process -Force
Get-Process uvicorn | Stop-Process -Force

# Iniciar wialon_sync en background
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\FuelAnalytics\Backend; python wialon_sync_enhanced.py" -WindowStyle Minimized

# Iniciar API en background  
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\FuelAnalytics\Backend; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4" -WindowStyle Minimized
```

### Opción C: Usar NSSM (Non-Sucking Service Manager)

```powershell
# Descargar NSSM desde https://nssm.cc/download
# Descomprimir a C:\nssm

# Crear servicio para API
C:\nssm\nssm.exe install FuelAnalytics-API "C:\Python310\python.exe"
C:\nssm\nssm.exe set FuelAnalytics-API AppParameters "-m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"
C:\nssm\nssm.exe set FuelAnalytics-API AppDirectory "C:\FuelAnalytics\Backend"
C:\nssm\nssm.exe set FuelAnalytics-API Start SERVICE_AUTO_START

# Crear servicio para Sync
C:\nssm\nssm.exe install FuelAnalytics-Sync "C:\Python310\python.exe"
C:\nssm\nssm.exe set FuelAnalytics-Sync AppParameters "wialon_sync_enhanced.py"
C:\nssm\nssm.exe set FuelAnalytics-Sync AppDirectory "C:\FuelAnalytics\Backend"
C:\nssm\nssm.exe set FuelAnalytics-Sync Start SERVICE_AUTO_START

# Iniciar servicios
Start-Service FuelAnalytics-API
Start-Service FuelAnalytics-Sync
```

---

## 6️⃣ Actualizar Frontend

### En tu Mac (Local)
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend

# Build de producción
npm run build

# Copiar a VM via RDP o SCP
# Opción 1: Comprimir
tar -czf dist.tar.gz dist/

# Copiar manualmente via RDP drag-and-drop
# O usar WinSCP/FileZilla
```

### En VM Windows
```powershell
# Descomprimir (si usaste tar)
# Instalar 7-Zip primero si no lo tienes
# Descargar de: https://www.7-zip.org/

# Extraer
cd C:\FuelAnalytics
7z x dist.tar.gz
7z x dist.tar

# Copiar archivos a IIS o Nginx
Copy-Item -Path dist\* -Destination C:\inetpub\wwwroot\fuelanalytics\ -Recurse -Force
```

### Configurar IIS (si usas IIS)
```powershell
# Abrir IIS Manager
inetmgr

# O via PowerShell
Import-Module WebAdministration

# Crear sitio si no existe
New-WebSite -Name "FuelAnalytics" `
    -Port 80 `
    -PhysicalPath "C:\inetpub\wwwroot\fuelanalytics" `
    -ApplicationPool "DefaultAppPool"

# Configurar reverse proxy para /api/
# Necesitas instalar URL Rewrite y ARR primero
# https://www.iis.net/downloads/microsoft/url-rewrite
# https://www.iis.net/downloads/microsoft/application-request-routing

# Crear web.config en C:\inetpub\wwwroot\fuelanalytics\
```

**web.config:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <!-- API Reverse Proxy -->
                <rule name="ReverseProxyAPI" stopProcessing="true">
                    <match url="^api/(.*)" />
                    <action type="Rewrite" url="http://localhost:8000/{R:1}" />
                </rule>
                <!-- SPA Fallback -->
                <rule name="SPA" stopProcessing="true">
                    <match url=".*" />
                    <conditions logicalGrouping="MatchAll">
                        <add input="{REQUEST_FILENAME}" matchType="IsFile" negate="true" />
                        <add input="{REQUEST_FILENAME}" matchType="IsDirectory" negate="true" />
                    </conditions>
                    <action type="Rewrite" url="/index.html" />
                </rule>
            </rules>
        </rewrite>
        <staticContent>
            <mimeMap fileExtension=".json" mimeType="application/json" />
            <mimeMap fileExtension=".woff" mimeType="application/font-woff" />
            <mimeMap fileExtension=".woff2" mimeType="application/font-woff2" />
        </staticContent>
    </system.webServer>
</configuration>
```

---

## 7️⃣ Verificación Post-Deploy

```powershell
# 1. API responde
Invoke-WebRequest -Uri http://localhost:8000/health | Select-Object -Expand Content
# Esperado: {"status":"healthy"}

# 2. ML endpoints funcionan
Invoke-WebRequest -Uri http://localhost:8000/api/v2/ml/theft/predictions | Select-Object -Expand Content
Invoke-WebRequest -Uri http://localhost:8000/api/v2/ml/maintenance/predictions | Select-Object -Expand Content

# 3. Sync está corriendo
Get-Process python | Where-Object {$_.CommandLine -like "*wialon*"}

# 4. Base de datos actualizada
mysql -u fuel_admin -p fuel_copilot -e "SELECT COUNT(*) FROM fuel_metrics WHERE timestamp_utc >= NOW() - INTERVAL 1 HOUR;"

# 5. MPG valores correctos (4-7.5 range)
mysql -u fuel_admin -p fuel_copilot -e "SELECT truck_id, mpg_current FROM fuel_metrics WHERE mpg_current IS NOT NULL AND mpg_current > 0 ORDER BY timestamp_utc DESC LIMIT 20;"
```

**MPG esperado:**
```
+----------+-------------+
| truck_id | mpg_current |
+----------+-------------+
| CO0681   |        6.82 |
| OM7769   |        5.91 |
| JR7099   |        7.12 |
| RT9127   |        5.45 |
| RR1272   |        6.23 |
```

❌ **NO deberías ver:**
- MPG > 9.0 (inflado)
- MPG < 3.5 (demasiado bajo)

---

## 8️⃣ Monitoreo y Logs

```powershell
# Logs en tiempo real
Get-Content C:\FuelAnalytics\Backend\logs\sync_$(Get-Date -Format "yyyyMMdd").log -Wait -Tail 50

# Errores recientes
Get-Content C:\FuelAnalytics\Backend\logs\sync_$(Get-Date -Format "yyyyMMdd").log | Select-String "ERROR"

# Performance
Get-Counter '\Processor(_Total)\% Processor Time'
Get-Counter '\Memory\Available MBytes'

# Procesos Python
Get-Process python | Format-Table Id, CPU, WorkingSet, ProcessName -AutoSize
```

---

## 9️⃣ Backup Automático

```powershell
# Crear script de backup
New-Item -Path "C:\FuelAnalytics\Scripts" -ItemType Directory -Force
notepad C:\FuelAnalytics\Scripts\backup_daily.ps1
```

**backup_daily.ps1:**
```powershell
$BackupDir = "C:\FuelAnalytics\Backups"
$Date = Get-Date -Format "yyyyMMdd_HHmmss"

# Crear directorio si no existe
New-Item -Path $BackupDir -ItemType Directory -Force

# Backup MySQL
$mysqldump = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
& $mysqldump -u fuel_admin -p'TU_PASSWORD' fuel_copilot | Out-File "$BackupDir\db_$Date.sql"

# Comprimir
Compress-Archive -Path "$BackupDir\db_$Date.sql" -DestinationPath "$BackupDir\db_$Date.zip"
Remove-Item "$BackupDir\db_$Date.sql"

# Backup modelos ML
Compress-Archive -Path "C:\FuelAnalytics\Backend\ml_models" -DestinationPath "$BackupDir\models_$Date.zip"

# Limpiar backups antiguos (> 7 días)
Get-ChildItem $BackupDir -Filter "*.zip" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item

Write-Host "✅ Backup completado: $Date"
```

```powershell
# Programar tarea diaria (3 AM)
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\FuelAnalytics\Scripts\backup_daily.ps1"
$Trigger = New-ScheduledTaskTrigger -Daily -At 3am
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "FuelAnalytics-Backup" -Action $Action -Trigger $Trigger -Settings $Settings -User "SYSTEM"
```

---

## 🔟 Troubleshooting

### API no inicia
```powershell
# Ver procesos bloqueando puerto 8000
netstat -ano | findstr :8000

# Matar proceso
Stop-Process -Id PID_AQUI -Force

# Iniciar manualmente para ver errores
cd C:\FuelAnalytics\Backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Sync no sincroniza
```powershell
# Ver errores en logs
Get-Content C:\FuelAnalytics\Backend\logs\sync_$(Get-Date -Format "yyyyMMdd").log | Select-String "ERROR" -Context 3

# Verificar conexión Wialon
python -c "from wialon_reader import WialonReader; w = WialonReader(); print(w.login())"
```

### Frontend no carga
```powershell
# Verificar IIS
Get-Website | Format-Table Name, State, PhysicalPath

# Reiniciar IIS
iisreset /restart

# Ver logs IIS
Get-Content "C:\inetpub\logs\LogFiles\W3SVC1\u_ex$(Get-Date -Format 'yyMMdd').log" -Tail 20
```

### MySQL lento
```powershell
# Optimizar tablas
mysql -u fuel_admin -p fuel_copilot -e "OPTIMIZE TABLE fuel_metrics;"

# Ver queries lentas
mysql -u fuel_admin -p fuel_copilot -e "SHOW FULL PROCESSLIST;"
```

---

## ✅ Checklist Final

- [ ] Backend actualizado a commit dd94dbb
- [ ] MPG inflados reseteados (script ejecutado)
- [ ] Modelos ML entrenados (theft + maintenance)
- [ ] API corriendo en puerto 8000
- [ ] Wialon sync activo
- [ ] Frontend desplegado en IIS
- [ ] Reverse proxy /api/ configurado
- [ ] Backup automático programado
- [ ] Logs monitoreables
- [ ] MPG mostrando 4-7.5 range

---

## 📞 Soporte

**GitHub:** fleetBooster/Fuel-Analytics-Backend  
**Logs:** `C:\FuelAnalytics\Backend\logs\`  
**Config:** Ver `.env` y `config.py`

---

**¡Deployment completado en Windows!** 🎉
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
