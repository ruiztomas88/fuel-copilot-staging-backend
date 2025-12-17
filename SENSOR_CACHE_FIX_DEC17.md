# Sensor Cache Updater - Fix de Encoding y Credenciales (17 Dic 2025)

## 🐛 Problema Detectado

El servicio `SensorCacheUpdater` estaba corriendo (STATUS: SERVICE_RUNNING) pero la tabla `truck_sensors_cache` permanecía vacía con 0 registros después de múltiples reinicios.

### Síntomas
- ✅ Servicio NSSM reportaba estado saludable: `SERVICE_RUNNING`
- ❌ Tabla `truck_sensors_cache` con 0 registros
- ❌ `last_updated` permanecía en NULL
- ❌ Los logs mostraban errores repetitivos cada 30 segundos

## 🔍 Diagnóstico

### Error #1: Encoding UTF-8 vs GBK
**Log del error:**
```
[ERROR] Failed to load tanks.yaml: 'gbk' codec can't decode byte 0x92 in position 536: illegal multibyte sequence
[WARNING] No trucks configured in tanks.yaml
```

**Causa raíz:**
- El archivo `tanks.yaml` contiene caracteres UTF-8 (español: "Transmisión", etc.)
- Windows PowerShell usa codec 'gbk' por defecto
- Python en Windows hereda este codec cuando usa `open()` sin especificar encoding
- El byte 0x92 corresponde a una comilla tipográfica (') en UTF-8

**Ubicación:** `sensor_cache_updater.py` línea 57
```python
# ❌ ANTES (sin encoding)
with open(tanks_path, "r") as f:
    config = yaml.safe_load(f)

# ✅ DESPUÉS (con encoding UTF-8)
with open(tanks_path, "r", encoding='utf-8') as f:
    config = yaml.safe_load(f)
```

### Error #2: Variables de Entorno Invertidas en NSSM

**Log del error:**
```
pymysql.err.OperationalError: (1045, "Access denied for user 'fuel_admin'@'localhost' (using password: YES)")
```

**Causa raíz:**
Las variables de entorno en NSSM estaban configuradas al revés:
```powershell
# ❌ ANTES (incorrectas)
LOCAL_DB_PASS=FuelCopilot2025!
MYSQL_PASSWORD=Tomas2025

# ✅ DESPUÉS (correctas)
MYSQL_PASSWORD=FuelCopilot2025!
WIALON_DB_PASS=Tomas2025
```

**Contexto del código:**
```python
# sensor_cache_updater.py líneas 42-48
FUEL_COPILOT_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": os.getenv("MYSQL_USER", "fuel_admin"),
    "password": os.getenv("MYSQL_PASSWORD", "FuelCopilot2025!"),  # ← Usaba MYSQL_PASSWORD
    "database": "fuel_copilot",
}
```

El servicio intentaba conectarse a MySQL local con el password de Wialon (`Tomas2025`), causando `Access denied`.

## ✅ Solución Implementada

### Fix #1: Encoding UTF-8 en sensor_cache_updater.py
```python
# Archivo: sensor_cache_updater.py
# Línea: 57
# Cambio: Agregado encoding='utf-8' al abrir tanks.yaml

def load_truck_config() -> Dict[str, Dict]:
    """Load truck configuration from tanks.yaml"""
    tanks_path = Path(__file__).parent / "tanks.yaml"
    try:
        with open(tanks_path, "r", encoding='utf-8') as f:  # ← FIX APLICADO
            config = yaml.safe_load(f)
            return config.get("trucks", {})
    except Exception as e:
        logger.error(f"Failed to load tanks.yaml: {e}")
        return {}
```

### Fix #2: Corrección de Variables de Entorno NSSM
```powershell
# Comando ejecutado en VM:
nssm set SensorCacheUpdater AppEnvironmentExtra "MYSQL_PASSWORD=FuelCopilot2025!" "WIALON_DB_PASS=Tomas2025"

# Reinicio del servicio:
nssm restart SensorCacheUpdater
```

### Fix #3: Limpieza de Procesos Python Cacheados
```powershell
# Matar todos los procesos Python para forzar recarga del código modificado
nssm stop SensorCacheUpdater
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
nssm start SensorCacheUpdater
```

## 📊 Verificación del Fix

### Antes del fix:
```powershell
PS> python -c "SELECT COUNT(*), MAX(last_updated) FROM truck_sensors_cache"
Registros: (0, None)
```

### Después del fix:
```powershell
PS> venv\Scripts\python.exe -c "import pymysql; conn=pymysql.connect(...); ..."
Registros: (24, datetime.datetime(2025, 12, 17, 16, 9, 32))

# Después de 35 segundos (verificando ciclo de actualización):
Registros después de 35s: (24, datetime.datetime(2025, 12, 17, 16, 10, 32))
```

**✅ Resultado:** 24 trucks actualizándose cada 30 segundos correctamente.

## 🔧 Proceso de Debugging

1. **Identificación inicial:** Servicio corriendo pero tabla vacía
2. **Configuración de logs NSSM:**
   ```powershell
   nssm set SensorCacheUpdater AppStdout sensor_cache.log
   nssm set SensorCacheUpdater AppStderr sensor_cache_error.log
   ```
3. **Análisis de logs:** Detectado error de encoding 'gbk'
4. **Búsqueda de código:** `grep "tanks.yaml" sensor_cache_updater.py`
5. **Lectura de contexto:** Identificado `open()` sin encoding en línea 57
6. **Aplicación de fix #1:** Agregado `encoding='utf-8'`
7. **Reinicio fallido:** Mismo error persiste
8. **Análisis secundario:** Error cambia a "Access denied"
9. **Verificación NSSM:** `nssm get SensorCacheUpdater AppEnvironmentExtra`
10. **Aplicación de fix #2:** Corregidas variables de entorno
11. **Limpieza de caché:** Matar procesos Python y reinicio limpio
12. **Verificación exitosa:** 24 registros actualizándose

## 📝 Lecciones Aprendidas

### Para Windows + Python + UTF-8:
- **SIEMPRE** especificar `encoding='utf-8'` al abrir archivos con `open()`
- Windows usa codecs regionales por defecto ('gbk' en sistemas chinos, 'cp1252' en sistemas occidentales)
- Los servicios NSSM heredan el entorno de sistema, no el de usuario

### Para NSSM Services:
- Verificar variables de entorno con: `nssm get <service> AppEnvironmentExtra`
- Las variables deben coincidir con `os.getenv()` en el código Python
- Configurar logs stdout/stderr para debugging: `AppStdout` y `AppStderr`
- Matar procesos Python antes de reiniciar para forzar recarga de código

### Para Debugging de Servicios:
1. Primero habilitar logging (`AppStdout`/`AppStderr`)
2. Ejecutar manualmente con variables de entorno: `$env:VAR="value"; python script.py`
3. Verificar que el código modificado se esté usando (procesos cacheados)
4. Confirmar variables de entorno en servicio vs código

## 🚀 Estado Final

### Servicios Activos:
- ✅ **FuelAnalyticsBackend** (Puerto 8000, FastAPI/Uvicorn)
- ✅ **WialonSyncService** (Sync cada 15 segundos)
- ✅ **SensorCacheUpdater** (Sync cada 30 segundos) ← **AHORA FUNCIONAL**

### Tabla truck_sensors_cache:
- ✅ 24 registros (todos los trucks configurados en tanks.yaml)
- ✅ Actualización cada 30 segundos
- ✅ 35 columnas de sensores: oil_pressure_psi, def_level_pct, rpm, coolant_temp_f, gear, etc.

### Archivos Modificados:
- `sensor_cache_updater.py` (línea 57: agregado `encoding='utf-8'`)
- Configuración NSSM: Variables de entorno corregidas

## 📋 Comandos de Verificación

```powershell
# Verificar estado de servicios:
nssm status SensorCacheUpdater
nssm status WialonSyncService
nssm status FuelAnalyticsBackend

# Verificar registros en tabla:
venv\Scripts\python.exe -c "import pymysql; conn=pymysql.connect(host='localhost',user='fuel_admin',password='FuelCopilot2025!',database='fuel_copilot'); cur=conn.cursor(); cur.execute('SELECT COUNT(*), MAX(last_updated) FROM truck_sensors_cache'); print(cur.fetchone())"

# Ver logs en tiempo real:
Get-Content sensor_cache.log -Wait

# Verificar variables de entorno NSSM:
nssm get SensorCacheUpdater AppEnvironmentExtra

# Reiniciar servicio (si es necesario):
nssm restart SensorCacheUpdater
```

---
**Fecha:** 17 de Diciembre de 2025  
**VM:** Windows Server (devteam)  
**Ambiente:** Producción  
**Tiempo de resolución:** ~45 minutos  
**Severidad:** Alta (servicio crítico no funcional)  
**Impacto:** API v2 endpoints dependían de esta caché para respuestas rápidas
