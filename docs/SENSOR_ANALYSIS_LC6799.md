# Análisis de Sensores Faltantes - LC6799

## 🔍 Problema Reportado
- Frontend muestra N/A para `gear` y `odometer`
- Se supone que reportan cada 60 segundos

## 📊 Análisis Realizado

### Truck: LC6799 (Unit ID: 402033131)
**Status**: MOVING  
**Última actualización**: 2025-12-30 13:05:11 UTC  
**Speed**: 35.4 mph ✅

### Sensores Reportados (✅):
- `speed`: 35.4 mph
- `coolant_temp`: 100.4°F
- `oil_pressure`: 71.9 psi
- `engine_load`: 31%
- `course`: 97° (dirección)
- `altitude`: 88.6 ft
- `hdop`: 0.6 (GPS accuracy)

### Sensores en NULL (❌):
- `gear`: null
- `odometer`: null (también `odom`)
- `rpm`: 0.0 (apagado o sensor malo)
- `fuel_lvl`: null
- `engine_hours`: null
- `total_fuel_used`: null
- `def_level`: null

## 🚨 Conclusión

**El problema NO es del código de Fuel Copilot**

El GPS/ECU del truck LC6799 simplemente **NO está enviando** estos parámetros a Wialon.

Posibles causas:
1. **GPS no configurado** - Los sensores no están habilitados en Wialon
2. **Cable OBD desconectado** - No hay comunicación J1939 con ECU
3. **ECU incompatible** - El truck no reporta estos parámetros vía J1939
4. **Sensor de transmisión ausente** - No todos los trucks tienen sensor de gear

## 🔧 Verificación en Wialon

### 1. Revisar Configuración de Sensores
En Wialon, ir a:
```
Unidades → LC6799 → Sensores
```

Verificar que estén configurados:
- ✅ **odometer** (Odómetro)
- ✅ **gear** (Marcha)
- ✅ **rpm** (RPM Motor)
- ✅ **engine_hours** (Horas Motor)
- ✅ **fuel_lvl** (Nivel Combustible)

### 2. Verificar Mensajes Recibidos
En Wialon:
```
Unidades → LC6799 → Mensajes
```

Ver qué parámetros está enviando el GPS en tiempo real.

### 3. Revisar Cable OBD
Verificar físicamente:
- Cable OBD conectado al puerto J1939
- LED del GPS indicando comunicación OBD
- Fusible del puerto OBD OK

## 📈 Comparación con Otros Trucks

**Trucks que SÍ reportan odometer:**
- DO9693 ✅
- PC1280 ✅
- RH1522 ✅

**Configuración común:**
- GPS con cable OBD conectado
- Sensores configurados en Wialon
- ECU compatible (Freightliner, Volvo, Kenworth)

## 🛠️ Soluciones Propuestas

### Solución 1: Configurar Sensores en Wialon
1. Login a Wialon
2. Ir a Unidades → LC6799
3. Sensores → Agregar nuevo sensor
4. Tipo: "Odometer" → Parámetro: `odom` o `odometer`
5. Tipo: "Gear" → Parámetro: `gear`
6. Tipo: "Engine RPM" → Parámetro: `rpm`
7. Guardar y esperar 1-2 minutos

### Solución 2: Verificar Hardware
1. Revisar cable OBD del GPS (debe tener conector de 9 pines)
2. Conectar a puerto J1939 del truck (usualmente cerca del volante)
3. Reiniciar GPS
4. Verificar LED de comunicación OBD

### Solución 3: Alternativas si no hay OBD
Si el truck NO tiene conexión OBD:
- Odometer → Calcular por GPS (distancia recorrida)
- RPM → No disponible sin OBD
- Gear → No disponible sin OBD
- Engine Hours → Calcular por tiempo en movimiento

## 📝 Script de Verificación

Para verificar todos los trucks con sensores faltantes:

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
/opt/anaconda3/bin/python -c "
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='fuel_copilot_local',
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cursor:
    # Find trucks with missing sensors
    cursor.execute('''
        SELECT truck_id, 
               COUNT(*) as total_records,
               SUM(CASE WHEN odometer_mi IS NULL THEN 1 ELSE 0 END) as null_odometer,
               SUM(CASE WHEN rpm IS NULL THEN 1 ELSE 0 END) as null_rpm
        FROM fuel_metrics
        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        GROUP BY truck_id
        HAVING null_odometer > 0 OR null_rpm > 0
        ORDER BY null_odometer DESC
    ''')
    
    results = cursor.fetchall()
    print(f'Trucks con sensores faltantes (últimas 24h):\\n')
    for row in results:
        pct_odom = (row['null_odometer'] / row['total_records']) * 100
        pct_rpm = (row['null_rpm'] / row['total_records']) * 100
        print(f'{row[\"truck_id\"]:8} - Odometer NULL: {pct_odom:5.1f}%  RPM NULL: {pct_rpm:5.1f}%')

conn.close()
"
```

## 🎯 Próximos Pasos

1. **Inmediato** - Verificar configuración en Wialon para LC6799
2. **Corto plazo** - Revisar cable OBD del truck
3. **Mediano plazo** - Implementar cálculo de odometer por GPS si no hay OBD
4. **Largo plazo** - Auditar todos los trucks y documentar cuáles NO tienen OBD

## 📞 Contacto

**Proveedor GPS/Wialon** - Para configurar sensores  
**Mecánico/Técnico** - Para verificar cable OBD  
**Fuel Copilot Support** - ruiztomas88@gmail.com

---

**Nota**: Este análisis se realizó el 2025-12-30 basado en datos reales de la base de datos y truck_sensors_cache.
