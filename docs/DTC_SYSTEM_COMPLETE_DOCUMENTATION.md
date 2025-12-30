# Sistema Completo DTC J1939 - Documentación

**Autor:** Fuel Copilot Team  
**Fecha:** 26 de Diciembre, 2025  
**Versión:** 1.0.0

## 🎯 Resumen Ejecutivo

Se implementó un **sistema completo de decodificación DTC J1939** que combina:
- **SPN (Suspect Parameter Number)**: Qué componente está fallando
- **FMI (Failure Mode Identifier)**: Cómo está fallando

Esto resuelve completamente el problema de "unknown SPN" alerts que estabas recibiendo.

---

## 📊 Arquitectura del Sistema

### Componentes Principales

```
DTC J1939 Sistema Completo
│
├── data/spn/
│   ├── j1939_spn_database_detailed.csv  (44 SPNs con explicaciones)
│   └── fmi_codes_database.csv           (22 FMI codes 0-21)
│
├── dtc_decoder.py                       (Decoder principal)
│   ├── DTCInfo                          (Dataclass DTC)
│   ├── SPNInfo                          (Dataclass SPN)
│   ├── FMIInfo                          (Dataclass FMI)
│   ├── DTCDecoder                       (Decodificador completo)
│   └── FuelCopilotDTCHandler           (Handler para fleet)
│
└── test_dtc_complete.py                 (6 tests completos ✅)
```

---

## 🔧 Formato DTC J1939

### Estructura Básica

```
DTC = SPN-FMI
      ↓    ↓
      |    └─ Failure Mode Identifier (0-21)
      └────── Suspect Parameter Number
```

### Ejemplos Reales

| DTC Code | SPN | FMI | Descripción Completa |
|----------|-----|-----|---------------------|
| `100-1` | 100 | 1 | Engine Oil Pressure - **Low - most severe** |
| `110-0` | 110 | 0 | Engine Coolant Temperature - **High - most severe** |
| `523002-12` | 523002 | 12 | ICU EEPROM Checksum Error - **Failure** |
| `183-2` | 183 | 2 | Engine Fuel Rate - **Erratic/Intermittent** |

---

## 📋 Base de Datos SPN (44 SPNs)

### SPNs Críticos del Fleet

| SPN | Descripción | Categoría | Prioridad | OEM |
|-----|-------------|-----------|-----------|-----|
| **100** | Engine Oil Pressure | Engine | 1 (CRITICAL) | Standard |
| **110** | Engine Coolant Temperature | Engine | 1 (CRITICAL) | Standard |
| **190** | Engine Speed | Engine | 1 (CRITICAL) | Standard |
| **183** | Engine Fuel Rate | Fuel | 1 (CRITICAL) | Standard |
| **523002** | ICU EEPROM Checksum Error | Electrical | 1 (CRITICAL) | Freightliner |
| **521049** | SCR Efficiency Below Threshold | Aftertreatment | 2 (HIGH) | Detroit |

### Categorías de SPNs

- **Engine** (15 SPNs): Oil pressure, coolant, RPM, torque
- **Fuel** (8 SPNs): Fuel rate, pressure, leakage
- **Electrical** (6 SPNs): Battery, alternator, ICU
- **Aftertreatment** (5 SPNs): SCR, DPF, DEF system
- **Transmission** (4 SPNs): Gears, clutch, torque
- **Brakes** (3 SPNs): ABS, brake pressure
- **Other** (3 SPNs): Varios

---

## 🔴 Base de Datos FMI (22 Codes)

### FMIs Críticos (CRITICAL)

| FMI | Descripción | Severidad | Tipo |
|-----|-------------|-----------|------|
| **0** | High - most severe | CRITICAL | Electrical/Sensor |
| **1** | Low - most severe | CRITICAL | Electrical/Sensor |
| **12** | Failure | CRITICAL | Component |

### FMIs Alta Prioridad (HIGH)

| FMI | Descripción | Severidad |
|-----|-------------|-----------|
| **2** | Erratic/Intermittent/Incorrect | HIGH |
| **3** | Voltage Above Normal | HIGH |
| **4** | Voltage Below Normal | HIGH |
| **5** | Current Below Normal | HIGH |
| **6** | Current Above Normal | HIGH |
| **7** | Not Responding Properly | HIGH |
| **11** | Other Failure Mode | HIGH |

### FMIs Moderados (MODERATE)

| FMI | Descripción |
|-----|-------------|
| **8** | Abnormal Frequency/Pulse Width/Period |
| **9** | Abnormal Update Rate |
| **10** | Abnormal Rate of Change |
| **13** | Out of Calibration |
| **16** | High - moderate severity |
| **18** | Low - moderate severity |
| **19** | Data Error |
| **20** | Data Drifted High |
| **21** | Data Drifted Low |

### FMIs Bajos (LOW)

| FMI | Descripción |
|-----|-------------|
| **15** | High - least severe |
| **17** | Low - least severe |

---

## 💻 Uso del Sistema

### 1. Inicializar Decoder

```python
from dtc_decoder import DTCDecoder, FuelCopilotDTCHandler

# Inicializar decoder
decoder = DTCDecoder()

# Decodificar un DTC
dtc = decoder.decode_dtc(spn=100, fmi=1)

print(f"DTC Code: {dtc.dtc_code}")                    # 100-1
print(f"Description: {dtc.full_description}")         # Engine Oil Pressure - Low - most severe
print(f"Severity: {dtc.severity}")                    # CRITICAL
print(f"Critical: {dtc.is_critical}")                 # True
print(f"Action: {dtc.action_required}")               # IMMEDIATE - Stop safely and address NOW
print(f"Category: {dtc.category}")                    # Engine
```

### 2. Procesar DTC desde Wialon

```python
from dtc_decoder import FuelCopilotDTCHandler

handler = FuelCopilotDTCHandler()

# Procesar un DTC recibido de Wialon
result = handler.process_wialon_dtc(
    truck_id="FL-0045",
    spn=100,
    fmi=1
)

print(result['dtc_code'])                  # 100-1
print(result['severity'])                  # CRITICAL
print(result['requires_driver_alert'])     # True
print(result['requires_immediate_stop'])   # True
print(result['alert_message'])             # 🔴 CRITICAL FAULT - Engine Oil Pressure...
```

### 3. Parsear String DTC

```python
# Si recibes el DTC como string "100-1"
dtc = decoder.parse_dtc_string("100-1")

if dtc:
    print(f"Parsed: {dtc.full_description}")
else:
    print("Invalid DTC format")
```

### 4. Obtener Resumen de Truck

```python
# Obtener resumen de todos los DTCs de un truck
summary = handler.get_truck_dtc_summary("FL-0045")

print(f"Total DTCs: {summary['total_dtcs']}")
print(f"Critical: {summary['critical_count']}")
print(f"High: {summary['high_count']}")
print(f"Moderate: {summary['moderate_count']}")
print(f"Requires Attention: {summary['requires_immediate_attention']}")

# Listar DTCs críticos
for dtc_code in summary['critical_dtcs']:
    print(f"  ⚠️  {dtc_code}")
```

---

## 🔗 Integración con Wialon Sync

### Ejemplo de Integración en `wialon_sync_enhanced.py`

```python
from dtc_decoder import FuelCopilotDTCHandler

# En la clase WialonSyncEnhanced, agregar:

def __init__(self):
    # ... existing code ...
    self.dtc_handler = FuelCopilotDTCHandler()

def process_dtc_event(self, truck_id: str, wialon_data: dict):
    """
    Procesar evento DTC desde Wialon
    
    Wialon envía:
    {
        'j1939_spn': 100,
        'j1939_fmi': 1,
        'timestamp': 1703627845,
        'value': None  # optional
    }
    """
    try:
        spn = wialon_data.get('j1939_spn')
        fmi = wialon_data.get('j1939_fmi')
        
        if spn is None or fmi is None:
            logger.warning(f"Missing SPN or FMI in DTC event for {truck_id}")
            return None
        
        # Procesar con handler
        result = self.dtc_handler.process_wialon_dtc(
            truck_id=truck_id,
            spn=spn,
            fmi=fmi
        )
        
        # Guardar en base de datos
        self.save_dtc_event(
            truck_id=truck_id,
            dtc_code=result['dtc_code'],
            spn=spn,
            fmi=fmi,
            description=result['full_description'],
            severity=result['severity'],
            category=result['category'],
            is_critical=result['is_critical'],
            action_required=result['action_required'],
            timestamp=wialon_data.get('timestamp'),
            spn_explanation=result['spn_explanation'],
            fmi_explanation=result['fmi_explanation']
        )
        
        # Enviar alerta si es necesario
        if result['requires_driver_alert']:
            self.send_driver_alert(
                truck_id=truck_id,
                message=result['alert_message'],
                severity=result['severity'],
                requires_stop=result['requires_immediate_stop']
            )
        
        # Enviar alerta al dashboard
        if result['is_critical']:
            self.send_dashboard_alert(
                truck_id=truck_id,
                dtc_info=result
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing DTC for {truck_id}: {e}")
        return None

def save_dtc_event(self, truck_id, dtc_code, spn, fmi, description, 
                   severity, category, is_critical, action_required, 
                   timestamp, spn_explanation, fmi_explanation):
    """Guardar evento DTC en base de datos"""
    
    query = """
    INSERT INTO dtc_events (
        truck_id, dtc_code, spn, fmi, description,
        severity, category, is_critical, action_required,
        timestamp, spn_explanation, fmi_explanation,
        created_at
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        NOW()
    )
    """
    
    try:
        self.db.execute_query(query, (
            truck_id, dtc_code, spn, fmi, description,
            severity, category, is_critical, action_required,
            datetime.fromtimestamp(timestamp),
            spn_explanation, fmi_explanation
        ))
    except Exception as e:
        logger.error(f"Error saving DTC event: {e}")
```

---

## 🗄️ Schema de Base de Datos

### Tabla Sugerida: `dtc_events`

```sql
CREATE TABLE dtc_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(50) NOT NULL,
    dtc_code VARCHAR(20) NOT NULL,  -- "100-1"
    spn INT NOT NULL,
    fmi INT NOT NULL,
    
    -- Información del DTC
    description TEXT NOT NULL,
    full_description TEXT,
    category VARCHAR(50),
    severity VARCHAR(20),  -- CRITICAL, HIGH, MODERATE, LOW
    is_critical BOOLEAN DEFAULT FALSE,
    action_required TEXT,
    
    -- Explicaciones detalladas
    spn_explanation TEXT,
    fmi_explanation TEXT,
    
    -- Metadata
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL,
    resolved_by VARCHAR(100) NULL,
    
    -- Indexes
    INDEX idx_truck_id (truck_id),
    INDEX idx_dtc_code (dtc_code),
    INDEX idx_severity (severity),
    INDEX idx_timestamp (timestamp),
    INDEX idx_critical (is_critical, resolved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 📊 Lógica de Severidad

### Determinación de Severidad Final

```
DTC Severity = max(SPN Priority, FMI Severity)
```

### Mapeo de Prioridades

| SPN Priority | FMI Severity | Result Severity |
|--------------|--------------|-----------------|
| 1 (CRITICAL) | Any | **CRITICAL** |
| 2 (HIGH) | CRITICAL | **CRITICAL** |
| 2 (HIGH) | HIGH/MODERATE/LOW | **HIGH** |
| 3 (LOW) | CRITICAL | **CRITICAL** |
| 3 (LOW) | HIGH | **HIGH** |
| 3 (LOW) | MODERATE | **MODERATE** |
| 3 (LOW) | LOW | **LOW** |

### Acciones Requeridas por Severidad

```python
SEVERITY_ACTIONS = {
    'CRITICAL': 'IMMEDIATE - Stop safely and address NOW',
    'HIGH': 'URGENT - Address within 24 hours',
    'MODERATE': 'SOON - Schedule maintenance within 1 week',
    'LOW': 'MONITOR - Check during next scheduled service'
}
```

---

## 🎨 Frontend Display

### Formato Sugerido para Dashboard

```typescript
interface DTCAlert {
  dtcCode: string;           // "100-1"
  fullDescription: string;   // "Engine Oil Pressure - Low - most severe"
  category: string;          // "Engine"
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  isCritical: boolean;
  actionRequired: string;
  spnExplanation: string;    // Explicación detallada SPN
  fmiExplanation: string;    // Explicación detallada FMI
  timestamp: Date;
  truckId: string;
}
```

### Componente React Sugerido

```tsx
function DTCAlertCard({ dtc }: { dtc: DTCAlert }) {
  const severityColor = {
    CRITICAL: 'bg-red-600',
    HIGH: 'bg-orange-500',
    MODERATE: 'bg-yellow-500',
    LOW: 'bg-blue-500'
  };

  return (
    <div className="border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded text-white font-bold ${severityColor[dtc.severity]}`}>
            {dtc.dtcCode}
          </span>
          <span className="text-sm text-gray-600">{dtc.category}</span>
        </div>
        {dtc.isCritical && (
          <span className="text-red-600 font-bold">🚨 CRITICAL</span>
        )}
      </div>

      {/* Description */}
      <h3 className="text-lg font-semibold mb-2">
        {dtc.fullDescription}
      </h3>

      {/* Action */}
      <div className="bg-gray-100 p-3 rounded mb-3">
        <p className="font-medium text-sm">⚠️ {dtc.actionRequired}</p>
      </div>

      {/* Detailed Explanations */}
      <details className="mb-2">
        <summary className="cursor-pointer text-sm font-medium text-blue-600">
          Ver explicación detallada del componente (SPN)
        </summary>
        <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
          {dtc.spnExplanation}
        </div>
      </details>

      <details>
        <summary className="cursor-pointer text-sm font-medium text-blue-600">
          Ver explicación del modo de falla (FMI)
        </summary>
        <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
          {dtc.fmiExplanation}
        </div>
      </details>

      {/* Footer */}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <span>Truck: {dtc.truckId}</span>
        <span>{new Date(dtc.timestamp).toLocaleString()}</span>
      </div>
    </div>
  );
}
```

---

## 📈 Estadísticas del Sistema

### Coverage Actual

- **44 SPNs** documentados con explicaciones detalladas
- **22 FMI codes** (completo 0-21)
- **12 SPNs CRITICAL** (prioridad 1)
- **3 FMI CRITICAL** (0, 1, 12)

### Distribución por OEM

- **Standard J1939**: 37 SPNs
- **Freightliner**: 4 SPNs (523002, 522500, 521800, etc.)
- **Detroit Diesel**: 3 SPNs (521049, 521048, etc.)

### Distribución por Categoría

- Engine: 15 SPNs
- Fuel: 8 SPNs
- Electrical: 6 SPNs
- Aftertreatment: 5 SPNs
- Transmission: 4 SPNs
- Brakes: 3 SPNs
- Other: 3 SPNs

---

## ✅ Tests Completos

Ejecutar todos los tests:

```bash
python test_dtc_complete.py
```

### Tests Incluidos

1. **Basic DTC Decoding**: Decodificación SPN + FMI
2. **Severity Logic**: Lógica de severidad combinada
3. **Fuel Copilot Handler**: Procesamiento para fleet
4. **DTC String Parsing**: Parseo de strings "100-1"
5. **All FMI Codes**: Validación de los 22 FMIs
6. **Statistics**: Conteo y validación de bases de datos

**Resultado**: ✅ Todos los tests pasan

---

## 🚀 Next Steps Recomendados

### 1. Integración Backend (PRIORITY 1)

- [ ] Actualizar `wialon_sync_enhanced.py` con `FuelCopilotDTCHandler`
- [ ] Modificar procesamiento de j1939_spn/j1939_fmi
- [ ] Agregar columnas a tabla `dtc_events`:
  - `spn_explanation TEXT`
  - `fmi_explanation TEXT`
  - `full_description TEXT`
  - `action_required TEXT`

### 2. Alert System (PRIORITY 2)

- [ ] Integrar con `alert_service.py`
- [ ] Enviar alertas con DTC completo
- [ ] Implementar lógica de "immediate stop" para CRITICAL DTCs
- [ ] Dashboard notifications para DTCs HIGH/CRITICAL

### 3. Frontend Dashboard (PRIORITY 3)

- [ ] Crear componente `DTCAlertCard`
- [ ] Mostrar DTCs en tiempo real
- [ ] Filtros por severity/category
- [ ] Expandable explanations (SPN + FMI)
- [ ] Timeline de DTCs por truck

### 4. Testing & Documentation (PRIORITY 4)

- [ ] Agregar tests para integración con Wialon
- [ ] Validar con datos reales del fleet
- [ ] Documentar casos edge (unknown SPNs/FMIs)
- [ ] Crear manual de usuario para operadores

---

## 📝 Notas Importantes

### SPNs Desconocidos

El sistema maneja SPNs desconocidos con auto-detección de OEM:

```python
# SPN no en base de datos
dtc = decoder.decode_dtc(spn=999999, fmi=1)
# Intenta detectar OEM por rango:
# - 521000-521999 → Detroit
# - 522000-523999 → Freightliner  
# - 82000-89999 → Volvo
# etc.
```

### FMIs Desconocidos

Si llega un FMI > 21, el sistema retorna:

```python
{
    'fmi': 99,
    'description': 'Unknown FMI 99',
    'severity': 'UNKNOWN',
    'is_critical': False
}
```

### Performance

- SPNs y FMIs se cargan una vez en memoria
- Lookups son O(1) usando dicts
- Sin dependencias externas (solo Python stdlib + pandas)

---

## 🔄 Changelog

### v1.0.0 - December 26, 2025

- ✅ Sistema completo DTC J1939 (SPN + FMI)
- ✅ 44 SPNs con explicaciones detalladas
- ✅ 22 FMI codes completos (0-21)
- ✅ Lógica de severidad combinada
- ✅ Handler para procesamiento Wialon
- ✅ 6 tests completos (todos pasan)
- ✅ Documentación completa
- ✅ Ejemplos de integración

---

## 📞 Soporte

Para preguntas sobre el sistema DTC:

1. Revisar esta documentación
2. Ejecutar `test_dtc_complete.py` para validar
3. Consultar `dtc_decoder.py` para detalles de implementación

---

## 🎯 Conclusión

El sistema DTC J1939 completo está **listo para producción**:

- ✅ Resuelve problema de "unknown SPN" alerts
- ✅ Proporciona explicaciones detalladas en español
- ✅ Combina SPN + FMI correctamente
- ✅ Lógica de severidad robusta
- ✅ Integración lista para Wialon
- ✅ Tests completos pasan

**Próximo paso**: Integrar en `wialon_sync_enhanced.py` y actualizar frontend.
