# Backend Monitoring & Recovery Guide

## 📋 Overview

Sistema completo de monitoreo y recuperación automática del backend para prevenir y diagnosticar caídas.

## 🚀 Componentes Creados

### 1. **monitor_backend.sh** - Monitor Automático
Script que monitorea el backend cada 30 segundos y lo reinicia automáticamente si falla.

**Uso:**
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./monitor_backend.sh
```

**Características:**
- ✅ Verifica proceso cada 30 segundos
- ✅ Health check HTTP
- ✅ Auto-reinicio hasta 3 intentos
- ✅ Logging detallado en `monitor.log`
- ✅ Maneja PID para evitar duplicados

### 2. **emergency_recovery.sh** - Recuperación de Emergencia
Script para recuperación manual cuando todo falla.

**Uso:**
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./emergency_recovery.sh
```

**Acciones:**
- 🔪 Mata todos los procesos del backend
- 📊 Verifica recursos del sistema
- 🧹 Limpia archivos temporales
- 💾 Respalda logs actuales
- 🚀 Reinicia backend y wialon sync
- ✅ Verifica que todo esté funcionando

### 3. **logger_config.py** - Sistema de Logging Avanzado
Configuración de logging con rotación automática y múltiples niveles.

**Características:**
- 📝 Logs rotativos (10MB max, 5 backups)
- 🔴 Log separado solo para errores
- 📅 Logs diarios (mantiene 7 días)
- 🎨 Colores en consola
- 💥 Logger especial para crashes

**Uso en código:**
```python
from logger_config import get_logger, crash_logger

logger = get_logger("mi_modulo")
logger.info("Mensaje informativo")
logger.error("Error detectado")

try:
    # código
except Exception as e:
    crash_logger.log_crash(e, "Contexto del error")
```

### 4. **health_check.py** - Endpoints de Health Check
Endpoints para monitoreo de salud del sistema.

**Endpoints:**
- `GET /health` - Health check básico
- `GET /health/detailed` - Info detallada del proceso
- `GET /health/ready` - Readiness check (Kubernetes)
- `GET /health/live` - Liveness check (Kubernetes)

**Respuesta ejemplo:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-28T...",
  "system": {
    "cpu_percent": 25.3,
    "memory_percent": 45.2,
    "disk_percent": 60.1
  },
  "health_checks": {
    "cpu_ok": true,
    "memory_ok": true,
    "disk_ok": true
  }
}
```

### 5. **error_tracker.py** - Rastreo de Errores
Sistema de análisis y tracking de errores.

**Uso:**
```python
from error_tracker import error_tracker, generate_diagnostic_report

# Trackear error
error_tracker.track_error(
    error=e,
    context="Procesando datos de truck",
    endpoint="/api/fleet",
    request_data={"truck_id": "ABC123"}
)

# Generar reporte
report = generate_diagnostic_report()
print(report)
```

**Comandos útiles:**
```bash
# Ver reporte de errores
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
python3 error_tracker.py

# Ver logs de crashes
cat logs/crashes.log

# Ver tracking de errores
cat logs/error_tracking.json
```

## 📊 Estructura de Logs

```
logs/
├── fuel_analytics.log          # Log principal rotativo
├── fuel_analytics_errors.log   # Solo errores
├── fuel_analytics_daily.log    # Log diario
├── crashes.log                 # Crashes con traceback completo
└── error_tracking.json         # Historial de errores
```

## 🔧 Integración con main.py

El health check router ya está integrado en main.py:

```python
from health_check import router as health_router
app.include_router(health_router)
```

## 📈 Uso Recomendado

### Para Desarrollo
```bash
# Terminal 1: Backend con logs visibles
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
python main.py

# Terminal 2: Wialon sync
python wialon_sync_enhanced.py
```

### Para Producción/Testing
```bash
# Usar monitor automático
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./monitor_backend.sh

# Esto corre en background y auto-reinicia el backend si falla
```

### Si el Backend se Cae
```bash
# Opción 1: Recovery automático (si monitor_backend.sh está corriendo)
# El monitor detectará y reiniciará automáticamente

# Opción 2: Recovery manual
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./emergency_recovery.sh

# Opción 3: Manual completo
pkill -9 -f "python.*main.py"
python main.py &
```

## 🔍 Diagnóstico de Problemas

### 1. Backend no arranca
```bash
# Ver últimos errores
tail -50 backend.log | grep -E "ERROR|CRITICAL"

# Ver crashes
cat logs/crashes.log

# Verificar recursos
top
df -h
```

### 2. Backend se cae repetidamente
```bash
# Ver reporte de errores
python3 error_tracker.py

# Ver logs del monitor
tail -100 monitor.log

# Verificar memoria
vm_stat
```

### 3. Endpoints responden lento
```bash
# Verificar health
curl http://localhost:8000/health/detailed

# Ver métricas del sistema
curl http://localhost:8000/health | python3 -m json.tool
```

## 📝 Prevención de Caídas

### Causas Comunes y Soluciones

1. **Memoria insuficiente**
   - Solución: Reiniciar backend periódicamente
   - Monitor: `monitor_backend.sh` detecta y reinicia

2. **Errores de base de datos**
   - Logs en: `logs/fuel_analytics_errors.log`
   - Solución: Verificar conexión MySQL

3. **Procesos huérfanos**
   - Solución: `emergency_recovery.sh` limpia todo

4. **Disco lleno**
   - Monitor: Health check detecta disk > 90%
   - Solución: Limpiar logs antiguos

## 🎯 Health Check en Frontend

El frontend puede usar estos endpoints:

```javascript
// Verificar si backend está vivo
const response = await fetch('http://localhost:8000/health');
const health = await response.json();

if (health.status !== 'healthy') {
  // Mostrar warning al usuario
}
```

## ⚙️ Configuración de Auto-inicio (macOS)

Para que el backend arranque automáticamente al encender el Mac:

```bash
# Crear launchd service (opcional)
# Ver: services/com.fuelanalytics.backend.plist
```

## 📞 Contacto de Emergencia

Si todo falla:
1. Revisar `logs/crashes.log`
2. Ejecutar `python3 error_tracker.py`
3. Revisar `backend.log` y `wialon_sync.log`
4. Contactar al equipo de desarrollo

## ✅ Checklist Diario

- [ ] Verificar `monitor.log` sin errores recurrentes
- [ ] Revisar `logs/crashes.log` está vacío
- [ ] Health check responde 200
- [ ] Disk usage < 80%
- [ ] Memory usage < 80%

## 🚨 Indicadores de Alerta

⚠️ **ATENCIÓN si ves:**
- Backend se reinicia más de 3 veces/hora
- Memory > 90%
- Disk > 90%
- Crashes.log crece rápidamente
- Error_tracking.json muestra el mismo error repetidamente

🔴 **CRÍTICO si ves:**
- Monitor.log dice "CRITICAL: Manual intervention required"
- Backend no arranca después de emergency_recovery
- Health check siempre devuelve 503
