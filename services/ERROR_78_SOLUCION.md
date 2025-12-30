# 🔧 Solución al Error 78 de LaunchD

## Problema Identificado

El error 78 en macOS launchd ("Function not implemented") puede ocurrir por varias razones:

1. **Falta el shebang** (#!/bin/bash) - ✅ Ya lo tenemos
2. **WorkingDirectory inválido** - ✅ Verificado que existe  
3. **Problemas de permisos en logs** - ✅ Usuario tiene permisos
4. **Usar sudo en ~/Library/LaunchAgents** - ✅ No usamos sudo
5. **macOS Sonoma/Sequoia tiene restricciones adicionales** - ⚠️ Posible causa

## Solución Recomendada: Login Items (Más Simple y Confiable)

En lugar de pelear con launchd, usa el sistema nativo de macOS para ejecutar scripts al iniciar sesión:

### Paso 1: Abrir System Settings

1. Abre **System Settings** (Configuración del Sistema)
2. Ve a **General** → **Login Items**

### Paso 2: Agregar el Script

1. En la sección "Open at Login", haz clic en el botón **+**
2. Navega a:
   ```
   /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/auto_start_on_login.sh
   ```
3. Selecciónalo y haz clic en "Open"

### Paso 3: Verificar Permisos

La primera vez que macOS ejecute el script, puede pedir permisos. Acepta todos los permisos necesarios:
- ✅ Acceso a Terminal/Shell
- ✅ Acceso a red (para el backend)
- ✅ Acceso a archivos

### Alternativa: Automator Application

Si el script simple no funciona, crea una Aplicación con Automator:

1. Abre **Automator**
2. Selecciona **Application** (Aplicación)
3. Busca y arrastra "Run Shell Script"
4. Pega esto:
   ```bash
   sleep 10
   /bin/bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh > /tmp/fuel_startup.log 2>&1
   ```
5. Guarda como: `Fuel Analytics Startup.app` en `/Applications/`
6. Agrega esta app a Login Items (paso 2 de arriba)

## Desactivar LaunchD (Opcional)

Si decidiste no usar launchd, desactiva los servicios:

```bash
# Descargar y remover los servicios de launchd
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.backend.plist 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist 2>/dev/null  
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist 2>/dev/null

# Opcional: Remover los archivos plist
rm ~/Library/LaunchAgents/com.fuelanalytics.*.plist
```

## Solución Manual (Mientras tanto)

Mientras configuras el inicio automático, puedes iniciar los servicios manualmente:

```bash
# Agregar alias a ~/.zshrc
echo 'alias fuel-start="bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh"' >> ~/.zshrc
echo 'alias fuel-stop="bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/stop_all_services.sh"' >> ~/.zshrc
echo 'alias fuel-status="bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/check_status.sh"' >> ~/.zshrc

# Recargar configuración
source ~/.zshrc

# Ahora puedes usar:
fuel-start   # Inicia todos los servicios
fuel-status  # Ver estado
fuel-stop    # Detener todo
```

## Verificación

Después de configurar Login Items, reinicia tu Mac y verifica:

```bash
# Espera 30 segundos después del login, luego ejecuta:
fuel-status

# Deberías ver:
# ✅ Backend corriendo en puerto 8000
# ✅ Wialon Sync activo  
# ✅ Frontend en puerto 3004 (o similar)
```

## Troubleshooting

### Los servicios no inician automáticamente

1. Revisa el log de startup:
   ```bash
   cat /Users/tomasruiz/fuel_analytics_startup.log
   ```

2. Verifica que el script tiene permisos:
   ```bash
   ls -la /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/auto_start_on_login.sh
   # Debe mostrar: -rwxr-xr-x
   ```

3. Prueba ejecutar el script manualmente:
   ```bash
   /bin/bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/auto_start_on_login.sh
   ```

### Quitó macOS el script de Login Items

A veces macOS remueve scripts "no firmados" de Login Items. Solución:

1. Usa la app de Automator (más confiable)
2. O firma el script con tu Developer ID (avanzado)

---

**Conclusión**: Login Items es más simple, más confiable y no tiene los problemas de launchd en macOS moderno. Es la solución recomendada para servicios que solo necesitan correr cuando el usuario está conectado.
