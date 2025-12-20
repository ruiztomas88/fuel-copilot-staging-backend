# 📊 Reporte: Datos de Conducción Disponibles en Wialon

**Fecha:** 20 de diciembre de 2025  
**Objetivo:** Identificar datos disponibles para métricas de aceleración y frenadas

---

## ❌ Columnas que NO existen en tabla `trips`

Las siguientes columnas **NO están disponibles** en Wialon:
- `driver` - No hay información de conductor en trips
- `harsh_accel_count` - No hay contador de aceleraciones bruscas
- `harsh_brake_count` - No hay contador de frenadas bruscas  
- `speeding_count` - No hay contador de excesos de velocidad

**Impacto:** El código en `wialon_full_sync_service.py` ya fue corregido (v6.4.2) para NO usar estas columnas.

---

## ✅ Datos Disponibles en Wialon

### 1. 🚨 Tabla `speedings` - Eventos de Exceso de Velocidad

**Descripción:** Tabla dedicada a eventos donde el truck excede el límite de velocidad

**Estadísticas:**
- **Total de eventos:** 178
- **Cobertura temporal:** 223 días (desde abril 2025)
- **Trucks con más eventos:** 
  - Unit 401741096: 125 eventos
  - Unit 401722617: 53 eventos

**Estructura (20 columnas):**
```
- unit                  (ID del truck)
- from_datetime         (inicio del evento)
- to_datetime           (fin del evento)
- from_timestamp        (unix timestamp inicio)
- to_timestamp          (unix timestamp fin)
- from_latitude         (coordenadas inicio)
- from_longitude
- to_latitude           (coordenadas fin)
- to_longitude
- max_speed             (velocidad máxima alcanzada)
- last_speed            (última velocidad registrada)
- limit                 (límite de velocidad de la zona)
- distance_miles        (distancia del evento en millas)
- m, f, state           (metadatos Wialon)
- measure_datetime
- measure_date
- measure_time
- measure_time_seconds
- updateTime
```

**Ejemplo de evento:**
```
Unit: 401722617
Período: 2025-11-17 10:44:54
Velocidad máxima: 66 mph
Límite: 55 mph
Exceso: 11 mph
Ubicación: 34.99°N, 85.20°W
```

**Utilidad para métricas:**
- ✅ Contar eventos de speeding por truck
- ✅ Calcular % de viajes con speeding
- ✅ Identificar zonas de speeding frecuente
- ✅ Medir severidad del exceso (max_speed - limit)

---

### 2. 🛑 Tabla `sensors` - Sensor `brake_switch`

**Descripción:** Eventos cuando el freno es activado

**Estadísticas:**
- **Total de eventos:** 1,704 registros
- **Último registro:** 2025-12-16 22:05:22
- **Valor:** 252-255 (probablemente estado digital ON/OFF)

**Estructura relevante:**
```
- unit              (ID del truck)
- p                 (parámetro = "brake_switch")
- n                 (nombre = "Brake Switch")
- value             (valor del sensor: 252-255)
- from_datetime     (timestamp del evento)
- from_latitude     (ubicación)
- from_longitude
```

**Limitación:**
- ❌ Solo indica ON/OFF del freno
- ❌ No mide intensidad de frenado
- ❌ No clasifica si es "frenada brusca" vs normal

**Utilidad para métricas:**
- ⚠️ Limitada - solo cuenta eventos de frenado
- ⚠️ NO puede clasificar "harsh brake" automáticamente
- ⚠️ Necesitaría análisis adicional (ej: correlación con desaceleración rápida)

---

### 3. 🚗 Otros Sensores Relevantes

**`Engine brake`** (71 registros)
- Freno del motor (engine brake/Jake brake)
- Útil para analizar estilo de conducción en bajadas

**`Average Fuel Economy`** (29 registros)
- Economía de combustible promedio
- Podría correlacionar con estilo de conducción

---

## 💡 Recomendaciones para Implementación

### Opción 1: Métrica de Speeding (Más Viable) ✅

**Tabla origen:** `speedings`

**Métricas a agregar:**
1. **Contador de eventos de speeding** por truck/día
2. **Severidad promedio** del exceso (mph sobre el límite)
3. **% de trips con speeding** 
4. **Ubicaciones frecuentes** de speeding

**Implementación:**
```python
# En wialon_full_sync_service.py
def sync_speeding_events():
    """
    Sincronizar eventos de exceso de velocidad desde Wialon
    """
    query = """
        SELECT 
            unit,
            from_datetime,
            to_datetime,
            max_speed,
            limit,
            (max_speed - limit) as speed_excess,
            from_latitude,
            from_longitude
        FROM speedings
        WHERE from_datetime > %s
        ORDER BY from_datetime
    """
    # Guardar en tabla local 'speeding_events'
```

**Nueva tabla local:**
```sql
CREATE TABLE speeding_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20),
    event_datetime DATETIME,
    max_speed INT,
    speed_limit INT,
    speed_excess INT,
    latitude DOUBLE,
    longitude DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_truck_date (truck_id, event_datetime)
);
```

---

### Opción 2: Análisis de Aceleración/Frenado (Requiere Cálculo) ⚠️

**Problema:** No hay datos directos de "harsh acceleration/braking"

**Solución propuesta:** Calcular desde datos de velocidad

**Enfoque:**
1. Usar `speed` o `obd_speed` de tabla `sensors`
2. Calcular **aceleración** = Δvelocidad / Δtiempo
3. Definir umbrales:
   - Harsh accel: > 8 mph/segundo
   - Harsh brake: < -8 mph/segundo

**Complejidad:**
- ⚠️ Requiere procesamiento de 800K+ registros de velocidad
- ⚠️ Necesita timestamps consecutivos del mismo truck
- ⚠️ Alto costo computacional
- ⚠️ Potencial inexactitud (GPS delay, datos faltantes)

**Implementación:**
```python
def detect_harsh_events_from_speed():
    """
    ADVERTENCIA: Proceso computacionalmente intensivo
    """
    # 1. Obtener series de tiempo de velocidad por truck
    # 2. Calcular diferencias entre lecturas consecutivas
    # 3. Clasificar según umbrales
    # 4. Guardar eventos detectados
```

---

### Opción 3: Frenos (Limitada) ⚠️

**Tabla origen:** `sensors` con `p = 'brake_switch'`

**Métricas posibles:**
- Contador de activaciones del freno por trip
- Frecuencia de uso del freno

**Limitaciones:**
- ❌ NO distingue frenada suave vs brusca
- ❌ Solo 1,704 registros (cobertura limitada)
- ❌ Valor binario (ON/OFF) sin intensidad

---

## 🎯 Recomendación Final

### **IMPLEMENTAR PRIMERO: Speeding Events** ✅

**Razones:**
1. ✅ Datos ya disponibles y limpios en tabla dedicada
2. ✅ 178 eventos con información completa
3. ✅ Implementación sencilla (< 1 día)
4. ✅ Alto valor para safety y compliance
5. ✅ Métricas claras y accionables

**Métricas sugeridas:**
- Dashboard: "Eventos de Speeding por Truck"
- Alertas: Truck excede velocidad > X veces/semana
- Reportes: Top 10 trucks con más speeding
- Mapa: Zonas calientes de speeding

---

### **CONSIDERAR DESPUÉS: Harsh Events Calculados** ⚠️

Solo si se requiere y se valida el esfuerzo:
- Proof of concept con 1-2 trucks
- Validar precisión vs datos reales
- Evaluar carga computacional
- Decidir si vale la pena el costo de procesamiento

---

## 📋 Próximos Pasos

1. **Crear tabla `speeding_events` en base local** ✅
2. **Agregar sync de speedings a `wialon_full_sync_service.py`** ✅
3. **Crear endpoint API para consultar speeding events** ✅
4. **Agregar métrica en dashboard frontend** ✅
5. **Configurar alertas de speeding** ✅

---

## 📊 Código de Validación Ejecutado

Scripts creados durante la investigación:
- `validate_wialon_trips_columns.py` - Validó columnas faltantes
- `explore_wialon_driving_events.py` - Exploró todas las tablas
- `explore_speedings_table.py` - Analizó tabla speedings

**Estado:** ✅ Investigación completada - Datos confirmados
