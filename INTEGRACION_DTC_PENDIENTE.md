# ⚠️ INTEGRACIÓN DTC HÍBRIDO - PENDIENTE

**Fecha:** 26 de Diciembre, 2025  
**Status:** ⚠️ 70% COMPLETO - Falta integración final

---

## ✅ LO QUE YA ESTÁ LISTO

### 1. Sistema DTC Híbrido ✅
- ✅ dtc_decoder.py implementado
- ✅ 111 SPNs DETAILED cargados
- ✅ 35,503 SPNs COMPLETE cargados
- ✅ 22 FMI codes completos
- ✅ 781,066 DTCs decodificables
- ✅ Tests 7/7 pasando

### 2. Sistema de Alertas Existente ✅
- ✅ alert_service.py con email + SMS
- ✅ Método `alert_dtc()` funcional
- ✅ Envío de SMS para CRITICAL
- ✅ Envío de Email para WARNING/CRITICAL

### 3. Infraestructura Wialon ✅
- ✅ wialon_sync_enhanced.py procesa DTCs
- ✅ Guarda en tabla `dtc_events`
- ✅ Usa dtc_analyzer.py (sistema antiguo)

---

## ❌ LO QUE FALTA - PARA RECIBIR EMAIL/SMS

### Problema Principal:
**wialon_sync_enhanced.py usa el sistema DTC ANTIGUO (dtc_analyzer.py)**  
**NO está usando el nuevo sistema HÍBRIDO (dtc_decoder.py)**

### Flujo Actual (ANTIGUO):
```
Wialon → wialon_sync_enhanced.py 
       → process_dtc_from_sensor_data() [dtc_analyzer.py - OLD]
       → send_dtc_alert() [con parámetros individuales]
       → alert_service.alert_dtc()
       → Email/SMS
```

### Flujo Necesario (NUEVO):
```
Wialon → wialon_sync_enhanced.py
       → FuelCopilotDTCHandler.process_wialon_dtc() [dtc_decoder.py - NEW]
       → send_dtc_alert(dtc_info=result) [con dict completo]
       → alert_service.alert_dtc()
       → Email/SMS
```

---

## 🔧 CAMBIOS NECESARIOS

### 1. Actualizar wialon_sync_enhanced.py (PRIORITY 1)

**Archivo:** `wialon_sync_enhanced.py`  
**Líneas:** 3254-3327

**Cambio:**
```python
# ANTES (sistema antiguo):
from dtc_analyzer import DTCSeverity, process_dtc_from_sensor_data

dtc_alerts = process_dtc_from_sensor_data(
    truck_id=truck_id,
    dtc_value=str(dtc_to_process),
    timestamp=truck_data.timestamp,
)

# DESPUÉS (sistema híbrido nuevo):
from dtc_decoder import FuelCopilotDTCHandler

dtc_handler = FuelCopilotDTCHandler()

# Procesar DTC con nuevo sistema
result = dtc_handler.process_wialon_dtc(
    truck_id=truck_id,
    spn=extract_spn(dtc_to_process),  # Necesitas parsear SPN
    fmi=extract_fmi(dtc_to_process),  # Necesitas parsear FMI
)

# Enviar alerta con info completa
if result['is_critical']:
    send_dtc_alert(dtc_info=result)  # ✅ Ya soportado en alert_service
```

**Problema:** Wialon envía DTCs en formato string (ej: "100.1,157.3")  
**Solución:** Necesitas parsear el string para extraer SPN y FMI

### 2. Parser de DTCs de Wialon (NUEVO)

**Crear función:**
```python
def parse_wialon_dtc_string(dtc_string: str) -> List[Tuple[int, int]]:
    """
    Parse Wialon DTC string to extract SPN and FMI pairs
    
    Wialon format examples:
    - "100.1" → SPN 100, FMI 1
    - "100.1,157.3" → [(100,1), (157,3)]
    - "523002.12" → SPN 523002, FMI 12
    
    Returns:
        List of (spn, fmi) tuples
    """
    dtc_pairs = []
    
    if not dtc_string or dtc_string in ["0", "1", "0.0", "1.0"]:
        return dtc_pairs
    
    # Split multiple DTCs
    codes = str(dtc_string).split(',')
    
    for code in codes:
        code = code.strip()
        if '.' in code:
            try:
                parts = code.split('.')
                spn = int(parts[0])
                fmi = int(parts[1])
                dtc_pairs.append((spn, fmi))
            except (ValueError, IndexError):
                logger.warning(f"Could not parse DTC: {code}")
                continue
    
    return dtc_pairs
```

### 3. Actualizar save_dtc_event() (MEJORAR)

**Problema:** Actualmente guarda datos del sistema antiguo  
**Solución:** Agregar campos del nuevo sistema híbrido

```python
INSERT INTO dtc_events (
    truck_id, dtc_code, spn, fmi, 
    description, severity, category, 
    is_critical, action_required,
    spn_explanation, fmi_explanation,  # ✅ NEW
    has_detailed_info, oem,            # ✅ NEW
    timestamp, created_at
) VALUES (...)
```

**Migración:** Necesitas agregar columnas a tabla `dtc_events`

---

## 📝 PLAN DE IMPLEMENTACIÓN

### PASO 1: Parser de DTCs (30 min)
```bash
# Crear función parse_wialon_dtc_string() en wialon_sync_enhanced.py
# Test con strings reales de Wialon
```

### PASO 2: Actualizar Database Schema (15 min)
```sql
ALTER TABLE dtc_events 
ADD COLUMN spn_explanation TEXT,
ADD COLUMN fmi_explanation TEXT,
ADD COLUMN has_detailed_info BOOLEAN DEFAULT FALSE,
ADD COLUMN oem VARCHAR(50);
```

### PASO 3: Integrar dtc_decoder en wialon_sync (45 min)
```python
# Reemplazar dtc_analyzer por dtc_decoder
# Actualizar líneas 3254-3327
# Usar FuelCopilotDTCHandler
# Parsear DTCs de Wialon
```

### PASO 4: Tests End-to-End (30 min)
```bash
# Simular DTC de Wialon
# Verificar email/SMS recibidos
# Validar info completa en alertas
```

**TIEMPO TOTAL ESTIMADO: 2 horas**

---

## 📊 ESTADO ACTUAL vs DESEADO

### Estado Actual (70% completo):
```
✅ Sistema DTC híbrido implementado
✅ Alert service con email/SMS
✅ Wialon sync procesa DTCs
❌ NO usa nuevo sistema híbrido
❌ NO extrae info detallada
❌ Emails/SMS con info limitada
```

### Estado Deseado (100% completo):
```
✅ Sistema DTC híbrido implementado
✅ Alert service con email/SMS
✅ Wialon sync usa dtc_decoder
✅ Extrae SPN + FMI correctamente
✅ Emails/SMS con explicaciones completas
✅ has_detailed_info = True para 95% de DTCs
```

---

## 🚨 RESPUESTA A TU PREGUNTA

### ¿Falta algo más o ya está implementado al 100%?
**❌ NO está al 100%. Falta 30% - La integración final.**

### ¿Voy a recibir email/SMS cuando haya un DTC?
**⚠️ SÍ recibirás email/SMS, PERO con el sistema antiguo:**
- ✅ Email/SMS se envían correctamente
- ✅ Para DTCs CRITICAL → SMS + Email
- ✅ Para DTCs WARNING → Solo Email
- ❌ PERO con info limitada (sistema antiguo dtc_analyzer)
- ❌ NO aprovecha las 781,066 DTCs del nuevo sistema
- ❌ NO muestra explicaciones detalladas en español

**Para usar el sistema HÍBRIDO nuevo (781,066 DTCs):**
- ❌ Necesitas hacer la integración (2 horas)
- ❌ Necesitas parsear DTCs de Wialon
- ❌ Necesitas actualizar wialon_sync_enhanced.py

---

## 💡 RECOMENDACIÓN

### Opción 1: Usar Sistema Actual (0 trabajo)
- ✅ Ya recibes email/SMS
- ❌ Info limitada
- ❌ No aprovechas 781,066 DTCs nuevos

### Opción 2: Integrar Sistema Híbrido (2 horas)
- ✅ Email/SMS con explicaciones COMPLETAS
- ✅ 781,066 DTCs decodificables
- ✅ Info detallada en español
- ✅ has_detailed_info flag
- ❌ Requiere 2 horas de trabajo

---

## 🔧 CÓDIGO LISTO PARA COPIAR

### Para cuando hagas la integración:

**1. Parser de DTCs:**
```python
def parse_wialon_dtc_string(dtc_string: str) -> List[Tuple[int, int]]:
    """Parse Wialon DTC string to (spn, fmi) pairs"""
    dtc_pairs = []
    
    if not dtc_string or str(dtc_string) in ["0", "1", "0.0", "1.0"]:
        return dtc_pairs
    
    codes = str(dtc_string).split(',')
    
    for code in codes:
        code = code.strip()
        if '.' in code:
            try:
                parts = code.split('.')
                spn = int(parts[0])
                fmi = int(parts[1])
                dtc_pairs.append((spn, fmi))
            except (ValueError, IndexError):
                logger.warning(f"Could not parse DTC: {code}")
                continue
    
    return dtc_pairs
```

**2. Procesamiento con Sistema Híbrido:**
```python
from dtc_decoder import FuelCopilotDTCHandler

# Inicializar handler (una vez)
dtc_handler = FuelCopilotDTCHandler()

# En el loop de procesamiento:
if dtc_to_process:
    try:
        # Parse DTCs de Wialon
        dtc_pairs = parse_wialon_dtc_string(dtc_to_process)
        
        for spn, fmi in dtc_pairs:
            # Procesar con sistema híbrido
            result = dtc_handler.process_wialon_dtc(
                truck_id=truck_id,
                spn=spn,
                fmi=fmi
            )
            
            # Guardar en database
            save_dtc_event_hybrid(local_conn, truck_id, result)
            
            # Enviar alerta si es crítico
            if result['is_critical']:
                send_dtc_alert(dtc_info=result)
                logger.warning(f"🚨 CRITICAL DTC: {result['dtc_code']}")
            elif result['severity'] == 'HIGH':
                send_dtc_alert(dtc_info=result)
                logger.info(f"⚠️ HIGH DTC: {result['dtc_code']}")
                
    except Exception as e:
        logger.error(f"DTC processing error: {e}")
```

**3. save_dtc_event_hybrid (nueva versión):**
```python
def save_dtc_event_hybrid(connection, truck_id: str, dtc_info: Dict) -> bool:
    """
    Save DTC event with complete hybrid system info
    
    Args:
        dtc_info: Result from FuelCopilotDTCHandler.process_wialon_dtc()
    """
    try:
        cursor = connection.cursor()
        
        # Check if already exists
        cursor.execute(
            """
            SELECT id FROM dtc_events 
            WHERE truck_id = %s 
            AND dtc_code = %s 
            AND resolved_at IS NULL
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            (truck_id, dtc_info['dtc_code'])
        )
        
        if cursor.fetchone():
            return True  # Already exists
        
        # Insert new DTC event
        cursor.execute(
            """
            INSERT INTO dtc_events (
                truck_id, dtc_code, spn, fmi,
                description, severity, category,
                is_critical, action_required,
                spn_explanation, fmi_explanation,
                has_detailed_info, oem,
                timestamp, created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                NOW(), NOW()
            )
            """,
            (
                truck_id,
                dtc_info['dtc_code'],
                dtc_info['spn'],
                dtc_info['fmi'],
                dtc_info['description'],
                dtc_info['severity'],
                dtc_info['category'],
                dtc_info['is_critical'],
                dtc_info['action_required'],
                dtc_info['spn_details'],
                dtc_info['fmi_details'],
                dtc_info['has_detailed_info'],
                dtc_info['oem']
            )
        )
        
        connection.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error saving DTC event: {e}")
        connection.rollback()
        return False
```

---

## ✅ RESUMEN

### Lo que tienes ahora:
- ✅ Sistema DTC híbrido funcionando (781,066 DTCs)
- ✅ Email/SMS funcionando
- ❌ Pero NO están conectados

### Lo que necesitas:
- 2 horas de trabajo para integrar
- Parser de DTCs de Wialon
- Actualizar wialon_sync_enhanced.py
- Agregar columnas a database

### Resultado final:
- ✅ Email/SMS con explicaciones completas
- ✅ Info detallada en español
- ✅ 95% de DTCs con has_detailed_info = True
- ✅ 781,066 DTCs decodificables

**¿Quieres que haga la integración ahora?**
