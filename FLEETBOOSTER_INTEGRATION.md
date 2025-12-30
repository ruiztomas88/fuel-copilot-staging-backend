# FleetBooster Integration - Documentación

## 📋 Resumen

Sistema de integración entre Fuel Copilot y FleetBooster app para sincronizar:
1. **Fuel Levels** (Kalman filtrados) - cada 60 segundos
2. **DTC Alerts** (códigos de diagnóstico) - cuando se detectan

## 🔗 Endpoint FleetBooster

```
URL: https://fleetbooster.net/fuel/send_push_notification
Método: POST (no PUT)
Content-Type: application/json
```

## 📊 Fuel Level Updates

### Payload Example:
```json
{
  "user": "",
  "unitId": "PC1280",
  "title": "Fuel Level Update",
  "body": "Tank at 30.4%, 60.9 gallons (kalman)",
  "data": {
    "type": "fuel_update",
    "screen": "fuel",
    "unitId": "PC1280",
    "fuel_pct": 30.4,
    "fuel_gallons": 60.9,
    "fuel_liters": 230.5,
    "fuel_source": "kalman",
    "timestamp": "2025-12-30T13:04:47.123456"
  }
}
```

### Rate Limiting:
- **1 envío cada 60 segundos** por truck
- Evita spam si Wialon sync corre cada 30s
- Usa timestamp para controlar rate limiting

### Fuel Sources:
- `kalman`: Valor filtrado con Kalman (MÁS PRECISO)
- `sensor`: Directo del sensor de tanque
- `ecu`: ECU cumulative fuel (NO se usa)

## 🚨 DTC Alerts

### Payload Example:
```json
{
  "user": "",
  "unitId": "DO9693",
  "title": "⚠️ WARNING: Engine Alert",
  "body": "DTC 523452.3 detected on DO9693: Freightliner Safety/Radar - Voltage Above Normal",
  "data": {
    "type": "dtc_alert",
    "screen": "alerts",
    "unitId": "DO9693",
    "dtc_code": "523452.3",
    "description": "Freightliner Safety/Radar - Voltage Above Normal",
    "severity": "WARNING",
    "system": "Safety/Radar",
    "timestamp": "2025-12-30T13:05:15.789012"
  }
}
```

### Severity Levels:
- `INFO`: ℹ️ Informativo
- `WARNING`: ⚠️ Advertencia (requiere atención)
- `CRITICAL`: 🚨 Crítico (requiere acción inmediata)

### DTC Detection:
- Sistema HYBRID con 781,066 códigos DTC
- 111 SPNs con explicación DETALLADA en español
- 35,503 SPNs con cobertura COMPLETA
- OEM detection (Freightliner, Detroit, Volvo, etc.)

## 🎯 Trucks Activos

**Registrados en FleetBooster** (reciben updates):
- PC1280 ✅ (confirmado funcionando)
- RR1272 ✅ (usado para test)
- (Más por agregar según tu tío configure en FleetBooster)

**Error 404** significa que el truck NO está registrado en FleetBooster:
```json
{"error":"Token not found for unitId=GP9677"}
```

## 📝 Logs

### Ubicación:
```bash
/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync_fleetbooster.log
```

### Mensajes típicos:

**SUCCESS (fuel update):**
```
[FLEETBOOSTER] ✓ PC1280: Fuel updated (30.4%, 60.9 gal, kalman)
```

**SUCCESS (DTC alert):**
```
[FLEETBOOSTER] ✓ DO9693: DTC alert sent (523452.3 - WARNING)
```

**SKIP (rate limiting):**
```
[FLEETBOOSTER] PC1280: Skipping fuel update (last update 45s ago)
```

**SKIP (duplicate DTC):**
```
[FLEETBOOSTER] DO9693: Skipping duplicate DTC alert (523452.3)
```

**FAILED (truck no registrado):**
```
[FLEETBOOSTER] ✗ GP9677: Fuel update failed (HTTP 404): {"error":"Token not found for unitId=GP9677"}
```

**FAILED (datos inválidos):**
```
[FLEETBOOSTER] GP9677: Invalid fuel data (pct=-1.5, gal=300)
```

## 🔧 Testing

### Test Manual:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
/opt/anaconda3/bin/python test_fleetbooster.py
```

### Test Output:
```
TEST 1: Fuel Level Update (silent)
Result: ✓ SUCCESS

TEST 2: DTC Alert (with notification)
Result: ✓ SUCCESS
```

### Verificar logs en tiempo real:
```bash
tail -f logs/wialon_sync_fleetbooster.log | grep FLEETBOOSTER
```

## 🚀 Deployment

### Iniciar servicios:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Backend API
/opt/anaconda3/bin/python main.py > logs/backend.log 2>&1 &

# Wialon Sync (con FleetBooster integration)
/opt/anaconda3/bin/python wialon_sync_enhanced.py > logs/wialon_sync_fleetbooster.log 2>&1 &
```

### Verificar status:
```bash
ps aux | grep -E "main.py|wialon_sync" | grep -v grep
```

### Detener servicios:
```bash
pkill -f "python.*main.py"
pkill -f "python.*wialon_sync"
```

## 📊 Estadísticas

### Envíos por minuto:
- **Fuel updates**: Máximo 45 trucks/min (1 por truck cada 60s)
- **DTC alerts**: Variable (solo cuando se detectan)

### Trucks con data reciente:
- 20/45 trucks activos (según último ciclo)
- 25 trucks OFFLINE/NO_DATA

### Response times:
- Fuel update: ~200-300ms
- DTC alert: ~200-300ms
- Timeout: 5 segundos

## 🔐 Seguridad

- **user field**: Vacío por instrucciones de tu tío
- **No API key requerida** en esta versión
- **HTTPS**: ✅ Conexión segura
- **Rate limiting**: ✅ Implementado (60s/truck)

## 🐛 Troubleshooting

### Problema: No se envían fuel updates
**Solución:**
1. Verificar que el truck tenga data reciente en Wialon
2. Revisar que `estimated_pct` o `sensor_pct` no sea None
3. Confirmar que pasaron 60 segundos desde último envío

### Problema: HTTP 404 "Token not found"
**Solución:**
- El truck NO está registrado en FleetBooster
- Contactar a tu tío para agregar el truck al sistema

### Problema: HTTP 405 "Method Not Allowed"
**Solución:**
- FIXED: Cambiado de PUT a POST
- Verificar que esté usando `requests.post()` no `requests.put()`

### Problema: DTCs no se envían
**Solución:**
1. Verificar que el truck tenga DTCs activos en Wialon
2. Revisar que el DTC sea diferente al último enviado (evita duplicados)
3. Confirmar que `save_dtc_event_hybrid()` esté guardando en MySQL

## 📞 Contacto

**Tu tío** (FleetBooster owner):
- URL del API proporcionada: `https://fleetbooster.net/fuel/send_push_notification`
- Configuración de trucks en su sistema
- Formato de payload validado

**Desarrollador** (Fuel Copilot):
- Implementación: `fleetbooster_integration.py`
- Integración: `wialon_sync_enhanced.py` (líneas ~3609-3620 para fuel, ~3386-3400 para DTCs)

## 📅 Changelog

### v1.0.0 (Dec 30, 2025)
- ✅ Implementación inicial fuel level updates
- ✅ Implementación DTC alerts
- ✅ Rate limiting (60s)
- ✅ Validación de datos
- ✅ Testing con RR1272 y PC1280
- ✅ HTTP POST (corregido de PUT)
- ✅ Manejo de errores 404 (truck no registrado)
- ✅ Logs detallados

## 🎯 Próximos pasos

1. **Agregar más trucks** a FleetBooster (coordinar con tu tío)
2. **Monitoring dashboard** para ver estadísticas de envíos
3. **Retry logic** para errores temporales (timeout, 500, etc.)
4. **Batch operations** si crece el número de trucks
5. **Webhook receiver** para recibir confirmaciones de FleetBooster
