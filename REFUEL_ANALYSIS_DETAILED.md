# 🔍 Análisis Completo: Refuel Detection Issue - MR7679

## 📋 Resumen Ejecutivo

**Problema**: MR7679 tuvo un refuel (69.0% → 80.4%) que se perdió - no fue registrado en la BD.

**Causa Raíz Encontrada**: 
- ✅ **FIXED**: Nombres de columna incorrectos en `save_refuel_event()` de `wialon_sync_enhanced.py`
- ⚠️ **CRITICAL**: El servicio `wialon_sync` no estaba corriendo en el momento del refuel

## 🐛 Bug #1: Column Name Mismatch (FIXED ✅)

### Lugar del Error
- **Archivo**: `/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/wialon_sync_enhanced.py`
- **Función**: `save_refuel_event()`
- **Línea**: ~1473

### El Problema
La función intentaba insertar usando nombres de columna EQUIVOCADOS:

```python
# ❌ LO QUE ESTABA HACIENDO (INCORRECTO):
INSERT INTO refuel_events 
    (timestamp_utc, truck_id, fuel_before, fuel_after, ...)
    
# ✅ LO QUE DEBERÍA HACER (CORRECTO):
INSERT INTO refuel_events 
    (refuel_time, truck_id, before_pct, after_pct, ...)
```

### Mapeo de Columnas
| Campo en el código | Campo correcto en BD | Tipo |
|---|---|---|
| `timestamp_utc` | `refuel_time` | datetime |
| `fuel_before` | `before_pct` | decimal(10,2) |
| `fuel_after` | `after_pct` | decimal(10,2) |

### Impacto
Cuando wialon_sync detectaba un refuel, intentaba guardarlo en la BD, pero fallaba silenciosamente porque MySQL no encontraba esas columnas.

### Fix Aplicado
✅ Actualizado el INSERT query en línea 1473 para usar los nombres correctos.

---

## ⚠️ Problema #2: wialon_sync No Estaba Corriendo

### Verificación
```bash
ps aux | grep wialon_sync_enhanced.py
# Si no hay output → servicio no está corriendo
```

### Por Qué Es Crítico
- `wialon_sync_enhanced.py` es el único proceso que:
  1. Descarga datos de Wialon cada 2-5 minutos
  2. Detecta cambios de combustible
  3. Identifica refuels
  4. Guarda eventos en la BD
  
- **Sin wialon_sync corriendo** → No se detectan refuels, sin importar qué tan buena sea la lógica

### Iniciar el Servicio
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Opción 1: Directo
nohup python3 wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &

# Opción 2: Con el script
bash restart_sync.sh
```

---

## 🧬 Lógica de Detección de Refuel

### Algoritmo de 2 Métodos (Dual Detection)

El código usa **2 métodos independientes** y acepta un refuel si **CUALQUIERA** detecta:

#### Método 1: Kalman
```
Compara:
  - Sensor actual (80.4%)
  - Estimación de Kalman (68.5%)
  
Diferencia = 11.9%
```

**Ventaja**: Tolera el consumo durante gaps (si hay 5 min sin datos)
**Desventaja**: Kalman puede estar calibrado incorrectamente

#### Método 2: Sensor-to-Sensor
```
Compara:
  - Sensor anterior (69.0%)
  - Sensor actual (80.4%)
  
Diferencia = 11.4%
```

**Ventaja**: Simple, directo, sin estimaciones
**Desventaja**: No funciona si hay consumo durante el gap

### Thresholds
Para aceptar un refuel, **AMBOS** criterios deben cumplirse:
- `increase_pct >= 10%` (configurable)
- `increase_gal >= 5 gallons` (configurable)

Para el caso de MR7679:
- Increase: 11.4% ✅ (> 10%)
- Gallons: ~14 gal ✅ (> 5 gal)
- Time gap: 5 min ✅ (entre 5 min y 96 horas)

**→ DEBERÍA detectarse** ✅

---

## 🚀 Cómo Verificar que Funciona

### 1. Verificar que wialon_sync está corriendo
```bash
ps aux | grep wialon_sync_enhanced.py | grep -v grep
```
Debe mostrar:
```
tomasruiz 68701 ... python wialon_sync_enhanced.py
```

### 2. Seguir logs en tiempo real
```bash
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log | grep -i "MR7679\|refuel"
```

### 3. Buscar refuels en la BD
```bash
# Últimos 5 refuels de MR7679
mysql -u root fuel_copilot_local << 'EOF'
SELECT 
    refuel_time, 
    truck_id, 
    before_pct, 
    after_pct, 
    gallons_added, 
    confidence 
FROM refuel_events 
WHERE truck_id = 'MR7679' 
ORDER BY refuel_time DESC 
LIMIT 5;
EOF
```

### 4. Revisar métricas en fuel_metrics
```bash
mysql -u root fuel_copilot_local << 'EOF'
SELECT 
    timestamp_utc, 
    estimated_pct, 
    sensor_pct,
    truck_status 
FROM fuel_metrics 
WHERE truck_id = 'MR7679' 
ORDER BY timestamp_utc DESC 
LIMIT 10;
EOF
```

---

## 📊 Esperado vs Actual

### Cuando ocurre un refuel, deberías ver en los logs:

```
⛽ [MR7679] REFUEL DETECTED (KALMAN): Baseline=69.0% → Sensor=80.4% (+11.4%, +14.2 gal) over 5 min gap
💧 REFUEL DETECTED [MR7679] gallons=14.2 (69.0% → 80.4%) detection_method=KALMAN confidence=90% location=...
✅ [MR7679] Refuel SAVED: 69.0% → 80.4% (+14.2 gal)
💾 Refuel saved to DB: MR7679 +14.2 gal
```

Si **NO ves estos logs**, significa:
1. wialon_sync no está corriendo (más probable)
2. MR7679 no está siendo sincronizado
3. Los datos de Wialon no muestran el refuel

---

## 🔧 Archivos Modificados

1. **wialon_sync_enhanced.py** (Línea ~1473)
   - ✅ Corregidos nombres de columnas en INSERT

2. **Archivos creados para debugging**:
   - `restart_sync.sh` - Script para reiniciar el servicio
   - `test_refuel_detection.py` - Test unitario del algoritmo
   - `check_recent_refuel.sh` - Check rápido de refuels
   - `REFUEL_FIX_NOTES.md` - Notas técnicas
   - `REFUEL_ANALYSIS_DETAILED.md` - Este archivo

---

## ✅ Checklist para Garantizar Refuel Detection

- [ ] `wialon_sync_enhanced.py` está corriendo
- [ ] No hay errores en `logs/wialon_sync.log`
- [ ] Refuels aparecen en los logs cuando ocurren
- [ ] Refuels se guardan en `refuel_events` tabla
- [ ] Frontend muestra los refuels en tiempo real
- [ ] Alertas de refuel se envían (si configuradas)

---

## 📞 Contacto

Si aún hay problemas después de:
1. Reiniciar wialon_sync
2. Aplicar el fix de columnas
3. Verificar logs

Revisar:
- Conexión MySQL (`LOCAL_DB_PASS` configurado)
- Tabla `refuel_events` existe y tiene permisos
- Datos de Wialon llegan (check logs de conexión a Wialon API)
