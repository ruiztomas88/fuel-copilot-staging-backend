/**
 * Confidence Display Helpers
 * 
 * FIX para BUG-002: Backend inconsistente entre 0-1 y 0-100
 * 
 * NOTA: Este archivo debe copiarse a frontend/src/utils/confidenceHelpers.ts
 * 
 * Uso:
 * import { displayConfidence, styleConfidence, getConfidenceColor, getConfidenceBgColor } from '../utils/confidenceHelpers';
 * 
 * // En JSX:
 * <span className={getConfidenceColor(alert.confidence)}>
 *   {displayConfidence(alert.confidence)}
 * </span>
 * <div style={{ width: `${styleConfidence(alert.confidence)}%` }} />
 */

/**
 * Normaliza y formatea confidence para display.
 * Detecta automáticamente si el valor es 0-1 o 0-100.
 * 
 * @param conf - Valor de confidence del backend
 * @returns String formateado como "85%"
 * 
 * @example
 * displayConfidence(0.85)  // "85%"
 * displayConfidence(85)    // "85%"
 * displayConfidence(95)    // "95%"
 * displayConfidence(0.95)  // "95%"
 */
export const displayConfidence = (conf: number | null | undefined): string => {
  if (conf === null || conf === undefined) return 'N/A';
  
  // Si > 1, asumir que ya es porcentaje (0-100) - legacy backend
  if (conf > 1) {
    return `${Math.min(conf, 100).toFixed(0)}%`;
  }
  
  // Si <= 1, es fracción normalizada (0-1) - nuevo formato
  return `${(conf * 100).toFixed(0)}%`;
};

/**
 * Normaliza confidence para uso en CSS width/progress bars.
 * 
 * @param conf - Valor de confidence del backend
 * @returns Número 0-100 para uso en CSS
 * 
 * @example
 * styleConfidence(0.85)  // 85
 * styleConfidence(85)    // 85 (legacy)
 */
export const styleConfidence = (conf: number | null | undefined): number => {
  if (conf === null || conf === undefined) return 0;
  
  // Si > 1, asumir que ya es porcentaje (legacy)
  if (conf > 1) {
    return Math.min(conf, 100);
  }
  
  // Si <= 1, convertir a porcentaje
  return conf * 100;
};

/**
 * Obtiene el color CSS basado en el nivel de confidence.
 * 
 * @param conf - Valor de confidence (0-1 o 0-100)
 * @returns Clase Tailwind CSS para el color
 */
export const getConfidenceColor = (conf: number | null | undefined): string => {
  const normalized = styleConfidence(conf);
  
  if (normalized >= 80) return 'text-green-600 dark:text-green-400';
  if (normalized >= 60) return 'text-yellow-600 dark:text-yellow-400';
  if (normalized >= 40) return 'text-orange-600 dark:text-orange-400';
  return 'text-red-600 dark:text-red-400';
};

/**
 * Obtiene el color de fondo para progress bars.
 * 
 * @param conf - Valor de confidence (0-1 o 0-100)
 * @returns Clase Tailwind CSS para el fondo
 */
export const getConfidenceBgColor = (conf: number | null | undefined): string => {
  const normalized = styleConfidence(conf);
  
  if (normalized >= 80) return 'bg-green-500';
  if (normalized >= 60) return 'bg-yellow-500';
  if (normalized >= 40) return 'bg-orange-500';
  return 'bg-red-500';
};

// =============================================================================
// EJEMPLO DE USO EN COMPONENTES:
// =============================================================================

/*
// ✅ CORRECTO - MaintenanceDashboard.tsx - DESPUÉS:
import { displayConfidence, styleConfidence, getConfidenceColor, getConfidenceBgColor } from '../utils/confidenceHelpers';

// Display text:
<span className={getConfidenceColor(event.confidence)}>
  {displayConfidence(event.confidence)}
</span>

// Progress bar:
<div className="w-full bg-gray-200 rounded-full h-2">
  <div 
    className={`h-2 rounded-full ${getConfidenceBgColor(event.confidence)}`}
    style={{ width: `${styleConfidence(event.confidence)}%` }}
  />
</div>

// ❌ INCORRECTO - MaintenanceDashboard.tsx - ANTES:
{(event.confidence * 100).toFixed(0)}%  // ❌ Bug si backend envía 0.85 como 85
*/

// =============================================================================
// ARCHIVOS A ACTUALIZAR CON ESTE FIX:
// =============================================================================
/*
1. src/pages/MaintenanceDashboard.tsx
   - Línea 157: Cambiar `(p.confidence * 100).toFixed(0)%` 
               → displayConfidence(p.confidence)
   - Línea 234: Cambiar `(summary.avgConfidence * 100).toFixed(0)%`
               → displayConfidence(summary.avgConfidence)
   - Línea 366: Cambiar `(event.confidence * 100).toFixed(0)%`
               → displayConfidence(event.confidence)

2. src/pages/PredictiveMaintenanceUnified.tsx
   - Línea 260: Cambiar `style={{ width: \`${alert.confidence * 100}%\` }}`
               → style={{ width: `${styleConfidence(alert.confidence)}%` }}
   - Línea 264: Cambiar `(alert.confidence * 100).toFixed(0)%`
               → displayConfidence(alert.confidence)

3. src/pages/AlertSettings.tsx
   - Línea 219: Cambiar `(settings?.thresholds.theft_confidence_min || 0) * 100}%`
               → displayConfidence(settings?.thresholds.theft_confidence_min)
*/

export default {
  displayConfidence,
  styleConfidence,
  getConfidenceColor,
  getConfidenceBgColor
};
