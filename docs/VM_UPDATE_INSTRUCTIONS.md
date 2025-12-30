# 🖥️ Instrucciones de Actualización para VM Windows

**Fecha:** Diciembre 20, 2025  
**Cambio principal:** Deprecación de `sensor_cache_updater.py` (consolidado en `wialon_sync_enhanced.py`)

---

## ⚠️ IMPORTANTE: sensor_cache_updater ya NO es necesario

El servicio `sensor_cache_updater` fue **deprecado** porque ahora `wialon_sync_enhanced.py` actualiza **AMBAS** tablas:
- ✅ `fuel_metrics` (como siempre)
- ✅ `truck_sensors_cache` (NUEVO - antes lo hacía sensor_cache_updater)

---

## 📋 Pasos de Actualización

### 1️⃣ Detener el servicio sensor_cache_updater (NSSM)

Abrir **PowerShell como Administrador** y ejecutar:

```powershell
# Ver estado actual del servicio
nssm status sensor_cache_updater

# Detener el servicio
nssm stop sensor_cache_updater

# Verificar que se detuvo
nssm status sensor_cache_updater
# Debería decir: SERVICE_STOPPED
```

### 2️⃣ Opcional: Remover el servicio NSSM (recomendado)

Ya no lo vas a necesitar más:

```powershell
# Remover el servicio completamente
nssm remove sensor_cache_updater confirm

# Verificar que se eliminó
nssm status sensor_cache_updater
# Debería decir: Can't open service!
```

### 3️⃣ Hacer pull de los cambios

```powershell
# Navegar al directorio del proyecto
cd C:\path\to\Fuel-Analytics-Backend

# Pull de los cambios
git pull origin main

# Verificar que se descargó correctamente
git log --oneline -5
```

Deberías ver estos commits:
```
9362bdc DEPRECATE: sensor_cache_updater.py - consolidado en wialon_sync_enhanced
e28b4b7 SYNC: Cambios de sesión anterior ya pusheados
3cedaa1 CONFIG: Aumentar MPG max threshold de 9.0 a 12.0 MPG
5e82fed AUDIT: Wialon data exploration y validation scripts
4373fe8 FIX: Sensor naming consistency - corregir odometer_mi y consolidar cache updates
```

### 4️⃣ Verificar que wialon_sync_enhanced esté corriendo

```powershell
# Si tienes wialon_sync_enhanced como servicio NSSM:
nssm status wialon_sync_enhanced

# Si está corriendo, reiniciarlo para cargar los cambios:
nssm restart wialon_sync_enhanced

# Si NO está corriendo, iniciarlo:
nssm start wialon_sync_enhanced
```

**Si NO tienes wialon_sync_enhanced como servicio**, crearlo:

```powershell
# Crear el servicio
nssm install wialon_sync_enhanced "C:\path\to\python.exe" "C:\path\to\Fuel-Analytics-Backend\wialon_sync_enhanced.py"

# Configurar directorio de trabajo
nssm set wialon_sync_enhanced AppDirectory "C:\path\to\Fuel-Analytics-Backend"

# Configurar logs
nssm set wialon_sync_enhanced AppStdout "C:\path\to\Fuel-Analytics-Backend\wialon_sync.log"
nssm set wialon_sync_enhanced AppStderr "C:\path\to\Fuel-Analytics-Backend\wialon_sync_error.log"

# Iniciar automáticamente
nssm set wialon_sync_enhanced Start SERVICE_AUTO_START

# Iniciar el servicio
nssm start wialon_sync_enhanced
```

### 5️⃣ Verificar que truck_sensors_cache se esté actualizando

Esperar 30 segundos y luego ejecutar este script en PowerShell:

```powershell
# Guardar este código en un archivo: check_sensors_cache.ps1
python -c @"
import pymysql
from datetime import datetime, timedelta

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

# Verificar últimas actualizaciones
cursor.execute('''
    SELECT truck_id, timestamp, data_age_seconds,
           rpm, speed_mph, odometer_mi, fuel_level_pct
    FROM truck_sensors_cache
    WHERE timestamp > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
    ORDER BY timestamp DESC
    LIMIT 10
''')

results = cursor.fetchall()
print('=== ÚLTIMAS ACTUALIZACIONES truck_sensors_cache ===')
if results:
    for r in results:
        print(f"{r['truck_id']}: {r['timestamp']} | RPM={r['rpm']}, Speed={r['speed_mph']}, Odom={r['odometer_mi']}")
    print(f'\n✅ Total actualizaciones recientes: {len(results)}')
else:
    print('❌ NO HAY ACTUALIZACIONES RECIENTES - VERIFICAR wialon_sync_enhanced.py')

conn.close()
"@
```

**Resultado esperado:**
```
=== ÚLTIMAS ACTUALIZACIONES truck_sensors_cache ===
DO9693: 2025-12-20 15:30:45 | RPM=1200, Speed=55, Odom=45678
FF7702: 2025-12-20 15:30:30 | RPM=1150, Speed=62, Odom=78901
...
✅ Total actualizaciones recientes: 10
```

### 6️⃣ Verificar logs de wialon_sync_enhanced

```powershell
# Ver últimas líneas del log
Get-Content "C:\path\to\Fuel-Analytics-Backend\wialon_sync.log" -Tail 50
```

**Deberías ver líneas como:**
```
2025-12-20 15:30:45 [INFO] 📋 Updated truck_sensors_cache for DO9693
2025-12-20 15:30:30 [INFO] 📋 Updated truck_sensors_cache for FF7702
2025-12-20 15:30:15 [INFO] ✅ Cycle 1234 complete: 15 trucks, 15 inserted
```

---

## 🔍 Troubleshooting

### ❌ Si truck_sensors_cache NO se actualiza:

```powershell
# 1. Verificar que wialon_sync_enhanced esté corriendo
nssm status wialon_sync_enhanced

# 2. Ver errores en el log
Get-Content "C:\path\to\Fuel-Analytics-Backend\wialon_sync_error.log" -Tail 100

# 3. Reiniciar el servicio
nssm restart wialon_sync_enhanced

# 4. Esperar 30 segundos y verificar nuevamente
Start-Sleep -Seconds 30
# Ejecutar check_sensors_cache.ps1 nuevamente
```

### ❌ Si hay errores de importación:

```powershell
# Activar el virtual environment y reinstalar dependencias
cd C:\path\to\Fuel-Analytics-Backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### ❌ Si sensor_cache_updater sigue corriendo:

```powershell
# Forzar detención
nssm stop sensor_cache_updater

# Si no responde, kill del proceso
Get-Process | Where-Object {$_.Name -like "*sensor_cache*"} | Stop-Process -Force

# Remover el servicio
nssm remove sensor_cache_updater confirm
```

---

## ✅ Validación Final

Ejecutar todos estos checks:

```powershell
# 1. Verificar que sensor_cache_updater esté DETENIDO
nssm status sensor_cache_updater
# Esperado: Can't open service! (o SERVICE_STOPPED)

# 2. Verificar que wialon_sync_enhanced esté CORRIENDO
nssm status wialon_sync_enhanced
# Esperado: SERVICE_RUNNING

# 3. Verificar actualizaciones recientes
python check_sensors_cache.ps1
# Esperado: 10+ registros en últimos 5 minutos

# 4. Verificar logs sin errores
Get-Content "wialon_sync.log" -Tail 20 | Select-String "ERROR"
# Esperado: Sin resultados (o muy pocos)
```

---

## 📊 Resumen de Cambios

| Antes | Ahora |
|-------|-------|
| `wialon_sync_enhanced.py` → `fuel_metrics` | `wialon_sync_enhanced.py` → `fuel_metrics` + `truck_sensors_cache` |
| `sensor_cache_updater.py` → `truck_sensors_cache` | ❌ **DEPRECADO** |
| 2 servicios NSSM | 1 servicio NSSM |
| 2 conexiones a Wialon | 1 conexión a Wialon |
| Datos cada 30s | Datos cada 15s |

---

## 🆘 Si algo falla

1. **NO ENTRES EN PÁNICO** - El archivo viejo está en `_deprecated/sensor_cache_updater.py`
2. **Contactar soporte** con los logs:
   - `wialon_sync.log`
   - `wialon_sync_error.log`
3. **Rollback temporal** (solo si es crítico):
   ```powershell
   copy _deprecated\sensor_cache_updater.py .
   nssm install sensor_cache_updater "C:\path\to\python.exe" "C:\path\to\sensor_cache_updater.py"
   nssm start sensor_cache_updater
   ```

---

**Autor:** GitHub Copilot  
**Última actualización:** Diciembre 20, 2025
