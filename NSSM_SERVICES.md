# 🔧 SERVICIOS NSSM - FUEL ANALYTICS BACKEND

## 📋 Servicios Instalados

### 1. **FuelAnalytics-API**
- **Ejecutable**: `C:\Users\devteam\Proyectos\fuel-analytics-backend\venv\Scripts\python.exe`
- **Script**: `main.py`
- **Puerto**: `8000`
- **Función**: 
  - API REST (FastAPI)
  - MPG Engine v2.0.0
  - Kalman Filter para fuel level
  - Predictive Maintenance (LSTM)
  - Theft Detection (ML)
  - Alertas y notificaciones
  - Cost tracking

### 2. **FuelAnalytics-WialonSync**
- **Ejecutable**: `C:\Users\devteam\Proyectos\fuel-analytics-backend\venv\Scripts\python.exe`
- **Script**: `wialon_sync_enhanced.py`
- **Función**:
  - Sincroniza datos de Wialon → MySQL
  - Detecta refuels automáticamente
  - Calcula métricas de combustible
  - Actualiza MPG en tiempo real
  - Depende de: `FuelAnalytics-API` (inicia 10 seg después)

---

## 🚀 Instalación

### Prerequisitos

1. **Descargar NSSM**:
   - URL: https://nssm.cc/download
   - Instalar en: `C:\Program Files\nssm\`

2. **Verificar que Python venv existe**:
   ```powershell
   Test-Path "C:\Users\devteam\Proyectos\fuel-analytics-backend\venv\Scripts\python.exe"
   ```

### Instalar Servicios

```powershell
# Ejecutar como Administrador
.\install-nssm-services.ps1
```

**El script hace**:
1. ✅ Verifica NSSM, Python y directorio del proyecto
2. 🛑 Detiene y remueve servicios existentes (si existen)
3. 📦 Instala `FuelAnalytics-API`
4. 📦 Instala `FuelAnalytics-WialonSync` con dependencia en API
5. 📁 Configura logs en `C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\`
6. 🔄 Configura reinicio automático en caso de fallo
7. 🚀 Inicia ambos servicios
8. ✅ Verifica estado

---

## 🎮 Comandos Útiles

### Ver Estado de Servicios
```powershell
Get-Service FuelAnalytics-*
```

### Iniciar/Detener/Reiniciar

```powershell
# Iniciar
Start-Service FuelAnalytics-API
Start-Service FuelAnalytics-WialonSync

# Detener
Stop-Service FuelAnalytics-API
Stop-Service FuelAnalytics-WialonSync

# Reiniciar
Restart-Service FuelAnalytics-API
Restart-Service FuelAnalytics-WialonSync

# Reiniciar ambos
Restart-Service FuelAnalytics-*
```

### Ver Logs en Tiempo Real

```powershell
# API logs
Get-Content "C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\api-stdout.log" -Wait

# Wialon Sync logs
Get-Content "C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\wialon-stdout.log" -Wait

# Errores
Get-Content "C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\api-stderr.log" -Wait
```

### Configurar Servicio con GUI

```powershell
# Abrir configuración gráfica de NSSM
nssm edit FuelAnalytics-API
```

### Verificar Configuración

```powershell
# Ver toda la configuración de un servicio
nssm dump FuelAnalytics-API

# Ver directorio de trabajo
nssm get FuelAnalytics-API AppDirectory

# Ver comando completo
nssm get FuelAnalytics-API Application
nssm get FuelAnalytics-API AppParameters
```

---

## 🗑️ Desinstalación

```powershell
# Ejecutar como Administrador
.\uninstall-nssm-services.ps1
```

O manualmente:

```powershell
# Detener servicios
Stop-Service FuelAnalytics-API, FuelAnalytics-WialonSync

# Remover servicios
nssm remove FuelAnalytics-API confirm
nssm remove FuelAnalytics-WialonSync confirm
```

---

## 🔧 Configuración Avanzada

### Cambiar Inicio Automático

```powershell
# Inicio automático (por defecto)
nssm set FuelAnalytics-API Start SERVICE_AUTO_START

# Inicio manual
nssm set FuelAnalytics-API Start SERVICE_DEMAND_START

# Deshabilitado
nssm set FuelAnalytics-API Start SERVICE_DISABLED
```

### Configurar Reintentos

```powershell
# Reiniciar siempre en caso de fallo
nssm set FuelAnalytics-API AppExit Default Restart

# Esperar 10 segundos antes de reiniciar
nssm set FuelAnalytics-API AppRestartDelay 10000

# Límite de throttling (evitar reinicio en loop)
nssm set FuelAnalytics-API AppThrottle 5000
```

### Variables de Entorno

```powershell
# Agregar variables de entorno al servicio
nssm set FuelAnalytics-API AppEnvironmentExtra "ENVIRONMENT=production" "DEBUG=false"

# Ver variables configuradas
nssm get FuelAnalytics-API AppEnvironmentExtra
```

### Prioridad del Proceso

```powershell
# Normal (por defecto)
nssm set FuelAnalytics-API AppPriority NORMAL_PRIORITY_CLASS

# Alta
nssm set FuelAnalytics-API AppPriority HIGH_PRIORITY_CLASS
```

---

## 📊 Monitoreo

### Event Viewer (Visor de Eventos de Windows)

Los servicios NSSM registran eventos en:
- **Aplicación** → Buscar por "FuelAnalytics-API" o "FuelAnalytics-WialonSync"

### Performance Monitor

```powershell
# Ver uso de CPU/RAM de los servicios
Get-Process python | Where-Object {$_.Path -like "*fuel-analytics-backend*"}
```

### Health Check

```powershell
# Verificar que la API responde
Invoke-WebRequest -Uri "http://localhost:8000/fuelAnalytics/api/health" | Select-Object StatusCode, Content
```

---

## 🚨 Troubleshooting

### Servicio no inicia

```powershell
# Ver últimos logs
Get-Content "C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\api-stderr.log" -Tail 50

# Ver eventos de Windows
Get-EventLog -LogName Application -Source "FuelAnalytics-API" -Newest 10
```

### Puerto 8000 ocupado

```powershell
# Encontrar qué proceso usa el puerto
Get-NetTCPConnection -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess

# Matar proceso
Stop-Process -Id <PID> -Force
```

### Servicio en loop de reinicio

```powershell
# Detener servicio
Stop-Service FuelAnalytics-API

# Verificar errores en logs
Get-Content "C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\api-stderr.log" -Tail 100

# Probar manualmente
cd "C:\Users\devteam\Proyectos\fuel-analytics-backend"
.\venv\Scripts\python.exe main.py
```

---

## 🔄 Actualización del Código

Cuando hagas `git pull` para actualizar el código:

```powershell
# 1. Ir al directorio
cd "C:\Users\devteam\Proyectos\fuel-analytics-backend"

# 2. Actualizar código
git pull origin main

# 3. Reinstalar dependencias (si hubo cambios en requirements.txt)
.\venv\Scripts\pip.exe install -r requirements.txt

# 4. Reiniciar servicios
Restart-Service FuelAnalytics-API, FuelAnalytics-WialonSync

# 5. Verificar logs
Start-Sleep -Seconds 5
Get-Content "logs\api-stdout.log" -Tail 20
```

---

## 📌 Ventajas de NSSM vs PowerShell Jobs

| Feature | NSSM | PowerShell Jobs (start-services.ps1) |
|---------|------|--------------------------------------|
| Inicio automático con Windows | ✅ | ❌ |
| Reinicio automático en fallo | ✅ | ❌ |
| Logs persistentes | ✅ | ⚠️ (requiere redirección) |
| Gestión desde Services.msc | ✅ | ❌ |
| Independiente de sesión | ✅ | ❌ (se pierden al cerrar sesión) |
| Configuración GUI | ✅ | ❌ |
| Event Viewer integration | ✅ | ❌ |

---

## ✅ Checklist Post-Instalación

- [ ] Ambos servicios aparecen en `services.msc`
- [ ] Estado de servicios = `Running`
- [ ] API responde en http://localhost:8000/docs
- [ ] Logs se generan en `logs/`
- [ ] No hay errores en `api-stderr.log`
- [ ] No hay errores en `wialon-stderr.log`
- [ ] MySQL recibe datos (verificar tabla `fuel_metrics`)
- [ ] Dashboard frontend se conecta correctamente

---

**🎉 Con NSSM, el backend se inicia automáticamente al arrancar Windows y se reinicia en caso de fallo.**
