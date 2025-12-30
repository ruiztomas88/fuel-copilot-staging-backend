# Fuel Analytics - macOS Services

Servicios launchd para correr el stack completo 24/7 en macOS.

## 📋 Servicios Incluidos

1. **Backend API** (`com.fuelanalytics.backend`)
   - Puerto: 8000
   - Archivo: `main.py`
   - Logs: `logs/backend.log`

2. **Wialon Sync** (`com.fuelanalytics.wialon`)
   - Sincronización cada 15 segundos
   - Archivo: `wialon_sync_enhanced.py`
   - Logs: `logs/wialon.log`

3. **Frontend Dev Server** (`com.fuelanalytics.frontend`)
   - Puerto: 3000
   - Framework: Vite + React
   - Logs: `../Fuel-Analytics-Frontend/logs/frontend.log`

## 🚀 Instalación

```bash
cd ~/Desktop/Fuel-Analytics-Backend
./install_services.sh
```

Esto hará:
- ✅ Crear directorios de logs
- ✅ Detener servicios existentes
- ✅ Copiar archivos .plist a `~/Library/LaunchAgents/`
- ✅ Cargar y arrancar los 3 servicios
- ✅ Mostrar estado inicial

## 📊 Verificar Estado

```bash
./check_services.sh
```

Muestra:
- Estado de cada servicio (✅ Running / ❌ Not running)
- Puertos escuchando (8000, 3000)
- PIDs de procesos activos
- Últimas 5 líneas de logs

## 🔄 Comandos Útiles

### Ver logs en tiempo real

```bash
# Backend API
tail -f logs/backend.log

# Wialon Sync
tail -f logs/wialon.log

# Frontend
tail -f ../Fuel-Analytics-Frontend/logs/frontend.log

# Errores (si hay)
tail -f logs/backend.error.log
tail -f logs/wialon.error.log
```

### Reiniciar un servicio

```bash
# Reiniciar backend
launchctl kickstart -k gui/$(id -u)/com.fuelanalytics.backend

# Reiniciar wialon
launchctl kickstart -k gui/$(id -u)/com.fuelanalytics.wialon

# Reiniciar frontend
launchctl kickstart -k gui/$(id -u)/com.fuelanalytics.frontend
```

### Detener un servicio

```bash
launchctl bootout gui/$(id -u)/com.fuelanalytics.backend
launchctl bootout gui/$(id -u)/com.fuelanalytics.wialon
launchctl bootout gui/$(id -u)/com.fuelanalytics.frontend
```

### Arrancar un servicio manualmente

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist
```

## 🗑️ Desinstalación

```bash
./uninstall_services.sh
```

Esto:
- Detiene todos los servicios
- Elimina archivos .plist de `~/Library/LaunchAgents/`
- **Preserva** los logs para revisión

## 🔧 Troubleshooting

### Problema: "main.py se cierra inmediatamente"

**Causa:** uvicorn.run() no se mantiene en loop cuando DEV_MODE=false

**Solución:** El service plist ya configura `DEV_MODE=false` y `KeepAlive=true`
- Si se crashea, launchd lo reinicia automáticamente
- Revisa `logs/backend.error.log` para ver el error

### Problema: "Service shows running pero puerto no escucha"

```bash
# Ver detalles del servicio
launchctl print gui/$(id -u)/com.fuelanalytics.backend

# Ver últimas líneas del log
tail -20 logs/backend.error.log

# Reiniciar
launchctl kickstart -k gui/$(id -u)/com.fuelanalytics.backend
```

### Problema: "Too many restarts" (ThrottleInterval)

Si un servicio crashea repetidamente, launchd espera 10 segundos antes de reiniciar (`ThrottleInterval=10`).

Ver errores:
```bash
tail -50 logs/backend.error.log
```

### Problema: "Permission denied"

```bash
# Verificar permisos de archivos .plist
ls -la ~/Library/LaunchAgents/com.fuelanalytics.*.plist

# Deben ser 644 (-rw-r--r--)
chmod 644 ~/Library/LaunchAgents/com.fuelanalytics.*.plist
```

## 📝 Configuración de Servicios

### Backend (main.py)

- **KeepAlive**: Reinicia si termina o crashea
- **DEV_MODE**: false (producción)
- **ThrottleInterval**: 10s entre reinicios
- **ProcessType**: Interactive (no daemon)

### Wialon Sync

- **KeepAlive**: Reinicia si termina
- **Loop**: while True interno con sleep 15s
- **ThrottleInterval**: 10s entre reinicios

### Frontend

- **KeepAlive**: Reinicia si Vite crashea
- **NODE_ENV**: development
- **Hot Reload**: Activado (vite dev server)

## 🎯 Auto-Start al Login

Los servicios se arrancan automáticamente al hacer login (`RunAtLoad=true`).

Para **desactivar** auto-start:
1. Editar el .plist correspondiente
2. Cambiar `<key>RunAtLoad</key>` a `<false/>`
3. Recargar: `launchctl unload` → `launchctl load`

## 📊 Monitoreo

### Health Check Backend

```bash
curl http://localhost:8000/health
```

### Health Check Frontend

```bash
curl http://localhost:3000
```

### Ver procesos activos

```bash
ps aux | grep -E "main.py|wialon_sync|vite" | grep -v grep
```

## 🔒 Seguridad

- Los servicios corren como **user** (no root)
- LaunchAgents en `~/Library/` (scope de usuario)
- Logs en directorios del proyecto (no system logs)

## 📚 Archivos de Servicio

```
~/Library/LaunchAgents/
├── com.fuelanalytics.backend.plist
├── com.fuelanalytics.wialon.plist
└── com.fuelanalytics.frontend.plist

~/Desktop/Fuel-Analytics-Backend/
├── services/
│   ├── com.fuelanalytics.backend.plist (source)
│   └── com.fuelanalytics.wialon.plist (source)
├── logs/
│   ├── backend.log
│   ├── backend.error.log
│   ├── wialon.log
│   └── wialon.error.log
├── install_services.sh
├── uninstall_services.sh
└── check_services.sh

~/Desktop/Fuel-Analytics-Frontend/
├── services/
│   └── com.fuelanalytics.frontend.plist (source)
└── logs/
    ├── frontend.log
    └── frontend.error.log
```

## ✅ Verificación Post-Instalación

1. **Espera 30 segundos** después de `./install_services.sh`
2. Ejecuta `./check_services.sh`
3. Verifica que todos muestren "✅ Running"
4. Prueba los endpoints:
   - http://localhost:8000/health
   - http://localhost:3000
5. Revisa logs si hay problemas

## 🆘 Soporte

Si los servicios no arrancan:

1. Revisa logs de error:
   ```bash
   tail -100 logs/backend.error.log
   tail -100 logs/wialon.error.log
   tail -100 ../Fuel-Analytics-Frontend/logs/frontend.error.log
   ```

2. Verifica que Python/Node estén en el PATH:
   ```bash
   which python3  # Debe ser /opt/anaconda3/bin/python3
   which npm      # Debe ser /opt/homebrew/bin/npm
   ```

3. Prueba ejecución manual:
   ```bash
   cd ~/Desktop/Fuel-Analytics-Backend
   python3 main.py  # Debe arrancar sin errores
   ```

4. Revisa system log de launchd:
   ```bash
   log show --predicate 'subsystem == "com.apple.launchd"' --last 5m | grep fuelanalytics
   ```
