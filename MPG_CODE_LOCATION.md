# 📊 CÓDIGO MPG - UBICACIÓN Y ARQUITECTURA

## ✅ BACKUPS AUTOMÁTICOS CONFIGURADOS

**Frecuencia:** Cada 6 horas (00:00, 06:00, 12:00, 18:00)  
**Ubicación:** `/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/backups/`  
**Retención:** 7 días (28 backups totales)  
**Tamaño actual:** ~3.5 MB comprimido por backup  

**Verificar cron:**
```bash
crontab -l | grep backup
```

**Restaurar backup:**
```bash
gunzip < backups/fuel_copilot_local_20251229_185438.sql.gz | mysql -u root fuel_copilot_local
```

**Logs:**
- Backup log: `backups/backup.log`
- Cron log: `logs/cron_backup.log`

---

## 🔧 CÓDIGO MPG - ARQUITECTURA

### **1. Cálculo Principal** 
📁 **Archivo:** `wialon_sync_enhanced.py`  
📍 **Líneas:** 2194-2260  

**Función:** Calcula delta_miles y delta_gallons usando **SOLO sensor %**

**Lógica:**
```python
# ✅ Verificar lecturas disponibles
has_odometer = (last_odometer AND odometer > 0)
has_fuel_lvl = (last_fuel_lvl_pct AND sensor_pct)

# Calcular deltas
delta_miles = odometer - last_odometer
fuel_drop_pct = last_fuel_lvl_pct - sensor_pct
delta_gallons = (fuel_drop_pct / 100) × tank_capacity_gal

# Validaciones
- Skip refuels (fuel_drop < -5%)
- Skip cambios pequeños (< 0.05%)
- Skip drops extremos (> 50%)

# Rango válido MPG
instant_mpg = delta_miles / delta_gallons
if 2.0 <= instant_mpg <= 12.0:
    mpg_state = update_mpg_state(...)
```

**⚠️ CAMBIO DEC 29:** Eliminado uso de ECU cumulative (causaba MPG inflado 20-70%)

---

### **2. Estado y Suavizado**
📁 **Archivo:** `mpg_engine_wednesday_utf8.py`  
📍 **Líneas:** 262-350  

**Función:** `update_mpg_state()` - Aplica EMA (Exponential Moving Average)

**Lógica:**
```python
def update_mpg_state(state, delta_miles, delta_gallons, config, truck_id):
    instant_mpg = delta_miles / delta_gallons
    
    # EMA suavizado (α = 0.15)
    mpg_current = (instant_mpg × 0.15) + (last_mpg × 0.85)
    
    # Acumuladores
    state.total_miles += delta_miles
    state.total_gallons += delta_gallons
    state.mpg_overall = total_miles / total_gallons
    
    return state
```

**Parámetros configurables:**
- `alpha = 0.15` (suavizado)
- `fallback_mpg = 5.7` (default cuando no hay datos)

---

### **3. Almacenamiento**
📁 **Base de datos:** MySQL `fuel_copilot_local`  
📊 **Tabla:** `fuel_metrics`  

**Columnas MPG:**
- `mpg_current` - MPG suavizado actual (EMA)
- `odometer_mi` - Odómetro total
- `odom_delta_mi` - Millas recorridas desde última lectura
- `sensor_pct` - Fuel level % del sensor
- `estimated_pct` - Fuel % estimado (Kalman filter)

**Frecuencia guardado:** ~30 segundos por truck

---

### **4. Configuración Tanques**
📁 **Archivo:** `tanks.yaml`  
📍 **Líneas:** 1-480  

**Capacidades:**
- DO9693, DO9356: **220 galones**
- OG2033: **260 galones**
- EM8514: **300 galones**
- Resto: **200 galones**

**Ejemplo:**
```yaml
DO9693:
  carrier_id: skylord
  capacity_gallons: 220
  capacity_liters: 832.79
  unit_id: 402055528
```

---

## 🔄 FLUJO COMPLETO

```
1. Wialon Sync (cada 30s)
   ↓
2. wialon_sync_enhanced.py
   - Lee sensor_pct, odometer
   - Calcula delta_miles, delta_gallons
   - Validaciones (2-12 MPG)
   ↓
3. mpg_engine_wednesday_utf8.py
   - update_mpg_state()
   - Aplica EMA suavizado
   - Actualiza acumuladores
   ↓
4. MySQL fuel_metrics
   - Guarda mpg_current
   - Timestamp, truck_id, GPS, sensores
   ↓
5. Backend API
   - GET /api/fleet → mpg_current
   - GET /api/trucks/{id} → MPG + historial
   ↓
6. Frontend Dashboard
   - TruckMPGComparison.tsx
   - Muestra MPG vs baseline
```

---

## 📝 LOGS Y MONITOREO

**Logs Wialon:**
```bash
tail -f logs/wialon.log | grep "MPG="
```

**Ejemplo output:**
```
[DO9693] ✓ MPG=6.20 (Δmi=12.3, Δgal=1.98, source=tank_level)
```

**Verificar data en MySQL:**
```sql
SELECT truck_id, timestamp_utc, mpg_current, odometer_mi, sensor_pct 
FROM fuel_metrics 
ORDER BY timestamp_utc DESC 
LIMIT 10;
```

---

## 🎯 PRODUCCIÓN vs STAGING

| Aspecto | Producción (Windows) | Staging (Mac) |
|---------|----------------------|---------------|
| Fuel source | sensor % ONLY | ✅ sensor % ONLY (DEC 29) |
| Rango MPG | 2.0 - 12.0 | ✅ 2.0 - 12.0 |
| Tank capacities | tanks.yaml | ✅ tanks.yaml |
| Validaciones | Skip refuels, extremos | ✅ Matching |
| Suavizado | EMA α=0.15 | ✅ EMA α=0.15 |

**Estado:** ✅ CÓDIGO SINCRONIZADO CON PRODUCCIÓN
