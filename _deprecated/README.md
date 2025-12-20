# 📁 Deprecated Services

Servicios que ya no se usan debido a consolidación o mejoras en el sistema.

---

## ❌ sensor_cache_updater.py

**Deprecado:** Diciembre 20, 2025  
**Razón:** Funcionalidad consolidada en `wialon_sync_enhanced.py`

### ¿Por qué se deprecó?

Antes teníamos 2 servicios leyendo de Wialon:
- `wialon_sync_enhanced.py` → leía cada 15s → guardaba en `fuel_metrics`
- `sensor_cache_updater.py` → leía cada 30s → guardaba en `truck_sensors_cache`

**Problema:**
- Redundancia: 2 servicios haciendo conexiones a Wialon
- Doble carga en la red
- Datos desincronizados (15s vs 30s)

**Solución:**
Consolidamos todo en `wialon_sync_enhanced.py`:
- Lee Wialon cada 15s (más rápido)
- Guarda en **AMBAS** tablas (fuel_metrics + truck_sensors_cache)
- Una sola conexión
- Datos siempre sincronizados

### ¿Cómo se reemplazó?

Se agregó la función `update_sensors_cache()` en `wialon_sync_enhanced.py` (línea 2089):

```python
def update_sensors_cache(connection, metrics: Dict, sensor_data: Dict) -> bool:
    """
    🆕 v6.4.1: Update truck_sensors_cache with latest sensor data.
    This replaces the need for sensor_cache_updater.py service.
    Uses RAW Wialon sensor names (same as sensor_cache_updater.py)
    """
    # ... inserta 52 columnas en truck_sensors_cache
```

Llamado en cada ciclo de sync (línea 2783):
```python
# Save to database
inserted = save_to_fuel_metrics(local_conn, metrics)

# 🆕 v6.4.1: Update sensors cache (replaces sensor_cache_updater.py)
update_sensors_cache(local_conn, metrics, sensor_data)
```

### ¿Es seguro eliminar?

✅ **SÍ** - El archivo se mantiene aquí solo por referencia histórica.

**Validación:**
- ✅ `truck_sensors_cache` se actualiza cada 15s
- ✅ Logs muestran: "📋 Updated truck_sensors_cache for {truck_id}"
- ✅ API v2 endpoint funciona correctamente
- ✅ Todos los sensores mapeados consistentemente

### Documentación relacionada

- [SENSOR_CONSISTENCY_AUDIT.md](../SENSOR_CONSISTENCY_AUDIT.md)
- Commit: `4373fe8` - "FIX: Sensor naming consistency - corregir odometer_mi y consolidar cache updates"

---

**Si necesitás reactivarlo por alguna emergencia:**
```bash
mv _deprecated/sensor_cache_updater.py .
python sensor_cache_updater.py &
```

(Aunque esto NO es recomendado - mejor solucionar el problema en wialon_sync_enhanced.py)
