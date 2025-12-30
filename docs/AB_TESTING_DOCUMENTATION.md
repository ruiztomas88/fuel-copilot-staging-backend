"""
📊 A/B TESTING & MONITORING - DOCUMENTATION
============================================

Sistema completo de A/B testing para validar algoritmos nuevos vs actuales.

## Componentes Implementados

### 1. ab_testing_framework.py
Framework principal de A/B testing con comparaciones:
- **AdaptiveMPGEngine vs MPG estándar**
  - Detecta highway/city/mixed
  - Ajusta ventana dinámicamente
  - Compara accuracy y performance

- **ExtendedKalmanFilter vs Linear Kalman**  
  - Modelo no-lineal de consumo
  - Detección de sensor bias
  - Mejora variance

- **EnhancedTheftDetector vs detector actual**
  - Multi-factor scoring (7 factores)
  - Reduce falsos positivos
  - Mayor confianza en detecciones

### 2. ab_integration_tests.py
Tests con datos reales de la base de datos:
- MPG con datos de fuel_metrics (últimos 7 días)
- Kalman con lecturas reales por truck
- Theft con drops detectados en producción
- Performance benchmarking
- Accuracy comparison con refuels conocidos

**Estado:** Tests básicos funcionando, algunos requieren ajustes de schema

### 3. ab_quick_tests.py
Tests rápidos con datos simulados:
- No require DB
- Valida lógica de algoritmos
- Casos edge conocidos
- Ejecución <5 segundos

**Estado:** ✅ MPG tests pasando, Kalman requiere ajustes de interface

### 4. ab_monitoring.py
Sistema de monitoring continuo para producción:

**Tablas de base de datos:**
```sql
ab_monitoring_log       -- Log de cada test A/B
ab_monitoring_summary   -- Resumen diario
ab_monitoring_alerts    -- Alertas automáticas
```

**Comandos:**
```bash
# Setup inicial (crea tablas)
python ab_monitoring.py --setup

# Ejecutar un ciclo de tests
python ab_monitoring.py --cycle

# Monitoring continuo (cada 60 min)
python ab_monitoring.py --monitor --interval 60

# Generar reporte de últimos 7 días
python ab_monitoring.py --report 7
```

**Alertas automáticas:**
- MPG_LARGE_DIFFERENCE: Diferencia >10%
- MPG_PERFORMANCE_DEGRADATION: Performance >50% peor
- KALMAN_BIAS_DETECTED: Sensor bias detectado
- KALMAN_VARIANCE_IMPROVEMENT: Variance mejora >20%
- THEFT_HIGH_CONFIDENCE: Confianza >90%
- THEFT_DISAGREEMENT: Detectores no concuerdan

## Flujo de Uso Recomendado

### Fase 1: Validación Inicial (1-2 días)
```bash
# 1. Setup de tablas
python ab_monitoring.py --setup

# 2. Quick tests para validar lógica
python ab_quick_tests.py

# 3. Integration tests con datos reales
python ab_integration_tests.py

# 4. Verificar resultados
python ab_monitoring.py --report 1
```

### Fase 2: Monitoring Continuo (1-2 semanas)
```bash
# Ejecutar monitoring cada hora
python ab_monitoring.py --monitor --interval 60 &

# Revisar reportes diarios
python ab_monitoring.py --report 7

# Revisar alertas en DB
mysql -u root fuel_copilot_local -e "
  SELECT * FROM ab_monitoring_alerts 
  WHERE resolved = FALSE 
  ORDER BY created_at DESC 
  LIMIT 20
"
```

### Fase 3: Análisis y Decisión
```bash
# Generar reporte completo
python ab_monitoring.py --report 14

# Análisis SQL de resultados
mysql -u root fuel_copilot_local -e "
  SELECT 
    test_type,
    COUNT(*) as tests,
    AVG(difference) as avg_diff,
    AVG(performance_impact_pct) as avg_perf,
    AVG(new_value) as avg_new,
    AVG(current_value) as avg_current
  FROM ab_monitoring_log
  WHERE timestamp >= NOW() - INTERVAL 14 DAY
  GROUP BY test_type
"
```

## Métricas de Decisión

### MPG Adaptativo
**Deploy si:**
- Avg difference < ±0.5 MPG (similar accuracy)
- Performance impact < 10% degradation
- Mejor detección de condiciones (highway/city)

### Extended Kalman
**Deploy si:**
- Variance improvement > 15%
- Detecta sensor bias en >10% de trucks
- Performance impact < 20% degradation

### Enhanced Theft Detection
**Deploy si:**
- Agreement > 90% con detector actual
- Confidence scores > 0.7 en casos claros
- Reduce falsos positivos > 20%
- Performance impact < 30% degradation

## Estado Actual de Implementación

✅ **Completado:**
- Framework de A/B testing
- Estructura de datos (dataclasses)
- MPG comparison (funcional)
- Quick tests (MPG pasando)
- Monitoring system con DB
- Sistema de alertas
- Reportes automáticos

⚠️ **En progreso:**
- Kalman comparison (ajustar interfaces)
- Theft comparison (validar con datos reales)
- Integration tests (corregir schema mismatches)

🔜 **Pendiente:**
- Dashboard web para visualización
- Notificaciones por email/Slack
- A/B switcheo automático basado en métricas
- Rollback automático si performance degrada

## Queries Útiles

### Ver últimos tests MPG
```sql
SELECT 
  truck_id,
  current_value as current_mpg,
  new_value as new_mpg,
  difference,
  JSON_UNQUOTE(JSON_EXTRACT(new_metadata, '$.condition')) as condition,
  timestamp
FROM ab_monitoring_log
WHERE test_type = 'MPG'
ORDER BY timestamp DESC
LIMIT 20;
```

### Resumen por truck
```sql
SELECT 
  truck_id,
  test_type,
  COUNT(*) as tests,
  AVG(difference) as avg_diff,
  MIN(difference) as min_diff,
  MAX(difference) as max_diff
FROM ab_monitoring_log
WHERE timestamp >= NOW() - INTERVAL 7 DAY
GROUP BY truck_id, test_type
ORDER BY truck_id, test_type;
```

### Alertas por severidad
```sql
SELECT 
  severity,
  alert_type,
  COUNT(*) as count,
  AVG(metric_value) as avg_metric
FROM ab_monitoring_alerts
WHERE created_at >= NOW() - INTERVAL 7 DAY
  AND resolved = FALSE
GROUP BY severity, alert_type
ORDER BY severity DESC, count DESC;
```

## Troubleshooting

### Tests fallan con "Unknown column"
- Verificar schema de DB con `DESCRIBE fuel_metrics`
- Ajustar queries en ab_integration_tests.py
- Ver AUDIT_P0_VERIFICATION_REPORT.md para schema correcto

### Performance muy degradado
- AdaptiveMPGEngine procesa más lecturas (overhead esperado)
- Monitorear con `--interval 60` primero
- Si >50% degradation, ajustar ventanas de algoritmo

### Theft detector no detecta
- Verificar datos de entrada (GPS, speed, timestamp)
- Threshold inicial puede ser alto (ajustar en EnhancedTheftDetector)
- Revisar factors weights en algorithm_improvements.py

## Next Steps

1. **Corregir integration tests** con schema real
2. **Ejecutar monitoring 24-48 horas** para datos baseline
3. **Analizar reportes** y ajustar thresholds de alertas
4. **Decidir por algoritmo** basado en métricas reales
5. **Deploy gradual** (1-2 trucks → 5 trucks → fleet completa)

## Contacto y Soporte

Para preguntas sobre A/B testing:
- Ver logs en `/var/log/fuel_analytics/ab_monitoring.log`
- Revisar alerts en tabla `ab_monitoring_alerts`
- Ejecutar `python ab_monitoring.py --report 1` para debug
