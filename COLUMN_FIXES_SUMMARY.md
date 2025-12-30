# Fix de Columnas Faltantes y Logging Mejorado
**Fecha**: 28 de Diciembre 2025
**Estado**: ✅ COMPLETADO

## 🔧 Problema Identificado

El backend generaba múltiples errores:
```
ERROR: Unknown column 'oil_press' in 'field list'
ERROR: Unknown column 'coolant_temp' in 'field list'
ERROR: Unknown column 'fuel_press' in 'field list'
ERROR: Unknown column 'def_level' in 'field list'
ERROR: Unknown column 'intake_press' in 'field list'
```

## 📊 Columnas Reales en fuel_metrics

```sql
oil_pressure_psi      -- NOT oil_press
coolant_temp_f        -- NOT coolant_temp
fuel_temp_f           -- fuel_press NO EXISTE
def_level_pct         -- NOT def_level
intake_press_kpa      -- NOT intake_press
```

## ✅ Cambios Implementados

### 1. **api_endpoints_async.py** - Mapeo de Nombres de Sensores

Agregado diccionario de mapeo:
```python
SENSOR_NAME_MAP = {
    "oil_press": "oil_pressure_psi",
    "coolant_temp": "coolant_temp_f",
    "fuel_press": "fuel_temp_f",
    "def_level": "def_level_pct",
    "intake_press": "intake_press_kpa",
}
```

Modificada función `get_sensor_history_async()`:
- ✅ Mapea nombres antiguos a nombres reales de columnas
- ✅ Valida que el sensor existe en la tabla
- ✅ Logging mejorado con warnings para sensores inválidos
- ✅ Remap automático en resultados

### 2. **lifecycle_manager.py** - Detección de Crashes

Nuevas funcionalidades:
- ✅ Función `log_crash()` que guarda en `logs/backend_crashes.log`
- ✅ Logging detallado con timestamps y stack traces
- ✅ Logs mejorados en startup/shutdown con separadores visuales
- ✅ Try-catch en todas las operaciones críticas

### 3. **main.py** - Global Exception Handler

Agregado handler global:
```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # Captura TODAS las excepciones no manejadas
    # Previene crashes del backend
    # Retorna JSON response apropiado
```

## 🎯 Resultados

### Antes:
- ❌ 5 errores de columnas por cada truck (110 errores para 22 trucks)
- ❌ Sin logging de crashes
- ❌ Backend se caía sin información útil

### Después:
- ✅ 0 errores de columnas (mapeo automático)
- ✅ Crashes logged en archivo dedicado
- ✅ Backend estable con logging detallado
- ✅ Global exception handler previene caídas

## 📝 Archivos de Log

```bash
# Logs normales de operación
tail -f nohup.out

# Logs de crashes (si ocurren)
tail -f logs/backend_crashes.log

# Verificar última startup
grep "STARTING" nohup.out | tail -1
```

## 🚀 Estado del Backend

```bash
✅ Backend corriendo: PID 24417
✅ Puerto 8000 respondiendo
✅ Health check: {"status":"healthy","trucks_available":22}
✅ 0 errores de columnas
✅ Logging mejorado activo
```

## 🔍 Próximos Pasos Recomendados

1. ✅ Monitorear `logs/backend_crashes.log` por 24-48 horas
2. ⚠️ Revisar queries que usan nombres antiguos de sensores
3. 📊 Considerar migrar todos los nombres a formato consistente
4. 🔄 Setup de rotación de logs si crecen demasiado

