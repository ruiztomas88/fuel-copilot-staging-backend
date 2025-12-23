# 🎨 Cambios Requeridos en Frontend - Algorithm Improvements v5.0.0

**Repositorio Frontend:** https://github.com/fleetBooster/Fuel-Analytics-Frontend  
**Backend Version:** v5.0.0  
**Fecha:** Diciembre 23, 2025

---

## 📋 Resumen Ejecutivo

Las nuevas features del backend **NO requieren cambios obligatorios** en el frontend. Todo es **opcional y backward-compatible**. Sin embargo, para aprovechar las nuevas capacidades, se recomiendan las siguientes mejoras.

---

## ✅ Compatibilidad Backward

### Sin Cambios en Frontend
- ✅ **Enhanced MPG** aparece como nuevo campo opcional (`mpg_enhanced`)
- ✅ **Endpoints existentes** siguen funcionando igual
- ✅ **API responses** mantienen estructura compatible
- ✅ **Theft Analysis** tiene algoritmo por defecto (`ml`)

### Cambios Opcionales Recomendados
Las siguientes mejoras son **opcionales** pero mejoran la experiencia del usuario:

---

## 🆕 1. Enhanced MPG - Mostrar MPG Normalizado

### Backend Response (ya disponible)
```json
{
  "truck_id": "DO9693",
  "mpg_current": 5.8,        // MPG crudo (como antes)
  "mpg_enhanced": 6.4,        // 🆕 MPG normalizado (nuevo)
  "mpg_weather_adjusted": 6.1 // Legacy (mantener por compatibilidad)
}
```

### Cambios Sugeridos en Frontend

#### A) Dashboard Fleet Summary
**Archivo:** `src/pages/FleetDashboard.tsx` (o similar)

```tsx
// ANTES
<td>{truck.mpg_current?.toFixed(2) || 'N/A'}</td>

// DESPUÉS (Opción 1: Mostrar ambos)
<td>
  {truck.mpg_enhanced ? (
    <div>
      <strong>{truck.mpg_enhanced.toFixed(2)}</strong>
      <span className="text-muted small"> ({truck.mpg_current.toFixed(2)} raw)</span>
    </div>
  ) : (
    truck.mpg_current?.toFixed(2) || 'N/A'
  )}
</td>

// DESPUÉS (Opción 2: Solo enhanced con tooltip)
<td>
  <Tooltip title={`Raw: ${truck.mpg_current.toFixed(2)} | Normalized: ${truck.mpg_enhanced.toFixed(2)}`}>
    <span>{truck.mpg_enhanced?.toFixed(2) || truck.mpg_current?.toFixed(2) || 'N/A'}</span>
  </Tooltip>
</td>
```

#### B) Truck Detail View
**Archivo:** `src/pages/TruckDetail.tsx`

Agregar indicador visual de ajuste:

```tsx
<div className="mpg-metric">
  <h4>Fuel Economy</h4>
  <div className="mpg-display">
    <span className="mpg-value">{truck.mpg_enhanced?.toFixed(2) || 'N/A'}</span>
    <span className="mpg-unit">MPG</span>
  </div>
  
  {truck.mpg_enhanced && truck.mpg_current && truck.mpg_enhanced !== truck.mpg_current && (
    <div className="mpg-adjustment-note">
      <InfoIcon fontSize="small" />
      Adjusted for altitude/temperature (raw: {truck.mpg_current.toFixed(2)})
    </div>
  )}
</div>
```

#### C) Charts - MPG History
**Archivo:** `src/components/charts/MPGChart.tsx`

Agregar serie adicional para MPG enhanced:

```tsx
const chartData = {
  labels: timestamps,
  datasets: [
    {
      label: 'MPG (Normalized)',
      data: history.map(h => h.mpg_enhanced || h.mpg_current),
      borderColor: '#2196F3',
      backgroundColor: 'rgba(33, 150, 243, 0.1)',
    },
    {
      label: 'MPG (Raw)',
      data: history.map(h => h.mpg_current),
      borderColor: '#9E9E9E',
      borderDash: [5, 5], // Línea punteada
      backgroundColor: 'transparent',
    }
  ]
}
```

**Impacto:** BAJO - Solo mejora visualización, no rompe nada
**Prioridad:** BAJA
**Tiempo estimado:** 2-3 horas

---

## 🛡️ 2. ML Theft Detection - Nuevo Algoritmo

### Backend Endpoint (ya disponible)
```
GET /fuelAnalytics/api/theft-analysis?algorithm=ml&days=7
```

### Cambios Sugeridos en Frontend

#### A) Selector de Algoritmo
**Archivo:** `src/pages/TheftAnalysis.tsx`

```tsx
const [algorithm, setAlgorithm] = useState<'ml' | 'advanced' | 'legacy'>('ml');

// UI Selector
<FormControl>
  <InputLabel>Detection Algorithm</InputLabel>
  <Select value={algorithm} onChange={(e) => setAlgorithm(e.target.value)}>
    <MenuItem value="ml">
      🤖 ML-Based (Recommended)
      <Chip label="NEW" size="small" color="primary" />
    </MenuItem>
    <MenuItem value="advanced">
      🔍 Trip Correlation (v4.1)
    </MenuItem>
    <MenuItem value="legacy">
      📊 Legacy Heuristic
    </MenuItem>
  </Select>
</FormControl>

// Fetch
const response = await fetch(
  `/fuelAnalytics/api/theft-analysis?algorithm=${algorithm}&days=${days}`
);
```

#### B) Mostrar Confidence y Feature Importance
**Archivo:** `src/pages/TheftAnalysis.tsx`

```tsx
// Response tipo
interface TheftEvent {
  truck_id: string;
  timestamp: string;
  fuel_drop_gal: number;
  confidence: number; // 0-100
  classification: 'ROBO CONFIRMADO' | 'ROBO SOSPECHOSO';
  feature_importance?: {
    fuel_drop_pct: number;
    speed: number;
    hour_of_day: number;
    // ... other features
  };
}

// Display
<Card className="theft-event">
  <CardHeader
    title={`${event.truck_id} - ${event.classification}`}
    subheader={new Date(event.timestamp).toLocaleString()}
  />
  <CardContent>
    <div className="metrics">
      <Chip 
        label={`${event.confidence}% confidence`}
        color={event.confidence > 85 ? 'error' : 'warning'}
      />
      <Typography variant="h6">
        {event.fuel_drop_gal} gallons stolen
      </Typography>
    </div>
    
    {/* 🆕 Feature Importance (solo para ML algorithm) */}
    {event.feature_importance && (
      <Accordion>
        <AccordionSummary>
          <Typography>ML Model Factors</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <ProgressBar 
            label="Fuel Drop" 
            value={event.feature_importance.fuel_drop_pct * 100} 
          />
          <ProgressBar 
            label="Speed" 
            value={event.feature_importance.speed * 100} 
          />
          <ProgressBar 
            label="Time of Day" 
            value={event.feature_importance.hour_of_day * 100} 
          />
          {/* ... more features */}
        </AccordionDetails>
      </Accordion>
    )}
  </CardContent>
</Card>
```

**Impacto:** MEDIO - Mejora UX significativa
**Prioridad:** MEDIA
**Tiempo estimado:** 4-6 horas

---

## 🔧 3. Predictive Maintenance - Widget Nuevo

### Backend Endpoint (ya disponible)
```
GET /fuelAnalytics/api/predictive-maintenance
GET /fuelAnalytics/api/predictive-maintenance?truck_id=DO9693
```

### Cambios Sugeridos en Frontend

#### A) Crear Nuevo Widget (Recomendado)
**Archivo:** `src/components/widgets/PredictiveMaintenanceWidget.tsx` (nuevo)

```tsx
import React, { useEffect, useState } from 'react';
import { 
  Card, CardContent, CardHeader, 
  Chip, LinearProgress, Alert 
} from '@mui/material';

interface MaintenancePrediction {
  truck_id: string;
  component: string;
  component_description: string;
  ttf_hours: number;
  ttf_days: number;
  alert_severity: 'OK' | 'WARNING' | 'CRITICAL';
  recommended_action: string;
  confidence_90: [number, number];
  current_sensor_value: number;
  sensor_monitored: string;
}

export const PredictiveMaintenanceWidget: React.FC = () => {
  const [predictions, setPredictions] = useState<MaintenancePrediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        const response = await fetch('/fuelAnalytics/api/predictive-maintenance');
        const data = await response.json();
        
        // Filter only CRITICAL and WARNING
        const urgent = data.predictions.filter(
          p => p.alert_severity !== 'OK'
        );
        
        setPredictions(urgent);
      } catch (error) {
        console.error('Failed to fetch maintenance predictions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPredictions();
    
    // Refresh every 5 minutes
    const interval = setInterval(fetchPredictions, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <LinearProgress />;
  
  if (predictions.length === 0) {
    return (
      <Alert severity="success">
        All components healthy - no maintenance alerts
      </Alert>
    );
  }

  return (
    <div className="maintenance-predictions">
      {predictions.map((pred, idx) => (
        <Card 
          key={idx}
          className={`prediction-card ${pred.alert_severity.toLowerCase()}`}
        >
          <CardHeader
            title={`${pred.truck_id} - ${pred.component_description}`}
            subheader={
              <Chip 
                label={pred.alert_severity}
                color={pred.alert_severity === 'CRITICAL' ? 'error' : 'warning'}
                size="small"
              />
            }
          />
          <CardContent>
            <div className="ttf-display">
              <Typography variant="h4">
                {pred.ttf_days.toFixed(0)} days
              </Typography>
              <Typography variant="caption" color="textSecondary">
                ({pred.ttf_hours.toFixed(0)} engine hours until failure)
              </Typography>
            </div>
            
            <Typography variant="body2" className="action">
              {pred.recommended_action}
            </Typography>
            
            <div className="sensor-info">
              <Typography variant="caption">
                Monitoring: {pred.sensor_monitored}
              </Typography>
              <Typography variant="caption">
                Current: {pred.current_sensor_value.toFixed(1)}
              </Typography>
            </div>
            
            <div className="confidence">
              <Typography variant="caption">
                90% Confidence: {pred.confidence_90[0].toFixed(0)} - {pred.confidence_90[1].toFixed(0)} hours
              </Typography>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};
```

#### B) Integrar en Dashboard Principal
**Archivo:** `src/pages/FleetDashboard.tsx`

```tsx
import { PredictiveMaintenanceWidget } from '../components/widgets/PredictiveMaintenanceWidget';

// En el grid layout
<Grid container spacing={3}>
  {/* Existing widgets */}
  <Grid item xs={12} md={6}>
    <FleetSummaryCard />
  </Grid>
  
  {/* 🆕 Nuevo widget */}
  <Grid item xs={12} md={6}>
    <Card>
      <CardHeader title="⚙️ Predictive Maintenance Alerts" />
      <CardContent>
        <PredictiveMaintenanceWidget />
      </CardContent>
    </Card>
  </Grid>
</Grid>
```

#### C) Página Dedicada (Opcional)
**Archivo:** `src/pages/PredictiveMaintenancePage.tsx` (nuevo)

Página completa con:
- Filtros por truck_id, component
- Tabla detallada con todas las predicciones
- Gráficos de sensor trends
- Export CSV

**Impacto:** ALTO - Nueva funcionalidad importante
**Prioridad:** ALTA
**Tiempo estimado:** 8-12 horas (widget básico) + 16-24 horas (página completa)

---

## 📊 4. Enhanced Confidence Intervals - Visualización Mejorada

### Backend Response (ya actualizado)
```json
{
  "total_loss_gallons": 1250.5,
  "confidence_intervals": {
    "90%": [1120.3, 1380.7],
    "95%": [1100.2, 1400.8],
    "99%": [1050.1, 1450.9]
  },
  "uncertainty_metrics": {
    "std_dev": 85.3,
    "coefficient_of_variation": 0.068,
    "uncertainty_rating": "LOW"
  }
}
```

### Cambios Sugeridos en Frontend

#### A) Loss Analysis Page
**Archivo:** `src/pages/LossAnalysis.tsx`

```tsx
// Display con múltiples CIs
<div className="loss-estimate">
  <Typography variant="h4">
    ${(data.total_loss_gallons * fuelPrice).toFixed(2)}
  </Typography>
  <Typography variant="subtitle1">
    Estimated Fuel Loss
  </Typography>
  
  {/* 🆕 Confidence Intervals */}
  <Accordion>
    <AccordionSummary>
      <Chip 
        label={data.uncertainty_metrics.uncertainty_rating}
        color={
          data.uncertainty_metrics.uncertainty_rating === 'LOW' ? 'success' :
          data.uncertainty_metrics.uncertainty_rating === 'MODERATE' ? 'warning' :
          'error'
        }
      />
      <Typography>Confidence Intervals</Typography>
    </AccordionSummary>
    <AccordionDetails>
      <div className="ci-ranges">
        <div className="ci-item">
          <Typography variant="caption">90% Confidence:</Typography>
          <Typography>
            {data.confidence_intervals['90%'][0].toFixed(0)} - {data.confidence_intervals['90%'][1].toFixed(0)} gal
          </Typography>
        </div>
        <div className="ci-item">
          <Typography variant="caption">95% Confidence:</Typography>
          <Typography>
            {data.confidence_intervals['95%'][0].toFixed(0)} - {data.confidence_intervals['95%'][1].toFixed(0)} gal
          </Typography>
        </div>
        <div className="ci-item">
          <Typography variant="caption">99% Confidence:</Typography>
          <Typography>
            {data.confidence_intervals['99%'][0].toFixed(0)} - {data.confidence_intervals['99%'][1].toFixed(0)} gal
          </Typography>
        </div>
      </div>
    </AccordionDetails>
  </Accordion>
</div>
```

**Impacto:** BAJO - Mejora credibilidad de reportes
**Prioridad:** BAJA
**Tiempo estimado:** 1-2 horas

---

## 🗂️ Archivos TypeScript Helper

Ya existe un archivo helper que puede copiarse:

**Source:** `backend/CONFIDENCE_HELPERS_FOR_FRONTEND.ts`  
**Destination:** `frontend/src/utils/confidenceHelpers.ts`

Contiene:
- `formatConfidencePercent()` - Normaliza 0-1 o 0-100 → "95%"
- `getConfidenceColor()` - Color por nivel de confianza
- `getConfidenceBadgeVariant()` - Badge style
- Helpers para uncertainty rating

---

## 📝 Resumen de Prioridades

### 🔴 Alta Prioridad (Recomendado Implementar)
1. **Predictive Maintenance Widget** - Nueva funcionalidad valiosa
   - Tiempo: 8-12 horas
   - ROI: Alto (proactive maintenance = $$$ savings)

### 🟡 Media Prioridad (Nice to Have)
2. **ML Theft Detection UI** - Mejora detección de robos
   - Tiempo: 4-6 horas
   - ROI: Medio (mejor UX, más confianza en alertas)

### 🟢 Baja Prioridad (Opcional)
3. **Enhanced MPG Display** - Solo cosmético
   - Tiempo: 2-3 horas
   - ROI: Bajo (informativo pero no crítico)

4. **Enhanced Confidence Intervals** - Mejor reporting
   - Tiempo: 1-2 horas
   - ROI: Bajo (credibilidad)

---

## ✅ Testing Frontend

### 1. Enhanced MPG
```javascript
// Verificar que mpg_enhanced existe
const truck = await fetch('/fuelAnalytics/api/trucks/DO9693').then(r => r.json());
console.log('MPG Current:', truck.mpg_current);
console.log('MPG Enhanced:', truck.mpg_enhanced); // Debe existir
```

### 2. ML Theft Detection
```javascript
// Test algoritmo ML
const thefts = await fetch('/fuelAnalytics/api/theft-analysis?algorithm=ml&days=7')
  .then(r => r.json());

console.log('Algorithm:', thefts.algorithm); // Debe ser "ml"
console.log('Events:', thefts.total_events);
console.log('Feature Importance:', thefts.events[0]?.feature_importance); // Debe existir
```

### 3. Predictive Maintenance
```javascript
// Test predictions
const maintenance = await fetch('/fuelAnalytics/api/predictive-maintenance')
  .then(r => r.json());

console.log('Predictions:', maintenance.total_predictions);
console.log('Critical:', maintenance.critical_alerts);
console.log('First Prediction:', maintenance.predictions[0]);
```

---

## 🚀 Roadmap de Implementación

### Sprint 1 (Semana 1) - Fundamentos
- [ ] Copiar `confidenceHelpers.ts` al frontend
- [ ] Actualizar tipos TypeScript para nuevos campos
- [ ] Test manual de endpoints nuevos

### Sprint 2 (Semana 2-3) - Features Core
- [ ] Implementar Predictive Maintenance Widget básico
- [ ] Integrar en Dashboard Principal
- [ ] ML Theft Detection selector de algoritmo

### Sprint 3 (Semana 4) - Polish
- [ ] Enhanced MPG display en charts
- [ ] Confidence Intervals visualización
- [ ] Testing E2E

### Sprint 4 (Futuro) - Advanced
- [ ] Página dedicada Predictive Maintenance
- [ ] Gráficos de sensor degradation
- [ ] Export/Reports con nuevos datos

---

## 📞 Soporte

**Backend Endpoints Documentación:** Ver `INTEGRATION_GUIDE.md`

**Preguntas sobre API:**
- Enhanced MPG: Línea 1998 en `wialon_sync_enhanced.py`
- ML Theft: Línea 1889 en `main.py`
- Predictive Maintenance: Línea 2066 en `main.py`

**Testing Backend:**
```bash
# Enhanced MPG
curl "http://localhost:8000/fuelAnalytics/api/trucks/DO9693" | jq '.mpg_enhanced'

# ML Theft
curl "http://localhost:8000/fuelAnalytics/api/theft-analysis?algorithm=ml&days=7"

# Predictive Maintenance
curl "http://localhost:8000/fuelAnalytics/api/predictive-maintenance"
```

---

## 🎯 Conclusión

**Cambios Obligatorios:** NINGUNO ✅  
**Cambios Recomendados:** 3 features principales  
**Tiempo Estimado Total:** 15-25 horas de desarrollo frontend  
**Impacto de Negocio:** ALTO (especialmente Predictive Maintenance)

El frontend puede **seguir funcionando sin cambios**. Las nuevas features solo **agregan valor adicional** cuando se implementan.
