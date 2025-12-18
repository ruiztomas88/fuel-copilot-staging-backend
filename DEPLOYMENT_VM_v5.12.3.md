# Deployment a VM - Command Center Integration v5.12.3

## Fecha: 17 Diciembre 2025

---

## ⚠️ IMPORTANTE: NO ES SOLO GIT PULL

Este deployment incluye **migraciones de base de datos CRÍTICAS**. Si solo haces `git pull` sin ejecutar las migraciones, **wialon_sync va a FALLAR** porque va a intentar insertar en columnas que no existen.

---

## 📋 Pasos de Deployment

### 1. Git Pull (obtener código actualizado)

```bash
cd ~/Fuel-Analytics-Backend
git pull origin main
```

**Verificar que obtuviste el commit:**
```bash
git log --oneline -1
# Deberías ver: 4342158 feat: Integrate predictive maintenance sensors into Command Center (v5.12.3)
```

---

### 2. ⚠️ CRÍTICO: Detener wialon_sync

**ANTES de ejecutar las migraciones, DETÉN wialon_sync** para evitar errores durante la migración:

```bash
# Buscar proceso de wialon_sync
ps aux | grep wialon_sync

# Detener el proceso (reemplaza <PID> con el número del proceso)
kill <PID>

# O si está como servicio:
sudo systemctl stop wialon_sync
```

---

### 3. ⚠️ CRÍTICO: Ejecutar Migraciones de Base de Datos

#### Opción A: Usando el script Python (RECOMENDADO)

```bash
cd ~/Fuel-Analytics-Backend

# Ejecutar migración de 19 columnas
python3 -c "
import pymysql
import re

# Leer SQL
with open('migrations/add_all_sensors_v5_12_3.sql', 'r') as f:
    sql = f.read()

# Conectar (ajusta credenciales si es necesario)
conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

# Extraer ALTER statements
alters = re.findall(r'ALTER TABLE[^;]+;', sql, re.IGNORECASE | re.DOTALL)

print(f'Ejecutando {len(alters)} ALTER TABLE statements...\n')

for i, stmt in enumerate(alters, 1):
    col_match = re.search(r'ADD COLUMN (\w+)', stmt)
    col_name = col_match.group(1) if col_match else 'unknown'
    
    try:
        cursor.execute(stmt)
        conn.commit()
        print(f'✅ [{i:2}/{len(alters)}] Added {col_name}')
    except Exception as e:
        if 'Duplicate column' in str(e):
            print(f'⚠️  [{i:2}/{len(alters)}] {col_name} already exists (OK)')
        else:
            print(f'❌ [{i:2}/{len(alters)}] Error: {e}')
            raise

print(f'\n✅ Migraciones completadas!')
conn.close()
"
```

**Resultado esperado:**
```
Ejecutando 14 ALTER TABLE statements...

✅ [ 1/14] Added oil_pressure_psi
✅ [ 2/14] Added oil_temp_f
✅ [ 3/14] Added battery_voltage
✅ [ 4/14] Added engine_load_pct
✅ [ 5/14] Added def_level_pct
✅ [ 6/14] Added ambient_temp_f
✅ [ 7/14] Added intake_air_temp_f
✅ [ 8/14] Added sats
✅ [ 9/14] Added gps_quality
✅ [10/14] Added pwr_int
✅ [11/14] Added terrain_factor
✅ [12/14] Added idle_hours_ecu
✅ [13/14] Added dtc
✅ [14/14] Added dtc_code

✅ Migraciones completadas!
```

---

#### Opción B: Usando MySQL directo

```bash
cd ~/Fuel-Analytics-Backend

# Ejecutar migración con MySQL
mysql -u fuel_admin -p'FuelCopilot2025!' fuel_copilot < migrations/add_all_sensors_v5_12_3.sql
```

---

### 4. Verificar que las Columnas se Crearon

```bash
python3 -c "
import pymysql
conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

# Columnas esperadas
expected = ['oil_pressure_psi', 'oil_temp_f', 'battery_voltage', 'engine_load_pct', 
            'def_level_pct', 'trans_temp_f', 'fuel_temp_f', 'intercooler_temp_f', 
            'intake_air_temp_f', 'intake_press_kpa', 'retarder_level', 'ambient_temp_f',
            'sats', 'gps_quality', 'pwr_int', 'terrain_factor', 'idle_hours_ecu', 
            'dtc', 'dtc_code']

cursor.execute('SHOW COLUMNS FROM fuel_metrics')
existing = [row[0] for row in cursor.fetchall()]

missing = [col for col in expected if col not in existing]

if missing:
    print('❌ FALTAN COLUMNAS:')
    for col in missing:
        print(f'   - {col}')
else:
    print('✅ Todas las 19 columnas existen correctamente')

conn.close()
"
```

**Resultado esperado:**
```
✅ Todas las 19 columnas existen correctamente
```

---

### 5. Reiniciar wialon_sync

Ahora que las columnas existen, reinicia wialon_sync:

```bash
# Si está como servicio:
sudo systemctl start wialon_sync
sudo systemctl status wialon_sync

# O ejecutar manualmente:
cd ~/Fuel-Analytics-Backend
nohup python3 wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &
```

---

### 6. Monitorear que wialon_sync está Guardando Datos

```bash
# Ver logs en tiempo real
tail -f logs/wialon_sync.log

# Verificar que no hay errores de columnas
tail -50 logs/wialon_sync.log | grep -i error
```

**Buscar en los logs:**
- ✅ `💾 Saved metrics for truck_id` - Confirmación de guardado exitoso
- ❌ `Unknown column` - ERROR: Las migraciones no se ejecutaron
- ❌ `Access denied` - ERROR: Problema de permisos de DB

---

### 7. Verificar que los Datos se Están Guardando

Después de ~5-10 minutos de wialon_sync corriendo:

```bash
python3 -c "
import pymysql
conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

cursor.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(oil_temp_f) as has_oil_temp,
        COUNT(trans_temp_f) as has_trans_temp,
        COUNT(intake_air_temp_f) as has_intake_temp,
        COUNT(dtc_code) as has_dtc
    FROM fuel_metrics
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 1 HOUR)
''')

result = cursor.fetchone()
print(f'''
Datos en última hora:
  Total registros: {result[0]}
  Con oil_temp: {result[1]} ({result[1]*100/result[0]:.1f}%)
  Con trans_temp: {result[2]} ({result[2]*100/result[0]:.1f}%)
  Con intake_temp: {result[3]} ({result[3]*100/result[0]:.1f}%)
  Con DTC: {result[4]} ({result[4]*100/result[0]:.1f}%)
''')

conn.close()
"
```

**Resultado esperado (después de 10-30 min):**
```
Datos en última hora:
  Total registros: 150
  Con oil_temp: 45 (30.0%)
  Con trans_temp: 42 (28.0%)
  Con intake_temp: 55 (36.7%)
  Con DTC: 60 (40.0%)
```

---

### 8. (Opcional) Reiniciar Command Center

Si el Command Center está corriendo, reinícialo para que use el query actualizado:

```bash
# Detener
ps aux | grep fleet_command_center
kill <PID>

# O si es servicio:
sudo systemctl restart command_center
```

---

## 🚨 Troubleshooting

### Error: "Unknown column 'oil_pressure_psi' in 'field list'"

**Problema:** Las migraciones NO se ejecutaron correctamente.

**Solución:**
```bash
# Ejecutar manualmente la migración
cd ~/Fuel-Analytics-Backend
python3 run_migration.py
```

---

### Error: "Access denied for user 'fuel_admin'@'localhost'"

**Problema:** Credenciales de DB incorrectas.

**Solución:** Ajustar credenciales en el script de migración:
```bash
# Editar el script con las credenciales correctas
nano run_migration.py
# Cambiar: user='fuel_admin', password='TU_PASSWORD'
```

---

### wialon_sync corre pero NO guarda datos nuevos

**Problema:** wialon_sync está usando una versión vieja del código.

**Solución:**
```bash
# Asegúrate que el proceso usa el código actualizado
pkill -f wialon_sync
cd ~/Fuel-Analytics-Backend
python3 wialon_sync_enhanced.py
```

---

### Command Center no detecta correlaciones

**Problema:** No hay suficientes datos todavía.

**Solución:** Esperar 30-60 minutos para que wialon_sync acumule datos:
```bash
# Verificar datos acumulados
python3 test_command_center_sensors.py
```

---

## ✅ Checklist de Deployment

Marca cada paso al completarlo:

- [ ] 1. Git pull ejecutado
- [ ] 2. wialon_sync detenido
- [ ] 3. Migraciones ejecutadas (19 columnas agregadas)
- [ ] 4. Columnas verificadas (todas existen)
- [ ] 5. wialon_sync reiniciado
- [ ] 6. Logs monitoreados (sin errores)
- [ ] 7. Datos verificados (sensores guardándose)
- [ ] 8. Command Center reiniciado (opcional)

---

## 📊 Resultado Esperado

**Después de 30-60 minutos:**

1. ✅ fuel_metrics tiene **19 columnas nuevas**
2. ✅ wialon_sync está guardando datos de sensores (30-40% cobertura)
3. ✅ Command Center puede detectar correlaciones de fallas
4. ✅ Action items se generan para patrones anormales

**Monitorear:**
```bash
# Ver detecciones de correlaciones
tail -f logs/command_center.log | grep -E "(CORRELATION|OVERHEAT|TURBO)"
```

---

## 🆘 Contacto

Si encuentras problemas durante el deployment, revisar:
- `logs/wialon_sync.log` - Errores de inserción
- `logs/command_center.log` - Errores de query
- [COMMAND_CENTER_INTEGRATION_SUMMARY.md](COMMAND_CENTER_INTEGRATION_SUMMARY.md) - Documentación completa

---

**Versión:** 5.12.3  
**Fecha:** 17 Diciembre 2025  
**Commit:** 4342158
