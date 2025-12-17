# DTC Alert System Improvements - December 2025

## 🎯 Objetivo
Mejorar el sistema de alertas de DTCs (Diagnostic Trouble Codes) para que los emails y el dashboard muestren información relevante y útil en español, en lugar de solo códigos SPN.FMI sin contexto.

## ❌ Problema Anterior
**Usuario reportó:**
> "podes revisar que los dtcs este andando bien, ayer te habia dado los dtc, la lista de spn y fmi la idea era q el dashboard nos reporte exactamente que significa ese dtc y los emails de alerta q me llega no dce nada relevante"

**Email anterior:**
```
🚨 ENGINE DIAGNOSTIC CODE
Code: SPN100.FMI4
System: ENGINE
Problema detectado
```

**Dashboard anterior:**
- Solo mostraba códigos: "100.4", "597.4"
- Texto genérico: "Schedule service - check engine diagnostic codes"

## ✅ Solución Implementada

### 1. Backend: Alertas de Email Mejoradas

#### Archivos modificados:
- `alert_service.py`: Función `alert_dtc()` mejorada
- `dtc_analyzer.py`: Clase `DTCCode` con campos `name_es` y `fmi_description_es`
- `wialon_sync_enhanced.py`: Llamadas a `send_dtc_alert()` actualizadas

#### Nuevo formato de email:
```
🚨 CÓDIGO DE DIAGNÓSTICO DEL MOTOR

🔧 Código: SPN100.FMI4 (SPN 100 / FMI 4)
⚙️ Sistema: ENGINE
📊 Severidad: CRÍTICO

🔍 Componente: Presión de Aceite del Motor
❌ Falla: Voltaje bajo lo normal, o cortocircuito a tierra

✅ Acción Recomendada:
⛔ PARAR INMEDIATAMENTE. Verificar nivel de aceite. NO arrancar si la presión está baja. Riesgo de daño catastrófico al motor.
```

#### Campos nuevos en `alert_dtc()`:
```python
def alert_dtc(
    # ... campos anteriores
    spn: Optional[int] = None,              # 🆕
    fmi: Optional[int] = None,              # 🆕
    spn_name_es: Optional[str] = None,      # 🆕
    fmi_description_es: Optional[str] = None, # 🆕
) -> bool:
```

#### Integración con dtc_database.py v5.8.0:
- 112 SPNs con nombres en español
- 23 FMIs con descripciones completas
- Acciones recomendadas específicas por componente
- Clasificación por sistema (ENGINE, AFTERTREATMENT, COOLING, etc.)

### 2. Frontend: Componente TruckDTCs.tsx

#### Características:
- **Diseño visual mejorado**: Cards con colores por severidad
- **Información completa**:
  - Código (SPN100.FMI4)
  - Componente en español ("Presión de Aceite del Motor")
  - Modo de falla ("Voltaje bajo lo normal...")
  - Sistema afectado (ENGINE, AFTERTREATMENT, etc.)
  - Acción recomendada específica
- **Resumen estadístico**:
  - Total de DTCs
  - Desglose por severidad (Críticos, Advertencias, Info)
  - Sistemas afectados
- **API Integration**: Consume `/api/v2/driver-alerts/{truck_id}/dtc-report`

#### Ejemplo de display:
```
┌─────────────────────────────────────────────────┐
│ 🚨 SPN100.FMI4              [CRÍTICO] badge     │
│ SPN 100 / FMI 4                                 │
│                                                 │
│ 🔧 Componente: Presión de Aceite del Motor     │
│ ⚙️ Sistema: ENGINE                             │
│                                                 │
│ ┌─────────────────────────────────────────────┐│
│ │ Modo de Falla:                              ││
│ │ Voltaje bajo lo normal, o cortocircuito...  ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ┌─────────────────────────────────────────────┐│
│ │ ✅ Acción Recomendada:                      ││
│ │ ⛔ PARAR INMEDIATAMENTE. Verificar...       ││
│ └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

### 3. Testing Completo

Archivo: `test_dtc_alerts_enhanced.py`

**Escenarios probados:**
1. ✅ DTC Crítico único: SPN 100.4 (Oil Pressure)
2. ✅ DTC Advertencia: SPN 597.4 (Cruise Control)
3. ✅ DTCs múltiples: 100.4,1761.0 (Oil + DEF)
4. ✅ API endpoint: `/driver-alerts/{truck}/dtc-report`

**Resultados:**
- ✅ Emails enviados con descripciones completas en español
- ✅ Campos `name_es` y `fmi_description_es` correctos
- ✅ Severidad clasificada correctamente (CRÍTICO/ADVERTENCIA/INFO)
- ✅ Acciones recomendadas específicas por componente
- ✅ API response con estructura completa

## 📊 Comparación Antes vs Después

### Email
| Antes | Después |
|-------|---------|
| "Code: SPN100.FMI4" | "🔧 Código: SPN100.FMI4 (SPN 100 / FMI 4)" |
| "System: ENGINE" | "⚙️ Sistema: ENGINE<br>📊 Severidad: CRÍTICO" |
| "Problema detectado" | "🔍 Componente: Presión de Aceite del Motor<br>❌ Falla: Voltaje bajo lo normal...<br>✅ Acción: ⛔ PARAR INMEDIATAMENTE..." |

### Dashboard
| Antes | Después |
|-------|---------|
| Código simple: "100.4" | Card con badge CRÍTICO |
| "Schedule service" | "Presión de Aceite del Motor" |
| Sin contexto | Modo de falla + acción específica |
| Sin información de sistema | "Sistema: ENGINE" + resumen de sistemas afectados |

## 🔧 Componentes Técnicos

### dtc_database.py v5.8.0
- **112 SPNs** con información completa
- **23 FMIs** con descripciones en español
- **6 sistemas**: ENGINE, TRANSMISSION, AFTERTREATMENT, COOLING, ELECTRICAL, BRAKES
- **Severidades**: CRITICAL, WARNING, INFO

### Flujo de Datos
```
1. Wialon sensor → dtc_string: "100.4,1761.0"
2. wialon_sync_enhanced.py → process_dtc_from_sensor_data()
3. dtc_analyzer.py → parse + lookup dtc_database.py
4. DTCCode con name_es + fmi_description_es
5. send_dtc_alert() → email con info completa
6. Frontend TruckDTCs.tsx → API call → display completo
```

## 📈 Ejemplos de DTCs Comunes

### SPN 100 - Presión de Aceite
- **FMI 0**: Datos sobre rango normal → "Presión de aceite anormalmente alta"
- **FMI 1**: Datos bajo rango normal → "Presión de aceite anormalmente baja"
- **FMI 4**: Voltaje bajo → "Sensor de presión de aceite con cortocircuito"

### SPN 1761 - Nivel DEF
- **FMI 0**: Sobre rango → "Nivel DEF reportado sobre 100%"
- **FMI 1**: Bajo rango → "Nivel DEF crítico - riesgo de derate"
- **FMI 18**: Abajo de valor mínimo → "Tanque DEF completamente vacío"

### SPN 110 - Temperatura Refrigerante
- **FMI 0**: Sobre rango → "Sobrecalentamiento del motor"
- **FMI 1**: Bajo rango → "Motor no alcanza temperatura operativa"

## 🎨 Paleta de Colores (Dashboard)

```typescript
CRÍTICO:
  - Background: bg-red-50 dark:bg-red-900/20
  - Border: border-red-200 dark:border-red-800
  - Text: text-red-700 dark:text-red-400
  - Badge: bg-red-100 text-red-700

ADVERTENCIA:
  - Background: bg-yellow-50 dark:bg-yellow-900/20
  - Border: border-yellow-200 dark:border-yellow-800
  - Text: text-yellow-700 dark:text-yellow-400
  - Badge: bg-yellow-100 text-yellow-700

INFO:
  - Background: bg-blue-50 dark:bg-blue-900/20
  - Border: border-blue-200 dark:border-blue-800
  - Text: text-blue-700 dark:text-blue-400
  - Badge: bg-blue-100 text-blue-700
```

## 🚀 Deployment

### Backend
```bash
cd Fuel-Analytics-Backend
git pull origin main
# Servicio se actualiza automáticamente (wialon_sync_enhanced.py con DTC alerts)
```

### Frontend
```bash
cd Fuel-Analytics-Frontend
git pull origin main
npm run build
# Deploy to Vercel/Netlify
```

## 🧪 Testing en Producción

### Verificar Email
1. Esperar un DTC real del truck
2. Revisar email recibido
3. Verificar formato:
   - ✅ Código con SPN/FMI
   - ✅ Componente en español
   - ✅ Modo de falla descriptivo
   - ✅ Acción recomendada específica

### Verificar Dashboard
1. Ir a TruckDetail page
2. Tab "Diagnostics"
3. Si hay DTCs activos, ver cards con:
   - ✅ Badge de severidad
   - ✅ Nombre del componente
   - ✅ Descripción del fallo
   - ✅ Acción recomendada
   - ✅ Resumen de sistemas afectados

## 📚 Recursos

### Documentación Técnica
- SAE J1939 Standard
- dtc_database.py v5.8.0 documentation
- MondoTracking DTC reference

### API Endpoints
- `GET /api/v2/driver-alerts/{truck_id}/dtc-report?dtc_string={codes}`
- Returns comprehensive DTC analysis with Spanish descriptions

### Archivos Clave
```
Backend:
  - dtc_database.py (112 SPNs, 23 FMIs)
  - dtc_analyzer.py (parsing + classification)
  - alert_service.py (email formatting)
  - wialon_sync_enhanced.py (DTC detection)

Frontend:
  - src/components/TruckDTCs.tsx (DTC display component)
  - src/pages/TruckDetail.tsx (integration)

Testing:
  - test_dtc_alerts_enhanced.py
```

## ✅ Checklist de Verificación

- [x] Emails muestran componente en español
- [x] Emails muestran modo de falla en español
- [x] Emails muestran acción recomendada específica
- [x] Dashboard muestra cards con severidad color-coded
- [x] Dashboard muestra información completa del DTC
- [x] API endpoint retorna datos estructurados
- [x] Testing con DTCs reales (100.4, 597.4, 1761.0)
- [x] Integración con dtc_database.py v5.8.0
- [x] Código pushed a repositorios
- [x] Documentación completa

## 🎯 Impacto

**Antes:**
- Usuario recibía emails genéricos sin información útil
- Dashboard mostraba solo códigos numéricos
- Técnicos necesitaban buscar en manuales qué significa cada código

**Después:**
- Emails con explicación completa en español
- Dashboard visual con toda la información necesaria
- Técnicos pueden actuar inmediatamente con la acción recomendada
- Flota puede priorizar reparaciones por severidad

---

**Status:** ✅ COMPLETADO
**Fecha:** 17 de diciembre 2025
**Versión:** Backend v5.8.0, Frontend v1.0.0
