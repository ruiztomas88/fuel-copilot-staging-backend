# Fuel Analytics 24/7 Stack - Guía de Uso

## 🚀 Inicio Rápido

### Iniciar todo el stack:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./start_stack.sh
```

### Detener todo el stack:
```bash
./stop_stack.sh
```

## 📊 Componentes

El stack completo consta de 3 servicios:

1. **Backend API** (Puerto 8000)
   - FastAPI server con uvicorn
   - Endpoint: http://localhost:8000
   - Logs: `logs/backend.log`

2. **Wialon Sync** (Servicio de fondo)
   - Sincronización cada 15 segundos
   - Logs: `logs/wialon.log`

3. **Frontend** (Puerto 3000)
   - Vite dev server
   - Endpoint: http://localhost:3000
   - Hot reload habilitado

## 📝 Comandos Útiles

### Ver logs en tiempo real:
```bash
# Backend
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log

# Wialon
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon.log
```

### Verificar que los servicios están corriendo:
```bash
# Backend (debe mostrar PID)
ps aux | grep "python.*main.py" | grep -v grep

# Wialon (debe mostrar PID)
ps aux | grep "wialon_sync_enhanced" | grep -v grep

# Frontend (debe mostrar PID)
ps aux | grep "vite" | grep -v grep

# Puertos (backend y frontend)
lsof -i :8000
lsof -i :3000
```

### Test rápido de conectividad:
```bash
# Backend health check
curl http://localhost:8000/

# Frontend (HTML response)
curl http://localhost:3000
```

## 🔧 Solución de Problemas

### "Address already in use" en puerto 8000:
```bash
# Ver qué proceso usa el puerto
lsof -i :8000

# Matar el proceso manualmente
kill -9 <PID>

# O usar stop_stack.sh
./stop_stack.sh
```

### Backend no inicia:
```bash
# Verificar logs de error
cat logs/backend.log | grep ERROR

# Ejecutar manualmente para ver errores
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
DEV_MODE=false /opt/anaconda3/bin/python main.py
```

### Wialon sync no conecta:
```bash
# Verificar credenciales en .env o hardcoded
grep -i "wialon" wialon_sync_enhanced.py | head -10

# Ver últimos logs
tail -50 logs/wialon.log
```

## 🎯 Ejecución Automática al Login (Opcional)

Para que el stack inicie automáticamente cuando enciendes la Mac:

### Opción 1: Script de Login
1. Abre **Sistema > Preferencias > Usuarios y Grupos**
2. Click en tu usuario
3. Pestaña "Elementos de inicio"
4. Click "+" y agrega `start_stack.sh`

### Opción 2: Alias en .zshrc
```bash
# Agregar a ~/.zshrc
alias fuel-start='/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/start_stack.sh'
alias fuel-stop='/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/stop_stack.sh'
alias fuel-logs='tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log'
```

Luego recarga el terminal:
```bash
source ~/.zshrc
```

Y usa:
```bash
fuel-start  # Iniciar stack
fuel-stop   # Detener stack  
fuel-logs   # Ver logs backend
```

## 📁 Estructura de Logs

```
logs/
├── backend.log      # API logs (FastAPI/Uvicorn)
├── wialon.log       # Sync service logs
└── backend.pid      # PID del proceso backend (si existe)
```

## ⚙️ Variables de Entorno

El backend usa las siguientes variables (opcional):
- `DEV_MODE=false` - Modo producción (sin auto-reload)
- `MYSQL_PASSWORD` - Contraseña MySQL (opcional, usa localhost)
- `LOCAL_DB_PASS` - Contraseña local DB

## 🔐 Seguridad

Los scripts usan `nohup` para mantener procesos corriendo en background.
Los logs se guardan en `/logs/` dentro del directorio del backend.

**IMPORTANTE**: Los procesos corren bajo tu usuario, NO como daemon del sistema.

## 📌 Notas

- El stack usa puertos 8000 (backend) y 3000 (frontend)
- Todos los procesos corren con `nohup` para sobrevivir cierre de terminal
- Los PID se muestran al iniciar para tracking manual si es necesario
- Para producción real, considera usar Docker Compose o PM2

---

✅ **Stack instalado y listo para usar 24/7**

Última actualización: 29 de diciembre 2025
