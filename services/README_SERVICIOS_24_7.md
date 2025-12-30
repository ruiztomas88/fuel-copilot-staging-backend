# 🚀 Fuel Analytics - Guía de Servicios 24/7

## 📋 Descripción

Este sistema está compuesto por 3 servicios principales:

1. **Backend API** (Puerto 8000) - FastAPI con toda la lógica de negocio
2. **Wialon Sync** - Sincronización en tiempo real con Wialon
3. **Frontend** (Puerto variable) - React + Vite interface

## 🎯 Scripts Disponibles

Todos los scripts están en: `/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/`

### ▶️ Iniciar Todos los Servicios

```bash
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh
```

Este script:
- ✅ Inicia Wialon Sync en background
- ✅ Inicia Backend API con todas las variables de entorno
- ✅ Inicia Frontend (Vite dev server)
- ✅ Verifica que cada servicio haya iniciado correctamente
- ✅ Muestra PIDs y puertos de cada servicio

### ⏹️ Detener Todos los Servicios

```bash
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/stop_all_services.sh
```

### 📊 Verificar Estado de Servicios

```bash
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/check_status.sh
```

Este script muestra:
- Procesos corriendo con sus PIDs
- Health check del Backend
- Estado del Frontend con puerto dinámico
- Últimas líneas de los logs

## 🔄 Inicio Automático al Arrancar macOS

### Opción 1: Login Items (Recomendado - Más Simple)

1. Abre **System Settings** → **General** → **Login Items**
2. Haz clic en el botón **+** debajo de "Open at Login"
3. Navega a `/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/`
4. Selecciona `start_all_services_v2.sh`
5. Asegúrate de que el script tenga permisos de ejecución:
   ```bash
   chmod +x /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh
   ```

**Nota**: Puede que macOS pregunte por permisos la primera vez que se ejecuta.

### Opción 2: Automator + Calendar (Inicio Retrasado)

Si quieres que los servicios inicien unos segundos después del login:

1. Abre **Automator** y crea un nuevo **Application**
2. Busca "Run Shell Script" y arrástralo
3. Pega esto:
   ```bash
   sleep 10  # Espera 10 segundos después del login
   /bin/bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh
   ```
4. Guarda como `Start Fuel Analytics.app` en Applications
5. Agrega esta app a Login Items (como en Opción 1)

### Opción 3: Crear Alias en Terminal

Agrega estos alias a tu `~/.zshrc` o `~/.bashrc`:

```bash
# Fuel Analytics Services
alias fuel-start="bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh"
alias fuel-stop="bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/stop_all_services.sh"
alias fuel-status="bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/check_status.sh"
```

Luego recarga la configuración:
```bash
source ~/.zshrc
```

Ahora puedes usar:
```bash
fuel-start   # Inicia todo
fuel-status  # Ver estado
fuel-stop    # Detener todo
```

## 📍 URLs de Acceso

Una vez iniciados los servicios:

- **Backend API**: http://localhost:8000
- **Backend Health**: http://localhost:8000/health
- **Backend Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3004 (o el puerto que muestre Vite)

**Nota**: El frontend usa puerto dinámico. Revisa el output del script de inicio o ejecuta `fuel-status` para ver el puerto actual.

## 📁 Ubicación de Logs

Los logs se guardan en:

```
/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/
├── backend.log      # Log del Backend API
├── wialon.log       # Log de Wialon Sync
└── ...

/Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs/
└── frontend.log     # Log del Frontend
```

Para ver los logs en tiempo real:
```bash
# Backend
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log

# Wialon
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon.log

# Frontend
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs/frontend.log
```

## 🔧 Troubleshooting

### El Backend no inicia

1. Verifica que el archivo `.env` existe:
   ```bash
   ls -la /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/.env
   ```

2. Revisa el log:
   ```bash
   tail -50 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log
   ```

3. Verifica que Python está disponible:
   ```bash
   /opt/anaconda3/bin/python --version
   ```

### El Frontend no responde

1. Verifica que Node está disponible:
   ```bash
   /opt/homebrew/bin/node --version
   ```

2. Revisa el log para ver en qué puerto está corriendo:
   ```bash
   tail -20 /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs/frontend.log
   ```

3. Busca la línea que dice:
   ```
   ➜  Local:   http://localhost:XXXX/
   ```

### Wialon Sync no funciona

1. Verifica que está corriendo:
   ```bash
   ps aux | grep wialon_sync_enhanced.py
   ```

2. Revisa el log:
   ```bash
   tail -50 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon.log
   ```

### Reinicio Completo

Si algo no funciona, reinicia todo:

```bash
# 1. Detener todo
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/stop_all_services.sh

# 2. Esperar 5 segundos
sleep 5

# 3. Iniciar todo
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh

# 4. Verificar estado
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/check_status.sh
```

## ✅ Verificación Rápida

Para verificar que todo está corriendo correctamente:

```bash
# 1. Ejecutar el script de estado
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/check_status.sh

# 2. Deberías ver:
#    ✅ 3 procesos: python main.py, wialon_sync, node vite
#    ✅ Backend health: {"status": "healthy"}
#    ✅ Frontend OK en puerto XXXX
```

## 🎯 Mantenimiento

### Actualizar el código

Cuando hagas cambios en el código:

```bash
# 1. Detener servicios
fuel-stop  # o el script completo

# 2. Actualizar código (git pull, etc.)

# 3. Reiniciar servicios
fuel-start
```

### Limpiar logs antiguos

```bash
# Limpiar logs de hace más de 7 días
find /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/ -name "*.log" -mtime +7 -delete
find /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs/ -name "*.log" -mtime +7 -delete
```

## 📞 Soporte

Si los servicios no inician o tienes problemas, revisa:

1. Los logs en las rutas indicadas arriba
2. Ejecuta el script de estado para diagnóstico
3. Verifica que los puertos no estén siendo usados por otros procesos:
   ```bash
   lsof -i :8000  # Backend
   lsof -i :3000  # Frontend (puede variar)
   ```

---

**Última actualización**: 29 de Diciembre, 2025  
**Versión**: 2.0
