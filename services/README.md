# 🚀 Servicios Fuel Analytics para macOS - Guía Completa

Este directorio contiene configuraciones para ejecutar el stack completo de Fuel Analytics **24/7** en macOS usando `launchd`.

## 📋 Servicios incluidos

| Servicio | Descripción | Puerto |
|----------|-------------|--------|
| **Backend API** | FastAPI (main.py via uvicorn) | 8000 |
| **Wialon Sync** | Sincronización continua de datos de camiones | - |
| **Frontend** | Servidor de desarrollo Vite (React + TypeScript) | 3000 |

## ⚡ Instalación Rápida (RECOMENDADO)

Ejecuta el script de configuración automatizada:

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services
bash setup_services.sh
```

Este script hace TODO:
- ✅ Crea directorios de logs
- ✅ Detiene servicios existentes
- ✅ Instala configuraciones actualizadas
- ✅ Inicia todos los servicios
- ✅ Verifica que estén corriendo correctamente

## 🎮 Gestión de Servicios (Scripts Simplificados)

### 📊 Ver estado
```bash
bash services/status.sh
```
Muestra el estado de cada servicio y si están escuchando en sus puertos.

### 🔄 Reiniciar todos
```bash
bash services/restart.sh
```
Detiene y reinicia todos los servicios automáticamente.

### ⏹️ Detener todos
```bash
bash services/stop.sh
```
Detiene todos los servicios (sin desinstalarlos).

### 📋 Ver logs
```bash
bash services/logs.sh
```
Menú interactivo para ver logs de cualquier servicio.

### 🗑️ Desinstalar
```bash
bash services/uninstall.sh
```
Elimina completamente los servicios de launchd.

## 📊 Comandos útiles

### Ver logs en tiempo real
```bash
# Todos los logs
tail -f ~/Desktop/Fuel-Analytics-Backend/logs/*.log

# Solo backend
tail -f ~/Desktop/Fuel-Analytics-Backend/logs/backend.log

# Solo wialon
tail -f ~/Desktop/Fuel-Analytics-Backend/logs/wialon.log

# Solo frontend
tail -f ~/Desktop/Fuel-Analytics-Frontend/logs/frontend.log
```

### Control manual de servicios individuales
```bash
# Backend
launchctl start com.fuelanalytics.backend
launchctl stop com.fuelanalytics.backend
launchctl restart com.fuelanalytics.backend

# Wialon
launchctl start com.fuelanalytics.wialon
launchctl stop com.fuelanalytics.wialon

# Frontend
launchctl start com.fuelanalytics.frontend
launchctl stop com.fuelanalytics.frontend
```

### Ver lista de servicios cargados
```bash
launchctl list | grep fuelanalytics
```

### EFrontend Dashboard**: http://localhost:3000
2. **Backend API Docs**: http://localhost:8000/docs
3. **Estado de servicios**: `bash services/status.sh`

### Comandos de verificación rápida
```bash
# Ver si los puertos están abiertos
lsof -ti:8000  # Backend
lsof -ti:3000  # Frontend

# Ver servicios en launchd
launchctl list | grep fuelanalytics
``kend.plist
rm ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
```

## 🔍 Verificación

Después de instalar, verifica que todo esté corriendo:

1. **Backend API**: http://localhost:8000/docs
2. **Frontend**: htProblemas

### ❌ Backend no inicia

1. **Ver logs de error**:
   ```bash
   tail -50 ~/Desktop/Fuel-Analytics-Backend/logs/backend.error.log
   ```

2. **Verificar dependencias**:
   ```bash
   cd ~/Desktop/Fuel-Analytics-Backend
   /opt/anaconda3/bin/python -c "import uvicorn; print('OK')"
   ```

3. **Reiniciar manualmente**:
   ```bash
   launchctl kickstart -k gui/$UID/com.fuelanalytics.backend
   ```

### ❌ Wialon Sync no funciona

1. **Ver logs**:
   ```bash
   tail -50 ~/Desktop/Fuel-Analytics-Backend/logs/wialon.error.log
   ```

2. **Verificar que el script no tenga errores de sintaxis**:
   ```bash
   cd ~/Desktop/Fuel-Analytics-Backend
   /opt/anaconda3/bin/python -m py_compile wialon_sync_enhanced.py
   ```

### ❌ Frontend no inicia

1. **Verificar que npm esté instalado**:
   ```bash
   which npm
   /opt/homebrew/bin/npm --version
   ```

2. **Verificar logs**:
   ```bash
   tail -50 ~/Desktop/Fuel-Analytics-Frontend/logs/frontend.error.log
   ```

### 🔧 Comandos útiles de diagnóstico

```bash
# Ver estado detallado de un servicio
launchctl print gui/$UID/com.fuelanalytics.backend

# Forzar reinicio de un servicio
launchctl kickstart -k gui/$UID/com.fuelanalytics.wialon

# Ver procesos Python corriendo
ps aux | grep python

# Ver qué está usando el puerto 8000
lsof -ti:8000

# Matar proceso en puerto (si es necesario)
kill -9 $(lsof -ti:8000)

### Ver estado detallado
```bash
launchctl print gui/$UID/com.fuelanalytics.backend
```

### Problemas con permisos
```bash
# Asegúrate de que los scripts tengan permisos de ejecución
chmod +x services/*.sh
```

## 📝 Notas importantes

1. Los servicios se ejecutan con tu usuario (no como root)
2. Los logs rotan automáticamente cuando se reinicia el servicio
3. Los servicios NO se ejecutan si no hay sesión de usuario activa
4. Para producción, considera usar diferentes configuraciones

## 🔄 Actualización de configuración

Si modificas los archivos `.plist`:

```bash
# Descargar el servicio
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.backend.plist

# Copiar nueva versión
cp services/com.fuelanalytics.backend.plist ~/Library/LaunchAgents/

# Volver a cargar
launchctl load ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
```

## 🚨 Antes de hacer deploy

Si vas a mover esto a producción o a otro servidor:

1. Actualiza las rutas en los archivos `.plist`
2. Configura las variables de entorno necesarias (JWT_SECRET, passwords, etc.)
3. Considera usar `screen` o `tmux` como alternativa en Linux
4. Para un servidor de producción, usa `systemd` (Linux) o `pm2` (Node.js)
